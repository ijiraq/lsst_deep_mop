# Uses lsst.analysis_tools visitQualityCore.yaml#calexpSummary task
#!/bin/bash

BUTLER_DIR="/arc/projects/NewHorizons/HSC_2024/PG2_BUTLER/"
pipetask run -p ${ANALYSIS_TOOLS_DIR}/pipelines/visitQualityCore.yaml#astrometricRefCatSourceVisit \
-b $BUTLER_DIR \
-i u/NH/newer-processCCD/20250721 \
-o QA_graphs_test \
--data-query "instrument='HSC' and detector=10" \
--register-dataset-types


# }pipelines/coaddQualityCore.yaml#analyzeObjectTableCore \
# ipelines/visitQualityCore.yaml
# --config analyzeObjectTableCore:doApplyColorTerms=False \
# pipetask run -p ${ANALYSIS_TOOLS_DIR}/pipelines/visitQualityCore.yaml#calexpSummary \