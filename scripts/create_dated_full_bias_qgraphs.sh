#!/bin/bash
# This script build qgraphs that execute the bias construction following the pattern
# From the 'lab notebook'
# pipetask run --register-dataset-types \
# -b $BUTLER_DIR \
# -i HSC/raw/all,HSC/calib \
# -o u/NH/bias-construct \
# -d "instrument='HSC' AND exposure.observation_type='bias' AND NOT detector=9" \
# -c cpBiasIsr:doVignette=False \
# -j 32

cmd=$(basename $0)
echo "${cmd} ${@}"
# Take detector range from command line
detector_low=$1 && shift
detector_high=$1 && shift
start_date=$1 && shift
end_date=$1 && shift

# Defines the subset of the yaml file to use. Trying to do it all in one go
# subset="cpBiasIsr"
# Adds extra configuration options from the command line syntax.
config="--config cpBiasIsr:doVignette=False --config cpBiasIsr:doMeasureBackground=False"


# File location where it draws inputs from.
input_collections="HSC/raw/all,HSC/calib"
# File location of the yaml file.
pipeline="${CP_PIPE_DIR}/pipelines/HSC/cpBias.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/hold"
# subsets because mosaic and bins are not needed for our processing
subsets="cpBiasIsr,cpBiasCombine"

# Initialize the LSST environment again to be safe.
echo "Initializing environment"
# init the LSST Science Pipiline environment
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
echo "Done"

output_collection="u/NH/new-bias-construct/${start_date}-${end_date}"
mkdir -p ${butler_dir}/${output_collection}
output=${output_collection}

# Loop over all detectors and produce qgraphs for them all.
for detector in $(seq $detector_low $detector_high)
do
    [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
    ([ ${detector} -eq 21 ] && [ ${start_date} -ge 20250000 ]) && echo "No detector 21 processing as of 2025" && continue
    
    dataset="instrument='HSC' AND exposure.observation_type='bias' AND detector=${detector} AND day_obs>=$start_date AND day_obs<=$end_date "

    # Include detector number in filename to separate detectors.
    qgraph_file="${qgraph_dir}/full-bias-${start_date}-${end_date}-${detector}.qgraph"
    # If the file already exists, delete it.
    [ -f ${qgraph_file} ] && rm ${qgraph_file}

    echo "Building qgraph"

    # Execute pipetask to create qgraph.
    pipetask --log-level INFO qgraph \
	     -p "${pipeline}#${subsets}" ${config}\
	     -b "${butler_dir}" \
	     -i "${input_collections}" \
	     -d "${dataset}" \
	     -o "${output}" \
	     --clobber-outputs \
	     --skip-existing \
	     --qgraph-datastore-records \
	     -q ${qgraph_file} 

done
