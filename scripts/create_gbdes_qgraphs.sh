#!bin/bash

butler=${1}
query=${2:-"instrument='HSC' AND visit.observation_reason='science'"}

visit_list=$(butler query-data-ids ${butler} visit --where "$query" | awk '{ print $4 }' | sed 1,2d)

for visit in ${visit_list}:
do
pipetask qgraph \
-b ${butler} \
-i u/NH/completeProcessing
-o u/NH/gbdes
-p pipeline/NHPipeline.yaml#gbdes
-d "instrument='HSC' AND visit=${visit}"
--qgraph-datastore-records
-q qgraphs-${butler}/gbdes${visit}.qgraph
done
