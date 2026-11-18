#!/bin/bash
# At least one quanta needs to have successfully run already for this script to work
# The --extend-run option will cause errors if not
# Recommend running the first visit with detector 0 the regular way (pipetask run) before running this script
# If someone can think of a fix PLEASE make it

source ${HOME}/.bashrc
setup -t jkavelaars obs_subaru -r /arc/projects/NewHorizons/obs_subaru/eb-gri
cd /arc/projects/NewHorizons/HSC_2024


butler=${1}

graph_dir="qgraphs-${butler}-redo"
mkdir -p ${graph_dir}
qgraph="${graph_dir}/processCcd_all_visits_qgraph"
echo "Creating qgraph for all visits needing isr in ${butler}"

pipetask qgraph \
	-b ${butler} \
	-i HSC/raw/all,refcats,HSC/calib,HSC/calib/run1 \
	-o u/NH/processCCD \
	-p pipelines/NHPipeline.yaml#processCcd \
	-d "instrument='HSC' AND NOT detector=9" \
	-c isr:doDark=False \
	-C calibrate:/arc/projects/NewHorizons/obs_subaru/eb-gri/config/calibrate.py \
	--skip-existing-in u/NH/processCCD \
	--qgraph-datastore-records \
	-q ${qgraph} \
	--output-run u/NH/processCCD/run1 \
	--extend-run \
	--clobber-outputs

# echo "Processes completed launching"
# mkdir -p "${graph_dir}/processed"
# ./scripts/merge.sh ${butler} ${graph_dir}
