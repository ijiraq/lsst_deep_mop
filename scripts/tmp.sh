#!/bin/bash
DETECTOR=$1
butler remove-runs BUTLER-20240612/butler_${DETECTOR}.yaml u/NH/processCCD/20240730T190508Z --no-confirm --force
