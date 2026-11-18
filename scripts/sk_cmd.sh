#!/bin/bash
# Run a command on skaha with FAILED/OK idiom to track success of container execution
# set -a 
# . ${HOME}/.bashrc
NAME="${HOSTNAME}"
cd "$1" && shift
[ -d "logs" ] || mkdir logs
echo "$@" > "logs/${NAME}.FAILED"
touch "logs/${NAME}.RUNNING"
[ -f "logs/${NAME}.OK" ] && rm "logs/${NAME}.OK"
"$@"  >& "logs/${NAME}.LOG" && touch "logs/${NAME}.OK"
rm "logs/${NAME}.RUNNING"
[ -f "logs/${NAME}.OK" ] && rm "logs/${NAME}.FAILED"
