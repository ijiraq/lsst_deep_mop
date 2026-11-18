#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"


# File location of the yaml file.
DEFAULT_PIPE_DIR="/arc/projects/NewHorizons/HSC_2024/pipelines"
PIPE_DIR="${PIPE_DIR-$DEFAULT_PIPE_DIR}"
pipeline="${PIPE_DIR}/DRP-Prod+injection_upd_JJK.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/hold"
subsets="newHorizons"

function show_help() {
    cat <<EOF 

Usage: ${cmd} DETECTOR_LOW DETECTOR_HIGH START_DATE END_DATE

Builds a qgraph for task ${pipeline}#${subset}, one job per detecrtor 

Qgraphs are stored in ${qgraph_dir}/${subset}-DETECTOR.qg and can be run
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


if [ $# -ne 4 ] 
then
   show_help
   exit -1
fi


# Initialize the LSST environment again to be safe.
echo "Initializing environment"
# init the LSST Science Pipiline environment
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
echo "Done"


# Take detector range and observation month from command line
detector_low=$1 && shift
detector_high=$1 && shift
start_date=$1 && shift
end_date=$1 && shift

# File location for the inputs and outputs.
input_collections="u/NH/fakes,skymaps"
output_collection="u/NH/fakes/202206"
# not everyday is a science day
#([ ${start_date} -eq 20220703 ] || [ ${start_date} -eq 20230908 ] || [ ${start_date} -eq 20240705 ]  || [ ${start_date} -eq 20200519 ] || [ ${start_date} -eq 20200619 ] || [ ${start_date} -eq 20250719 ] || [ ${start_date} -eq 20250720 ]) && echo "No science observations on ${start_date}" && continue

# Loop over all detectors and produce qgraphs for them all.
for detector in $(seq $detector_low $detector_high)
do
    #these two were causing issues so they're not at the bottom anymore, good luck
    extendrun="--extend-run"
    output_type="--output-run"

    #rip
    [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
    ([ ${detector} -eq 21 ] && [ ${start_date} -ge 20250000 ]) && echo "No detector 21 processing as of 2025" && continue
    # removed AND band='r' 
    dataset="instrument='HSC' AND day_obs>${start_date} AND day_obs<${end_date} AND detector=${detector} AND skymap='big_2022'"
    
    # Include detector number, year and month in filename to separate detectors.
    qgraph_file="${qgraph_dir}/diff-${start_date}_${end_date}_${detector}.qgraph"
    # If the file already exists, delete it.
    [ -f ${qgraph_file} ] && rm ${qgraph_file}

    echo "Building qgraph for ${detector}"

    # Execute pipetask to create qgraph.
    pipetask --log-level INFO qgraph --rebase \
        -p "${pipeline}#${subsets}"\
        -b "${butler_dir}" \
        -i "${input_collections}" \
        -d "${dataset}" \
        --output-run "${output_collection}" \
        --clobber-outputs \
        --qgraph-datastore-records \
        -q ${qgraph_file} 
    
	# --skip-existing \

done
