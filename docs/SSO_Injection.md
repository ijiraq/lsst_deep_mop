# SSO injection (`sso_injection`)

How synthetic Solar System Object (SSO) catalogs are built and consumed inside
`lsst_deep_mop`, what Butler datasets they produce, and how to make diagnostic
plots or standalone example orbit tables.

This package area also provides multi-night **image / visit selection** via
`lsst_deep_mop.selectImages.MovingTargetSelectVisitsTask` (see the runbook
template section). SSO catalog generation is the focus of this page.

---

## Role in the pipeline

```text
calexp
  → GenerateSsoInjectionCatalogTask   (sso_injection)
       writes sso_injection_catalog
  → InjectSsoVisitTask                (sso_injection wrapper around stock GalSim)
       reads sso_injection_catalog
       writes injected_calexp + injected_calexp_catalog
```

Stock LSST `source_injection` does **not** know about orbits. All SD-MOC
sampling and Keplerian propagation live in `sso_injection`; injection only
sees plain Trail/Star columns (`ra`, `dec`, `mag`, `trail_length`, `beta`, …).

Wiring is in [`pipelines/NewHorizons.yaml`](../pipelines/NewHorizons.yaml)
(`#single_visit`). A smaller stub lives in
[`pipelines/generateSsoInjection.yaml`](../pipelines/generateSsoInjection.yaml).

---

## Coverage model (SD-MOC)

**SD-MOC** = heliocentric HEALPix × distance shells (Space–Distance MOC),
analogous to IVOA MOC / ST-MOC with **distance** instead of time.

1. At model epoch `T0` (`population.model_epoch_mjd`), each synthetic object is
   owned by one cell (HEALPix id + distance bin). Distance shells are spaced
   **uniformly in \(r^2\)** between `distance_inner_au` and `distance_outer_au`
   so the population is weighted uniformly with sky rate (rate \(\sim r^{-1/2}\)).
2. For a visit, FOV ICRS directions are given observer–object distances, then
   transformed with Astropy `SkyCoord` into heliocentric ecliptic (observatory
   from `visitInfo`, else geocenter). Matching T0 cells are expanded by
   circular-orbit motion \(n\Delta t\) plus eccentricity/inclination fuzz.
3. Cells are sampled on the fly (no monolithic orbit file), propagated to the
   visit epoch, clipped to the detector, and emitted as a Trail catalog.

---

## Pipeline usage

```bash
setup lsst_distrib
setup -r /path/to/lsst_deep_mop -t ${USER}
setup -r /path/to/obs_subaru -t ${USER}

pipetask run --register-dataset-types \
  -b ${BUTLER_DIR} \
  -i HSC/raw/all,refcats,HSC/calib \
  -o u/NH/processCCD/${day_obs} \
  -p ${PIPE_DIR}/NewHorizons.yaml#single_visit \
  -d "instrument='HSC' AND visit.observation_reason='science' AND detector.purpose='SCIENCE' AND NOT detector=9 AND day_obs=${day_obs}" \
  -j 32
```

No `fakes/{day_obs}` collection is required.

### Useful `-c` overrides

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

---

## Outputs

### Butler datasets (`#single_visit`)

| Dataset | Dimensions | Meaning |
|---------|------------|---------|
| `sso_injection_catalog` | instrument, visit, detector | Per-detector Trail (or Star) table for GalSim |
| `injected_calexp` | instrument, visit, detector | Calexp with synthetic sources drawn |
| `injected_calexp_catalog` | instrument, visit, detector | Catalog of successfully injected sources + flags |

### Columns in `sso_injection_catalog` (Trail)

Columns carry Astropy units (preserved by the `ArrowAstropy` butler storage class).

| Column | Unit / notes |
|--------|----------------|
| `injection_id` | Stable id within the cell seed |
| `population` | Orbit-model key from `config.populations` (e.g. `tno`) |
| `ra`, `dec` | ICRS at visit epoch (`deg`) |
| `dra`, `ddec` | On-sky rate components (`arcsec / h`); PA East of North |
| `rate` | Total on-sky rate (`arcsec / h`) |
| `source_type` | `Trail` (default) or `Star` |
| `mag` | Apparent magnitude (Bowell H-G) |
| `trail_length` | Physical trail over the exposure in pixels (may be sub-pixel) |
| `beta` | Trail position angle (`deg`) |
| `a` | Semi-major axis (`AU`) |
| `e` | Eccentricity (dimensionless) |
| `inc`, `Omega`, `omega`, `M` | Keplerian angles (`rad`) at model epoch |
| `H` | Absolute magnitude |
| `r` | Heliocentric distance at visit (`AU`) |
| `delta` | Observer–object distance at visit (`AU`) |
| `healpix`, `dist_bin` | SD-MOC ownership cell |

