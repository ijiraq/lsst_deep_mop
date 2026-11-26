import os
from lsst.daf.butler import Butler

# 1. Fetch the skymap object from dp2
src_butler = Butler("dp2", collections=["skymaps"])
skymap = src_butler.get("skyMap", skymap="lsst_cells_v2")

# 2. Register the dimension records (skymap, tract, patch) and store the dataset
dest_butler = Butler(os.environ["BUTLER_DIR"], writeable=True)
skymap.register("lsst_cells_v2", dest_butler)

