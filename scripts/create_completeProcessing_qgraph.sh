#!/bin/bash

butler=${1}

pipetask qgraph \
-b ${1} \
-i u/NH/processCCD,skymaps \
-o u/NH/completeProcessing \
-p pipelines/NHPipeline.yaml#completeProcessing \
--qgraph-datastore-records \
-q qgraphs-${butler}/completeProcessing.qgraph \
--output-run u/NH/completeProcessing/run1 \
#--extend-run \
#--skip-existing-in u/NH/completeProcessing \
--clobber-outputs