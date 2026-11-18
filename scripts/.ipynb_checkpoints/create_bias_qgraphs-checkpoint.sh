#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

subset="cpBiasCombine"
config=""
output_collection="u/NH/bias-construct"
input_collections="u/NH/bias-construct/batch"
pipeline="${CP_PIPE_DIR}/pipelines/HSC/cpBias.yaml"
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
qgraph_dir="${butler_dir}/qgraphs/queue"

function show_help() {
    cat <<EOF 

Usage: ${cmd} DETECTOR_LOW DETECTOR_HIGH

Builds a qgraph for task ${pipeline}#${subset}, one job per detecrtor 

Qgraphs are stored in ${qgraph_dir}/${subset}-DETECTOR.qgraph and can be run
using launch_qrunner.sh  

Likely you want to launch a bunch of qrunners.

input_collections=${input_collections}
ouptut_collection=${output_collection}

EOF
}

OPTIND=1
while getopts l:h opt; do
   case "${opt}" in
       h) show_help
          exit 0
          ;;
       *) show_help >& 1
          exit 2
          ;;
   esac
done
shift $(( OPTIND - 1 ))


if [ $# -ne 2 ] 
then
   show_help
   exit -1
fi


day_start=$1 && shift
day_end=$1 && shift
output_collection=${output_collection}/${day_start}
extendrun=""
output_type="--output-run"
for detector in $(seq 0 103)
do    


    [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
    
    dataset="instrument='HSC' AND exposure.observation_type='bias' AND detector=${detector} AND day_obs IN (${day_start}..${day_end})"


    mkdir -p ${qgraph_dir}
    qgraph_file="${qgraph_dir}/${subset}-${day_start}-${detector}.qgraph"
    [ -f ${qgraph_file} ] && rm ${qgraph_file}

    echo "Building qgraph"
    
    pipetask --log-level INFO qgraph \
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
