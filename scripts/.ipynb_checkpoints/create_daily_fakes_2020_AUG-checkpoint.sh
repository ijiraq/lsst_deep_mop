#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

#list of all necessary variables for the injection catalogues queried by the butler
dates=(20200812 20200813 20200814 20200815)
ras=(286.26 287.68 286.23 287.75)
decs=(-20.139 -20.098 -20.14 -20.139)
filters=('r' 'r' 'r' 'r')
seeds=(96962691 73923017 93741270 71605767)

for obs in $(seq 0 $(( ${#dates[@]} - 1 )))
do
    generate_sso_injection_catalog -a ${ras[obs]} -d ${decs[obs]} -r 2 -b PG2_BUTLER/ -s 4000 --day-obs ${dates[obs]} -i ${filters[obs]} -o fakes/master-fakes/${dates[obs]} --seed ${seeds[obs]} --overwrite 
    echo "${dates[obs]} faked successfully"
    
done