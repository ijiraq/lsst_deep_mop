#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

config="--config isr:doDark=False"
# File location of the yaml file.
pipeline="${PIPE_DIR}/DRP-Prod+injection_upd.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/hold"
# subsets because mosaic and bins are useless
subsets="processCcd"

for obs_date in ${days[@]}
do
    # File location for the inputs and outputs.
    if [ $obs_month == "sep2021" ]; then #because sep2021 doesn't have flat frames, so pulling the closest ones
        input_collections="HSC/raw/all,HSC/calib,refcats,HSC/calib/${obs_month}-masterv1,HSC/calib/jun2021-masterv1,fakes/master-fakes/${obs_date}"
    else
        input_collections="HSC/raw/all,HSC/calib,refcats,HSC/calib/${obs_month}-masterv1,fakes/master-fakes/${obs_date}"
    fi
    output_collection="u/NH/master-things/master-processCCD/${obs_date}"
    mkdir -p ${butler_dir}/${output_collection}
    ([ ${obs_date} -eq 20220703 ] || [ ${obs_date} -eq 20230908 ] || [ ${obs_date} -eq 20240705 ]) && echo "No science observations on ${obs_date}" && continue

    # Loop over all detectors and produce qgraphs for them all.
    for detector in $(seq $detector_low $detector_high)
    do
        #these two were causing issues so they're not at the bottom anymore
        extendrun="--extend-run"
        output_type="--output-run"

        #rip
        [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
        
        dataset="instrument='HSC' AND visit.observation_reason='science' AND detector.purpose='SCIENCE' AND detector=${detector} AND day_obs=${obs_date}" 

        # Include detector number, year and month in filename to separate detectors.
        qgraph_file="${qgraph_dir}/master-processCCD-${obs_date}-${detector}.qgraph"
        # If the file already exists, delete it.
        [ -f ${qgraph_file} ] && rm ${qgraph_file}

        echo "Building processCCD qgraph for detector ${detector} on ${obs_date}"

        # Execute pipetask to create qgraph.
        pipetask --log-level INFO qgraph \
            -p "${pipeline}#${subsets}" ${config}\
            -b "${butler_dir}" \
            -i "${input_collections}" \
            -d "${dataset}" \
            ${output_type} "${output_collection}" ${extendrun} \
            --clobber-outputs \
            --qgraph-datastore-records \
            -q ${qgraph_file} 
        

    done
done

$SCRIPT_DIR/launch_qrunners.sh 1 20

sleep 60

while [[ $(find "${butler_dir}/qgraphs/processing" -mindepth 1 | wc -l) -gt 0 ]]; do
    echo "Waiting for processing to complete..."
    sleep 1500
done

echo "CCD processing complete. Continuing..."

#checking logs
for obs_date in ${days[@]}
do
    while true; do
        rand_det=$((RANDOM % ( $detector_high - $detector_low + 1 ) + $detector_low ))

        tail -n 100 ${butler_dir}/qgraphs/logs/master-processCCD-${obs_date}-${rand_det}.log
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
done

mv ${butler_dir}/qgraphs/processed/* ${butler_dir}/qgraphs/examined

$SCRIPT_DIR/merge.sh

sleep 10

exit 0