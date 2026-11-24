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
from .trails import _empty_injection_table, orbits_to_trail_catalog


def _mix_population_seed(master_seed: int, population_name: str) -> int:
    """Derive a per-population master seed so injection_ids cannot collide."""
    digest = hashlib.blake2b(
        f"{int(master_seed)}:{population_name}".encode(),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "little") & 0x7FFFFFFF


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

        for name, base_config in populations:
            config = base_config.copy()
            config.master_seed = _mix_population_seed(base_config.master_seed, name)

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
            self.log.info(
                "Population %s: %d injectable sources (%s)",
                name,
                len(catalog),
                config.source_type,
            )
            if len(catalog) > 0:
                source_types.add(str(config.source_type))
                tables.append(catalog)

        if len(source_types) > 1:
            raise ValueError(
                "All populations must share the same source_type when concatenating; "
                f"got {sorted(source_types)}"
            )

        if not tables:
            catalog = _empty_injection_table(populations[0][1].source_type)
            self.log.info(
                "Wrote 0 injectable sources across %d population(s)",
                len(populations),
            )
            return Struct(output_catalog=catalog)

        catalog = vstack(tables, metadata_conflicts="silent")
        self.log.info(
            "Wrote %d injectable sources from %d population(s) (%s)",
            len(catalog),
            len(populations),
            next(iter(source_types)),
        )
        return Struct(output_catalog=catalog)
