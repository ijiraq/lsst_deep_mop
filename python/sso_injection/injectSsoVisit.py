# This file is part of sso_injection.
"""Visit inject wrapper that reads per-detector SSO catalogs (not HTM prereqs)."""

from __future__ import annotations

__all__ = ["InjectSsoVisitConnections", "InjectSsoVisitConfig", "InjectSsoVisitTask"]

from typing import cast

from lsst.pipe.base.connectionTypes import Input
from lsst.source.injection.inject_visit import VisitInjectConfig, VisitInjectConnections, VisitInjectTask


class InjectSsoVisitConnections(  # type: ignore[call-arg]
    VisitInjectConnections,
    dimensions=("instrument", "visit", "detector"),
):
    """Like VisitInjectConnections, but catalog is a per-detector pipeline Input."""

    injection_catalogs = Input(
        doc="Per-detector synthetic SSO catalog from GenerateSsoInjectionCatalogTask.",
        name="sso_injection_catalog",
        storageClass="ArrowAstropy",
        dimensions=("instrument", "visit", "detector"),
        multiple=True,
        minimum=0,
    )

    def __init__(self, *, config=None):
        config = cast(InjectSsoVisitConfig, config)
        super().__init__(config=config)


class InjectSsoVisitConfig(  # type: ignore[call-arg]
    VisitInjectConfig,
    pipelineConnections=InjectSsoVisitConnections,
):
    """Config for InjectSsoVisitTask."""


class InjectSsoVisitTask(VisitInjectTask):
    """Inject sources using a per-detector catalog from ``sso_injection``."""

    _DefaultName = "injectSsoVisit"
    ConfigClass = InjectSsoVisitConfig
