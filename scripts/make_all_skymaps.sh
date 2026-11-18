#!/bin/bash

if [ $# != 2 ] 
then
    echo "Usage: $0 collection day_obs"
    echo ""
    echo "Creates a 'skymap' for all detectors for the given day_obs"
    echo "using the footprints/bounding box of the injected_calexp datasets found"
    echo "in collection. A new 'tagged' collection is used to create"
    echo "the input list of injected_calexp files to build the skymap from"
    exit
fi

REPO=$BUTLER_DIR

COLLECTION=$1 && shift
DAY_OBS=$1 && shift

DATASET_TYPE="calexp"
SKYMAP_CONFIG="/arc/projects/NewHorizons/HSC_2024/configs/makeSkyMap_config.py"

for DETECTOR in $(seq 0 103)
do 
    INPUT_DATA_COLL="visit_${DAY_OBS}_${DETECTOR}"
    SKYMAP_ID="small_${DAY_OBS}_${DETECTOR}"

    butler --log-level VERBOSE associate ${REPO} ${INPUT_DATA_COLL} \
        --dataset-type ${DATASET_TYPE} \
        --collections ${COLLECTION} \
        --where "instrument='HSC' AND day_obs=${DAY_OBS} AND detector=${DETECTOR}"


    butler --log-level VERBOSE make-discrete-skymap ${REPO} HSC \
        --collections ${INPUT_DATA_COLL} \
        --skymap-id ${SKYMAP_ID} \
        --config-file ${SKYMAP_CONFIG}
done