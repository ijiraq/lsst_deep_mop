# This file is part of sso_injection.
"""On-the-fly sampling of SD-MOC cells into Keplerian orbit tables."""

from __future__ import annotations

__all__ = ["sample_sdmoc_cell", "sample_sdmoc_cells"]

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table, vstack
from astropy.time import Time

from .config import OrbitPopulationConfig
from .kepler import GM_SUN_AU3_DAY2, cartesian_to_keplerian, true_anomaly_from_mean
from .sdmoc import SDMocCell, SDMocIndex


def _sample_directions(index: SDMocIndex, ipix: int, n: int, rng: np.random.Generator) -> SkyCoord:
    """Uniform-ish directions inside a nested HEALPix pixel."""
    import healpy as hp

    lon = np.empty(n)
    lat = np.empty(n)
    filled = 0
    while filled < n:
        vecs = rng.normal(size=(3, max(n * 8, 32)))
        vecs /= np.linalg.norm(vecs, axis=0)
        pix = hp.vec2pix(index.nside, vecs[0], vecs[1], vecs[2], nest=True)
        hit = np.where(pix == ipix)[0]
        if hit.size == 0:
            continue
        take = min(int(hit.size), n - filled)
        theta, phi = hp.vec2ang(vecs[:, hit[:take]].T)
        lon[filled : filled + take] = np.rad2deg(phi)
        lat[filled : filled + take] = 90.0 - np.rad2deg(theta)
        filled += take
    obstime = Time(index.config.model_epoch_mjd, format="mjd")
    return SkyCoord(
        lon=lon * u.deg,
        lat=lat * u.deg,
        frame="heliocentrictrueecliptic",
        obstime=obstime,
    )


