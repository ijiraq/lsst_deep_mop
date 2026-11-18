#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

# Defines the subset of the yaml file to use. Trying to do it all in one go
# subset="cpFlatIsr"
# Adds extra configuration options from the command line syntax.
config="--config cpFlatIsr:doBias=False --config cpFlatIsr:doDark=False --config cpFlatIsr:doVignette=False"

# File location where it draws inputs from.
input_collections="HSC/raw/all,HSC/calib"
# File location of the yaml file.
pipeline="${CP_PIPE_DIR}/pipelines/HSC/cpFlat.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/hold"
# subsets because mosaic and bins are useless
subsets="cpFlatIsr,cpFlatMeasure,cpFlatNormalize,cpFlatCombine"

function show_help() {
    cat <<EOF 

Usage: ${cmd} DETECTOR_LOW DETECTOR_HIGH START_DATE END_DATE

Builds a qgraph for task ${pipeline}#${subset}, one job per detecrtor 

Qgraphs are stored in ${qgraph_dir}/${subset}-DETECTOR.qgraph and can be run
using launch_qrunner.sh  

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


if [ $# -ne 4 ] 
then
   show_help
   exit -1
fi


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


# Take detector range from command line
detector_low=$1 && shift
detector_high=$1 && shift
start_date=$1 && shift
end_date=$1 && shift

#hopefully this will automate nomenclature
if [ $start_date -gt 20260000 ] || [ $start_date -lt 20200000 ]; then
    echo "Year not in registry"
    exit -1
elif [ $start_date -gt 20250000 ]; then
    year=2025
elif [ $start_date -gt 20240000 ]; then
    year=2024
elif [ $start_date -gt 20230000 ]; then 
    year=2023
elif [ $start_date -gt 20220000 ]; then 
    year=2022
elif [ $start_date -gt 20210000 ]; then 
    year=2021
elif [ $start_date -gt 20200000 ]; then
    year=2020
fi

echo 'Year established'

let month_det=$start_date-year*10000

if [ $month_det -gt 1200 ]; then
    month='dec'
elif [ $month_det -gt 1100 ]; then
    month='nov'
elif [ $month_det -gt 1000 ]; then
    month='oct'
elif [ $month_det -gt 900 ]; then
    month='sep'
elif [ $month_det -gt 800 ]; then
    month='aug'
elif [ $month_det -gt 700 ]; then
    month='jul'
elif [ $month_det -gt 600 ]; then
    month='jun'
elif [ $month_det -gt 500 ]; then
    month='may'
elif [ $month_det -gt 400 ]; then
    month='apr'
elif [ $month_det -gt 300 ]; then
    month='mar'
elif [ $month_det -gt 200 ]; then
    month='feb'
elif [ $month_det -gt 100 ]; then
    month='jan'
else 
    echo "Invalid date structure"
    exit -1
fi

echo 'Month established'

# File location for the outputs.
output_collection="u/NH/new-flat-construct/${month}${year}"
mkdir -p ${butler_dir}/${output_collection}
#these two were causing issues so they're not at the bottom anymore
#extendrun="--extend-run"
#output_type="--output-run"
# Loop over all detectors and produce qgraphs for them all.
for detector in $(seq $detector_low $detector_high)
do
    #rip
    [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue

    ([ ${detector} -eq 21 ] && [ ${year} -ge 2025 ]) && echo "No detector 21 processing as of 2025" && continue
    
    dataset="instrument='HSC' AND exposure.observation_type='domeflat' AND detector=${detector} AND day_obs>=$start_date AND day_obs<=$end_date" #oddly enough you cannot combine > statements here

    # Include detector number, year and month in filename to separate detectors.
    qgraph_file="${qgraph_dir}/full-flat-${month}${year}-${detector}.qgraph"
    # If the file already exists, delete it.
    [ -f ${qgraph_file} ] && rm ${qgraph_file}

    echo "Building qgraph"

    # Execute pipetask to create qgraph.
    pipetask --log-level INFO qgraph \
	     -p "${pipeline}#${subsets}" ${config}\
	     -b "${butler_dir}" \
	     -i "${input_collections}" \
	     -d "${dataset}" \
	     -o "${output_collection}" \
	     --clobber-outputs \
	     --qgraph-datastore-records \
	     -q ${qgraph_file}

done
