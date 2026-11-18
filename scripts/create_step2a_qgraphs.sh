#!/bin/bash
USAGE="$0 VISIT"

cmd=$(basename $0)
subset="step2a"
pipeline="/arc/projects/NewHorizons/HSC_2024/pipelines/DRP-Prod.yaml"
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
qgraph_dir="${butler_dir}/qgraphs/queue"


# input_collections="HSC/raw/all,refcats,HSC/calib"
input_collections="u/NH/step1"
output_collection="u/NH/step2/batch"

function show_help() {
    cat <<EOF 

Usage: ${cmd} VISIT

Builds a qgraph for task ${pipeline}#${subset}.  Q

graphs are stored in ${qgraph_dir}/${cmd}-VISIT.qgraph and can be run
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


echo "initializing"
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
setup -r /arc/projects/NewHorizons/source_injection -t ${USER}
echo "Done"

day_obs=$1 && shift
for visit in $(butler query-dimension-records ${butler_dir} visit --where "instrument='HSC' and visit.observation_reason='science' and visit.day_obs=${day_obs}"  | grep ${day_obs} | awk ' { print $2}')
do
    echo "Building step2a Q for ${visit}"
    dataset="instrument='HSC' AND detector.purpose='SCIENCE' AND detector!=9 AND visit=${visit}"
    mkdir -p "${qgraph_dir}"
    qgraph_file="${qgraph_dir}/${subset}-${day_obs}-${visit}.qgraph"
    [ -f ${qgraph_file} ] && rm ${qgraph_file}
    output_type="--output-run"
    extendrun="--extend-run"

    pipetask qgraph \
	     -p ${pipeline}#${subset} \
	     -b ${butler_dir}\
	     -i ${input_collections} \
	     -d "${dataset}" \
	     ${output_type} ${output_collection} ${extendrun} \
	     --skip-existing \
	     --skip-existing-in u/NH/step2 \
	     --clobber-outputs \
	     --qgraph-datastore-records \
	     -q ${qgraph_file} --rebase

done
