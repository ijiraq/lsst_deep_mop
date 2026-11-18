# lsst_deep_mop

HSC / New Horizons processing on the LSST Science Pipelines (`latest_daily` / v30).

**One EUPS / Python product** that provides both:

| Python package | Role |
|----------------|------|
| `lsst_deep_mop` | Multi-night **image / visit selection** (`MovingTargetSelectVisitsTask`) for deep templates |
| `sso_injection` | **SSO injection catalog builder** (SD-MOC sampling → Trail tables) + `InjectSsoVisitTask` |

Downstream GalSim drawing uses stock LSST `source_injection` (no orbit logic there).

## Start here

| Document | Purpose |
|----------|---------|
| [docs/NewHorizons_Pipeline_Runbook.md](docs/NewHorizons_Pipeline_Runbook.md) | Full setup and run instructions (Postgres → diffs) |
| [docs/SSO_Injection.md](docs/SSO_Injection.md) | SSO usage, Butler outputs, diagnostics, example orbit files |
| [docs/QA_Checkpoints.md](docs/QA_Checkpoints.md) | QA gates after each stage |
| [pipelines/NewHorizons.yaml](pipelines/NewHorizons.yaml) | Canonical pipeline (ISR → inject → warp → template → diff) |

Science flow:

```text
raw → ingest → HSC/cp (build bias/flat) → certify into HSC/calib
    → ISR + calibrate → generate SSO Trail catalog → inject → warp
    → multi-night template select/coadd → difference images
```

## Layout

```text
lsst_deep_mop/
  README.md
  docs/
    NewHorizons_Pipeline_Runbook.md
    SSO_Injection.md
    QA_Checkpoints.md
    arrokoth_injection_diagnostics.png   # example SSO diagnostic figure
  pipelines/
    NewHorizons.yaml
    generateSsoInjection.yaml
  python/
    lsst_deep_mop/     # MovingTargetSelectVisitsTask
    sso_injection/     # SD-MOC catalog generation + inject wrapper
  tests/
  bin/
    plot_injection_diagnostics.py
  configs/
  scripts/
```

## Setup

```bash
setup lsst_distrib
setup -r /path/to/lsst_deep_mop -t ${USER}
setup -r /path/to/obs_subaru -t ${USER}   # NH filters / instrument
```

## Pipeline subsets (`NewHorizons.yaml`)

| Subset | Stage |
|--------|--------|
| `single_visit` | ISR, calibrate, **generate SSO catalog**, inject |
| `visit_summary` | Injected visit summaries |
| `warp` | Direct + PSF-matched warps |
| `template` | Multi-night **visit selection** + goodSeeing coadd |
| `difference` | getTemplate + subtract |
| `new_horizons_end_to_end` | Full path (prefer staged runs + QA) |

Confirmed task classes in that YAML:

- `sso_injection.GenerateSsoInjectionCatalogTask` → `sso_injection_catalog`
- `sso_injection.InjectSsoVisitTask` → `injected_calexp` / `injected_calexp_catalog`
- `lsst_deep_mop.selectImages.MovingTargetSelectVisitsTask` → template visit selection

## SSO diagnostics & example orbits

See [docs/SSO_Injection.md](docs/SSO_Injection.md).

```bash
# Example diagnostic figure (fiducial vs +24h sky + element CDFs)
python bin/plot_injection_diagnostics.py -o docs/arrokoth_injection_diagnostics.png

# Example Keplerian + sky tables (no pipetask)
python bin/write_example_orbits.py -o /tmp/sso_examples

pytest tests/test_kepler_horizons.py tests/test_sdmoc.py -v
```

Historical notes: [docs/archive/LSST_Pipeline_v29_in_ARCADES.md](docs/archive/LSST_Pipeline_v29_in_ARCADES.md).
