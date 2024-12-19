import os
import io
from typing_extensions import Generator
import pickle

import pytest
import pandas as pd
import numpy as np

from silvimetric import (Log, StorageConfig, ShatterConfig, Storage, Data,
    Bounds, Metric)
from silvimetric.resources.metrics.stats import sm_max, sm_min
from silvimetric.resources.metrics.p_moments import mean
from silvimetric import __version__ as svversion

@pytest.fixture(scope='function')
def autzen_storage(tmp_path_factory: pytest.TempPathFactory) -> Generator[StorageConfig, None, None]:
    path = tmp_path_factory.mktemp("test_tdb")
    p = os.path.abspath(path)

    srs = """PROJCS[\"NAD83 / Oregon GIC Lambert (ft)\",
GEOGCS[\"NAD83\",DATUM[\"North_American_Datum_1983\",SPHEROID[\"GRS 1980\",
6378137,298.257222101,AUTHORITY[\"EPSG\",\"7019\"]],AUTHORITY[\"EPSG\",\"6269\"]],
PRIMEM[\"Greenwich\",0,AUTHORITY[\"EPSG\",\"8901\"]],UNIT[\"degree\",
0.0174532925199433,AUTHORITY[\"EPSG\",\"9122\"]],AUTHORITY[\"EPSG\",\"4269\"]],
PROJECTION[\"Lambert_Conformal_Conic_2SP\"],PARAMETER[\"latitude_of_origin\",
41.75],PARAMETER[\"central_meridian\",-120.5],PARAMETER[\"standard_parallel_1\",
43],PARAMETER[\"standard_parallel_2\",45.5],PARAMETER[\"false_easting\",
1312335.958],PARAMETER[\"false_northing\",0],UNIT[\"foot\",0.3048,
AUTHORITY[\"EPSG\",\"9002\"]],AXIS[\"Easting\",EAST],AXIS[\"Northing\",NORTH],
AUTHORITY[\"EPSG\",\"2992\"]]"""
    b = Bounds(635579.2,848884.83,639003.73,853536.21)
    sc = StorageConfig(b, srs, 10, tdb_dir=p)
    Storage.create(sc)
    yield sc

@pytest.fixture(scope='function')
def autzen_data(autzen_filepath: str, autzen_storage: StorageConfig) -> Generator[Data, None, None]:
    d = Data(autzen_filepath, autzen_storage)
    yield d

@pytest.fixture(scope='function')
def metric_data(autzen_data: Data) -> Generator[pd.DataFrame, None, None]:
    p = autzen_data.pipeline
    autzen_data.execute()
    points = p.get_dataframe(0)
    points.loc[:, 'xi'] = np.floor(points.xi)
    points.loc[:, 'yi'] = np.ceil(points.yi)
    points = points.loc[points.xi == 1]
    points = points.loc[points.yi == 437]
    yield points[['Z', 'xi', 'yi']]

