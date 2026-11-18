#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

subset="inject_visit"
output_collection="u/NH/fakes"
input_collections="u/NH/fakes,fakes/master-fakes/20250822"
# pipeline="${DRP_PIPE_DIR}/pipelines/HSC/DRP-RC2+injected_deepCoadd.yaml"
pipeline="/arc/projects/NewHorizons/HSC_2024/pipelines/DRP-Prod+injection_upd.yaml"
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
qgraph_dir="${butler_dir}/qgraphs/queue"

mkdir -p ${qgraph_dir}


function show_help() {
    cat <<EOF 

Usage: ${cmd}  DETECTOR_LOW DETECTOR_HIGH START_DATE END_DATE

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


if [ $# -ne 4 ] 
then
   show_help
   exit -1
fi


echo "Initializing environment"
# init the LSST Science Pipiline environment
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
echo "Done"

detector_low=$1 && shift
detector_high=$1 && shift
start_day=$1 && shift
end_day=$1 && shift

# input_collections=${input_collections},HSC/calib/${start_day}-${end_day}

for detector in $(seq $detector_low $detector_high)
do    
    # Do all exporsure that are for science, skip detector 9
    [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
    ([ ${detector} -eq 21 ] && [ ${start_date} -ge 20250000 ]) && echo "No detector 21 processing as of 2025" && continue

    dataset="instrument='HSC' AND detector=${detector} AND visit.observation_reason='science' AND visit.day_obs>=${start_day} and visit.day_obs<=${end_day} AND band='r' "

    qgraph_file="${qgraph_dir}/${subset}-${start_day}-${end_day}-${detector}.qg"
    [ -f ${qgraph_file} ] && rm ${qgraph_file}

    echo "Building qgraph"
    
    pipetask --log-level INFO qgraph \
	     -p "${pipeline}#${subset}" ${config}\
	     -b "${butler_dir}" \
	     -i "${input_collections}" \
	     -d "${dataset}" \
	     --output-run "${output_collection}" --extend-run \
	     --clobber-outputs \
	     --qgraph-datastore-records \
	     --skip-existing \
	     -q ${qgraph_file} 

done
