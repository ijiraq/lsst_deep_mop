#!/bin/bash
butler=${1}
query=${2:-"instrument='HSC' AND visit.observation_reason='science'"}

visit_list=$(butler query-data-ids ${butler} visit --where "$query" | awk '{ print $4 }' | sed 1,2d)

for visit in $visit_list
do
#sk_launch lsst/science_pipeline:7-stack-lsst_distrib-v26_0_0 ${visit}-qgraph \
pipetask qgraph \
-b ${butler} \
-i HSC/raw/all,refcats,HSC/calib,HSC/calib/run1 \
-o u/NH/processCCD \
-p pipelines/NHPipeline.yaml#processCcd \
-d "instrument='HSC' AND visit=${visit} AND detector.purpose='SCIENCE' AND NOT detector=9" \
-c isr:doDark=False \
--skip-existing-in u/NH/processCCD \
--qgraph-datastore-records \
-q qgraphs-${butler}/processCcd${visit}.qgraph \
--output-run u/NH/processCCD/run1 \
#--extend-run \
--clobber-outputs
done
