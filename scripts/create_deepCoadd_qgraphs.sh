#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

subset="assembleDeepCoadd"
# config="--config isr:doDark=False"
pipeline="/arc/projects/NewHorizons/HSC_2024/pipelines/DRP-Prod+injection.yaml"
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
qgraph_dir="${butler_dir}/qgraphs/queue"
mkdir -p ${qgraph_dir}

function show_help() {
    cat <<EOF 

Usage: ${cmd} DETECTOR_LOW DETECTOR_HIGH

Builds a qgraph for task ${pipeline}#${subset}.  

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


if [ $# -ne 3 ] 
then
   show_help
   exit -1
fi


echo "Initializing Science Pipeline environment"
# init the LSST Science Pipiline environment
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
echo "Done"

day_obs=$1 && shift
detector_low=$1 && shift
detector_high=$1 && shift
echo "Building graphs for ${day_obs} detectoris ${detector_low} to ${detector_high}"

for detector in $(seq ${detector_low} ${detector_high})
do
    [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
    echo "Building qgraph for ${detector}"
    input_collections="u/NH/step1/*,u/NH/step2,u/NH/step2/batch,skymaps,fakes/${day_obs},u/NH/step1/20241106T165851Z"
    output_collection="u/NH/fakes"
    # config="--config-file makeWarp:configs/makeWarpConfig.py --config-file warpDiff:configs/warpDiff.py"
    config=""
    extendrun="--extend-run"
    output_type="--output-run"
    if [ ${day_obs} -eq 20240612 ]
    then
	skymap="small_325772_${detector}"
    else
	skymap="small_${day_obs}_${detector}"
    fi

    # Do all exporsure that are for science, skip detector 9
    dataset="instrument='HSC' AND detector=${detector} AND skymap='${skymap}' AND visit.observation_reason='science' AND visit.day_obs=${day_obs}"
    qgraph_file="${qgraph_dir}/${subset}-${day_obs}-${detector}.qgraph"
    [ -f ${qgraph_file} ] && rm ${qgraph_file}

    cat <<EOF

    pipetask run \
	     -p "${pipeline}#${subset}" ${config}\
	     -b "${butler_dir}" \
	     -i "${input_collections}" \
	     -d "${dataset}" \
	     ${output_type} "${output_collection}" ${extendrun} \
	     --clobber-outputs \
	     --qgraph-datastore-records \
	     --register-dataset-types \
	     --skip-existing 
	     #-q ${qgraph_file} 

EOF

done
