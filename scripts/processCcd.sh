#!/bin/bash
set -a
. /etc/profile
setup -t clairesibbald -r /arc/projects/NewHorizons/obs_subaru/eb-gri/
pipetask run --register-dataset-types \
  -b BUTLER \
  -i HSC/raw/all,refcats,HSC/calib,HSC/calib/run1 \
  -o u/NH/processCCD$2 \
  -p NHPipeline.yaml#processCcd \
  -d "instrument='HSC' AND visit=${1} AND detector.purpose='SCIENCE' AND NOT detector=9" \
  -c isr:doDark=False 
