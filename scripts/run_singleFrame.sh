#!/bin/bash
BUTLER=$1
RUN=$2
pipetask run --register-dataset-types \
-b ${BUTLER} \
-i ${RUN} \
-o ${RUN}/single_frame \
-p pipelines/DRP-RC2_subset.yaml#singleFrame
