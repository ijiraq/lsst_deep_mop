#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

#why visit summaries? who knows
#can we agree to ignore comments on this one it was just a one off don't pay it too much attention

DEFAULT_PIPE_DIR="/arc/projects/NewHorizons/HSC_2024/pipelines"
PIPE_DIR="${PIPE_DIR-$DEFAULT_PIPE_DIR}"
pipeline="${PIPE_DIR}/DRP-Prod+injection_upd_JJK.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/hold"
# subsets because mosaic and bins are useless
subsets="consolidateVisitSummary"

function show_help() {
    cat <<EOF 

Usage: ${cmd} det_low det_high start_date end_date

Builds a qgraph for task ${pipeline}#${subset}, one job per detector 

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


if [ $# -ne 1 ] 
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

day_obs=$1 && shift
input_collections="u/NH/newer-processCCD/20220602"
output_collection="u/NH/newer-processCCD/20220602"

# File location for the inputs and outputs.

# echo "Inputs = ${input_collections}"
# Loop over all detectors and produce qgraphs for them all.

# Include detector number, year and month in filename to separate detectors.


qgraph_file="${qgraph_dir}/visitSumm-${day_obs}.qg"
# If the file already exists, delete it.
[ -f ${qgraph_file} ] && rm ${qgraph_file}


# Execute pipetask to create qgraph.
pipetask --log-level INFO qgraph --rebase \
        -p "${pipeline}#${subsets}"\
        -b "${butler_dir}" \
        -i "${input_collections}" \
	--data-query "instrument='HSC' AND day_obs=${day_obs}" \
        --output "${output_collection}" \
        --clobber-outputs \
        --qgraph-datastore-records \
        -q ${qgraph_file} 


