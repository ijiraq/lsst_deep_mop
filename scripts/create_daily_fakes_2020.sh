#!/bin/bash
cmd=$(basename $0)
echo "${cmd} ${@}"

#list of all necessary variables for the injection catalogues queried by the butler
dates=(20200526 20200528 20200529 20200530 20200531 20200601 20200620 20200621 20200622 20200624 20200625)
ras=(287.37 288.74 287.33 288.71 287.31 288.68 288.66 287.11 288.62 287.06 288.57)
decs=(-20.22 -20.58 -20.12 -20.38 -20.12 -20.38 -20.05 -20.05 -20.05 -20.06 -20.05)
filters=('r' 'r' 'r' 'r' 'r' 'r' 'r' 'r' 'r' 'r' 'r')
seeds=(62036530 79583378 38838446 80567582 32833562 83290504 76476856 55822521 40085298 96445508 50130619)

for obs in $(seq 0 $(( ${#dates[@]} - 1 )))
do
    generate_sso_injection_catalog -a ${ras[obs]} -d ${decs[obs]} -r 2 -b PG2_BUTLER/ -s 4000 --day-obs ${dates[obs]} -i ${filters[obs]} -o fakes/master-fakes/${dates[obs]} --seed ${seeds[obs]} --overwrite 
    echo "${dates[obs]} faked successfully"
    
done