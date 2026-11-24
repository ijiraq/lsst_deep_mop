# This file is part of sso_injection.
"""PipelineTask: SD-MOC sample → Trail injection catalog for one visit/detector."""

from __future__ import annotations

__all__ = [
    "GenerateSsoInjectionCatalogConnections",
    "GenerateSsoInjectionCatalogConfig",
    "GenerateSsoInjectionCatalogTask",
]

import hashlib

import numpy as np
from astropy.table import Table, vstack
from lsst.geom import Point2D
from lsst.pex.config import ConfigDictField, ConfigField
from lsst.pipe.base import PipelineTask, PipelineTaskConfig, PipelineTaskConnections, Struct
from lsst.pipe.base.connectionTypes import Input, Output

from .config import OrbitPopulationConfig
from .sample import sample_sdmoc_cells
from .sdmoc import SDMocIndex
from .trails import apply_catalog_units, _empty_injection_table, orbits_to_trail_catalog


def _mix_population_seed(master_seed: int, population_name: str) -> int:
    """Derive a per-population master seed so injection_ids cannot collide."""
    digest = hashlib.blake2b(
        f"{int(master_seed)}:{population_name}".encode(),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "little") & 0x7FFFFFFF


def _population_meta(name: str, base_config: OrbitPopulationConfig, mixed_seed: int) -> dict:
    """JSON-friendly per-population provenance for the written catalog."""
    edges = [float(x) for x in base_config.resolve_distance_edges()]
    return {
        "name": name,
        "master_seed": int(base_config.master_seed),
        "mixed_seed": int(mixed_seed),
        "model_epoch_mjd": float(base_config.model_epoch_mjd),
        "density": float(base_config.density),
        "healpix_order": int(base_config.healpix_order),
        "distance_inner_au": float(base_config.distance_inner_au),
        "distance_outer_au": float(base_config.distance_outer_au),
        "n_distance_bins": int(base_config.n_distance_bins),
        "distance_bin_edges_au": edges,
        "mag_limits": [float(x) for x in base_config.mag_limits],
        "h_limits": [float(x) for x in base_config.h_limits],
        "eccentricity_max": float(base_config.eccentricity_max),
        "inclination_max_deg": float(base_config.inclination_max_deg),
        "eccentricity_fuzz": float(base_config.eccentricity_fuzz),
        "inclination_fuzz_deg": float(base_config.inclination_fuzz_deg),
        "source_type": str(base_config.source_type),
        "trail_dt_hours": (
            None if base_config.trail_dt_hours is None else float(base_config.trail_dt_hours)
        ),
    }


def _catalog_meta(visitInfo, populations_meta: list[dict]) -> dict:
    """File-level metadata stored with the Arrow/parquet injection catalog."""
    obstime = visitInfo.date.toAstropy()
    epochs = sorted({float(p["model_epoch_mjd"]) for p in populations_meta})
    return {
        "visit_mjd": float(obstime.mjd),
        "visit_isot": str(obstime.isot),
        "exposure_time_s": float(visitInfo.getExposureTime() or 0.0),
        # Element epoch(s) at which SD-MOC ownership / sampling is defined.
        "model_epoch_mjd": epochs[0] if len(epochs) == 1 else epochs,
        "element_angle_unit": "rad",
        "rate_unit": "arcsec / h",
        "distance_unit": "AU",
        "populations": populations_meta,
    }


class GenerateSsoInjectionCatalogConnections(
    PipelineTaskConnections,
    dimensions=("instrument", "visit", "detector"),
):
    """Connections for per-detector SSO injection catalog generation."""

    input_exposure = Input(
        doc="Calibrated exposure providing WCS, bbox, and visitInfo.",
        name="calexp",
        storageClass="ExposureF",
        dimensions=("instrument", "visit", "detector"),
    )
    output_catalog = Output(
        doc="Synthetic SSO injection catalog (Trail/Star) for stock source_injection.",
        name="sso_injection_catalog",
        storageClass="ArrowAstropy",
        dimensions=("instrument", "visit", "detector"),
    )


