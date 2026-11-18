#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"
# Take detector range to process 
detector_low=$1 && shift
detector_high=$1 && shift

# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"

# File location of the pipeline definition yaml file.
pipeline="${CP_PIPE_DIR}/pipelines/HSC/cpBias.yaml"
# Defines the subset of the yaml file to use.
subset="cpBiasIsr"
# Adds extra configuration options from the command line syntax.
config="--config cpBiasIsr:doVignette=False --config cpBiasIsr:doMeasureBackground=False"

# File location where it draws inputs from.
input_collection="HSC/raw/all,HSC/calib"
# File location for the outputs.
output_collection="u/NH/bias-construct/batch"

# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/queue"

# Loop over all detectors and produce qgraphs for them all.
for detector in $(seq $detector_low $detector_high)
do
   extendrun="--extend-run"
   output_type="--output-run"

   [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
   
   dataset="instrument='HSC' AND exposure.observation_type='bias' AND detector=${detector}"

   # Create a unique filename for the qgraph file
   TIMESTAMP=$(date +"%Y%m%d%H%M%S")
   qgraph_file="${qgraph_dir}/${subset}-${detector}-${TIMESTAMP}.qgraph"
   # If the file already exists, delete it.
   [ -f ${qgraph_file} ] && rm ${qgraph_file}

   echo "Building qgraph"

   # Execute pipetask to create qgraph.
   pipetask --log-level INFO qgraph \
      -p "${pipeline}#${subset}" ${config}\
      -b "${butler_dir}" \
      -i "${input_collections}" \
      -d "${dataset}" \
      ${output_type} "${output_collection}" ${extendrun} \
      --clobber-outputs \
      --qgraph-datastore-records \
      --skip-existing-in "${output_collection}" \
      -q ${qgraph_file} 

done