Table metadata (parquet / Arrow) includes `visit_mjd`, `visit_isot`,
`exposure_time_s`, `model_epoch_mjd` (element epoch), and a `populations`
list with per-population `master_seed`, `mixed_seed`, density, and shell grid.

Inspect after a run:

```bash
butler query-datasets ${BUTLER_DIR} sso_injection_catalog \
  --collections u/NH/processCCD/${day_obs} --limit 20
```

---

## Diagnostic plots

Example figure (Arrokoth-centered cell on 2022-06-20):  
[`docs/arrokoth_injection_diagnostics.png`](arrokoth_injection_diagnostics.png)

The figure shows:

- Fiducial-night sky positions (blue) vs the **same** orbits +24 h later (red)
- CDFs of \(a\), \(e\), \(i\), \(\Omega\), \(\omega\), \(M\) with Arrokoth reference lines

### Regenerate

Needs network access to JPL Horizons (`astroquery`), plus `healpy` and
`matplotlib`.

```bash
setup -r /path/to/lsst_deep_mop -t ${USER}

python bin/plot_injection_diagnostics.py \
  --epoch 2022-06-20 \
  -o docs/arrokoth_injection_diagnostics.png \
  --density 20000 \
  --max-plot 1500
```

Or from Python:

```python
from sso_injection.diagnostics import run_arrokoth_injection_diagnostics

sky, info, path = run_arrokoth_injection_diagnostics(
    "2022-06-20",
    output_path="docs/arrokoth_injection_diagnostics.png",
)
```

Unit tests (Horizons test skips cleanly without network/astroquery):

```bash
pytest tests/test_kepler_horizons.py tests/test_sdmoc.py -v
```

---

## Example orbit files (offline / notebooks)

You can write Keplerian orbit tables or sky Trail tables without running
`pipetask`. These are useful for QA, notebooks, or feeding a custom ingest.

CLI helper:

```bash
# Fixed cell
python bin/write_example_orbits.py -o /tmp/sso_examples --density 3000

# Arrokoth-centered cell (needs Horizons / network)
python bin/write_example_orbits.py --arrokoth -o /tmp/sso_examples
```

Produces `example_orbits.ecsv`, `example_orbits.parquet`, and `example_sky.ecsv`.

### 1. Sample orbits in one SD-MOC cell

```python
from astropy.table import Table
from sso_injection.config import OrbitPopulationConfig
from sso_injection.sdmoc import SDMocIndex, SDMocCell
from sso_injection.sample import sample_sdmoc_cell

config = OrbitPopulationConfig()
config.density = 5000
config.healpix_order = 6
config.distance_inner_au = 40.0
config.distance_outer_au = 46.0
config.n_distance_bins = 1
config.model_epoch_mjd = 59750.0  # ~2022-06-20

index = SDMocIndex(config)
cell = SDMocCell(ipix=30472, dist_bin=0)  # example; use your own cell id
orbits = sample_sdmoc_cell(cell, index, config=config)

orbits.write("example_orbits.ecsv", format="ascii.ecsv", overwrite=True)
orbits.write("example_orbits.parquet", format="parquet", overwrite=True)
```

Orbit table columns: `injection_id`, `a`, `e`, `inc`, `Omega`, `omega`, `M`,
`H`, `healpix`, `dist_bin` (angles in radians). Meta includes `day_obs` /
`model_epoch_mjd`.

### 2. Propagate to sky (ICRS + rates)

```python
from astropy.time import Time
from sso_injection.diagnostics import propagate_orbits_to_sky

sky = propagate_orbits_to_sky(orbits, Time("2022-06-20"))
sky.write("example_sky_trails.ecsv", format="ascii.ecsv", overwrite=True)
```

Sky columns include `ra`, `dec`, `ra_next`, `dec_next` (+24 h), `mag`, `rate`
(arcsec/hour), `angle`, `r`, `delta`, and elements in degrees.

### 3. Arrokoth-centered example (Horizons + cell sample)

```python
from sso_injection.diagnostics import run_arrokoth_injection_diagnostics

sky, info, _ = run_arrokoth_injection_diagnostics(
    "2022-06-20",
    output_path="docs/arrokoth_injection_diagnostics.png",
    max_plot_sources=2000,
)
sky.write("arrokoth_cell_sky.ecsv", format="ascii.ecsv", overwrite=True)
print(info["ra_deg"], info["dec_deg"], info["r_au"])
```

---

## Related docs

- [NewHorizons_Pipeline_Runbook.md](NewHorizons_Pipeline_Runbook.md) — full
  ISR → inject → warp → template → diff path
- [QA_Checkpoints.md](QA_Checkpoints.md) — post-injection QA gates
