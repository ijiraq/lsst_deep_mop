#!/bin/bash
cmd=$(basename $0)
echo "$cmd ${@}"

# subset="injected_makeDirectWarp"
# subset="injected_makePsfMatchedWarp"
subset="injected_templateGen"
# subset="injected_getTemplate"
DEFAULT_PIPE_DIR="/arc/projects/NewHorizons/HSC_2024/pipelines"
PIPE_DIR="${PIPE_DIR-$DEFAULT_PIPE_DIR}"
pipeline="${PIPE_DIR}/DRP-Prod+injection_upd_JJK.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"

# File location to store qgraphs for execution.
build_dir="${butler_dir}/qgraphs/build"
queue_dir="${butler_dir}/qgraphs/queue"
processing_dir="${butler_dir}/qgraphs/processing"
processed_dir="${butler_dir}/qgraphs/processed"
merged_dir="${butler_dir}/qgraphs/merged"
for dir in $build_dir $queue_dir $processing_dir $processed_dir $merge_dir
do 
   mkdir -p $dir
done

# input_collections="u/NH/newer-processCCD/20250722,u/NH/newer-processCCD/20250721,skymaps"
# input_collections="u/NH/median,u/NH/multi"
input_collections="u/NH/coadd"
output_collection="u/NH/coadd"
output_type="-o"


function show_help() {
    cat <<EOF 

Usage: ${cmd} DETECTOR

Builds a qgraph for task ${pipeline}#${subset} for detector.

Qgraphs are stored in ${qgraph_dir}/${subset}-VISIT-DETECTOR.qg and can be run
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

patch=$1 && shift
# for detector in $(seq 0 103)
#for visit in $(butler query-dimension-records PG2_BUTLER visit --datasets injected_calexp --collections ${input_collections} | grep 202507 | sort -k 2n | awk ' {print $2} ')
# do
logline "patch: ${patch}"
#    echo ""
#    do
	# [ $detector -eq 9 ] && continue
	# [ $detector -eq 21 ] && continue
	# logline "Detector: ${detector}"
	skymap='big_2025'
	dataset="instrument='HSC' AND skymap='${skymap}' AND band='gri' and patch=${patch} and tract=0"
	qgraph="${subset//,/_}-${output_collection//\//_}-${patch}.qg"
	skip=0
	for dirname in "$build_dir" "$queue_dir" "$processing_dir" "$processed_dir" "$merged_dir"
	do
	    qgraph_file="${dirname}/${qgraph}"
	    [ -f ${qgraph_file} ] && skip=1 && logline ${qgraph_file} && break
	done
	[ $skip -gt 0 ] && exit 0
	qgraph_file=${build_dir}/${qgraph}
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
		 --skip-existing-in $output_collection \
		 --rebase \
		 --clobber-outputs \
		 -q ${qgraph_file} 
	[ -f ${qgraph_file} ] && mv ${qgraph_file} ${queue_dir}
#done

