import pdal
import numpy as np
import json

import dask
import dask.array as da
from dask.distributed import performance_report, progress

from .bounds import Bounds
from .extents import Extents
from .storage import Storage
from .config import ShatterConfig
from .metric import Metrics, Metric, Attribute

def cell_indices(xpoints, ypoints, x, y):
    return da.logical_and(xpoints == x, ypoints == y)

def floor_x(points: da.Array, bounds: Bounds, resolution: float):
    return da.array(da.floor((points - bounds.minx) / resolution),
        np.int32)

def floor_y(points: da.Array, bounds: Bounds, resolution: float):
    return da.array(da.floor((bounds.maxy - points) / resolution),
        np.int32)

#TODO move pruning of attributes to this method so we're not grabbing everything
def get_atts(points: da.Array, chunk: Extents, attrs: list[str]):
    bounds = chunk.root
    xypoints = points[['X','Y']].view()
    xis = floor_x(xypoints['X'], bounds, chunk.resolution)
    yis = floor_y(xypoints['Y'], bounds, chunk.resolution)
    # get attribute_data
    att_view = points[:][attrs]
    dt = att_view.dtype
    return [da.array(att_view[cell_indices(xis, yis, x, y)], dt)
                for x,y in chunk.indices]

def get_metrics(data, metrics: list[Metric], attrs: list[str]):
    ## data comes in as { 'att': [data] }
    for attr in attrs:
        for m in metrics:
            m: Metric
            name = m.entry_name(attr)
            data[name] = np.array([m(cell_data) for cell_data in data[attr]],
                                  m.dtype).flatten(order='C')
    return data

def get_data(filename, chunk):
    pipeline = create_pipeline(filename, chunk)
    try:
        pipeline.execute()
    except Exception as e:
        print(pipeline.pipeline, e)

    return pipeline.arrays[0]

@dask.delayed
def arrange_data(chunk: Extents, config: ShatterConfig,
                 storage: Storage=None):

    points = get_data(config.filename, chunk)
    if not points.size:
        return 0
    attrs = [a.name for a in config.attrs]
    data = get_atts(points, chunk, attrs)

    dd = {}
    for att in attrs:
        try:
            dd[att] = np.array(dtype=object, object=[
                *[np.array(col[att], data[0][att].dtype) for col in data],
                None])[:-1]
        except Exception as e:
            raise Exception(f"Missing attribute {att}: {e}")

    counts = np.array([z.size for z in dd['Z']], np.int32)

    ## remove empty indices
    empties = np.where(counts == 0)[0]
    dd['count'] = counts
    dx = chunk.indices['x']
    dy = chunk.indices['y']
    if bool(empties.size):
        for att in dd:
            dd[att] = np.delete(dd[att], empties)
        dx = np.delete(dx, empties)
        dy = np.delete(dy, empties)

    ## perform metric calculations
    dd = get_metrics(dd, config.metrics, attrs)

    if storage is not None:
        storage.write(dx, dy, dd)
    sum = counts.sum()
    del data, dd, points, chunk
    return sum

def create_pipeline(filename, chunk):
    reader = pdal.Reader(filename, tag='reader')
    reader._options['threads'] = 2
    crop = pdal.Filter.crop(bounds=str(chunk))
    class_zero = pdal.Filter.assign(value="Classification = 0")
    rn = pdal.Filter.assign(value="ReturnNumber = 1 WHERE ReturnNumber < 1")
    nor = pdal.Filter.assign(value="NumberOfReturns = 1 WHERE NumberOfReturns < 1")
    # smrf = pdal.Filter.smrf()
    # hag = pdal.Filter.hag_nn()
    return reader | crop | class_zero | rn | nor #| smrf | hag

def run(leaves: list[Extents], config: ShatterConfig, storage: Storage):
    # debug uses single threaded dask

    if config.debug:
        data_futures = dask.compute([arrange_data(leaf, config, storage)
                                     for leaf in leaves])
    else:
        with performance_report(f'dask-report.html'):
            data_futures = dask.compute([
                arrange_data(leaf, config, storage)
                for leaf in leaves])

            progress(data_futures)
    c = 0
    for f in data_futures:
        c += sum(f)
    return c

#TODO OPTIMIZE: try using dask.persist and seeing if you can break up the tasks
# into things like get_data, get_atts, arrange_data so that they aren't waiting
# on each other to compute and still using the resources.
def shatter(config: ShatterConfig):
    print('Filtering out empty chunks...')
    # set up tiledb
    storage = Storage.from_db(config.tdb_dir)
    extents = Extents.from_storage(storage, config.tile_size)
    leaves = list(extents.chunk(config.filename, 1000))

    # Begin main operations
    print('Fetching and arranging data...')
    pc = run(leaves, config, storage)
    config.point_count = pc.item()
    storage.saveMetadata('shatter', str(config))