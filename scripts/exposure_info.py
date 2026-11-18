import MakeFake
from lsst.daf.butler import Butler
# from lsst.source.injection import CoaddInjectConfig,CoaddInjectTask
# NOTE: For injections into other dataset types, use the following instead:
# from lsst.source.injection import ExposureInjectConfig,ExposureInjectTask
from lsst.source.injection import VisitInjectConfig,VisitInjectTask
from astropy.table import Table
from astropy.coordinates import EarthLocation
import sys

# Instantiate a butler.
REPO="BUTLER"
collections="u/NH/processCCD"
INPUT_DATA_COLL=collections
instrument="HSC"
visit=332136
band="gri"
detector_raft='1'
detector_name_in_raft='53'

master_fakes_table = Table.read('NH_makefake_orbits.parquet')

butler = Butler(REPO)

# Load an input deepCoadd dataset.
dataId = {
        "instrument": instrument,
        "visit": visit,
        "band": band,
        "detector.raft": detector_raft,
        "detector.name_in_raft": detector_name_in_raft,
}

"""
    detector_dimensions = butler.registry.queryDimensionRecords(
    element='detector',
    # dataId={'raft': detector_raft}
    )# Don't need as the detector ID comes with the input_exposure object
for x in detector_dimensions:
    if x.name_in_raft==dataId['detector.name_in_raft'] and x.raft==dataId['detector.raft']:
        dataId['detector'] = x.id
        break
"""

input_exposure = butler.get(
    "calexp",
    dataId=dataId,
    collections=collections,
)

dataId['detector'] = input_exposure.detector.getId()
observatory = input_exposure.visitInfo.getObservatory()
print(EarthLocation.from_geodetic(lon=observatory.getLongitude().asDegrees(), lat=observatory.getLatitude().asDegrees(), height=observatory.getElevation()))
print(EarthLocation.of_site('Subaru'))
