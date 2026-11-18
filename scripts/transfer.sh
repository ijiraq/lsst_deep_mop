 butler transfer-datasets BUTLER PG_BUTLER \
     --dataset-type calexp\
     --collections u/NH/processCCD\
     --where "instrument='HSC' AND detector.raft='1' AND detector.name_in_raft='53'"\
     --transfer copy --register-dataset-types
