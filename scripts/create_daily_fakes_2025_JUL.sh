#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

#list of all necessary variables for the injection catalogues queried by the butler
dates=(20250721 20250722)
ras=(288.8749541666666 288.87505416666664)
decs=(-20.36668611111111 -20.36661388888889)
filters=('gri' 'gri')
seeds=(70998016 18326045)

for obs in $(seq 0 $(( ${#dates[@]} - 1 )))
do
    generate_sso_injection_catalog -a ${ras[obs]} -d ${decs[obs]} -r 2 -b PG2_BUTLER/ -s 4000 --day-obs ${dates[obs]} -i ${filters[obs]} -o fakes/master-fakes/${dates[obs]} --seed ${seeds[obs]} --overwrite 
    echo "${dates[obs]} faked successfully"
    
done