@pytest.fixture(scope='function')
def metric_data_results() -> Generator[pd.DataFrame, None, None]:
    # result_bytes = io.BytesIO(b'\x80\x05\x95!\x04\x00\x00\x00\x00\x00\x00\x8c\x11pandas.core.frame\x94\x8c\tDataFrame\x94\x93\x94)\x81\x94}\x94(\x8c\x04_mgr\x94\x8c\x1epandas.core.internals.managers\x94\x8c\x0cBlockManager\x94\x93\x94\x8c\x16pandas._libs.internals\x94\x8c\x0f_unpickle_block\x94\x93\x94\x8c\x13numpy._core.numeric\x94\x8c\x0b_frombuffer\x94\x93\x94(\x960\x00\x00\x00\x00\x00\x00\x00\xbe:\xa92\x86U}@\x08cw\x9f\xa1Z/@s\xeeL\x14X\\\xd3?J\xe0E\xf4\xae\xc7\xfe?z\xbb\xad\x1f\r\x1a\xa1?g$\x8a\x06u\xc2\x93?\x94\x8c\x05numpy\x94\x8c\x05dtype\x94\x93\x94\x8c\x02f8\x94\x89\x88\x87\x94R\x94(K\x03\x8c\x01<\x94NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK\x00t\x94bK\x06K\x01\x86\x94\x8c\x01C\x94t\x94R\x94\x8c\x08builtins\x94\x8c\x05slice\x94\x93\x94K\x00K\x06K\x01\x87\x94R\x94K\x02\x87\x94R\x94h\x0bh\x0e(\x96\x08\x00\x00\x00\x00\x00\x00\x00\xec\xeb\xeeJ\x06j\xbf?\x94h\x15K\x01K\x01\x86\x94h\x19t\x94R\x94h\x1eK\x06K\x07K\x01\x87\x94R\x94K\x02\x87\x94R\x94\x86\x94]\x94(\x8c\x18pandas.core.indexes.base\x94\x8c\n_new_Index\x94\x93\x94h-\x8c\x05Index\x94\x93\x94}\x94(\x8c\x04data\x94\x8c\x16numpy._core.multiarray\x94\x8c\x0c_reconstruct\x94\x93\x94h\x10\x8c\x07ndarray\x94\x93\x94K\x00\x85\x94C\x01b\x94\x87\x94R\x94(K\x01K\x07\x85\x94h\x12\x8c\x02O8\x94\x89\x88\x87\x94R\x94(K\x03\x8c\x01|\x94NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?t\x94b\x89]\x94(\x8c\x06m_Z_l1\x94\x8c\x06m_Z_l2\x94\x8c\x06m_Z_l3\x94\x8c\x06m_Z_l4\x94\x8c\x07m_Z_lcv\x94\x8c\rm_Z_lskewness\x94\x8c\rm_Z_lkurtosis\x94et\x94b\x8c\x04name\x94Nu\x86\x94R\x94h/\x8c\x19pandas.core.indexes.multi\x94\x8c\nMultiIndex\x94\x93\x94}\x94(\x8c\x06levels\x94]\x94(h/h1}\x94(h3h\x0e(\x96\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf0?\x94h\x15K\x01\x85\x94h\x19t\x94R\x94hL\x8c\x02xi\x94u\x86\x94R\x94h/h1}\x94(h3h\x0e(\x96\x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00P{@\x94h\x15K\x01\x85\x94h\x19t\x94R\x94hL\x8c\x02yi\x94u\x86\x94R\x94e\x8c\x05codes\x94]\x94(h\x0e(C\x01\x00\x94h\x12\x8c\x02i1\x94\x89\x88\x87\x94R\x94(K\x03hANNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK\x00t\x94bK\x01\x85\x94h\x19t\x94R\x94h\x0e(C\x01\x00\x94hjK\x01\x85\x94h\x19t\x94R\x94e\x8c\tsortorder\x94N\x8c\x05names\x94]\x94(hZhbeu\x86\x94R\x94e\x86\x94R\x94\x8c\x04_typ\x94\x8c\tdataframe\x94\x8c\t_metadata\x94]\x94\x8c\x05attrs\x94}\x94\x8c\x06_flags\x94}\x94\x8c\x17allows_duplicate_labels\x94\x88sub.')
    result_bytes = io.BytesIO(b'\x80\x04\x95$\x04\x00\x00\x00\x00\x00\x00\x8c\x11pandas.core.frame\x94\x8c\tDataFrame\x94\x93\x94)\x81\x94}\x94(\x8c\x04_mgr\x94\x8c\x1epandas.core.internals.managers\x94\x8c\x0cBlockManager\x94\x93\x94\x8c\x16pandas._libs.internals\x94\x8c\x0f_unpickle_block\x94\x93\x94\x8c\x15numpy.core.multiarray\x94\x8c\x0c_reconstruct\x94\x93\x94\x8c\x05numpy\x94\x8c\x07ndarray\x94\x93\x94K\x00\x85\x94C\x01b\x94\x87\x94R\x94(K\x01K\x06K\x01\x86\x94h\x0f\x8c\x05dtype\x94\x93\x94\x8c\x02f8\x94\x89\x88\x87\x94R\x94(K\x03\x8c\x01<\x94NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK\x00t\x94b\x89C0\xbe:\xa92\x86U}@\x08cw\x9f\xa1Z/@s\xeeL\x14X\\\xd3?J\xe0E\xf4\xae\xc7\xfe?z\xbb\xad\x1f\r\x1a\xa1?g$\x8a\x06u\xc2\x93?\x94t\x94b\x8c\x08builtins\x94\x8c\x05slice\x94\x93\x94K\x00K\x06K\x01\x87\x94R\x94K\x02\x87\x94R\x94h\x0bh\x0eh\x11K\x00\x85\x94h\x13\x87\x94R\x94(K\x01K\x01K\x01\x86\x94h\x1b\x89C\x08\xec\xeb\xeeJ\x06j\xbf?\x94t\x94bh"K\x06K\x07K\x01\x87\x94R\x94K\x02\x87\x94R\x94\x86\x94]\x94(\x8c\x18pandas.core.indexes.base\x94\x8c\n_new_Index\x94\x93\x94h3\x8c\x05Index\x94\x93\x94}\x94(\x8c\x04data\x94h\x0eh\x11K\x00\x85\x94h\x13\x87\x94R\x94(K\x01K\x07\x85\x94h\x18\x8c\x02O8\x94\x89\x88\x87\x94R\x94(K\x03\x8c\x01|\x94NNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK?t\x94b\x89]\x94(\x8c\x06m_Z_l1\x94\x8c\x06m_Z_l2\x94\x8c\x06m_Z_l3\x94\x8c\x06m_Z_l4\x94\x8c\x07m_Z_lcv\x94\x8c\rm_Z_lskewness\x94\x8c\rm_Z_lkurtosis\x94et\x94b\x8c\x04name\x94Nu\x86\x94R\x94h5\x8c\x19pandas.core.indexes.multi\x94\x8c\nMultiIndex\x94\x93\x94}\x94(\x8c\x06levels\x94]\x94(h5h7}\x94(h9h\x0eh\x11K\x00\x85\x94h\x13\x87\x94R\x94(K\x01K\x01\x85\x94h\x1b\x89C\x08\x00\x00\x00\x00\x00\x00\xf0?\x94t\x94bhL\x8c\x02xi\x94u\x86\x94R\x94h5h7}\x94(h9h\x0eh\x11K\x00\x85\x94h\x13\x87\x94R\x94(K\x01K\x01\x85\x94h\x1b\x89C\x08\x00\x00\x00\x00\x00P{@\x94t\x94bhL\x8c\x02yi\x94u\x86\x94R\x94e\x8c\x05codes\x94]\x94(h\x0eh\x11K\x00\x85\x94h\x13\x87\x94R\x94(K\x01K\x01\x85\x94h\x18\x8c\x02i1\x94\x89\x88\x87\x94R\x94(K\x03hANNNJ\xff\xff\xff\xffJ\xff\xff\xff\xffK\x00t\x94b\x89C\x01\x00\x94t\x94bh\x0eh\x11K\x00\x85\x94h\x13\x87\x94R\x94(K\x01K\x01\x85\x94hq\x89hst\x94be\x8c\tsortorder\x94N\x8c\x05names\x94]\x94(h\\hfeu\x86\x94R\x94e\x86\x94R\x94\x8c\x04_typ\x94\x8c\tdataframe\x94\x8c\t_metadata\x94]\x94\x8c\x05attrs\x94}\x94\x8c\x06_flags\x94}\x94\x8c\x17allows_duplicate_labels\x94\x88sub.')
    result_bytes.seek(0)
    df = pickle.load(result_bytes)
    yield df