def _random_unit_perp(rhat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Random unit vectors perpendicular to ``rhat`` (shape (3, N))."""
    tmp = rng.normal(size=rhat.shape)
    v = tmp - rhat * np.sum(tmp * rhat, axis=0, keepdims=True)
    norm = np.linalg.norm(v, axis=0)
    bad = norm < 1e-12
    if np.any(bad):
        # Rare: tmp nearly parallel to rhat; use a coordinate-axis fallback.
        fallback = np.zeros_like(rhat)
        abs_r = np.abs(rhat)
        min_ax = np.argmin(abs_r, axis=0)
        fallback[min_ax, np.arange(rhat.shape[1])] = 1.0
        v[:, bad] = fallback[:, bad] - rhat[:, bad] * np.sum(
            fallback[:, bad] * rhat[:, bad], axis=0, keepdims=True
        )
        norm = np.linalg.norm(v, axis=0)
    return v / norm


def sample_sdmoc_cell(
    cell: SDMocCell,
    index: SDMocIndex,
    config: OrbitPopulationConfig | None = None,
) -> Table:
    """
    Sample Keplerian orbits owned by one SD-MOC cell at model epoch T0.

    Positions are drawn inside the cell. Eccentricity and mean anomaly are drawn
    from the configured priors; velocity uses the polar Keplerian (v_r, v_θ) at
    that true anomaly so ``M`` is not pinned to apoapsis. Orbital-plane
    orientation is random among planes containing the position, subject to
    ``inclination_max_deg``.
    """
    config = config or index.config
    n = index.n_objects_per_cell(cell.dist_bin)
    if n <= 0:
        return Table()

    rng = np.random.default_rng(index.cell_seed(cell))
    r_lo = index.distance_edges[cell.dist_bin]
    r_hi = index.distance_edges[cell.dist_bin + 1]
    # Uniform in r^2 within the shell (sky-rate weighting; rate ~ r**(-1/2)).
    r = np.sqrt(rng.uniform(r_lo**2, r_hi**2, size=n))

    directions = _sample_directions(index, cell.ipix, n, rng)
    lon = directions.lon.to_value(u.rad)
    lat = directions.lat.to_value(u.rad)
    x = r * np.cos(lat) * np.cos(lon)
    y = r * np.cos(lat) * np.sin(lon)
    z = r * np.sin(lat)
    xyz = np.vstack([x, y, z])
    rhat = xyz / r

    # Orbital elements priors. M must be drawn explicitly — a purely tangential
    # speed with |v|<v_circ forces apoapsis and collapses M to ~180 deg.
    e = rng.uniform(0.0, config.eccentricity_max, size=n)
    M = rng.uniform(0.0, 2.0 * np.pi, size=n)
    nu = true_anomaly_from_mean(e, M)
    one_minus_e2 = np.maximum(1.0 - e**2, 1e-12)
    a = r * (1.0 + e * np.cos(nu)) / one_minus_e2
    p = a * one_minus_e2  # semi-latus rectum
    mu = GM_SUN_AU3_DAY2
    # Polar velocity components (AU/day) in the {rhat, theta_hat} basis.
    vr = np.sqrt(mu / p) * e * np.sin(nu)
    vt = np.sqrt(mu / p) * (1.0 + e * np.cos(nu))

    # Random orbital planes containing r, rejecting i above the configured max.
    i_max = np.deg2rad(config.inclination_max_deg)
    theta_hat = np.empty_like(rhat)
    pending = np.ones(n, dtype=bool)
    for _ in range(64):
        if not np.any(pending):
            break
        n_pend = int(pending.sum())
        rhat_p = rhat[:, pending]
        th = _random_unit_perp(rhat_p, rng)
        nhat = np.cross(rhat_p, th, axis=0)
        nhat /= np.linalg.norm(nhat, axis=0)
        inc_p = np.arccos(np.clip(nhat[2], -1.0, 1.0))
        ok = inc_p <= i_max
        # Write accepted theta_hat; leave rejects for another draw.
        idxs = np.flatnonzero(pending)
        theta_hat[:, idxs[ok]] = th[:, ok]
        pending[idxs[ok]] = False
    if np.any(pending):
        # Fallback: accept whatever plane we get for stubborn leftovers.
        th = _random_unit_perp(rhat[:, pending], rng)
        theta_hat[:, pending] = th

    v_day = vr * rhat + vt * theta_hat
    vxyz_year = v_day * 365.25

    # Convert the constructed state; M should track the drawn mean anomaly
    # (not collapse to apoapsis as with a purely tangential |v|<v_circ prior).
    elements = cartesian_to_keplerian(xyz, vxyz_year)

    h = rng.uniform(config.h_limits[0], config.h_limits[1], size=n)
    local_index = np.arange(n, dtype=np.int64)
    injection_id = (np.int64(index.cell_seed(cell)) & 0xFFFFF) * np.int64(10**6) + local_index

    obstime = Time(config.model_epoch_mjd, format="mjd")
    table = Table(
        {
            "injection_id": injection_id,
            "a": elements["a"],
            "e": elements["e"],
            "inc": elements["inc"],
            "Omega": elements["Omega"],
            "omega": elements["omega"],
            "M": elements["M"],
            "H": h,
            "healpix": np.full(n, cell.ipix, dtype=np.int64),
            "dist_bin": np.full(n, cell.dist_bin, dtype=np.int32),
        },
        meta={
            "day_obs": obstime.isot,
            "model_epoch_mjd": config.model_epoch_mjd,
            "master_seed": config.master_seed,
        },
    )
    return table


def sample_sdmoc_cells(
    cells: list[SDMocCell],
    index: SDMocIndex,
    config: OrbitPopulationConfig | None = None,
) -> Table:
    """Sample and stack orbit tables for many SD-MOC cells."""
    tables = [sample_sdmoc_cell(cell, index, config=config) for cell in cells]
    tables = [t for t in tables if len(t) > 0]
    if not tables:
        return Table()
    return vstack(tables, metadata_conflicts="silent")
