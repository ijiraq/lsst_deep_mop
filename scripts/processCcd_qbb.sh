#!/bin/bash
#At least one quanta needs to have successfully run already for this script to work
#The --extend-run option will cause errors if not
#Recommend running the first visit with detector 0 the regular way (pipetask run) before running this script
#If someone can think of a fix PLEASE make it

source ${HOME}/.bashrc

butler=${1}
query=${2:-"instrument='HSC' AND visit.observation_reason='science'"}

visit_list=$(butler query-data-ids ${butler} visit --where "$query" | awk '{ print $4 }' | sed 1,2d)

for visit in $visit_list
do
	for detector in $(seq 0 103)
	do
		graph_dir="qgraphs-${butler}"
		qgraph="${graph_dir}/processCcd${visit}_${detector}.qgraph"
		echo "Creating qgraph for ${visit} detector ${detector}"

		pipetask qgraph \
		-b ${butler} \
		-i HSC/raw/all,refcats,HSC/calib,HSC/calib/run1 \
		-o u/NH/processCCD \
		-p pipelines/NHPipeline.yaml#processCcd \
		-d "instrument='HSC' AND visit=${visit} AND detector=${detector}" \
		-c isr:doDark=False \
		-C calibrate:/arc/projects/NewHorizons/obs_subaru/eb-gri/config/calibrate.py \
		--skip-existing-in u/NH/processCCD \
		--qgraph-datastore-records \
		-q ${qgraph} \
		--output-run u/NH/processCCD/run1 \
		--extend-run \
		--clobber-outputs

		sk_launch lsst/science_pipeline:7-stack-lsst_distrib-v26_0_0 ${visit}-${detector} scripts/run_single_qgraph.sh ${butler} ${qgraph}
	done
done

echo "Processes completed launching"
mkdir -p "${graph_dir}/processed"
./scripts/merge.sh ${butler} ${graph_dir}