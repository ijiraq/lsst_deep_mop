#!/bin/bash
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
setup -r /arc/projects/NewHorizons/source_injection -t  ${USER}
detector=$1
logLevel="INFO"
skymap="small_325772_${detector}"
day_obs=20240612


echo ""
echo "****************************************************************************"
echo "                                  injected_step1 ${detector}"
echo "****************************************************************************"
echo ""
pipetask --log-level  $logLevel run \
	 -b PG2_BUTLER \
	 -d "instrument='HSC' AND detector=${detector} AND skymap='${skymap}' AND visit.observation_reason='science' AND visit.day_obs=${day_obs}" \
	 -p pipelines/DRP-Prod+injection.yaml#injected_step1 \
	 -i u/NH/step1,u/NH/step2,skymaps,fakes/20240612 \
	 --output-run u/NH/fakes \
	 --extend-run \
	 --skip-existing \
	 --clobber-outputs \
	 -j 16

echo ""
echo "****************************************************************************"
echo "                                  makeWarp ${detector} "
echo "****************************************************************************"
echo ""

pipetask --log-level  ${logLevel} run \
	 -b PG2_BUTLER \
	 -d "instrument='HSC' AND detector=${detector} AND skymap='${skymap}' AND visit.observation_reason='science' AND visit.day_obs=${day_obs}" \
	 -i u/NH/step1,u/NH/step2/*,skymaps,fakes/20240612 \
	 -p pipelines/DRP-Prod+injection.yaml#makeWarp \
	 --config-file makeWarp:configs/makeWarpConfig.py \
	 --output-run u/NH/fakes \
	 --extend-run \
	 --skip-existing \
	 --clobber-outputs \
	 -j 16

echo ""
echo "****************************************************************************"
echo "                                  goodSeeing ${detector}"
echo "****************************************************************************"
echo ""
pipetask --log-level   ${logLevel} run \
	 -b PG2_BUTLER \
	 -d "instrument='HSC' AND detector=${detector} AND skymap='${skymap}' AND visit.observation_reason='science' AND visit.day_obs=${day_obs}" \
	 -p pipelines/DRP-Prod+injection.yaml#selectGoodSeeingVisits \
	 -i u/NH/step1,u/NH/step2,skymaps,fakes/20240612 \
	 --output-run u/NH/fakes \
	 --skip-existing \
	 --extend-run \
	 --clobber-outputs \
	 -j 16



echo ""
echo "****************************************************************************"
echo "                                  templateGen ${detector}"
echo "****************************************************************************"
echo ""
pipetask --log-level   ${logLevel} run \
	 -b PG2_BUTLER \
	 -d "instrument='HSC' AND detector=${detector} AND skymap='${skymap}' AND visit.observation_reason='science' AND visit.day_obs=${day_obs}" \
	 -p pipelines/DRP-Prod+injection.yaml#templateGen \
	 -i u/NH/step1,u/NH/step2,skymaps,fakes/20240612 \
	 --output-run u/NH/fakes \
	 --skip-existing \
	 --extend-run \
	 --clobber-outputs \
	 -j 16

# 	 -i u/NH/goodSeeing,u/NH/directWarps,skymaps,u/NH/injection2 \

echo ""
echo "****************************************************************************"
echo "                                  imaegDifference ${detector}"
echo "****************************************************************************"
echo ""

pipetask --log-level  ${logLevel} run \
	 -b PG2_BUTLER \
	 -d "instrument='HSC' AND detector=${detector} AND skymap='${skymap}' AND visit.observation_reason='science' AND visit.day_obs=${day_obs}" \
	 -p pipelines/DRP-Prod+injection.yaml#imageDifference \
	 -i u/NH/step1,u/NH/step2,skymaps,fakes/20240612\
	 --output-run u/NH/fakes \
	 --extend-run \
	 --rebase \
	 --skip-existing \
	 --clobber-outputs \
	 -j 16

echo ""
echo "****************************************************************************"
echo "                                  warpDiff ${detector}"
echo "****************************************************************************"
echo ""
pipetask --log-level ${logLevel} run\
         -b PG2_BUTLER\
         -p pipelines/warpDiff.yaml#warpDiff\
	 -i u/NH/step1,u/NH/step2/*,skymaps,fakes/20240612\
         --output-run u/NH/fakes \
	 --skip-existing \
         --config-file warpDiff:configs/warpDiff.py \
         --extend-run \
         --rebase \
         --clobber-outputs \
         -d "instrument='HSC' AND skymap='${skymap}' AND detector=${detector} and visit.observation_reason='science' AND visit.day_obs=${day_obs}"\
         -j 16

echo ""
echo "****************************************************************************"
echo "                                  fix_parq_rates ${detector}"
echo "****************************************************************************"
echo ""
python python_scripts/fix_parq_rates.py ${detector}
