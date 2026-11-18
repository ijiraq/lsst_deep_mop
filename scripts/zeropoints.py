from lsst.daf.butler import Butler
import sys, os
import logging
import lsst.afw.display as afwDisplay
import argparse
import glob

parser = argparse.ArgumentParser()
parser.add_argument('butler_dir')
parser.add_argument('visit', type=int)
parser.add_argument('--detector', default=22, type=int)
parser.add_argument('--collections', default='u/NH/processCCD*')
parser.add_argument('--log-level', default='INFO')
args = parser.parse_args()

logging.basicConfig(level=getattr(logging, args.log_level))
logging.debug(f"{args}")

collections = []
for dir_path in glob.glob(os.path.join(args.butler_dir, args.collections)):
    collection = os.path.relpath(dir_path, args.butler_dir)
    logging.debug(f"Adding {collection}")
    collections.append(collection)

logging.debug(f"Looking in collections: {collections}")
logging.info("making Butler")

butler = Butler(args.butler_dir)
logging.info("Querying Butler")
#deepCoadd = butler.get('deepCoadd', dataId={'filter': 'HSC-R2', 'tract': 0, 'patch': '4,6'})
#deepDiff = butler.get('diff', dataId={'filter': 'HSC-R2', 'tract': 0, 'patch': '4,6'})
registry = butler.registry

result = registry.queryDatasets('calexp', visit=325430, collections=collections, instrument='HSC')

for dataRef in result:
    calexp = butler.get(dataRef)
    print(calexp.visitInfo.id, calexp.detector.getName(), calexp.photoCalib.instFluxToMagnitude(1.0))
