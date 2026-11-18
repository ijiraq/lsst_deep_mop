
#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

# Defines the subset of the yaml file to use. Trying to do it all in one go
# subset="cpFlatIsr"
# Adds extra configuration options from the command line syntax.
config="--config isr:doDark=False"

# File location where it draws inputs from.
# File location of the yaml file.
pipeline="${PIPE_DIR}/DRP-Prod+injection_upd.yaml"
# Base Butler directory.
butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"
# File location to store qgraphs for execution.
qgraph_dir="${butler_dir}/qgraphs/hold"
# subsets because mosaic and bins are useless
subsets="processCcd"

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


# Take detector range from command line
detector_low=$1 && shift
detector_high=$1 && shift
obs_month=$1 && shift

echo $obs_month

if [ $obs_month == "jun2021" ]; then
    days=(20210609 20210617 20210705)
elif [ $obs_month == "sep2021" ]; then
    days=(20210905 20210906)
elif [ $obs_month == "jun2022" ]; then
    days=(20220602 20220603 20220629 20220630 20220703)
elif [ $obs_month == "oct2022" ]; then 
    #days=(20221020 20221021)
    days=(20221023)
elif [ $obs_month == "sep2023" ]; then 
    days=(20230908 20230909) # 20230910)
elif [ $obs_month == "jun2024" ]; then
    days=(20240611 20240612 20240705 20240708 20240709 20240710)
elif [ $obs_month == "jul2024" ]; then
    days=(20240731 20240801 20240802)
elif [ $obs_month == "jul2024" ]; then
    days=(20200519 20200526 20200528 20200529 20200530 20200531 20200601 20200619 20200620 20200621 20200622 20200624 20200625)
else
    echo "Not a valid observation period"
    exit -1
fi

echo 'Observation days acquired'

# echo "pipetask run --register-dataset-types --rebase -b $BUTLER_DIR -p $PIPE_DIR/DRP-Prod+injection_upd.yaml#processCcd -c isr:doDark=False -i "HSC/raw/all,HSC/calib,refcats,HSC/calib/oct2022v2,fakes/master-fakes/20221020" -o "u/NH/newer-processCCD/junk" -d "instrument='HSC' AND visit.observation_reason='science' AND detector.purpose='SCIENCE' AND detector=1 AND day_obs=20221020 AND visit=289614" "



for start_date in ${days[@]}
do

    # File location for the inputs and outputs.
    if [ $obs_month == "sep2021" ]; then #because sep2021 doesn't have flat frames, so pulling the closest ones
        input_collections="HSC/raw/all,HSC/calib,refcats,HSC/calib/${obs_month}v2,HSC/calib/jun2021v2,fakes/master-fakes/${start_date}"
    elif [ $obs_month == "jun2022" ]; then #because god knows why the data was deleted and it messed with calibrations, will make it better later
        input_collections="HSC/raw/all,HSC/calib,refcats,HSC/calib/${obs_month}v2,HSC/calib/${obs_month}v3,fakes/master-fakes/${start_date}"
    else
        input_collections="HSC/raw/all,HSC/calib,refcats,HSC/calib/${obs_month}v2,fakes/master-fakes/${start_date}"
    fi
    output_collection="u/NH/newer-processCCD/${start_date}"
    # echo "Inputs = ${input_collections}"
    mkdir -p ${butler_dir}/${output_collection}
    ([ ${start_date} -eq 20220703 ] || [ ${start_date} -eq 20230908 ] || [ ${start_date} -eq 20240705 ]) && echo "No science observations on ${start_date}" && continue

    # Loop over all detectors and produce qgraphs for them all.
    for detector in $(seq $detector_low $detector_high)
    do
        #these two were causing issues so they're not at the bottom anymore
        extendrun="--extend-run"
        output_type="--output-run"

        #rip
        [ ${detector} -eq 9 ] && echo "No detector 9 processing" && continue
        
        dataset="instrument='HSC' AND visit.observation_reason='science' AND detector.purpose='SCIENCE' AND detector=${detector} AND day_obs=$start_date" 
        
        # Include detector number, year and month in filename to separate detectors.
        qgraph_file="${qgraph_dir}/processCCD-${start_date}-${detector}-new.qgraph"
        # If the file already exists, delete it.
        [ -f ${qgraph_file} ] && rm ${qgraph_file}

        echo "Building qgraph for ${detector} on ${start_date}"

        # echo "pipetask run --register-dataset-types --rebase -b "${butler_dir}" -p "${pipeline}#${subsets}" ${config} -i "${input_collections}" -o "${output_collection}" -d "${dataset}""

        # Execute pipetask to create qgraph.
        pipetask --log-level INFO qgraph --rebase \
            -p "${pipeline}#${subsets}" ${config}\
            -b "${butler_dir}" \
            -i "${input_collections}" \
            -d "${dataset}" \
            -o "${output_collection}" \
            --clobber-outputs \
            --qgraph-datastore-records \
            -q ${qgraph_file} 
        

    done
done


