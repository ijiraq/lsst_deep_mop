
logline(){
    local COLUMNS=$(tput cols) 
    local msg=$1
    local LEN=$((($COLUMNS-${#msg}-2)/2))
    for i in $(seq 1 $LEN); do echo -n "#"; done
    echo -n " $msg "
    for i in $(seq 2 $LEN); do echo -n "#"; done
    echo -ne "#\r"
}

BASE_DIR="/arc/projects/NewHorizons/HSC_2024"
PIPE_DIR="${BASE_DIR}/pipelines"
pipeline="${PIPE_DIR}/DRP-Prod+injection_upd_JJK.yaml"
butler_dir="${BASE_DIR}/PG2_BUTLER"

# File location to store qgraphs for execution.
function setup_qgraph_dirs() {
    qgraph_dir=$1
    declare -gA status_dirs
    declare -a status_types=( "build" "hold" "queue" "processing" "processed" "merging" "merged" "failed")
    for dirname in ${status_types[@]}
    do
	status_dirs["${dirname}"]="${qgraph_dir}/${dirname}"
	mkdir -p ${status_dirs[$dirname]} || exit
    done
}


function qgraph_exists() {
    # check if given directory exists and take apropriate action
    filename=$1
    for dirname in ${status_dirs[@]}
    do
	[[ -f "$filename" ]] && logline "$filename" && return
    done
    false
    }
