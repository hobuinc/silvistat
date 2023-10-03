import time
import types

import tiledb
import pdal
import numpy as np

import dask
import dask.array as da
from dask.diagnostics import ProgressBar
from dask.distributed import performance_report, progress, Client

from .bounds import Bounds, create_bounds
from .chunk import Chunk, get_leaves

def cell_indices(xpoints, ypoints, x, y):
    return da.logical_and(xpoints == x, ypoints == y)

def floor_x(points: da.Array, bounds: Bounds):
    return da.array(da.floor((points - bounds.minx) / bounds.cell_size),
        np.int32)

def floor_y(points: da.Array, bounds: Bounds):
    return da.array(da.floor((bounds.maxy - points) / bounds.cell_size),
        np.int32)

def get_atts(points, chunk, bounds):
    xypoints = points[['X','Y']].view()
    xis = floor_x(xypoints['X'], bounds)
    yis = floor_y(xypoints['Y'], bounds)
    att_data = [da.array(points[:][cell_indices(xis,
        yis, x, y)], dtype=points.dtype) for x,y in chunk.indices ]
    return dask.compute(att_data, scheduler="Threads")[0]

def get_data(pipeline, chunk):
    for stage in pipeline.stages:
        if 'readers' in stage.type:
            reader = stage
            break
    reader._options['bounds'] = str(chunk.bounds)

    try:
        pipeline.execute()
    except Exception as e:
        print(pipeline.pipeline, e)

    return da.array(pipeline.arrays[0])

def write_tdb(tdb, res):
    dx, dy, dd = res
    tdb[dx, dy] = dd

@dask.delayed
def arrange_data(pipeline, bounds: list[float], root_bounds: Bounds, tdb=None):

    chunk = Chunk(*bounds, root=root_bounds)
    points = get_data(pipeline, chunk)
    if not points.size:
        return np.array([0], np.int32)

    data = get_atts(points, chunk, root_bounds)
    dd = {}
    for att in ['Z', 'HeightAboveGround']:
        dd[att] = np.array([col[att] for col in data], object)
    counts = np.array([z.size for z in dd['Z']], np.int32)
    dd['count'] = counts
    dx = chunk.indices['x']
    dy = chunk.indices['y']
    if tdb != None:
        write_tdb(tdb, [ dx, dy, dd ])
    del data, dd, points, chunk
    return counts

def create_pipeline(filename):
    reader = pdal.Reader(filename, tag='reader')
    reader._options['threads'] = 2
    reader._options['resolution'] = 1
    class_zero = pdal.Filter.assign(value="Classification = 0")
    rn = pdal.Filter.assign(value="ReturnNumber = 1 WHERE ReturnNumber < 1")
    nor = pdal.Filter.assign(value="NumberOfReturns = 1 WHERE NumberOfReturns < 1")
    smrf = pdal.Filter.smrf()
    hag = pdal.Filter.hag_nn()
    return reader | class_zero | rn | nor | smrf | hag

def shatter(filename: str, tdb_dir: str, group_size: int, res: float,
            debug: bool, client=None, polygon=None):

    client: Client = client
    # read pointcloud
    pipeline = create_pipeline(filename)
    reader = pipeline.stages[0]
    bounds = create_bounds(reader, res, group_size, polygon)

    # set up tiledb
    config = create_tiledb(bounds, tdb_dir)

    # Begin main operations
    with tiledb.open(tdb_dir, "w", config=config) as tdb:
        start = time.perf_counter_ns()

        # debug uses single threaded dask
        if debug:
            c = Chunk(bounds.minx, bounds.maxx, bounds.miny, bounds.maxy,
                bounds)
            f = c.filter(filename)

            leaf_procs = dask.compute([leaf.get_leaf_children() for leaf in
                get_leaves(f)])[0]
            l = [arrange_data(pipeline, ch, bounds, tdb) for leaf in leaf_procs
                for ch in leaf]
            dask.compute(*l, optimize_graph=True)
        else:
            with performance_report(f'{tdb_dir}-dask-report.html'):
                print('Filtering out empty chunks...')
                t = client.scatter(tdb)
                b = client.scatter(bounds)

                c = Chunk(bounds.minx, bounds.maxx, bounds.miny, bounds.maxy,
                    bounds)
                f = c.filter(filename)

                leaf_procs = client.compute([node.get_leaf_children() for node
                    in get_leaves(f)])

                print('Fetching and arranging data...')
                data_futures = client.compute([
                    arrange_data(pipeline, ch, b, t)
                    for leaf in leaf_procs for ch in leaf
                ])

                progress(data_futures)
                client.gather(data_futures)

        end = time.perf_counter_ns()
        print("Done in", (end-start)/10**9, "seconds")
        return


def create_tiledb(bounds: Bounds, dirname):
    if tiledb.object_type(dirname) == "array":
        with tiledb.open(dirname, "d") as A:
            A.query(cond="X>=0").submit()
    else:
        dim_row = tiledb.Dim(name="X", domain=(0,bounds.xi), dtype=np.float64)
        dim_col = tiledb.Dim(name="Y", domain=(0,bounds.yi), dtype=np.float64)
        domain = tiledb.Domain(dim_row, dim_col)

        count_att = tiledb.Attr(name="count", dtype=np.int32)
        # names = atts.names
        # tdb_atts = [tiledb.Attr(name=name, dtype=names[name], var=True, fill=np.dtype()) for name in names]

        z_att = tiledb.Attr(name="Z", dtype=np.float64, var=True)
        hag_att = tiledb.Attr(name="HeightAboveGround", dtype=np.float32, var=True)
        atts = [count_att, z_att, hag_att]

        schema = tiledb.ArraySchema(domain=domain, sparse=True,
            capacity=len(atts)*bounds.xi*bounds.yi, attrs=[count_att, z_att, hag_att], allows_duplicates=True)
        schema.check()
        tiledb.SparseArray.create(dirname, schema)

    return tiledb.Config({
        "sm.check_coord_oob": False,
        "sm.check_global_order": False,
        "sm.check_coord_dedups": False,
        "sm.dedup_coords": False
    })