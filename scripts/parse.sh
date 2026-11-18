#!/bin/bash

USAGE="${USAGE:-No USAGE defined}"   # should be defined in each script, giving the usage
NOPTS="${NOPTS:-0}"                  # should be defined in each script, number of CL options expected
loglevel=ERROR

function show_help(){
    echo "##################################################################################"
    echo "${USAGE}"
    echo "##################################################################################"
}

function init_lsst(){
    echo "Initializing LSST Science Pipeline"
    # init the LSST Science Pipiline environment
    export SHELL=/bin/bash
    export USER=$(whoami)
    .  /opt/lsst/software/stack/loadLSST.bash
    setup lsst_distrib
    setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
    setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
    echo "Done"
 }


OPTIND=1
while getopts lhf: opt; do
    shift
    case "${opt}" in
	l) loglevel="${1}"
           export ${loglevel}
	   ;;
	h) show_help
	   exit 0
	   ;;
	*) show_help >& 2
	   exit 1
	   ;;
    esac
done
shift $(( OPTIND - 1 ))

if [[ "${NOPTS}" == "+"* ]]
then
	NOPTS=${NOPTS#+}
	if [ $# -lt "${NOPTS}" ] 
	then
             echo "Got $# CL args, expected ${NOPTS} or more"
             show_help
	     exit 255
	fi
elif [ $# -ne "${NOPTS}" ]
then
   echo "Got $# CL args, expected ${NOPTS}"
   show_help
   exit 255
fi


