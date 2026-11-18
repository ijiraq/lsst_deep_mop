#!/bin/bash
first=$1
last=$2
SK_CORES=1
#SK_CORES=${SK_CORES:-16} 
SK_RAM=$((8*SK_CORES))
SK_RAM=16
source ${HOME}/skaha_tools/scripts/sk_utils.sh


#whole reason this was made was because of version changes
#next dream was to set up a priority queuing system instead of manually baiting your runners, couldn't figure that one out in a simple way though
for i in $(seq ${first} ${last})
do
    sk_launch lsst/sciplat-lab:20250803 lsst-pog-${SK_CORES}-${SK_RAM}-${i} ./scripts/run_single_qgraph.sh PG2_BUTLER PG2_BUTLER/qgraphs
done
