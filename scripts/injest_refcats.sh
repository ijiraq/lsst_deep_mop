#!/bin/bash
BUTLER_DIR=$1
butler ingest-files -t direct $BUTLER_DIR ps1_pv3_3pi_20170110 refcats ps1_pv3_3pi_20170110.ecsv
butler ingest-files -t direct $BUTLER_DIR gaia_dr3_20230707 refcats gaia_dr3_20230707.ecsv
# butler collection-chain $BUTLER_DIR --mode extend refcats refcats/gen2
