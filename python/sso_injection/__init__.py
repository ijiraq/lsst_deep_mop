# This file is part of sso_injection.
"""Synthetic SSO injection catalogs (SD-MOC sampling → Trail tables)."""

from __future__ import annotations

__all__ = [
    "OrbitPopulationConfig",
    "equal_r2_distance_edges",
    "GenerateSsoInjectionCatalogConfig",
    "GenerateSsoInjectionCatalogConnections",
    "GenerateSsoInjectionCatalogTask",
    "InjectSsoVisitConfig",
    "InjectSsoVisitConnections",
    "InjectSsoVisitTask",
    "apparent_magnitude",
    "cartesian_to_keplerian",
    "geocenter_location",
    "get_reference_frame",
    "icrs_los_to_heliocentric",
    "kepToHelioCartSkyCoord",
    "keplerian_to_cartesian",
    "observer_location_from_visit_info",
    "propagate_orbits",
    "sample_sdmoc_cells",
    "SDMocIndex",
    "SDMocCell",
    "orbits_to_trail_catalog",
    "propagate_to_visit",
]


def __getattr__(name: str):
    if name in {"OrbitPopulationConfig", "equal_r2_distance_edges"}:
        from .config import OrbitPopulationConfig, equal_r2_distance_edges

        return {
            "OrbitPopulationConfig": OrbitPopulationConfig,
            "equal_r2_distance_edges": equal_r2_distance_edges,
        }[name]
    if name in {
        "GenerateSsoInjectionCatalogConfig",
        "GenerateSsoInjectionCatalogConnections",
        "GenerateSsoInjectionCatalogTask",
    }:
        from .generateSsoInjectionCatalog import (
            GenerateSsoInjectionCatalogConfig,
            GenerateSsoInjectionCatalogConnections,
            GenerateSsoInjectionCatalogTask,
        )

        return {
            "GenerateSsoInjectionCatalogConfig": GenerateSsoInjectionCatalogConfig,
            "GenerateSsoInjectionCatalogConnections": GenerateSsoInjectionCatalogConnections,
            "GenerateSsoInjectionCatalogTask": GenerateSsoInjectionCatalogTask,
        }[name]
    if name in {"InjectSsoVisitConfig", "InjectSsoVisitConnections", "InjectSsoVisitTask"}:
        from .injectSsoVisit import InjectSsoVisitConfig, InjectSsoVisitConnections, InjectSsoVisitTask

        return {
            "InjectSsoVisitConfig": InjectSsoVisitConfig,
            "InjectSsoVisitConnections": InjectSsoVisitConnections,
            "InjectSsoVisitTask": InjectSsoVisitTask,
        }[name]
    if name in {
        "apparent_magnitude",
        "cartesian_to_keplerian",
        "geocenter_location",
        "get_reference_frame",
        "icrs_los_to_heliocentric",
        "kepToHelioCartSkyCoord",
        "keplerian_to_cartesian",
        "observer_location_from_visit_info",
        "propagate_orbits",
    }:
        from . import kepler as _kepler

        return getattr(_kepler, name)
    if name in {"sample_sdmoc_cells"}:
        from .sample import sample_sdmoc_cells

        return sample_sdmoc_cells
    if name in {"SDMocIndex", "SDMocCell"}:
        from .sdmoc import SDMocCell, SDMocIndex

        return {"SDMocIndex": SDMocIndex, "SDMocCell": SDMocCell}[name]
    if name in {"orbits_to_trail_catalog", "propagate_to_visit"}:
        from .trails import orbits_to_trail_catalog, propagate_to_visit

        return {
            "orbits_to_trail_catalog": orbits_to_trail_catalog,
            "propagate_to_visit": propagate_to_visit,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
