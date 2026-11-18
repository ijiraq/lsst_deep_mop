# Configuration overrides for MakeDirectWarpTask (New Horizons).
#
# Referenced from pipelines when you want file-based config instead of -c flags:
#   connections / task config:
#     file:
#       - $CONFIG_DIR/makeDirectWarpConfig.py
#
# Keep campaign-specific tuning here rather than hardcoding absolute paths
# inside the pipeline YAML. Uncomment and adjust as needed.

# Example (illustrative — enable only after validating against your stack version):
# config.doApplyLocalPhotoCalib = True
# config.select.maxUsableFraction = 0.75
