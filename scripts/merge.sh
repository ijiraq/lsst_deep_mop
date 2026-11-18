#!/bin/bash

BUTLER_DIR="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
GRAPH_DIR="${BUTLER_DIR}/qgraphs"
EXAMINED_DIR="${GRAPH_DIR}/processed"
MERGED_DIR="${GRAPH_DIR}/merged" && mkdir -p "$MERGED_DIR" || exit -1
MERGING_DIR="${GRAPH_DIR}/merging" && mkdir -p "$MERGING_DIR" || exit -1
LOG_DIR="${GRAPH_DIR}/logs" && mkdir -p "$LOG_DIR" || exit -1
FAILED="${GRAPH_DIR}/merge_failed"  && mkdir -p "$FAILED" || exit -1

shopt -s nullglob 
for file in ${EXAMINED_DIR}/*.qg* 
do
    mv ${file} ${MERGING_DIR} || continue
    file="${MERGING_DIR}/${file##*\/}"
    log_file="${LOG_DIR}/${file##*\/}"
    log_file="${log_file%%.qg}_merge.log"
    echo "Processing ${file} and  putting logs into ${log_file}"
    butler --log-level=INFO --log-file "${log_file}" \
	   --no-log-tty transfer-from-graph \
	   --register-dataset-types \
	   --update-output-chain "${file}" "${BUTLER_DIR}" && mv -v "${file}" "${MERGED_DIR}/" || mv -v "${file}" "${FAILED}/"
done
