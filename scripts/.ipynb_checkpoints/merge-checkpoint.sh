#!/bin/bash

BUTLER_DIR=${1:-PG2_BUTLER}
GRAPH_DIR="${BUTLER_DIR}/qgraphs"
MERGED_DIR="${GRAPH_DIR}/merged"
FAILED="${GRAPH_DIR}/failed"
EXAMINED_DIR="${GRAPH_DIR}/examined"

mkdir -p ${MERGED_DIR}
mkdir -p ${FAILED}
while true
do
	for file in ${EXAMINED_DIR}/*.qgraph 
	do
		echo ${file}
		butler --log-level=INFO --long-log transfer-from-graph --register-dataset-types \
		--update-output-chain ${file} ${BUTLER_DIR} && mv -v ${file} ${MERGED_DIR}/ || mv -v ${file} ${FAILED}/
	done
        break
	# echo "Waiting for files to appear in ${PROCESSED_DIR}"
	# sleep 60
done
