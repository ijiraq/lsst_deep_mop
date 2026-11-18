#!/bin/bash
cmd=$(basename $0)
echo "$cmd ${@}"

# subset="injected_makeDirectWarp"
# subset="injected_makePsfMatchedWarp"
subset="makeDirectWarp"
DEFAULT_PIPE_DIR="/arc/projects/NewHorizons/HSC_2024/pipelines"
PIPE_DIR="${PIPE_DIR-$DEFAULT_PIPE_DIR}"
pipeline="${PIPE_DIR}/DRP-Prod+injection_upd_JJK.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
queue_dir="${butler_dir}/qgraphs/queue"
processing_dir="${butler_dir}/qgraphs/processing"
processed_dir="${butler_dir}/qgraphs/processed"
merged_dir="${butler_dir}/qgraphs/merged"
mkdir -p ${queue_dir}

input_collections="u/NH/newer-processCCD/20250722,u/NH/newer-processCCD/20250721,skymaps"
output_collection="u/NH/multi"
# output_collection="u/NH/median"
output_type="-o"


function show_help() {
    cat <<EOF 

Builds a qgraph for task ${pipeline}#${subset} for day_obs patch and all detectors

Qgraphs are stored in ${qgraph_dir}/${subset}-DAYOBS-PATCH.qg and can be run
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

logline(){
    local COLUMNS=$(tput cols) 
    local msg=$1
    local LEN=$((($COLUMNS-${#msg}-2)/2))
    for i in $(seq 1 $LEN); do echo -n "#"; done
    echo -n " $msg "
    for i in $(seq 2 $LEN); do echo -n "#"; done
    echo -ne "#\r"
}



# init the LSST Science Pipiline environment
# echo "Initializing LSST Science Pipeline"
# export SHELL=/bin/bash
# export USER=$(whoami)
# .  /opt/lsst/software/stack/loadLSST.bash
# setup lsst_distrib
# setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
# setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}

# File location for the inputs and outputs.
day_obs=$1
skymap='big_2025'
for patch in $2
do
	dataset="instrument='HSC' AND tract=0 AND patch=${patch} AND skymap='${skymap}' AND day_obs=${day_obs}"
	qgraph="${subset/,/_}-${day_obs}-${patch}.qg"
	skip=0
	for dirname in "$queue_dir" "$processing_dir" "$processed_dir" "$merged_dir"
	do
	    qgraph_file="${dirname}/${qgraph}"
	    # [ -f ${qgraph_file} ] && skip=1 && logline ${qgraph_file} && break
	    [ -f ${qgraph_file} ] && rm ${qgraph_file} && break
	done
	[ $skip -gt 0 ] && continue
	qgraph_file=${queue_dir}/${qgraph}
	logline "${qgraph_file}"
	echo ""
	[ -f ${qgraph_file} ] && continue || touch ${qgraph_file}
    
	pipetask --log-level INFO --long-log qgraph \
		 -p $pipeline#$subset \
		 -b $butler_dir \
		 -d "$dataset" \
		 -i $input_collections \
		 -o $output_collection \
		 --qgraph-datastore-records \
		 --rebase \
		 --clobber-outputs \
		 -q ${qgraph_file} 
done
