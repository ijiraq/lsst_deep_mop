#!/bin/bash
script_dir=$(dirname $0)
echo "Initializing LSST environment"
set -a
# init the LSST Science Pipiline environment
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
echo "Done"

BUTLER=${1}
QGRAPH_DIR=${2}
CORES=${OMP_NUM_THREADS:-1}
THREADS=${CORES}

# THREADS=1
export DAF_BUTLER_CACHE_DIRECTORY=/scratch/${USER}
mkdir -p ${DAF_BUTLER_CACHE_DIRECTORY}
echo "Running ${THREADS} threads"

QUEUE_DIR="${QGRAPH_DIR}/queue"
PROCESSING_DIR="${QGRAPH_DIR}/processing"
FAILED_DIR="${QGRAPH_DIR}/failed"
PROCESSED_DIR="${QGRAPH_DIR}/processed"
MEMORY_LOG="${QGRAPH_DIR}/memory"
LOG_DIR="${QGRAPH_DIR}/logs"

mkdir -p ${LOG_DIR}
mkdir -p ${PROCESSING_DIR}
mkdir -p ${PROCESSED_DIR}
mkdir -p ${FAILED_DIR}
mkdir -p ${MEMORY_LOG}

${script_dir}/memInfo.sh >& ${MEMORY_LOG}/$(hostname) &

status=0

while [ $(ls ${QUEUE_DIR}/*.qgraph|wc -l) -gt 0 ]
do
    ls ${QUEUE_DIR}/*.qgraph | while read FILENAME
    do

	mv ${FILENAME} ${PROCESSING_DIR} || continue
	echo " Processing ${FILENAME} using ${THREADS} cores "
	QGRAPH="${PROCESSING_DIR}/$(basename ${FILENAME})"
	LOGFILE="${LOG_DIR}/$(echo $(basename ${FILENAME})|sed -e 's/.qgraph/.log/')"
	
	echo ${BUTLER} ${QGRAPH} ${LOGFILE} ${THREADS}
	
	pipetask --log-file ${LOGFILE} --no-log-tty run-qbb \
		 ${BUTLER} -j ${THREADS} \
		 ${QGRAPH}

	this_status=$?
	if [ ${this_status} ];
	then
	    mv ${QGRAPH} ${PROCESSED_DIR}
	else
	    mv ${QGRAPH} ${FAILED_DIR}
	fi
	status=$((status + this_status))
    done
done
echo ${status}
