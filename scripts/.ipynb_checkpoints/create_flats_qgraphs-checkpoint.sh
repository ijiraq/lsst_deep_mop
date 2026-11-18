#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

subset="cpFlatIsr"
config="--config cpFlatIsr:doVignette=False --config cpFlatIsr:doMeasureBackground=False"
output_collection="u/NH/flat-construct"
pipeline="${CP_PIPE_DIR}/pipelines/HSC/cpFlat.yaml"
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
qgraph_dir="${butler_dir}/qgraphs/queue"

# 20240611 20240612 
day_start=$1 && shift
day_end=$1 && shift

output_collection=${output_collection}/${day_start}
output_type="--output-run"
extendrun="--extend-run"
for detector in $(seq 0 103)
do
    [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
    dataset="instrument='HSC' AND exposure.observation_type='domeflat' AND detector=${detector} AND day_obs IN (${day_start}..${day_end})"
    mkdir -p ${qgraph_dir}
    qgraph_file="${qgraph_dir}/${subset}-${day_start}-${detector}.qgraph"
    [ -f ${qgraph_file} ] && rm ${qgraph_file}

    pipetask --log-file INFO qgraph \
	     -p "${pipeline}#${subset}" ${config}\
	     -b "${butler_dir}" \
	     -i "${input_collections}" \
	     -d "${dataset}" \
	     ${output_type} "${output_collection}" ${extendrun} \
	     --clobber-outputs \
	     --qgraph-datastore-records \
	     --skip-existing-in "${output_collection}" \
	     -q ${qgraph_file} 

done
