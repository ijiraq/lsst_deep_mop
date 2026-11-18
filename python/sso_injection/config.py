# This file is part of sso_injection.
"""Population configuration for synthetic SSO orbit models."""

from __future__ import annotations

__all__ = ["OrbitPopulationConfig", "equal_r2_distance_edges"]

import numpy as np
from lsst.pex.config import Config, Field, ListField


def equal_r2_distance_edges(r_inner: float, r_outer: float, n_bins: int) -> list[float]:
    """
    Heliocentric shell edges with equal width in distance-squared.

    Sky rate scales roughly as ``r**(-1/2)``; equal spacing in ``r**2`` gives
    uniform weighting with respect to that rate proxy between ``r_inner`` and
    ``r_outer``.
    """
    if n_bins < 1:
        raise ValueError("n_distance_bins must be >= 1")
    if not (r_outer > r_inner > 0):
        raise ValueError("Require distance_outer_au > distance_inner_au > 0")
    u = np.linspace(r_inner**2, r_outer**2, int(n_bins) + 1)
    return np.sqrt(u).tolist()


class OrbitPopulationConfig(Config):
    """YAML-tunable synthetic SSO population (SD-MOC orbit model)."""

    density = Field(
        dtype=float,
        default=10000.0,
        doc="Surface density of synthetic objects per square degree on the "
        "heliocentric sphere, integrated over the full [inner, outer] distance "
        "range and apportioned uniformly in distance-squared (sky-rate weight).",
    )
    master_seed = Field(
        dtype=int,
        default=20240611,
        doc="Master RNG seed; combined with SD-MOC cell ids for reproducibility.",
    )
    model_epoch_mjd = Field(
        dtype=float,
        default=60500.0,
        doc="Model epoch T0 (MJD) at which SD-MOC cell ownership is defined.",
    )
    healpix_order = Field(
        dtype=int,
        default=8,
        doc="HEALPix order (nside = 2**order) for heliocentric SD-MOC space index.",
    )
    distance_inner_au = Field(
        dtype=float,
        default=30.0,
        doc="Inner heliocentric distance bound (AU) for injection weighting.",
    )
    distance_outer_au = Field(
        dtype=float,
        default=50.0,
        doc="Outer heliocentric distance bound (AU) for injection weighting.",
    )
    n_distance_bins = Field(
        dtype=int,
        default=4,
        doc="Number of SD-MOC distance shells between inner and outer, spaced "
        "uniformly in distance-squared. Ignored if distance_bin_edges_au is set.",
    )
    distance_bin_edges_au = ListField(
        dtype=float,
        default=[],
        doc="Optional explicit heliocentric shell edges (AU). When empty, edges "
        "are built from distance_inner_au / distance_outer_au / n_distance_bins "
        "with equal width in r^2. Prefer the inner/outer/n_bins knobs.",
    )
    mag_limits = ListField(
        dtype=float,
        default=[22.0, 27.0],
        doc="Apparent-magnitude sampling limits [bright, faint] used via H scatter.",
    )
    h_limits = ListField(
        dtype=float,
        default=[5.0, 12.0],
        doc="Absolute magnitude H limits [min, max] drawn uniformly per object.",
    )
    eccentricity_max = Field(
        dtype=float,
        default=0.2,
        doc="Maximum eccentricity when scattering around circular prior.",
    )
    inclination_max_deg = Field(
        dtype=float,
        default=30.0,
        doc="Maximum inclination (degrees) when scattering around ecliptic.",
    )
    eccentricity_fuzz = Field(
        dtype=float,
        default=0.2,
        doc="Extra fractional expansion of circular-motion cell query for eccentricity.",
    )
    inclination_fuzz_deg = Field(
        dtype=float,
        default=5.0,
        doc="Extra angular expansion (degrees) of cell query for inclination scatter.",
    )
    source_type = Field(
        dtype=str,
        default="Trail",
        doc="GalSim source_type for the output injection catalog (Trail or Star).",
    )
    trail_dt_hours = Field(
        dtype=float,
        default=None,
        optional=True,
        doc="If set, trail length uses this duration (hours) instead of visit exptime.",
    )

    def resolve_distance_edges(self) -> list[float]:
        """Return shell edges: explicit override or equal-r^2 from inner/outer."""
        edges = list(self.distance_bin_edges_au)
        if len(edges) >= 2:
            return edges
        return equal_r2_distance_edges(
            self.distance_inner_au,
            self.distance_outer_au,
            self.n_distance_bins,
        )
