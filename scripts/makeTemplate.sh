#!/bin/bash
butler=PG_BUTLER
collection=20240612_0
# query="instrument='HSC' AND visit.observation_reason='science'"
# visit_list=$(butler query-data-ids ${butler} visit --where "$query" | awk '{ print $4 }' | sed 1,2d)

pipetask run \
-b ${butler} \
-i ${collection} \
-o u/NH/template \
-p pipelines/NHPipeline.yaml#makeTemplate \
-s "skymap = '20240612_0'" \
--config makeWarp:matchingKernelSize=29


# pipetask run --register-dataset-types \
# -b $RC2_SUBSET_DIR/SMALL_HSC/butler.yaml \
# -i u/$USER/source_calibration,u/$USER/gbdes,u/$USER/fgcm \
# -o u/$USER/warps \
# -p $DRP_PIPE_DIR/pipelines/HSC/DRP-RC2_subset.yaml#makeWarp \
# -d "skymap = 'hsc_rings_v1' AND tract = 9813 AND patch in (38, 39, 40, 41)"
