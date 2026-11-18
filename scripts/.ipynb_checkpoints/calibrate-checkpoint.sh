#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"


function show_help() {
    cat <<EOF 

Usage: ${cmd} calibration_type start_date end_date

calibration type can be bias or flat

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

calibration=$1 && shift
start_date=$1 && shift
end_date=$1 && shift



if [ $start_date -gt 20250000 ] || [ $start_date -lt 20200000 ]; then
    echo "Year not in registry"
    exit -1
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

#just being safe
start_val=$(( ${start_date} - 2 ))
end_val=$(( ${end_date} + 2 ))

if [ $start_date -eq 20220602 ]; then #silly exception
    start_val=20220531
fi

input="u/NH/new-${calibration}-construct/${month}${year}"
output="HSC/calib/${month}${year}v2"

#careful with iso format
butler certify-calibrations \
    ${butler_dir} ${input} ${output} ${calibration} \
    --begin-date "${start_val:0:4}-${start_val:4:2}-${start_val:6:2}" --end-date "${end_val:0:4}-${end_val:4:2}-${end_val:6:2}" \
    --search-all-inputs

echo "${calibration} calibration certified for ${month} ${year}"