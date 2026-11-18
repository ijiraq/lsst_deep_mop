#!/bin/bash
BUTLER=$1
RUN=$2
pipetask run --register-dataset-types \
-b ${BUTLER} \
-i ${RUN} \
-o ${RUN}/fgcm \
-p pipelines/DRP-RC2_subset.yaml#fgcm
