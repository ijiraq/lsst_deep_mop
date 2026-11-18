# New Horizons QA Checkpoints

Mandatory quality gates between pipeline stages. Full processing runbook: [`NewHorizons_Pipeline_Runbook.md`](NewHorizons_Pipeline_Runbook.md).

Analysis Tools pipelines live under `$ANALYSIS_TOOLS_DIR/pipelines/` inside the LSST stack (exact path varies by release). Common ones:

| Pipeline | Use |
|----------|-----|
| `cpCore.yaml` | Calibration product quality (bias / flat) |
| `visitQualityCore.yaml` | Visit-level calexp / injected_calexp quality |
| `visitQualityExtended.yaml` | Deeper follow-up when core QA fails |
| `wholeSkyCore.yaml` | Sky / skymap-scale checks |

---

## 1. After bias / flat construction (`HSC/cp/START-END`)

- [ ] Masters live under `HSC/cp/START-END` (calibration products build area).
- [ ] Bias and flat certified into `HSC/calib` for the intended ISO date window (`--begin-date` / `--end-date`).
- [ ] Spot-check ≥3 detectors with `display_frame` / ds9 (no odd structure, sensible levels).
- [ ] Run calibration verification, e.g. `VerifyBias` / `cpCore` as available in your stack.

```bash
# Example pattern (adjust pipeline name to your stack)
pipetask run \
  -b ${BUTLER_DIR} \
  -p ${ANALYSIS_TOOLS_DIR}/pipelines/cpCore.yaml \
  -i HSC/cp/START-END,HSC/raw/all,HSC/calib \
  -o u/NH/qa/bias/${campaign} \
  -d "instrument='HSC' AND detector=10" \
  --register-dataset-types
```

**Fail closed:** do not certify into `HSC/calib` or proceed to science ISR if verification fails systematically.

---

## 2. After reference catalog ingest

- [ ] `butler query-datasets --collections refcats ${BUTLER_DIR}` shows PS1 and Gaia HTM shards.
- [ ] Source trees are `/arc/projects/LSST/refcats/...` (shared CANFAR), not a local copy.

---

## 3. After SSO catalog generation + injection (`#single_visit`)

Catalogs are produced in-pipeline by `generateSsoInjectionCatalog` (no `fakes/{day_obs}`).

- [ ] `sso_injection_catalog` exists for sample visit/detector data IDs in the output collection.
- [ ] Catalog has Trail columns: `ra`, `dec`, `mag`, `source_type`, `trail_length`, `beta` (and stable `injection_id`).
- [ ] Row counts scale reasonably with `population.density` and FOV; empty catalogs only where expected (edge / no overlap).
- [ ] `injected_calexp` shows the `INJECTED` mask plane where sources were drawn; `injected_calexp_catalog` rows match successful injections.
- [ ] Spot-check trail orientation (`beta`) vs expected sky motion for a few bright Trails.

---

## 4. After single-visit processing (`#single_visit`) — calexp QA

- [ ] Sample `calexp` and `injected_calexp` look calibrated (WCS, background, no ISR disasters).
- [ ] Run visit-level analysis tools on a representative detector set:

```bash
pipetask run \
  -b ${BUTLER_DIR} \
  -p ${ANALYSIS_TOOLS_DIR}/pipelines/visitQualityCore.yaml#astrometricRefCatSourceVisit \
  -i u/NH/processCCD/${day_obs} \
  -o u/NH/qa/visit/${day_obs} \
  -d "instrument='HSC' AND detector=10" \
  --register-dataset-types
```

- [ ] Review qgraph logs before merge; rebuild remaining failed quanta with `--skip-existing-in`.
- [ ] Accept a small number of systemic bad visits; escalate if failure rate is high.

Legacy stub: [`scripts/calexp_summary_QA.sh`](../scripts/calexp_summary_QA.sh) (hardcoded paths — update collections before use).

---

## 5. After warps (`#warp`)

- [ ] Skymap name matches the query (`big_YYYY`).
- [ ] Expected patches have non-empty `injected_directWarp` / `injected_psfMatchedWarp`.
- [ ] Empty quanta for non-overlapping patches are expected; mass failure is not.

---

## 6. After multi-night templates (`#template`)

Goal: moving sources that trail in single-night stacks should be suppressed in multi-night mean coadds.

- [ ] Selected visits span multiple nights (`selectTemplateVisits` / `nGroups`).
- [ ] Inspect `injected_goodSeeingCoadd_nImage` for coverage (no large holes in the science field).
- [ ] Visually compare template vs a single-night stack: trails should not dominate the template.
- [ ] Artifact masks from CompareWarp look reasonable.

**CONFIGURATION POINT** if trails remain: increase temporal baseline / `nGroups`, or adjust `qMax` / `nVisitsMin` in `pipelines/NewHorizons.yaml`.

---

## 7. After difference imaging (`#difference`)

- [ ] Spot-check `injected_goodSeeingDiff_differenceTempExp` for subtraction residuals.
- [ ] Kernel / matched-template products exist for successful quanta.
- [ ] **Fake recovery:** match DIA detections (or forced photometry) against `injected_calexp_catalog` / `sso_injection_catalog`; record completeness vs magnitude as a campaign metric.
- [ ] Flag nights with anomalous residual structure before handing diffs to shift-and-stack.

---

## 8. Qgraph merge gate (all stages)

Before `merge.sh` (or equivalent):

- [ ] Log contains a successful completion marker (e.g. `and 0 remain`).
- [ ] No silent OOM (graph in `processed/` but incomplete work).
- [ ] No duplicate dataset risk from merging half-finished runs.

```bash
# Example: list processCCD logs that do NOT look complete
grep -L "and 0 remain" ${BUTLER_DIR}/qgraphs/logs/processCCD-*
```

---

## Suggested collection naming for QA outputs

```text
u/NH/qa/bias/{campaign}
u/NH/qa/flat/{campaign}
u/NH/qa/visit/{day_obs}
u/NH/qa/template/{campaign}
u/NH/qa/diff/{day_obs}
```

Keep QA outputs out of science collection chains unless intentionally chained for downstream consumers.
