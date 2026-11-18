export BUTLER_DIR=$(pwd)/PG2_BUTLER
mkdir -p $BUTLER_DIR
export PIPE_DIR=$(pwd)/pipelines
export CONFIG_DIR=$(pwd)/configs

echo "Initializing Science Pipeline environment"
# init the LSST Science Pipiline environment
export SHELL=/bin/bash
export USER=$(whoami)
.  /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib
setup -r /arc/projects/NewHorizons/lsst_deep_mop -t ${USER}
setup -r /arc/projects/NewHorizons/obs_subaru -t ${USER}
# Optional: local source_injection fork only if you have non-SSO patches.
# setup -r /arc/projects/NewHorizons/source_injection -t ${USER}
echo "Done"

# First time setup only
if [ -f ${BUTLER_DIR}/butler.yaml ] ; then
    butler create seed-config /arc/projects/NewHorizons/HSC_2024/butler-seed.yaml override $BUTLER_DIR 
    butler create $BUTLER_DIR
fi

butler register-instrument $BUTLER_DIR lsst.obs.subaru.HyperSuprimeCam
butler write-curated-calibrations $BUTLER_DIR HSC

butler register-dataset-type $BUTLER_DIR ps1_pv3_3pi_20170110 SimpleCatalog htm7
butler register-dataset-type $BUTLER_DIR gaia_dr3_20230707 SimpleCatalog htm7

butler ingest-files -t direct $BUTLER_DIR ps1_pv3_3pi_20170110 refcats/gen2 <PS1 FILENAME>
butler ingest-files -t direct $BUTLER_DIR gaia_dr3_20230707 refcats/gen2 <GAIA FILENAME>
butler collection-chain $BUTLER_DIR --mode extend refcats refcats/gen2

# Bring in a new setof data
RAW_DIR=$(pwd)/raw/June112024
butler ingest-raws $BUTLER_DIR ${RAW_DIR} -t link
butler query-dimension-records $BUTLER_DIR exposure --where "instrument='HSC' AND exposure.observation_type='bias'"
butler define-visits $BUTLER_DIR lsst.obs.subaru.HyperSuprimeCam

# Preproc the BIAS frames
pipetask run --register-dataset-types \
-b $BUTLER_DIR \
-i HSC/raw/all,HSC/calib \
-o u/NH/bias-construct \
-p $CP_PIPE_DIR/pipelines/HSC/cpBias.yaml \
-d "instrument='HSC' AND exposure.observation_type='bias' AND NOT detector=9" \
--config cpBiasIsr:doVignette=False \
--config cpBiasIsr:doMeasureBackground=False \
	 -j 32

# Register the bias frames
# do this grouped by observing season
# Craete input collections that select frames into date ranges
butler certify-calibrations $BUTLER_DIR u/NH/bias-construct HSC/calib/run1 bias --begin-date and --end-date

# Preproc the FLAT frames
pipetask run --register-dataset-types \
-b $BUTLER_DIR \
-i HSC/raw/all,HSC/calib \
-o u/NH/flat-construct \
-p $CP_PIPE_DIR/pipelines/HSC/cpFlat.yaml \
-d "instrument='HSC' AND exposure.observation_type='domeflat' AND NOT detector=9" \
--config cpFlatIsr:doVignette=False  \
--config isr:doBias=True \
-c isr:doDark=False \
--skip-existing \
-j 32
# Register the flats
# Do this in grouped by observing season
butler certify-calibrations $BUTLER_DIR u/NH/flat-construct HSC/calib/run1 flat --begin-date --end-date

pipetask run -b ${BUTLER_DIR} -p $CP_VERIFY_DIR/pipelines/HSC/VerifyBias.yaml \
     -i u/NH/bias-construct,HSC/raw/all,HSC/calib \
     -o u/NH/verifyBias \
     -d "instrument='HSC' AND detector=0 AND exposure.observation_type='bias' 

