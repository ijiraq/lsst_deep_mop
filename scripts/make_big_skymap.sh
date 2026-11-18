#!/bin/bash

YEAR_OBS=$1 && shift

case "$YEAR_OBS" in

    2020)
        count=11
        ;;
    2021)
        count=5
        ;;
    2022)
        count=7
        ;;
    2023)
        count=2
        ;;
    2024)
        count=8
        ;;
    2025)
        count=2
        ;;
    *)
        echo "What?"
        exit -1

esac


if [ "$#" -lt "$count" ]
then
    echo "Usage: $0 year_obs exp_list"
    echo "exp_list is passed as one chosen exposure per night, expected $count exposures"
    echo ""
    echo "Creates a 'skymap' for the entire field of view for that year"
    echo "using the footprints/bounding box of the injected_calexp datasets found"
    echo "in collection. A new 'tagged' collection is used to create"
    echo "the input list of injected_calexp files to build the skymap from"
    exit -1
fi

exposures=()
for ((i=0; i<count; i++)); do
  exposures+=("$1")
  shift
done

REPO=$BUTLER_DIR

COLLECTION="u/NH/newer-processCCD/${YEAR_OBS}*"

let YEAR_ST=${YEAR_OBS}*10000
let YEAR_EN=${YEAR_ST}+10000

echo "Progressing..."

exp_list=$(IFS=,; echo "${exposures[*]}")
#echo "instrument='HSC' AND NOT detector=9 AND visit IN (${exposures[@]}) "

DATASET_TYPE="calexp"
SKYMAP_CONFIG="/arc/projects/NewHorizons/HSC_2024/configs/makeSkyMap_config.py"

INPUT_DATA_COLL="visit_${YEAR_OBS}_miniwini"
SKYMAP_ID="big_${YEAR_OBS}"

echo "Progressing..."

butler --log-level VERBOSE associate ${REPO} ${INPUT_DATA_COLL} \
    --dataset-type ${DATASET_TYPE} \
    --collections ${COLLECTION} \
    --where "instrument='HSC' AND NOT detector=9 AND visit IN (${exp_list})"

echo "Progressing..."

butler query-datasets $BUTLER_DIR \
    $DATASET_TYPE \
    --collections $INPUT_DATA_COLL \
    --limit 15


butler --log-level VERBOSE make-discrete-skymap ${REPO} HSC \
    --collections ${INPUT_DATA_COLL} \
    --skymap-id ${SKYMAP_ID} \
    --config-file ${SKYMAP_CONFIG}