#!/bin/bash
BUTLER_DIR=$1
butler register-dataset-type $BUTLER_DIR ps1_pv3_3pi_20170110 SimpleCatalog htm7
butler register-dataset-type $BUTLER_DIR gaia_dr3_20230707 SimpleCatalog htm7
