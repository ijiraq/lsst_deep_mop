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
qgraph_dir="${butler_dir}/qgraphs/queue"
# subsets because mosaic and bins are useless
subsets="injected_consolidateVisitSummary"

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


day_obs=$1 && shift
input_collections="u/NH/newer-processCCD/${day_obs}"
output_collection="u/NH/newer-processCCD/${day_obs}"

# File location for the inputs and outputs.

# echo "Inputs = ${input_collections}"
# Loop over all detectors and produce qgraphs for them all.

# Include detector number, year and month in filename to separate detectors.



# Execute pipetask to create qgraph.
for visit in $(butler query-dimension-records PG2_BUTLER visit --datasets injected_calexp --collections ${input_collections} | grep ${day_obs} | sort -k 2n | awk ' {print $2} ')
do
    qgraph_file="${qgraph_dir}/visitSummary-${visit}.qg"
    # If the file already exists, delete it.
    [ -f ${qgraph_file} ] && rm ${qgraph_file}
    
    pipetask --log-level INFO qgraph --rebase \
             -p "${pipeline}#${subsets}"\
             -b "${butler_dir}" \
             -i "${input_collections}" \
	     --data-query "instrument='HSC' AND visit=${visit}" \
             --output "${output_collection}" \
             --clobber-outputs \
             --qgraph-datastore-records \
             -q ${qgraph_file}
done



