#!/bin/bash

BUTLER_DIR=${1}
GRAPH_DIR="qgraphs-${BUTLER_DIR}"
QGRAPH="${GRAPH_DIR}/fgcm.qgraph"

pipetask qgraph \
-b ${BUTLER_DIR} \
-i u/NH/completeProcessing \
-o u/NH/fgcm \
-p pipelines/NHPipeline.yaml#fgcm \
--qgraph-datastore-records \
-q qgraphs-${QGRAPH} \
--output-run u/NH/fgcm/run1 \
#--extend-run \
#--skip-existing-in u/NH/fgcm \
--clobber-outputs


sk_launch lsst/science_pipeline:7-stack-lsst_distrib-v26_0_0 fgcm scripts/run_single_qgraph.sh ${BUTLER_DIR} ${QGRAPH}
echo "Process completed launching"
mkdir -p "${GRAPH_DIR}/processed"
./scripts/merge.sh ${BUTLER_DIR} ${GRAPH_DIR}