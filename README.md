# New Horizons LSST Processing

HSC / New Horizons processing on the LSST Science Pipelines (`latest_daily` / v30): ISR, synthetic SSO injection (SD-MOC), warps to sky patches, **multi-night** templates, and difference images.

## Start here

| Document | Purpose |
|----------|---------|
| [docs/NewHorizons_Pipeline_Runbook.md](docs/NewHorizons_Pipeline_Runbook.md) | Canonical setup and run instructions (Postgres → diffs) |
| [docs/QA_Checkpoints.md](docs/QA_Checkpoints.md) | QA gates after each stage |
| [pipelines/NewHorizons.yaml](pipelines/NewHorizons.yaml) | Simplified pipeline with clear configuration points |

Science flow:

```text
raw → ingest → HSC/cp (build bias/flat) → certify into HSC/calib
    → ISR + calibrate → generate SSO Trail catalog → inject → warp
    → multi-night template select/coadd → difference images
```

Calibration collections: build under `HSC/cp/START-END`; certify into `HSC/calib` (no `HSC/calib/START-END` on later `-i` chains). Reference catalogs: `/arc/projects/LSST/refcats` (runbook §5).

SSO catalogs come from `sso_injection` (heliocentric SD-MOC sampling) inside `#single_visit`; stock `source_injection` only draws Trails/Stars. No pre-built `fakes/{day_obs}` orbit table.

## Layout

```text
NewHorizons/
  README.md
  docs/
    NewHorizons_Pipeline_Runbook.md
    QA_Checkpoints.md
    archive/                         # historical student cookbook
  pipelines/
    NewHorizons.yaml                 # use this
  configs/
    butler_seed.template.yaml        # copy → butler_seed.yaml (secrets local only)
    makeDirectWarpConfig.py
  packages/
    obs_subaru/                      # HSC + NH filters
    sso_injection/                   # SD-MOC SSO catalogs + InjectSsoVisitTask
    nh/                              # MovingTargetSelectVisitsTask
  scripts/                           # legacy CANFAR qgraph helpers (cleanup planned)
  DRP-Prod+injection_upd_JJK.yaml    # full DRP+injection reference only
```

## Packages

```bash
setup lsst_distrib
setup -r /path/to/packages/sso_injection -t ${USER}
setup -r /path/to/packages/obs_subaru -t ${USER}
setup -r /path/to/packages/nh -t ${USER}
```

`sso_injection` depends on stock `source_injection` from the distribution.

Template visit selection also relates to [ijiraq/lsst_deep_mop](https://github.com/ijiraq/lsst_deep_mop).

## Pipeline subsets (`NewHorizons.yaml`)

| Subset | Stage |
|--------|--------|
| `single_visit` | ISR, calibrate, generate SSO catalog, inject |
| `visit_summary` | Injected visit summaries |
| `warp` | Direct + PSF-matched warps |
| `template` | Multi-night select + goodSeeing coadd |
| `difference` | getTemplate + subtract |
| `new_horizons_end_to_end` | Full path (prefer staged runs + QA) |

## Known follow-ups

- Parameterize date-/collection-hardcoded scripts under `scripts/`.
- Fix git pre-commit issues in local package checkouts (uncommitted working changes may exist).
- Deeper packaging integration with `lsst_deep_mop`.

Historical notes: [docs/archive/LSST_Pipeline_v29_in_ARCADES.md](docs/archive/LSST_Pipeline_v29_in_ARCADES.md).
