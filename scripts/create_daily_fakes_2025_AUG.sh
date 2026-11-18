#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

#list of all necessary variables for the injection catalogues queried by the butler
dates=(20250822)
ras=(288.4213958)
decs=(-20.4298416666)
filters=('r')
seeds=(123456789)

for obs in $(seq 0 $(( ${#dates[@]} - 1 )))
do
    echo "Building fakes for around ${ras[obs]} ${dec[obs]} on ${dates[obs]}"
    generate_sso_injection_catalog -a ${ras[obs]} -d ${decs[obs]} -r 2 -b PG2_BUTLER/ -s 4000 --day-obs ${dates[obs]} -i ${filters[obs]} -o fakes/master-fakes/${dates[obs]} --seed ${seeds[obs]} --overwrite 
    echo "Result code: $?"
done
