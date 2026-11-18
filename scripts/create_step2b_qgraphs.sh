#!/bin/bash

cmd=$(basename $0)
subset="step2b"
pipeline="/arc/projects/NewHorizons/HSC_2024/pipelines/DRP-Prod+injection.yaml"
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
qgraph_dir="${butler_dir}/qgraphs/queue"
config="isolatedStarAssociation:band_order=['i','z','r','gri','g','y','u']"

input_collections="u/NH/step2,skymaps,u/NH/injection"
output_collection="u/NH/step2b_injection"

function show_help() {
    cat <<EOF 

Usage: ${cmd} VISIT

Builds a qgraph for task ${pipeline}#${subset}.  Q

graphs are stored in ${qgraph_dir}/${cmd}-DETECTOR.qgraph and can be run
using run_single_qgraph.sh.  

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


if [ $# -ne 1 ] 
then
   show_help
   exit -1
fi

detector=$1 && shift
day_obs=20240612
skymap="discrete_325772_${detector}"
dataset="instrument='HSC' AND tract=0 AND detector=${detector} AND skymap='${skymap}' AND visit.observation_reason='science' AND visit.day_obs=${day_obs}"
mkdir -p "${qgraph_dir}"
qgraph_file="${qgraph_dir}/${subset}-${detector}.qgraph"

[ -f ${qgraph_file} ] && rm ${qgraph_file}
if [[ $(eups list obs_subaru | grep NewHorizons | wc -l ) -lt 1 ]]
then
    echo "initializing"
    export SHELL=/bin/bash
    export USER=$(whoami)
    .  /opt/lsst/software/stack/loadLSST.bash
    setup lsst_distrib
    setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
    setup -r /arc/projects/NewHorizons/source_injection -t ${USER}
fi

# check if output run alraedy exists
extendrun=""
output_type="--output"
[ $(butler --no-log-tty query-collections ${butler_dir} ${output_collection} --collection-type RUN | wc -l) -gt 0 ] && ( extendrun="--extend-run" && output_type="--output-run")

pipetask qgraph \
	 -p ${pipeline}#${subset} \
	 --config ${config} \
	 -b ${butler_dir} \
	 -i ${input_collections} \
	 -d "${dataset}" \
	 ${output_type} ${output_collection} ${extendrun} \
	 --skip-existing-in ${output_collection} \
	 --clobber-outputs \
	 --qgraph-datastore-records \
	 -q ${qgraph_file}

