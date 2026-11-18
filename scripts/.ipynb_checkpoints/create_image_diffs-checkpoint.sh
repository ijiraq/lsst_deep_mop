#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"


# File location of the yaml file.
DEFAULT_PIPE_DIR="/arc/projects/NewHorizons/HSC_2024/pipelines"
PIPE_DIR="${PIPE_DIR-$DEFAULT_PIPE_DIR}"
pipeline="${PIPE_DIR}/DRP-Prod+injection_upd.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/hold"
subsets="newHorizons"

function show_help() {
    cat <<EOF 

Usage: ${cmd} DETECTOR_LOW DETECTOR_HIGH PROCESS_DATE

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


if [ $# -ne 3 ] 
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
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
echo "Done"


# Take detector range and observation month from command line
detector_low=$1 && shift
detector_high=$1 && shift
obs_month=$1 && shift

echo $obs_month


#our sorted list of dates
if [ $obs_month == "jun2021" ]; then
    days=(20210609 20210617 20210705)
elif [ $obs_month == "sep2021" ]; then
    days=(20210905 20210906)
elif [ $obs_month == "jun2022" ]; then
    days=(20220602 20220603 20220629 20220630 20220703)
elif [ $obs_month == "oct2022" ]; then 
    days=(20221020 20221021 20221023)
elif [ $obs_month == "sep2023" ]; then 
    days=(20230908 20230909 20230910)
elif [ $obs_month == "jun2024" ]; then
    days=(20240611 20240612 20240705 20240708 20240709 20240710)
elif [ $obs_month == "jul2024" ]; then
    days=(20240731 20240801 20240802)
elif [ $obs_month == "may2020" ]; then
    days=(20200519 20200526 20200528 20200529 20200530 20200531 20200601 20220619 20200620 20200621 20200622 20200624 20200625)
elif [ $obs_month == "aug2020" ]; then
    days=(20200812 20200813 20200814 20200815)
elif [ $obs_month == "jul2025" ]; then
    days=(20250719 20250720 20250721 20250722)
else
    echo "Not a valid observation period"
    exit -1
fi

echo 'Observation days acquired'


#main loop, every day in a month uses the same calibration so this saves space
for start_date in ${days[@]}
do

    age="${start_date:0:4}"
    let year=$age+0

    # File location for the inputs and outputs.
    input_collections="u/NH/newer-processCCD/${start_date},u/NH/postSM/${start_date},skymaps"
    output_collection="u/NH/postSM+VS/${start_date}"
    mkdir -p ${butler_dir}/${output_collection}
    #not everyday is a science day
    ([ ${start_date} -eq 20220703 ] || [ ${start_date} -eq 20230908 ] || [ ${start_date} -eq 20240705 ]  || [ ${start_date} -eq 20200519 ] || [ ${start_date} -eq 20200619 ] || [ ${start_date} -eq 20250719 ] || [ ${start_date} -eq 20250720 ]) && echo "No science observations on ${start_date}" && continue

    # Loop over all detectors and produce qgraphs for them all.
    for detector in $(seq $detector_low $detector_high)
    do
        #these two were causing issues so they're not at the bottom anymore, good luck
        extendrun="--extend-run"
        output_type="--output-run"

        #rip
        [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
        ([ ${detector} -eq 21 ] && [ ${start_date} -gt 20250000 ]) && echo "No detector 21 processing as of 2025" && continue
        
        dataset="instrument='HSC' AND day_obs=${start_date} AND detector=${detector} AND skymap='big_${age}'"
        
        # Include detector number, year and month in filename to separate detectors.
        qgraph_file="${qgraph_dir}/imageDiff-${start_date}-${detector}.qgraph"
        # If the file already exists, delete it.
        [ -f ${qgraph_file} ] && rm ${qgraph_file}

        echo "Building qgraph for ${detector} on ${start_date}"

        # Execute pipetask to create qgraph.
        pipetask --log-level INFO qgraph --rebase \
            -p "${pipeline}#${subsets}"\
            -b "${butler_dir}" \
            -i "${input_collections}" \
            -d "${dataset}" \
            -o "${output_collection}" \
            --clobber-outputs \
            --qgraph-datastore-records \
            -q ${qgraph_file} 
        

    done
done
