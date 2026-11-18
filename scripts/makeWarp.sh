pipetask run -b PG2_BUTLER\
	 -p pipelines/DRP-Prod+injection.yaml#makeWarp \
	 -o u/NH/makeWarp\
	 -i u/NH/injection,u/NH/step2,skymaps \
	 --register-dataset-types \
	 --config-file makeWarp:configs/makeWarpConfig.py \
	 -d "instrument='HSC' AND detector=22 AND visit=325832 AND skymap='discrete_325772_22'" \
	 --clobber-outputs
