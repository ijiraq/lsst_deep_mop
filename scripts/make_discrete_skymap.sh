#!/bin/bash

if [ $# != 4 ] 
then
    echo "Usage: $0 repo collection day_obs detector"
    echo ""
    echo "Creates a 'skymap' for the given day_obs/detector combination"
    echo "using the footprints/bounding box of the calexp datasets found"
    echo "in collection. A new 'tagged' collection is used to create"
    echo "the input list of calexp files to build the skymap from"
    exit
fi

REPO=$1 && shift
COLLECTION=$1 && shift
DAY_OBS=$1 && shift
DETECTOR=$1 && shift

DATASET_TYPE="calexp"
SKYMAP_CONFIG="/arc/projects/NewHorizons/HSC_2024/configs/makeSkyMap_config.py"


INPUT_DATA_COLL="${DAY_OBS}_${DETECTOR}"

SKYMAP_ID="${DAY_OBS}_${DETECTOR}"

# group the selected exposures into an association as make-discrete-skymap doesn't allow a where clause?
butler --log-level VERBOSE associate ${REPO} ${INPUT_DATA_COLL} \
       --dataset-type ${DATASET_TYPE} \
       --collections ${COLLECTION} \
       --where "instrument='HSC' AND day_obs=${DAY_OBS} AND detector=${DETECTOR}"


butler --log-level VERBOSE make-discrete-skymap ${REPO} HSC \
        --collections ${INPUT_DATA_COLL} \
        --skymap-id ${SKYMAP_ID} \
        --config-file ${SKYMAP_CONFIG}