class GenerateSsoInjectionCatalogConfig(
    PipelineTaskConfig,
    pipelineConnections=GenerateSsoInjectionCatalogConnections,
):
    """Config: one or more named orbit populations for a single output catalog."""

    population = ConfigField(
        dtype=OrbitPopulationConfig,
        doc="Fallback single population used when ``populations`` is empty.",
    )
    populations = ConfigDictField(
        keytype=str,
        itemtype=OrbitPopulationConfig,
        default={},
        doc="Named orbit populations to sample and concatenate into one catalog. "
        "When non-empty, ``population`` is ignored.",
    )


class GenerateSsoInjectionCatalogTask(PipelineTask):
    """
    Sample synthetic SSOs for this detector FOV an injection catalog.

    Each entry in ``config.populations`` (or the fallback ``config.population``)
    is sampled independently via SD-MOC, then concatenated. Inject tasks
    consume a ``sso_injection_catalog`` dataset.
    """

    ConfigClass = GenerateSsoInjectionCatalogConfig
    _DefaultName = "generateSsoInjectionCatalog"

    def _resolve_populations(self) -> list[tuple[str, OrbitPopulationConfig]]:
        named = dict(self.config.populations.items())
        if named:
            return list(named.items())
        return [("default", self.config.population)]

    def run(self, input_exposure):
        visitInfo = input_exposure.getInfo().getVisitInfo()
        wcs = input_exposure.getWcs()
        bbox = input_exposure.getBBox()

        # FOV corners in ICRS for SD-MOC query (shared across populations).
        corners = bbox.getCorners()
        ras = []
        decs = []
        for corner in corners:
            sp = wcs.pixelToSky(Point2D(corner))
            ras.append(sp.getRa().asDegrees())
            decs.append(sp.getDec().asDegrees())
        ras = np.asarray(ras + ras[:1], dtype=float)
        decs = np.asarray(decs + decs[:1], dtype=float)
        ras = np.concatenate([ras, 0.5 * (ras[:-1] + ras[1:])])
        decs = np.concatenate([decs, 0.5 * (decs[:-1] + decs[1:])])

        visit_mjd = visitInfo.date.toAstropy().mjd
        populations = self._resolve_populations()
        tables: list[Table] = []
        source_types: set[str] = set()
        populations_meta: list[dict] = []

        for name, base_config in populations:
            config = base_config.copy()
            config.master_seed = _mix_population_seed(base_config.master_seed, name)
            populations_meta.append(_population_meta(name, base_config, config.master_seed))

            index = SDMocIndex(config)
            cells = index.cells_for_visit(ras, decs, visitInfo=visitInfo)
            self.log.info(
                "Population %s: SD-MOC selected %d cells (order=%d, dens=%.1f/deg2) "
                "for visit MJD %.4f",
                name,
                len(cells),
                config.healpix_order,
                config.density,
                visit_mjd,
            )

            orbits = sample_sdmoc_cells(cells, index, config=config)
            self.log.info(
                "Population %s: sampled %d synthetic orbits before FOV clip",
                name,
                len(orbits),
            )

            catalog = orbits_to_trail_catalog(
                orbits,
                visitInfo,
                wcs,
                bbox,
                config,
            )
            if len(catalog) > 0:
                # Orbit-model key from config.populations (e.g. "tno", "centaur").
                catalog["population"] = np.full(len(catalog), str(name))
            self.log.info(
                "Population %s: %d injectable sources (%s)",
                name,
                len(catalog),
                config.source_type,
            )
            if len(catalog) > 0:
                source_types.add(str(config.source_type))
                tables.append(catalog)

        file_meta = _catalog_meta(visitInfo, populations_meta)

        if len(source_types) > 1:
            raise ValueError(
                "All populations must share the same source_type when concatenating; "
                f"got {sorted(source_types)}"
            )

        if not tables:
            catalog = _empty_injection_table(populations[0][1].source_type)
            catalog.meta.update(file_meta)
            self.log.info(
                "Wrote 0 injectable sources across %d population(s)",
                len(populations),
            )
            return Struct(output_catalog=catalog)

        catalog = vstack(tables, metadata_conflicts="silent")
        apply_catalog_units(catalog)
        catalog.meta.update(file_meta)
        self.log.info(
            "Wrote %d injectable sources from %d population(s) (%s)",
            len(catalog),
            len(populations),
            next(iter(source_types)),
        )
        return Struct(output_catalog=catalog)
