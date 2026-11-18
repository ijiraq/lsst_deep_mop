#!/bin/bash
cmd=$(basename $0)
echo "$cmd ${@}"
subset="imageDifference"
input_collections="u/NH/goodSeeing,u/NH/directWarps,skymaps,u/NH/injection2"
output_collection="u/NH/diffs/${detector}"

pipeline="/arc/projects/NewHorizons/HSC_2024/pipelines/DRP-Prod+injection.yaml"
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
qgraph_dir="${butler_dir}/qgraphs/queue"
day_obs=20240612
# input_collections="HSC/raw/all,HSC/calib,refcats"

function show_help() {
    cat <<EOF 

Usage: ${cmd} DETECTOR

Builds a qgraph for task ${pipeline}#${subset} for ${day_obs} on detector ${detector}.  

Qgraphs are stored in ${qgraph_dir}/${subset}-DETECTOR.qgraph and can be run
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
# Do all exporsure that are for science, skip detector 9
[ ${detector} -eq 9 ] && echo "No detector 9 processing" && exit


output_collection="u/NH/diffs/${detector}"
output_type="--output-run"
if [ -d ${butler_dir}/${output_collection} ]
then
    extendrun="--extend-run"
fi

skymap="discrete_325772_${detector}"
dataset="instrument='HSC' AND detector=${detector} AND skymap='${skymap}' AND visit.observation_reason='science' AND visit.day_obs=${day_obs}"

mkdir -p ${qgraph_dir}
qgraph_file="${qgraph_dir}/${subset}-${detector}.qgraph"
[ -f ${qgraph_file} ] && rm ${qgraph_file}

# init the LSST Science Pipiline environment
echo "Initializing LSST Science Pipeline"
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}


pipetask --log-level INFO \
	 qgraph \
	 -p "${pipeline}#${subset}" ${config}\
	 -b "${butler_dir}" \
	 -i "${input_collections}" \
	 -d "${dataset}" \
	 ${output_type} "${output_collection}" \
	 --skip-existing-in "${output_collection}" \
	 --clobber-outputs \
	 --rebase \
	 --qgraph-datastore-records \
	 -q ${qgraph_file}  