@pytest.fixture(scope='function')
def metric_shatter_config(tmp_path_factory, copc_filepath, attrs, metrics, bounds,
        date, crs, resolution) -> Generator[pd.Series, None, None]:

    path = tmp_path_factory.mktemp("test_tdb")
    p = os.path.abspath(path)
    log = Log('DEBUG')

    def dummy_fn(df: pd.DataFrame) -> pd.DataFrame:
        assert isinstance(df, pd.DataFrame)
        ndf = df[df['NumberOfReturns'] >= 1]
        assert isinstance(ndf, pd.DataFrame)
        return ndf

    metrics[0].add_filter(dummy_fn, 'This is a function.')
    metrics[0].attributes=attrs

    """Make output"""
    st_config=StorageConfig(tdb_dir=p,
                        log=log,
                        crs=crs,
                        root=bounds,
                        resolution=resolution,
                        attrs=attrs,
                        metrics=metrics,
                        version=svversion)

    s = Storage.create(st_config)
    sh_config = ShatterConfig(tdb_dir=p,
            log=log,
            filename=copc_filepath,
            bounds=bounds,
            debug=True,
            date=date)
    yield sh_config

@pytest.fixture
def depless_crr():
    def m_crr_1(data, *args):
        mean = data.mean()
        mi = data.min()
        ma = data.max()
        d = (ma - mi)
        if d == 0:
            return np.nan

        return (mean - mi) / d

    return Metric('depless_crr', np.float32, m_crr_1)

@pytest.fixture
def dep_crr():
    def m_crr_2(data, *args):
        m, mi, ma = args
        den = (ma- mi)
        if den == 0:
            return np.nan
        return (m - mi) / den

    return Metric('deps_crr', np.float32, m_crr_2, [mean, sm_min, sm_max])