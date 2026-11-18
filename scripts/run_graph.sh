#!/bin/bash
BUTLER=${1}
QGRAPH=${2}
FILENAME=$(echo ${QGRAPH} | sed "s/.*\///g")
GRAPH_DIR=$(echo ${QGRAPH} | sed "s/\/.*//g")

setup -t clairesibbald obs_subaru -r /arc/projects/NewHorizons/obs_subaru/eb-gri
pipetask run-qbb ${BUTLER} ${QGRAPH}
mv ${QGRAPH} ${GRAPH_DIR}/processed/${FILENAME}
