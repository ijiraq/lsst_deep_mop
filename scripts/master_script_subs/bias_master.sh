#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

# File location where it draws inputs from.
input_collections="HSC/raw/all,HSC/calib"
# File location of the yaml file.
pipeline="${CP_PIPE_DIR}/pipelines/HSC/cpBias.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/hold"
# subsets because mosaic and bins are useless
subsets="cpBiasIsr,cpBiasCombine"
# File location for the outputs.
output_collection="u/NH/master-things/master-bias-construct/${obs_month}"

mkdir -p ${butler_dir}/${output_collection}

extendrun="--extend-run"
output_type="--output-run"

# Loop over all detectors and produce qgraphs for them all.
for detector in $(seq $detector_low $detector_high)
do
    #f
    [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
    
    #what is useful for now
    dataset="instrument='HSC' AND exposure.observation_type='bias' AND detector=${detector} AND day_obs>=$start_date AND day_obs<=$end_date "

    # Include detector number in filename to separate detectors.
    qgraph_file="${qgraph_dir}/master-bias-${obs_month}-${detector}.qgraph"
    # If the file already exists, delete it.
    [ -f ${qgraph_file} ] && rm ${qgraph_file}

    echo "Building bias qgraph for detector ${detector} on ${obs_month}"

    # Execute pipetask to create qgraph.
    pipetask --log-level INFO qgraph \
	     -p "${pipeline}#${subsets}" ${config}\
	     -b "${butler_dir}" \
	     -i "${input_collections}" \
	     -d "${dataset}" \
	     ${output_type} "${output_collection}" ${extendrun}\
	     --clobber-outputs \
	     --qgraph-datastore-records \
	     -q ${qgraph_file} 

done

$SCRIPT_DIR/launch_qrunners.sh 1 20

sleep 60

while [[ $(find "${butler_dir}/qgraphs/processing" -mindepth 1 | wc -l) -gt 0 ]]; do
    echo "Waiting for processing to complete..."
    sleep 300
done

echo "Bias processing complete. Continuing..."

#checking logs
while true; do
    rand_det=$((RANDOM % (detector_high - detector_low + 1) + detector_low))

    tail -n 100 ${butler_dir}/qgraphs/logs/master-bias-${obs_month}-${rand_det}.log
    echo "File log for ${rand_det}"

    read -rp "Looks good? [y/n/quit]" input

    if [[ "$input" == "y" ]]; then
        echo "Continuing..."
        break
    elif [[ "$input" == "quit" ]]; then
        exit -1
    fi

    sleep 1  
done

mv ${butler_dir}/qgraphs/processed/* ${butler_dir}/qgraphs/examined

$SCRIPT_DIR/merge.sh

sleep 10

exit 0