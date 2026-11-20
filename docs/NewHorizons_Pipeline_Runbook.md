# New Horizons Pipeline Runbook

Canonical instructions for setting up and running the LSST Science Pipelines (latest_daily; v30) as the New Horizons HSC processing path: ISR → synthetic source injection → warp to sky patches → multi-night templates → difference images, with QA at each stage.

A simplified pipeline definition that describes the workflow [`pipelines/NewHorizons.yaml`](../pipelines/NewHorizons.yaml).

An older student cookbook is archived at [`docs/archive/LSST_Pipeline_v29_in_ARCADES.md`](archive/LSST_Pipeline_v29_in_ARCADES.md). Prefer this runbook.

---

## 1. Purpose and prerequisites

### Science goal

New Horizons needs to:

1. Create ISR-calibrated visit images.
2. Inject synthetic sources (for completeness / recovery tests).
3. Warp images onto a discrete sky map (tracts/patches).
4. Build **multi-night** good-seeing templates so moving sources (trails in single-night stacks) are suppressed in the mean coadd.
5. Difference each science image against the template per patch.

### Environment

- CANFAR science pipeline container with LSST Science Pipelines **latest_daily**.
- Custom packages (setup order matters; see §2):
  - [`lsst_deep_mop`](https://github.com/ijiraq/lsst_deep_mop) — this repo: multi-night visit selection (`lsst_deep_mop.selectImages`) **and** SD-MOC SSO injection (`sso_injection`).
  - [`packages/obs_subaru`](../packages/obs_subaru) — HSC instrument config (includes New Horizons filter definitions).
  - Stock `source_injection` from the LSST distribution (GalSim Trail/Star inject; no SSO logic). Use a local fork only if you have non-SSO patches.
  - Shared reference catalogs on CANFAR: `/arc/projects/LSST/refcats` (do not rebuild locally).
  - PostgreSQL-backed Butler registry (see §3).

### Working layout (typical)

```text
/arc/projects/NewHorizons/clean_horizons/     # the project root (${PROJECT_DIR})
  PG2_BUTLER/                                 # Butler repo (${BUTLER_DIR})
  pipelines/                                  # NewHorizons.yaml, etc.
  configs/                                    # task config overrides
  scripts/                                    # qgraph helpers (legacy; see §15)
  raw/                                        # unpacked SMOKA data
```

---

## 2. Environment variables and package setup

Add something like the following to your shell startup (or source a project `env.sh` every session):

```bash
export REFCATS=/arc/projects/LSST/refcats
export PROJECT_DIR=/arc/projects/NewHorizons/clean_horizons
export BUTLER_DIR=${PROJECT_DIR}/PG2_BUTLER
export PIPE_DIR=${PROJECT_DIR}/pipelines          # or path to this repo's pipelines/
export CONFIG_DIR=${PROJECT_DIR}/configs
export LSST_PACKAGES=/arc/projects/LSST/packages       # packages live under here or in this repo

export SHELL=/bin/bash
export USER=$(whoami)
. /opt/lsst/software/stack/loadLSST.bash
setup lsst_distrib

# One product: lsst_deep_mop (SSO + MovingTargetSelect), then obs_subaru so NH filters win.
setup -r ${LSST_PACKAGES}/lsst_deep_mop -t ${USER}
setup -r ${LSST_PACKAGES}/obs_subaru -t ${USER}
```

Getting the correct obs_subaru package is critical, the first time you setup a new processing environment be sure to confirm the instrument package is picking up our local version:

```bash
pydoc lsst.obs.subaru
# Path be ${LSST_PACKAGES}/obs_subaru, not the stack default.
```

---

## 3. PostgreSQL registry and Butler repository

### 3.1 Seed file (no secrets in git)

Copy the template and fill in credentials from your password manager / project secrets store:

```bash
cp ${CONFIG_DIR}/butler_seed.template.yaml ${CONFIG_DIR}/butler_seed.yaml
# Edit butler_seed.yaml: host, database, namespace, username, password.
# Do not commit butler_seed.yaml as the password id clear text in that file.
```

Template fields (see [`configs/butler_seed.template.yaml`](../configs/butler_seed.template.yaml)):

```yaml
registry:
  db: "postgresql://HOST:5432/DATABASE"
  namespace: "clean_horizons"   # note: key name is namespace
  username: "butler"
  password: "<from secrets>"
```

The Postgres database must already exist and the Butler user must be able to create schema objects. Creating the Butler repo initializes the registry schema.

### 3.2 Create the Butler repo

```bash
butler create --seed-config ${CONFIG_DIR}/butler_seed.yaml --override ${BUTLER_DIR}
butler register-instrument ${BUTLER_DIR} lsst.obs.subaru.HyperSuprimeCam
butler write-curated-calibrations ${BUTLER_DIR} lsst.obs.subaru.HyperSuprimeCam --collections HSC/calib
```

`write-curated-calibrations` populates the **`HSC/calib`** collection with *instrument-package* products that ISR needs for every detector: `camera`, `defects`, `bfKernel`, and the various `transmission_*` datasets (see `obs_subaru` curated types). These are not the nightly bias/flat masters you build later; they are static (or slowly changing) instrument recipes shipped with the HSC package. Later, when you `certify-calibrations` masters built under `HSC/cp/…`, those bias/flat products are registered into the same **`HSC/calib`** collection with `--begin-date` / `--end-date` so downstream ISR can select them by exposure date.

Verify:

```bash
ls ${BUTLER_DIR}/butler.yaml
butler query-collections ${BUTLER_DIR}
# Expect curated types under HSC/calib, e.g. defects, camera, bfKernel, transmission_*
butler query-dataset-types ${BUTLER_DIR} | head
```

---

## 4. Ingest raw images and define visits

### 4.1 Obtain and unpack SMOKA data

[mostly you don't need to do this step as all the data are alraedy in ${PROJECT_DIR}/raw ]
1. From a CANFAR desktop, request HSC data at [SMOKA](http://smoka.nao.ac.jp) (filter, observation type: science / bias / domeflat; FPACK).
2. Download with the provided `wget` list; verify with `md5sum`.
3. Unpack into a raw tree, e.g. `${PROJECT_DIR}/raw/<campaign>/`.

### 4.2 Ingest

```bash
butler ingest-raws ${BUTLER_DIR} ${PROJECT_DIR}/raw/<campaign>/ -t link
```

Verify calibrations for a night:

Replace the 'YYYYMMDD' strings below with the UT Year, Month, Day the observations of interest were aquired on.

```bash
butler query-dimension-records ${BUTLER_DIR} exposure \
  --where "instrument='HSC' AND exposure.observation_type='bias' AND day_obs=YYYYMMDD"

butler query-dimension-records ${BUTLER_DIR} exposure \
  --where "instrument='HSC' AND exposure.observation_type='domeflat' AND day_obs=YYYYMMDD"
```

### 4.3 Define visits

```bash
butler define-visits ${BUTLER_DIR} lsst.obs.subaru.HyperSuprimeCam \
  --where "instrument='HSC' AND day_obs=YYYYMMDD"
```

To remove a bad ingest (careful, this deletes data from the butler):

[The process of ingesting raw data will have put symbolic links to the files in subdirectories of ${BUTLER}/HSC/raw/all where 'HSC/raw/all' is the collection of raw observations]

```bash
butler prune-datasets ${BUTLER_DIR} HSC/raw/all --purge HSC/raw/all \
  --where "instrument='HSC' AND day_obs=YYYYMMDD" --find-all
```

**Always skip detector 9** in later queries (readout suspended since 2018). For 2025+ data, also skip detector 21 in processing scripts.

---

## 5. Reference catalogs

Use the shared CANFAR catalogs under ${REFCATS} [defined above]. Do **not** download or rebuild PS1/Gaia locally.

The calibrated data are located in these directories:

```text
${REFCATS}/ps1_pv3_3pi_20170110/
${REFCATS}/gaia_dr3_20230707/
```

### 5.1 Register dataset types

```bash
butler register-dataset-type ${BUTLER_DIR} ps1_pv3_3pi_20170110 SimpleCatalog htm7
butler register-dataset-type ${BUTLER_DIR} gaia_dr3_20230707 SimpleCatalog htm7
```

### 5.2 Build ingest lookup tables (once)

[the needed .ecsv files are already in ${REFCATS}.  The process to reproduce them is given here, in case you want to use a different set of reference catalogs.]

```python
"""Build .ecsv lookup tables for butler ingest-files from HTM7 refcat shards."""
import os
import glob
import astropy.table

REFCATS = os.environ["REFCATS"]

refcats = [
    f"{REFCATS}/ps1_pv3_3pi_20170110",
    f"{REFCATS}/gaia_dr3_20230707",
]
out_dir = REFCATS

for refcat_dir in refcats:
    out_file = f"{out_dir}/{os.path.basename(refcat_dir)}.ecsv"
    table = astropy.table.Table(names=("filename", "htm7"), dtype=("str", "int"))
    files = glob.glob(f"{refcat_dir}/[0-9]*.fits")
    for i, path in enumerate(files):
        print(f"{i}/{len(files)} ({100 * i / len(files):0.1f}%)", end="\r")
        file_index = int(os.path.basename(os.path.splitext(path)[0]))
        table.add_row((path, file_index))
    table.write(out_file, overwrite=True)
    print(f"\nWrote {out_file}")
```

### 5.3 Ingest and chain

```bash

butler ingest-files -t direct ${BUTLER_DIR} ps1_pv3_3pi_20170110 refcats/gen2 \
  ${REFCATS}/ps1_pv3_3pi_20170110.ecsv

butler ingest-files -t direct ${BUTLER_DIR} gaia_dr3_20230707 refcats/gen2 \
  ${REFCATS}/gaia_dr3_20230707.ecsv

butler collection-chain ${BUTLER_DIR} --mode extend refcats refcats/gen2
```

Verify:

```bash
butler query-datasets --collections refcats ${BUTLER_DIR}
```

---

## 6. Bias and flat calibrations

Calibrations are typically valid on ~month timescales. Group nights into observing seasons when you **certify** (validity dates), not by putting dated children on every later `-i` chain.

**Collection layout**

| Collection | Role |
|------------|------|
| `HSC/cp/START-END` | **Calibration products (cp)** build area: bias, flat, and later dark/fringe masters for one validity window. Both `cpBias` and `cpFlat` write here. |
| `HSC/calib` | Certified products ISR searches: curated instrument recipes plus certified bias/flat (selected by exposure date). |

`START-END` is a human label for that build window (often `YYYYMMDD-YYYYMMDD`). Use it in `-o` and as the certify **source**. Do **not** put `HSC/calib/START-END` on input chains — certify into plain `HSC/calib` and let `--begin-date` / `--end-date` choose the right master.

### Why `-i` collections matter

Butler does not magically know which products a pipeline needs. `-i` is a **search path**: a comma-separated list of collections the quantum graph builder may pull inputs from. Put every collection that supplies a required dataset type on that list; omit collections that would shadow the product you intend to use.

### 6.1 Bias

`cpBias.yaml` does two things: run ISR on each raw bias (`cpBiasIsr`), then combine those ISR'd frames into a master bias (`cpBiasCombine`). Even though you are *building* the bias, ISR still needs instrument metadata from curated calibrations.

```bash
pipetask run --register-dataset-types \
  -b ${BUTLER_DIR} \
  -i HSC/raw/all,HSC/calib \
  -o HSC/cp/START-END \
  -p ${CP_PIPE_DIR}/pipelines/HSC/cpBias.yaml \
  -d "instrument='HSC' AND exposure.observation_type='bias' AND NOT detector=9 AND NOT ( detector=21 AND day_obs > 20250425) AND NOT detector > 103 AND NOT　(detector=44 AND day_obs> 20261006) AND day_obs >= START AND day_obs <= END" \
  -c cpBiasIsr:doVignette=False \
  -j 32
```

| Input collection | Why it is on the chain |
|------------------|------------------------|
| `HSC/raw/all` | Raw bias exposures to ISR and combine. Selected by the `-d` query (`observation_type='bias'`). |
| `HSC/calib` | Curated instrument products from §3.2 (`camera`, `defects`, `bfKernel`, `transmission_*`, …). `cpBiasIsr` applies these during ISR of each bias frame. |

Certify with ISO date bounds (hyphens required). Certify *from* `HSC/cp/START-END` *into* `HSC/calib`. Science processing searches `HSC/calib` only; the dates below define which exposures get this bias.

```bash
butler certify-calibrations ${BUTLER_DIR} \
  HSC/cp/START-END \
  HSC/calib \
  bias \
  --begin-date YYYY-MM-DD --end-date YYYY-MM-DD \
  --search-all-inputs
```

### 6.2 Flat

Flats need the newly certified bias for the same window (`doBias=True`), plus the same curated instrument products. Both come from `HSC/calib` after §6.1 certify — there is no separate `HSC/calib/START-END` input.

```bash
pipetask run --register-dataset-types \
  -b ${BUTLER_DIR} \
  -i HSC/raw/all,HSC/calib \
  -o HSC/cp/START-END \
  -p ${CP_PIPE_DIR}/pipelines/HSC/cpFlat.yaml \
  -d "instrument='HSC' AND exposure.observation_type='domeflat' AND NOT detector=9 AND day_obs >= START AND day_obs <= END" \
  -c cpFlatIsr:doBias=True \
  -c cpFlatIsr:doDark=False \
  -j 32
```

| Input collection | Why it is on the chain |
|------------------|------------------------|
| `HSC/raw/all` | Raw dome flats to ISR and combine. |
| `HSC/calib` | Curated instrument products (defects, camera, ...) as well as the `bias` from the previous step for use in `cpFlatIsr`. |

```bash
butler certify-calibrations ${BUTLER_DIR} \
  HSC/cp/START-END \
  HSC/calib \
  flat \
  --begin-date YYYY-MM-DD --end-date YYYY-MM-DD \
  --search-all-inputs
```

After both certify steps, `HSC/calib` holds curated recipes plus bias **and** flat masters for that date range. Science ISR needs only `HSC/calib` on `-i` (plus raws/refcats); it resolves the correct master by exposure date.

**QA gate:** run `cpCore` / bias-flat verification and visually spot-check a few detectors (see [`QA_Checkpoints.md`](QA_Checkpoints.md)).

Legacy qgraph helpers: `scripts/create_dated_full_bias_qgraphs.sh`, `scripts/create_full_flats_qgraphs.sh`, `scripts/calibrate.sh`.

---

## 7. Synthetic SSO catalogs (`sso_injection` / SD-MOC)

SSO catalog generation is **in-pipeline**. There is no pre-built `fakes/{day_obs}` HTM catalog and no orbit logic in `source_injection`.

### Coverage model (SD-MOC)

**SD-MOC** = heliocentric HEALPix × distance shells (Space–Distance MOC), analogous to IVOA [MOC](https://www.ivoa.net/documents/MOC/) / [ST-MOC](https://www.ivoa.net/documents/stmoc/index.html) but with **distance** instead of time:

1. At model epoch `T0` (`population.model_epoch_mjd`), each synthetic object is owned by one SD-MOC cell (HEALPix id + distance bin). Distance shells are spaced uniformly in `r^2` between `distance_inner_au` and `distance_outer_au` so injections are weighted uniformly with sky rate (rate ~ `r**(-1/2)`), not uniform in `r`. Seeds are deterministic per cell.
2. For a visit at epoch `T`, take detector FOV ICRS directions, attach observer–object distances spanning the shells, and transform with Astropy `SkyCoord` into heliocentric ecliptic (observer from `visitInfo` observatory, else geocenter). Map to geometric SD-MOC cells, then **expand** by circular-orbit motion \(n\Delta t\) plus e/i fuzz.
3. Regenerate only those cells, convert state → Keplerian elements, propagate to `visitInfo`, keep in-detector hits, emit a plain **Trail** (or Star) catalog.

Circular-orbit prediction selects cells; injected orbits still carry `e`/`i` and are fully propagated.

### Tasks in `NewHorizons.yaml`

| Task | Package | Role |
|------|---------|------|
| `generateSsoInjectionCatalog` | `sso_injection` (in `lsst_deep_mop`) | SD-MOC sample → `sso_injection_catalog` |
| `inject_visit` (`InjectSsoVisitTask`) | `sso_injection` (in `lsst_deep_mop`) | GalSim inject via stock `VisitInjectTask` |

### YAML knobs (`population.*`)

Edit under `generateSsoInjectionCatalog` in [`pipelines/NewHorizons.yaml`](../pipelines/NewHorizons.yaml), or pass `-c`:

```bash
-c generateSsoInjectionCatalog:population.density=5000
-c generateSsoInjectionCatalog:population.master_seed=20240611
-c generateSsoInjectionCatalog:population.model_epoch_mjd=60500.0
-c generateSsoInjectionCatalog:population.healpix_order=8
-c generateSsoInjectionCatalog:population.distance_inner_au=30
-c generateSsoInjectionCatalog:population.distance_outer_au=50
-c generateSsoInjectionCatalog:population.n_distance_bins=4
-c generateSsoInjectionCatalog:population.eccentricity_fuzz=0.2
-c generateSsoInjectionCatalog:population.inclination_fuzz_deg=5.0
-c generateSsoInjectionCatalog:population.mag_limits=[22.0,27.0]
```

TNO / NH: modest motion expansion and fuzz. Faster movers use the same algorithm with larger \(n\Delta t\) at small `r`.

**QA gate:** after `#single_visit`, query `sso_injection_catalog` and `injected_calexp_catalog` for a sample detector; check Trail columns (`ra`, `dec`, `mag`, `trail_length`, `beta`) and non-empty inject masks where expected (see QA doc).

Full SSO usage, outputs, diagnostics, and example orbit-file recipes: [`SSO_Injection.md`](SSO_Injection.md).

---

## 8. Single-visit processing (ISR + calibrate + generate + inject)

Pipeline subset: `NewHorizons.yaml#single_visit`

```bash
pipetask run --register-dataset-types \
  -b ${BUTLER_DIR} \
  -i HSC/raw/all,refcats,HSC/calib \
  -o u/NH/processCCD/${day_obs} \
  -p ${PIPE_DIR}/NewHorizons.yaml#single_visit \
  -d "instrument='HSC' AND visit.observation_reason='science' AND detector.purpose='SCIENCE' AND NOT detector=9 AND day_obs=${day_obs}" \
  -c isr:doDark=False \
  -c calibrateImage:astrometry.maxIter=7 \
  -c calibrateImage:astrometry.maxMeanDistanceArcsec=0.01 \
  -j 32
```

| Input collection | Why it is on the chain |
|------------------|------------------------|
| `HSC/raw/all` | Science raws to process (filtered by `-d`). |
| `refcats` | PS1 / Gaia HTM shards for astrometric and photometric calibration in `calibrateImage`. |
| `HSC/calib` | Curated instrument products **and** certified bias/flat masters. ISR picks the masters whose certify timespan covers the exposure date — do not add `HSC/calib/START-END` here. |

No `fakes/{day_obs}` collection is required: catalogs are produced by `generateSsoInjectionCatalog` into the output run.

Configuration knobs live under `CONFIGURATION POINT` comments in [`pipelines/NewHorizons.yaml`](../pipelines/NewHorizons.yaml). Prefer editing those (or passing `-c`) rather than forking the YAML.

Products of interest: `calexp`, `sso_injection_catalog`, `injected_calexp`, `injected_calexp_catalog`.

**QA gate:** `visitQualityCore` / `calexpSummary` on a sample of detectors (see QA doc). Review failed quanta before merging qgraphs into the Butler. Spot-check Trail QA (§7).

Legacy helper: `scripts/create_processCCD.sh` (may still mention `fakes/` — prefer the command above).

---

## 9. Skymap and warps

### 9.1 Yearly skymap

Prefer one skymap per year covering all nights (empty warp quanta for non-overlapping patches are expected):

```bash
# Legacy helper; pass year and one exposure ID per night
scripts/make_big_skymap.sh YYYY exp1 exp2 ... expN
```

Skymap name convention in recent runs: `big_YYYY` (e.g. `big_2025`).

### 9.2 Visit summaries

Consolidate visit summaries for injected (or non-injected) calexps as required by warp inputs. Legacy: `scripts/create_visits.sh`.

### 9.3 Warp

Pipeline subset: `NewHorizons.yaml#warp`

```bash
pipetask run --register-dataset-types \
  -b ${BUTLER_DIR} \
  -i u/NH/processCCD/${day_obs},skymaps \
  -o u/NH/warps/${campaign} \
  -p ${PIPE_DIR}/NewHorizons.yaml#warp \
  -d "instrument='HSC' AND skymap='big_${year}' AND ..." \
  -j 32
```

| Input collection | Why it is on the chain |
|------------------|------------------------|
| `u/NH/processCCD/${day_obs}` | Injected calexps (and visit summaries if already there) to warp. |
| `skymaps` | Discrete sky map defining tracts/patches (`big_YYYY`). Without it, warps have no target geometry. |

Products: `injected_directWarp`, `injected_psfMatchedWarp` (names match the connections in the YAML).

Legacy helpers: `scripts/create_makeWarp_qgraphs.sh`, `scripts/create_newhorizons.sh`.

---

## 10. Multi-night template building

Moving Solar System objects leave trails in single-night deep stacks. Templates for New Horizons are built from **multiple nights** so that a moving source does not land in the same pixels across the stack and is suppressed in the mean coadd.

Visit selection uses `lsst_deep_mop.selectImages.MovingTargetSelectVisitsTask`, which:

- Splits candidate visits into `nGroups` time groups across the available timespan.
- Within each group, keeps a seeing quantile (`qMin`–`qMax`) with at least `nVisitsMin` visits.

**CONFIGURATION POINT** defaults in `NewHorizons.yaml`:

| Parameter   | Typical NH value | Meaning                                      |
|-------------|------------------|----------------------------------------------|
| `qMax`      | 0.5              | Upper seeing quantile (with `qMin=0`)        |
| `nGroups`   | 5                | Time groups across the multi-night baseline  |
| `nVisitsMin`| 10               | Minimum visits per group                     |

Upstream / related package: [lsst_deep_mop](https://github.com/ijiraq/lsst_deep_mop).

Pipeline subset: `NewHorizons.yaml#template`

```bash
pipetask run --register-dataset-types \
  -b ${BUTLER_DIR} \
  -i u/NH/warps/${campaign},skymaps \
  -o u/NH/templates/${campaign} \
  -p ${PIPE_DIR}/NewHorizons.yaml#template \
  -d "instrument='HSC' AND skymap='big_${year}' AND tract=0 AND patch=..." \
  -j 32
```

| Input collection | Why it is on the chain |
|------------------|------------------------|
| `u/NH/warps/${campaign}` | Direct / PSF-matched warps (and visit summaries) spanning **multiple nights**. Selection + coadd read these. |
| `skymaps` | Same sky map used for warping; patch geometry for selection and assemble. |

Products: selected visit lists, `injected_goodSeeingCoadd`, `injected_goodSeeingCoadd_nImage`.

**QA gate:** inspect `nImage` coverage, artifact masks, and that templates span multiple nights (no single-night trail dominance). See QA doc.

Legacy helpers: `scripts/create_selectGoodSeeinVisits_qgraphs.sh`, `scripts/create_templateGen_qgraphs.sh`.

---

## 11. Difference imaging

Pipeline subset: `NewHorizons.yaml#difference`

```bash
pipetask run --register-dataset-types \
  -b ${BUTLER_DIR} \
  -i u/NH/processCCD/${day_obs},u/NH/templates/${campaign},skymaps \
  -o u/NH/diffs/${day_obs} \
  -p ${PIPE_DIR}/NewHorizons.yaml#difference \
  -d "instrument='HSC' AND skymap='big_${year}' AND day_obs=${day_obs} AND ..." \
  -j 32
```

| Input collection | Why it is on the chain |
|------------------|------------------------|
| `u/NH/processCCD/${day_obs}` | Science / injected calexps to difference (`injected_calexp`). |
| `u/NH/templates/${campaign}` | Multi-night goodSeeing coadd used by `getTemplate`. |
| `skymaps` | Patch/tract geometry for template cutouts. |

Or run the combined science path after prerequisites exist:

```bash
# subsets: single_visit | warp | template | difference | new_horizons_end_to_end
pipetask build -p ${PIPE_DIR}/NewHorizons.yaml --show pipeline
```

Primary product: `injected_goodSeeingDiff_differenceTempExp` (plus matched template / kernel datasets).

**QA gate:** spot-check difference images; measure recovery of injected sources (see QA doc).

Legacy helpers: `scripts/create_getTemplate_qgraphs.sh`, `scripts/create_subtractImages_qgraphs.sh`, `scripts/create_image_diffs_2025.sh`.

---

## 12. QA checkpoints (summary)

Full checklist: [`docs/QA_Checkpoints.md`](QA_Checkpoints.md).

| Stage              | Minimum QA                                      |
|--------------------|-------------------------------------------------|
| Bias / flat        | `cpCore` / verify pipelines; visual spot-check  |
| Refcats            | `butler query-datasets --collections refcats`   |
| Injection catalog  | `sso_injection_catalog` + Trail columns present |
| Single-visit       | `visitQualityCore` / calexp summary             |
| Warps / skymap     | Non-empty warps for expected patches            |
| Templates          | Multi-night `nImage`; no trail-dominated coadd  |
| Diffim             | Sample diffs; fake recovery stats               |

Do not merge qgraphs into the Butler until logs show successful completion (see §13).

---

## 13. Qgraph / CANFAR runner lifecycle

For large campaigns, build quantum graphs and process them headlessly:

1. A create script writes a qgraph into `${BUTLER_DIR}/qgraphs/hold/`.
2. Move approved graphs to `queue/`.
3. `scripts/launch_qrunners.sh START END` starts runners that pull from `queue/` → `processing/` → `processed/`.
4. Inspect logs under `qgraphs/logs/` (`tail -f` while running). Look for completion markers such as `and 0 remain`.
5. Move good graphs to `examined/`, then run `scripts/merge.sh` → `merged/` (or `failed/`).

Memory guidance used historically on CANFAR:

| Stage        | RAM per runner |
|--------------|----------------|
| Bias / flat  | ~2 GB          |
| processCCD   | ~4 GB          |
| warps / NH   | ~16 GB         |

Notes:

- Headless jobs may be preempted; stuck graphs in `processing/` need cleanup and rebuild.
- OOM can leave a graph in `processed/` without real success — always read the log.
- Prefer rebuilding remaining failed quanta with `--skip-existing-in <OUTPUT_COLLECTION>` rather than redoing everything.

---

## 14. Troubleshooting

| Issue | Guidance |
|-------|----------|
| Detector 9 failures | Always exclude with `NOT detector=9`. |
| Detector 21 (2025+) | Exclude in processing queries/scripts. |
| Database lock | Do not use `-j` across many detectors of one visit incorrectly; qrunners should be one quantum at a time. |
| Recertify calibs | Cannot recertify the same date range into `HSC/calib` again; use a new destination collection or a non-overlapping timespan. Rebuild under a new `HSC/cp/START-END` if needed. Use `--search-all-inputs` after partial rebuilds. |
| Partial rerun | Add `--skip-existing-in <output_collection>`. |
| Duplicate datasets / skymap failures | Avoid merging half-finished qgraphs; search logs missing `and 0 remain`. |
| Package order | `lsst_deep_mop` then `obs_subaru`. |
| Disk full | Symptoms include inability to save files; free space before continuing. |

---

## 15. Package and script map

| Path | Role |
|------|------|
| [`pipelines/NewHorizons.yaml`](../pipelines/NewHorizons.yaml) | Canonical NH pipeline (use this) |
| [`DRP-Prod+injection_upd_JJK.yaml`](../DRP-Prod+injection_upd_JJK.yaml) | Full DRP+injection reference |
| [`packages/obs_subaru`](../packages/obs_subaru) | HSC / NH instrument |
| This repo (`lsst_deep_mop`) | SSO catalogs + multi-night visit selection |
| Stock `source_injection` | GalSim Trail/Star inject (no SSO) |
| [`configs/`](../configs) | Butler seed template, warp configs |
| [`scripts/`](../scripts) | Legacy date-hardcoded qgraph drivers (cleanup planned) |
| [`docs/archive/`](archive/) | Historical student cookbook |

### Follow-ups (not in this documentation pass)

- Parameterize qgraph scripts (replace date/collection hardcoding).
- Resolve git pre-commit issues in local `obs_subaru` / `lsst_deep_mop` checkouts.
- Retire or archive the standalone `sso_injection` git remote now that code lives here.

---

## Useful links

- [Butler CLI](https://pipelines.lsst.io/modules/lsst.daf.butler/scripts/butler.html)
- [pipetask](https://pipelines.lsst.io/modules/lsst.ctrl.mpexec/pipetask.html)
- [LSST Science Pipelines getting started](https://pipelines.lsst.io/getting-started/index.html)
