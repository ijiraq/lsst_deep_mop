# This file is part of sso_injection.
"""PipelineTask: SD-MOC sample → Trail injection catalog for one visit/detector."""

from __future__ import annotations

__all__ = [
    "GenerateSsoInjectionCatalogConnections",
    "GenerateSsoInjectionCatalogConfig",
    "GenerateSsoInjectionCatalogTask",
]

import numpy as np
from lsst.pex.config import ConfigField
from lsst.pipe.base import PipelineTask, PipelineTaskConfig, PipelineTaskConnections, Struct
from lsst.pipe.base.connectionTypes import Input, Output

from .config import OrbitPopulationConfig
from .sample import sample_sdmoc_cells
from .sdmoc import SDMocIndex
from .trails import orbits_to_trail_catalog


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
    """Config: population model is nested for clear YAML overrides."""

    population = ConfigField(
        dtype=OrbitPopulationConfig,
        doc="Synthetic SSO orbit population / SD-MOC model parameters.",
    )


class GenerateSsoInjectionCatalogTask(PipelineTask):
    """
    Sample synthetic SSOs for this detector FOV and emit a Trail catalog.

    Uses heliocentric SD-MOC cell ownership at ``population.model_epoch_mjd``,
    expands cells with circular-orbit motion + e/i fuzz, propagates to the
    exposure epoch, and writes a catalog consumable by stock VisitInjectTask.
    """

    ConfigClass = GenerateSsoInjectionCatalogConfig
    _DefaultName = "generateSsoInjectionCatalog"

    def run(self, input_exposure):
        config = self.config.population
        index = SDMocIndex(config)
        visitInfo = input_exposure.getInfo().getVisitInfo()
        wcs = input_exposure.getWcs()
        bbox = input_exposure.getBBox()

        # FOV corners in ICRS for SD-MOC query.
        corners = bbox.getCorners()
        ras = []
        decs = []
        for corner in corners:
            sp = wcs.pixelToSky(corner)
            ras.append(sp.getRa().asDegrees())
            decs.append(sp.getDec().asDegrees())
        # Densify edges slightly for healpix coverage.
        ras = np.asarray(ras + ras[:1], dtype=float)
        decs = np.asarray(decs + decs[:1], dtype=float)
        # Midpoints
        ras = np.concatenate([ras, 0.5 * (ras[:-1] + ras[1:])])
        decs = np.concatenate([decs, 0.5 * (decs[:-1] + decs[1:])])

        visit_mjd = visitInfo.date.toAstropy().mjd
        # ICRS FOV → heliocentric SD-MOC via SkyCoord + visitInfo observatory.
        cells = index.cells_for_visit(ras, decs, visitInfo=visitInfo)
        self.log.info(
            "SD-MOC selected %d cells (order=%d, dens=%.1f/deg2) for visit MJD %.4f",
            len(cells),
            config.healpix_order,
            config.density,
            visit_mjd,
        )

        orbits = sample_sdmoc_cells(cells, index, config=config)
        self.log.info("Sampled %d synthetic orbits before FOV clip", len(orbits))

        catalog = orbits_to_trail_catalog(
            orbits,
            visitInfo,
            wcs,
            bbox,
            config,
        )
        self.log.info("Wrote %d injectable sources (%s)", len(catalog), config.source_type)
        return Struct(output_catalog=catalog)
