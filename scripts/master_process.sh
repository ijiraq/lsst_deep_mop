#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

function show_help() {
    cat <<EOF 

Usage: ${cmd} START_DATE END_DATE (DETECTOR_LOW) (DETECTOR_HIGH)

Important: start date and end date should encompass a short enough period of time where you are comfortable with them sharing calibrations.

--dlow: initial detector, standard is 0
--dhigh: last detector, standard is 103

Process an entire dataset, make sure you have created your injection catalogues beforehand running create_daily_fakes.sh

Bias
Flat
ProcessCCD
more to come

EOF
}

# Initialize the LSST environment again to be safe.
echo "Initializing environment"
# init the LSST Science Pipiline environment
export SHELL=/bin/bash
export USER=$(whoami)
export SCRIPT_DIR="/arc/projects/NewHorizons/HSC_2024/scripts"
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
echo "Done"

if [ $# -lt 2 ] || [ $# -gt 4 ]; then
   show_help
   exit -1
fi

start_date=$1 && shift && export start_date
end_date=$1 && shift && export end_date
detector_low=0
detector_high=103

while [ $# -gt 0 ]; do
    case "$1" in
        --dlow)
            detector_low="$2"
            shift 2
            ;;
        --dhigh)
            detector_high="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit -1
            ;;
        *)
            echo "Unknown option: $1"
            exit -1
            ;;
    esac
done

export detector_low
export detector_high

if [ $start_date -gt 20250000 ] || [ $start_date -lt 20200000 ]; then
    echo "Year not in registry"
    exit -1
else
    age="${start_date:0:4}"
    let year=$age+0
fi

echo "Year established: ${year}"

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

echo "Month established: ${month}"
export obs_month="${month}${year}"

#previously determined, edit as fit
case "$obs_month" in
    jun2021)
        days=(20210609 20210617 20210705)
        filter='HSC-R2'
        ;;
    sep2021)
        days=(20210905 20210906)
        filter='HSC-R2'
        ;;
    jun2022)
        days=(20220602 20220603 20220629 20220630 20220703)
        filter='HSC-R2'
        ;;
    oct2022)
        days=(20221020 20221021 20221023)
        filter='EB-GRI'
        ;;
    sep2023)
        days=(20230908 20230909 20230910)
        filter='EB-GRI'
        ;;
    jun2024)
        days=(20240611 20240612 20240705 20240708 20240709 20240710)
        filter='EB-GRI'
        ;;
    jul2024)
        days=(20240731 20240801 20240802)
        filter='EB-GRI'
        ;;
    *)
        echo "Not a valid observation period"
        exit 1
        ;;
esac

echo "Days of observation acquired ${days[@]}"
echo "Filter being used: ${filter}"
export days

#making biases
$SCRIPT_DIR/master_things/bias_master.sh
sleep 1
status=$?

if [[ $status -ne 0 ]]; then
    echo "Bias script failed with code $status. Exiting..."
    exit $status
fi

#displaying and checking
while true; do
    rand_det=$((RANDOM % (detector_high - detector_low + 1) + detector_low))

    python $SCRIPT_DIR/display_frame.py bias $butler_dir/u/NH/master-things/master-bias-construct/${obs_month} ${rand_det} bogus off 
    echo "Bias frame for ${rand_det}"

    read -rp "Looks good? [y/n/quit]" input

    if [[ "$input" == "y" ]]; then
        echo "Continuing..."
        break
    elif [[ "$input" == "quit" ]]; then
        exit -1
    fi

    sleep 1  
done

#certifying calibrations

start_val=$(( ${start_date} - 2 ))
end_val=$(( ${end_date} + 2 ))

if [ $start_date -eq 20220602 ]; then #silly exception
    start_val=20220531
fi

#careful with iso format
butler certify-calibrations \
    ${butler_dir} u/NH/master-things/master-bias-construct/${obs_month} HSC/calib/${obs_month}-masterv1 bias \
    --begin-date "${start_val:0:4}-${start_val:4:2}-${start_val:6:2}" --end-date "${end_val:0:4}-${end_val:4:2}-${end_val:6:2}" \
    --search-all-inputs

echo "Bias calibration certified for ${obs_month}"

#making flats
$SCRIPT_DIR/master_things/flat_master.sh
sleep 1
status=$?

if [[ $status -ne 0 ]]; then #could also be a function
    echo "Flat script failed with code $status. Exiting..."
    exit $status
fi

#checking the flats
while true; do #could be a function
    rand_det=$((RANDOM % (detector_high - detector_low + 1) + detector_low))

    python $SCRIPT_DIR/display_frame.py flat $butler_dir/u/NH/master-things/master-flat-construct/${obs_month} ${rand_det} ${filter} off 
    echo "Flat frame for ${rand_det}"

    read -rp "Looks good? [y/n/quit]" input

    if [[ "$input" == "y" ]]; then
        echo "Continuing..."
        break
    elif [[ "$input" == "quit" ]]; then
        exit -1
    fi

    sleep 1  
done

#certifying flats
butler certify-calibrations \
    ${butler_dir} u/NH/master-things/master-flat-construct/${obs_month} HSC/calib/${obs_month}-masterv1 flat \
    --begin-date "${start_val:0:4}-${start_val:4:2}-${start_val:6:2}" --end-date "${end_val:0:4}-${end_val:4:2}-${end_val:6:2}" \
    --search-all-inputs

echo "Flat calibration certified for ${obs_month}"

#processCCD, shaking in my boots

$SCRIPT_DIR/master_script_subs/processCCD_master.sh
sleep 1
status=$?

if [[ $status -ne 0 ]]; then
    echo "ProcessCCD script failed with code $status. Exiting..."
    exit $status
fi
