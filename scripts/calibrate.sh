#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

butler_dir="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER"


function show_help() {
    cat <<EOF 

Usage: ${cmd} calibration_type start_date end_date

calibration type can be bias or flat

Collections will have the form:

input="u/NH/new-${calibration}-construct/start_date-end_date"
output="HSC/calib/start_date-end_date"


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


input="u/NH/new-${calibration}-construct/${start_date}-${end_date}"
output="HSC/calib/${start_date}-${end_date}"

#careful with iso format
butler certify-calibrations \
    ${butler_dir} ${input} ${output} ${calibration} \
    --begin-date "${start_date:0:4}-${start_date:4:2}-${start_date:6:2}" --end-date "${end_date:0:4}-${end_date:4:2}-${end_date:6:2}" \
    --search-all-inputs

echo "${calibration} calibration certified for ${start_date}-${end_date}"
