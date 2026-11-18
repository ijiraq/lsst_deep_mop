#!/bin/bash
script_dir=$(dirname $0)
delay=$1 && shift

awk ' BEGIN { printf("%10s %10s\n", "MemTotal", "MemFree") }' /proc/meminfo
while true
do
    awk -f ${script_dir}/memInfo.awk /proc/meminfo
    sleep ${delay}
done

