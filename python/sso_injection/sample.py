# This file is part of sso_injection.
"""On-the-fly sampling of SD-MOC cells into Keplerian orbit tables."""

from __future__ import annotations

__all__ = ["sample_sdmoc_cell", "sample_sdmoc_cells"]

import numpy as np
from astropy.table import Table
from astropy.time import Time

from .config import OrbitPopulationConfig
from .kepler import GM_SUN_AU3_DAY2, cartesian_to_keplerian, true_anomaly_from_mean
from .sdmoc import SDMocCell, SDMocIndex

try:
    import healpy as hp
except ImportError as exc:  # pragma: no cover
    raise ImportError("sso_injection requires healpy for SD-MOC sampling") from exc

# Nested HEALPix order for equal-area sub-pixel directions (~0.39 mas at order 29).
_DIRECTION_ORDER = 29

# Uniform draws per object: r^2, sub-pixel direction, e, M, plane angle, H.
_N_UNIFORMS = 6


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
    return sample_sdmoc_cells([cell], index, config=config)


def sample_sdmoc_cells(
    cells: list[SDMocCell],
    index: SDMocIndex,
    config: OrbitPopulationConfig | None = None,
) -> Table:
    """
    Sample and stack orbit tables for many SD-MOC cells.

    Each cell is seeded independently via ``index.cell_seed(cell)`` so a cell's
    orbits are identical whether sampled alone or inside a larger batch. Uniform
    draws are a fixed ``(6, n)`` block per cell (no rejection sampling).
    """
    config = config or index.config
    if not cells:
        return Table()

    ipix_all = np.fromiter((c.ipix for c in cells), dtype=np.int64, count=len(cells))
    dist_bin_all = np.fromiter((c.dist_bin for c in cells), dtype=np.int64, count=len(cells))

    shift = _DIRECTION_ORDER - index.order
    if shift < 0:
        raise ValueError(
            f"healpix_order={index.order} exceeds direction order {_DIRECTION_ORDER}"
        )
    n_sub = np.int64(4**shift)
    nside_fine = 2**_DIRECTION_ORDER
    i_max = np.deg2rad(config.inclination_max_deg)
    mu = GM_SUN_AU3_DAY2
    h_lo = float(config.h_limits[0])
    h_hi = float(config.h_limits[1])
    e_max = float(config.eccentricity_max)

    chunks: list[dict[str, np.ndarray]] = []

    for dist_bin in range(index.n_dist_bins):
        n = index.n_objects_per_cell(dist_bin)
        sel = np.flatnonzero(dist_bin_all == dist_bin)
        if n <= 0 or sel.size == 0:
            continue

        n_cells = int(sel.size)
        # Per-cell seeded uniforms; row order is fixed for reproducibility.
        u = np.empty((n_cells, _N_UNIFORMS, n), dtype=float)
        seeds = np.empty(n_cells, dtype=np.int64)
        for k, j in enumerate(sel):
            seed = index.cell_seed(cells[j])
            seeds[k] = seed
            u[k] = np.random.default_rng(seed).random((_N_UNIFORMS, n))

        # Shape (_N_UNIFORMS, n_cells * n): objects contiguous per cell.
        u = u.transpose(1, 0, 2).reshape(_N_UNIFORMS, -1)
        ipix = np.repeat(ipix_all[sel], n)
        injection_id = (
            (seeds[:, None] & 0xFFFFF).astype(np.int64) * np.int64(10**6)
            + np.arange(n, dtype=np.int64)
        ).reshape(-1)

        r_lo = float(index.distance_edges[dist_bin])
        r_hi = float(index.distance_edges[dist_bin + 1])
        r = np.sqrt(r_lo**2 + u[0] * (r_hi**2 - r_lo**2))

        sub = np.minimum((u[1] * float(n_sub)).astype(np.int64), n_sub - 1)
        theta, phi = hp.pix2ang(nside_fine, ipix * n_sub + sub, nest=True)
        lat = 0.5 * np.pi - theta
        cos_lat = np.cos(lat)
        sin_lat = np.sin(lat)
        cos_lon = np.cos(phi)
        sin_lon = np.sin(phi)

        rhat = np.vstack(
            [
                cos_lat * cos_lon,
                cos_lat * sin_lon,
                sin_lat,
            ]
        )
        xyz = r * rhat

        e = u[2] * e_max
        M = u[3] * (2.0 * np.pi)
        nu = true_anomaly_from_mean(e, M)
        # Semi-latus rectum from r and true anomaly: p = r (1 + e cos ν).
        p = r * (1.0 + e * np.cos(nu))
        vr = np.sqrt(mu / p) * e * np.sin(nu)
        vt = np.sqrt(mu / p) * (1.0 + e * np.cos(nu))

        # Local tangent basis: east (increasing lon), north (increasing lat).
        east = np.vstack([-sin_lon, cos_lon, np.zeros_like(phi)])
        north = np.cross(rhat, east, axis=0)

        # Closed-form plane angle with cos(i) = cos(ψ) cos(lat).
        with np.errstate(invalid="ignore", divide="ignore"):
            ratio = np.cos(i_max) / cos_lat
        psi_max = np.arccos(np.clip(ratio, -1.0, 1.0))
        psi_max = np.where(np.isfinite(psi_max), psi_max, 0.0)
        psi = (2.0 * u[4] - 1.0) * psi_max
        theta_hat = np.cos(psi) * east + np.sin(psi) * north

        vxyz_year = (vr * rhat + vt * theta_hat) * 365.25
        elements = cartesian_to_keplerian(xyz, vxyz_year)
        h = h_lo + u[5] * (h_hi - h_lo)

        chunks.append(
            {
                "injection_id": injection_id,
                "a": elements["a"],
                "e": elements["e"],
                "inc": elements["inc"],
                "Omega": elements["Omega"],
                "omega": elements["omega"],
                "M": elements["M"],
                "H": h,
                "healpix": ipix.astype(np.int64, copy=False),
                "dist_bin": np.full(ipix.size, dist_bin, dtype=np.int32),
            }
        )

    if not chunks:
        return Table()

    obstime = Time(config.model_epoch_mjd, format="mjd")
    keys = (
        "injection_id",
        "a",
        "e",
        "inc",
        "Omega",
        "omega",
        "M",
        "H",
        "healpix",
        "dist_bin",
    )
    return Table(
        {key: np.concatenate([c[key] for c in chunks]) for key in keys},
        meta={
            "day_obs": obstime.isot,
            "model_epoch_mjd": config.model_epoch_mjd,
            "master_seed": config.master_seed,
        },
    )
