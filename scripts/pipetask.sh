#!/bin/bash
set -a
. /etc/profile
setup -t clairesibbald -r /arc/projects/NewHorizons/obs_subaru/eb-gri/
pipetask run --register-dataset-types \
  -b BUTLER-TEST \
  -i HSC/raw/all,refcats,HSC/calib \
  -o u/NH/processCCD-20240610 \
  -p NHPipeline.yaml#processCcd \
  -d "instrument='HSC' AND visit=${1} AND detector.purpose='SCIENCE' AND NOT de>
  -c isr:doDark=False -c isr:doFlat=False -c isr:doBias=False 
