pipetask run --register-dataset-types \
-b $BUTLER_DIR \
-i u/NH/processCCD,HSC/raw/all,HSC/calib \
-o u/NH/sky-construct \
-p $CP_PIPE_DIR/pipelines/HSC/cpSky.yaml \
-d "instrument='HSC' AND detector=20 AND visit in (325722, 325754, 332104, 332360, 332746) " \

