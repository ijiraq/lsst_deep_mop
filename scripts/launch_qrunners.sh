#!/bin/bash
first=$1
last=$2
SK_CORES=1
#SK_CORES=${SK_CORES:-16}
SK_RAM=$((8*SK_CORES))
SK_RAM=4
source ${HOME}/skaha_tools/scripts/sk_utils.sh

for i in $(seq ${first} ${last})
do
    sk_launch lsst/science_pipeline:d_latest lsst-d-latest-${SK_CORES}-${SK_RAM}-${i} ./scripts/run_single_qgraph.sh PG2_BUTLER PG2_BUTLER/qgraphs
done
