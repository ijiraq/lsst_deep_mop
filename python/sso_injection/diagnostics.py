# This file is part of sso_injection.
"""Diagnostic plots and helpers for synthetic SSO injection catalogs."""

from __future__ import annotations

__all__ = [
    "fetch_arrokoth_ephemeris",
    "sample_cell_at_sky_point",
    "propagate_orbits_to_sky",
    "plot_injection_diagnostics",
    "run_arrokoth_injection_diagnostics",
]

from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import EarthLocation, SkyCoord
from astropy.table import Table
from astropy.time import Time

from .config import OrbitPopulationConfig
from .kepler import (
    apparent_magnitude,
    geocenter_location,
    get_reference_frame,
    icrs_los_to_heliocentric,
    kepToHelioCartSkyCoord,
    propagate_orbits,
)
from .sample import sample_sdmoc_cell, sample_sdmoc_cells
from .sdmoc import SDMocCell, SDMocIndex

try:
    from astroquery.jplhorizons import Horizons
except ImportError:  # pragma: no cover
    Horizons = None

try:
    import healpy as hp
except ImportError:  # pragma: no cover
    hp = None

_EMPTY_SKY_NAMES = (
    "injection_id",
    "ra",
    "dec",
    "ra_next",
    "dec_next",
    "mag",
    "rate",
    "angle",
    "r",
    "delta",
    "H",
    "a",
    "e",
    "inc",
    "Omega",
    "omega",
    "M",
)


def fetch_arrokoth_ephemeris(
    epoch: str | Time = "2022-06-20",
    *,
    location: str = "500",
) -> dict:
    """
    Query JPL Horizons for Arrokoth sky position and heliocentric state.

    Parameters
    ----------
    epoch
        UTC/TT date for the ephemeris (ISO string or ``Time``).
    location
        Horizons observer code for the ephemeris (``500`` = geocenter).

    Returns
    -------
    info : `dict`
        Keys include ``obstime``, ``ra_deg``, ``dec_deg``, ``delta_au``,
        ``r_au``, heliocentric ecliptic cartesian state, and osculating elements.
    """
    if Horizons is None:
        raise ImportError("astroquery is required for Horizons diagnostics")
    obstime = Time(epoch) if not isinstance(epoch, Time) else epoch

    eph_obj = Horizons(
        id="486958;",
        location=location,
        epochs=obstime.tdb.jd,
        id_type="smallbody",
    )
    eph = eph_obj.ephemerides()

    sun_obj = Horizons(
        id="486958;",
        location="500@10",
        epochs=obstime.tdb.jd,
        id_type="smallbody",
    )
    vec = sun_obj.vectors(refplane="ecliptic")
    el = sun_obj.elements(refplane="ecliptic")

    def _q(col):
        return float(np.asarray(col[0]))

    return {
        "obstime": obstime,
        "ra_deg": _q(eph["RA"]),
        "dec_deg": _q(eph["DEC"]),
        "delta_au": _q(eph["delta"]),
        "r_au": _q(eph["r"]),
        "x_au": _q(vec["x"]),
        "y_au": _q(vec["y"]),
        "z_au": _q(vec["z"]),
        "vx_au_day": _q(vec["vx"]),
        "vy_au_day": _q(vec["vy"]),
        "vz_au_day": _q(vec["vz"]),
        "a_au": _q(el["a"]),
        "e": _q(el["e"]),
        "incl_deg": _q(el["incl"]),
        "Omega_deg": _q(el["Omega"]),
        "w_deg": _q(el["w"]),
        "M_deg": _q(el["M"]),
        "Vmag": _q(eph["V"]) if "V" in eph.colnames else np.nan,
    }


def cell_for_heliocentric_state(
    index: SDMocIndex,
    x_au: float,
    y_au: float,
    z_au: float,
) -> SDMocCell:
    """Map a heliocentric ecliptic cartesian position to an SD-MOC cell."""
    if hp is None:
        raise ImportError("healpy is required for SD-MOC diagnostics")
    r = float(np.sqrt(x_au**2 + y_au**2 + z_au**2))
    theta = np.arccos(np.clip(z_au / r, -1.0, 1.0))
    phi = np.arctan2(y_au, x_au) % (2 * np.pi)
    ipix = int(hp.ang2pix(index.nside, theta, phi, nest=True))
    dist_bin = int(index.dist_bin_of_heliocentric_r(r))
    if dist_bin < 0:
        # Clamp to nearest configured shell for diagnostics.
        if r < index.distance_edges[0]:
            dist_bin = 0
        else:
            dist_bin = index.n_dist_bins - 1
    return SDMocCell(ipix=ipix, dist_bin=dist_bin)


def sample_cell_at_sky_point(
    ra_deg: float,
    dec_deg: float,
    delta_au: float,
    obstime: Time,
    config: OrbitPopulationConfig | None = None,
    *,
    location: EarthLocation | None = None,
    include_neighbors: bool = True,
    density_override: float | None = 50000.0,
) -> tuple[Table, SDMocIndex, SDMocCell, SkyCoord]:
    """
    Sample the SD-MOC cell (and optional neighbors) covering a sky LOS + distance.

    Returns orbits at model epoch T0, the index, the primary cell, and the
    heliocentric ``SkyCoord`` of the query point.
    """
    config = OrbitPopulationConfig() if config is None else config.copy()
    if density_override is not None:
        config.density = float(density_override)
    index = SDMocIndex(config)
    if location is None:
        location = geocenter_location()

    helio = icrs_los_to_heliocentric(
        ra_deg, dec_deg, delta_au, obstime=obstime, location=location
    )
    cell = cell_for_heliocentric_state(
        index,
        float(helio.cartesian.x.to_value(u.au)),
        float(helio.cartesian.y.to_value(u.au)),
        float(helio.cartesian.z.to_value(u.au)),
    )

    cells = [cell]
    if include_neighbors:
        for nb in hp.get_all_neighbours(index.nside, cell.ipix, nest=True):
            if nb >= 0:
                cells.append(SDMocCell(int(nb), cell.dist_bin))

    orbits = sample_sdmoc_cells(cells, index, config=config)
    return orbits, index, cell, helio


def propagate_orbits_to_sky(
    orbits: Table,
    obstime: Time,
    *,
    location: EarthLocation | None = None,
    rate_dt: u.Quantity = 24 * u.hour,
) -> Table:
    """
    Propagate synthetic orbits to ``obstime`` and return ICRS sky + rates.

    Also stores sky positions at ``obstime + rate_dt`` as ``ra_next`` /
    ``dec_next`` (default +24 h) for two-epoch diagnostic plots.

    Does not require an LSST ``VisitInfo`` (uses geocenter unless ``location``
    is given).
    """
    if len(orbits) == 0:
        return Table(names=_EMPTY_SKY_NAMES)
    if location is None:
        location = geocenter_location()

    frame = get_reference_frame(obstime=obstime, location=location)
    frame2 = get_reference_frame(obstime=obstime + rate_dt, location=location)

    orbits_t = propagate_orbits(orbits.copy(), frame.obstime.mjd)
    orbits2 = propagate_orbits(orbits.copy(), frame2.obstime.mjd)

    coordinates, _ = kepToHelioCartSkyCoord(orbits_t)
    r_helio = np.sqrt(
        coordinates.x * coordinates.x + coordinates.y * coordinates.y + coordinates.z * coordinates.z
    )
    coordinates = coordinates.transform_to(frame)
    coordinates = SkyCoord(
        coordinates.ra,
        coordinates.dec,
        distance=coordinates.distance,
        obstime=coordinates.obstime,
        frame="icrs",
    )

    coordinates2, _ = kepToHelioCartSkyCoord(orbits2)
    coordinates2 = coordinates2.transform_to(frame2)
    coordinates2 = SkyCoord(
        coordinates2.ra,
        coordinates2.dec,
        distance=coordinates2.distance,
        obstime=coordinates2.obstime,
        frame="icrs",
    )

    rate = coordinates.separation(coordinates2) / rate_dt
    angle = coordinates.position_angle(coordinates2)
    delta = coordinates.distance.to_value(u.au)
    mag = apparent_magnitude(
        np.asarray(r_helio),
        np.asarray(delta),
        1.0,
        np.asarray(orbits_t["H"]),
    )

    return Table(
        {
            "injection_id": orbits_t["injection_id"],
            "ra": coordinates.ra.to_value(u.deg),
            "dec": coordinates.dec.to_value(u.deg),
            "ra_next": coordinates2.ra.to_value(u.deg),
            "dec_next": coordinates2.dec.to_value(u.deg),
            "mag": np.asarray(mag, dtype=float),
            "rate": rate.to_value(u.arcsec / u.hour),
            "angle": angle.to_value(u.deg),
            "r": np.asarray(r_helio, dtype=float),
            "delta": np.asarray(delta, dtype=float),
            "H": orbits_t["H"],
            "a": orbits_t["a"],
            "e": orbits_t["e"],
            "inc": np.rad2deg(np.asarray(orbits_t["inc"], dtype=float)),
            "Omega": np.rad2deg(np.asarray(orbits_t["Omega"], dtype=float)),
            "omega": np.rad2deg(np.asarray(orbits_t["omega"], dtype=float)),
            "M": np.rad2deg(np.asarray(orbits_t["M"], dtype=float)),
        },
        meta={
            "day_obs": obstime.isot,
            "day_obs_next": (obstime + rate_dt).isot,
            "rate_dt_hours": float(rate_dt.to_value(u.hour)),
        },
    )


def _plot_element_cdfs(axes, sky: Table, arrokoth: dict | None = None) -> None:
    """Fill a 2×3 axes grid with CDFs of a, e, i, Ω, ω, M."""
    specs = [
        ("a", "a [AU]", None if arrokoth is None else arrokoth.get("a_au")),
        ("e", "e", None if arrokoth is None else arrokoth.get("e")),
        ("inc", "i [deg]", None if arrokoth is None else arrokoth.get("incl_deg")),
        ("Omega", "Ω [deg]", None if arrokoth is None else arrokoth.get("Omega_deg")),
        ("omega", "ω [deg]", None if arrokoth is None else arrokoth.get("w_deg")),
        ("M", "M [deg]", None if arrokoth is None else arrokoth.get("M_deg")),
    ]
    for ax, (col, label, ref) in zip(np.asarray(axes).ravel(), specs, strict=True):
        x = np.sort(np.asarray(sky[col], dtype=float))
        y = np.linspace(0.0, 1.0, len(x), endpoint=True)
        ax.plot(x, y, color="C0", lw=1.5)
        if ref is not None and np.isfinite(ref):
            ax.axvline(float(ref), color="crimson", ls="--", lw=1.0, label="Arrokoth")
            ax.legend(fontsize=7, loc="lower right")
        ax.set_xlabel(label)
        ax.set_ylabel("CDF")
        ax.set_ylim(0.0, 1.0)
        ax.grid(True, alpha=0.3)


def plot_injection_diagnostics(
    sky: Table,
    *,
    arrokoth: dict | None = None,
    trail_hours: float = 1.0,
    output_path: str | Path | None = None,
    title: str | None = None,
):
    """
    Multi-panel diagnostics for a synthetic injection sky catalog.

    Panels:
      1. RA/Dec on the fiducial night (blue) and +24 h (red)
      2–7. CDFs of a, e, i, Ω, ω, M (Arrokoth reference lines when provided)
    """
    import matplotlib.pyplot as plt

    if len(sky) == 0:
        raise ValueError("sky catalog is empty; nothing to plot")
    for col in ("ra_next", "dec_next", "Omega", "omega", "M"):
        if col not in sky.colnames:
            raise ValueError(f"sky catalog missing required column {col!r}")

    del trail_hours  # kept for API compatibility with older callers

    fig = plt.figure(figsize=(12, 11))
    gs = fig.add_gridspec(3, 3, height_ratios=[1.15, 1.0, 1.0], hspace=0.38, wspace=0.32)
    ax_sky = fig.add_subplot(gs[0, :])
    cdf_axes = [fig.add_subplot(gs[1 + i // 3, i % 3]) for i in range(6)]

    ra = np.asarray(sky["ra"], dtype=float)
    dec = np.asarray(sky["dec"], dtype=float)
    ra_next = np.asarray(sky["ra_next"], dtype=float)
    dec_next = np.asarray(sky["dec_next"], dtype=float)
    dt_h = float(sky.meta.get("rate_dt_hours", 24.0))
    night0 = sky.meta.get("day_obs", "fiducial")
    night1 = sky.meta.get("day_obs_next", f"+{dt_h:g} h")

    ax_sky.scatter(ra, dec, s=10, c="C0", alpha=0.55, label=f"fiducial ({night0})", zorder=2)
    ax_sky.scatter(
        ra_next,
        dec_next,
        s=10,
        c="crimson",
        alpha=0.55,
        label=f"+{dt_h:g} h ({night1})",
        zorder=3,
    )
    # Light connectors show nightly motion for a subset of objects.
    n_link = min(80, len(sky))
    step = max(len(sky) // n_link, 1)
    for i in range(0, len(sky), step):
        ax_sky.plot(
            [ra[i], ra_next[i]],
            [dec[i], dec_next[i]],
            color="0.5",
            lw=0.4,
            alpha=0.35,
            zorder=1,
        )
    if arrokoth is not None:
        ax_sky.scatter(
            [arrokoth["ra_deg"]],
            [arrokoth["dec_deg"]],
            s=90,
            marker="*",
            c="gold",
            edgecolors="k",
            linewidths=0.4,
            zorder=5,
            label="Arrokoth (fiducial)",
        )
    ax_sky.set_xlabel("RA [deg]")
    ax_sky.set_ylabel("Dec [deg]")
    ax_sky.set_title(title or f"Injected sky: fiducial vs +{dt_h:g} h (n={len(sky)})")
    ax_sky.invert_xaxis()
    ax_sky.set_aspect("equal", adjustable="datalim")
    ax_sky.legend(loc="best", fontsize=8)
    ax_sky.grid(True, alpha=0.3)

    _plot_element_cdfs(cdf_axes, sky, arrokoth=arrokoth)
    fig.suptitle("sso_injection diagnostics", fontsize=13, y=0.995)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    return fig


def run_arrokoth_injection_diagnostics(
    epoch: str = "2022-06-20",
    *,
    output_path: str | Path = "arrokoth_injection_diagnostics.png",
    config: OrbitPopulationConfig | None = None,
    density_override: float = 20000.0,
    trail_hours: float = 1.0,
    model_epoch_mjd: float | None = None,
    include_neighbors: bool = False,
    max_plot_sources: int = 2000,
) -> tuple[Table, dict, Path]:
    """
    End-to-end Arrokoth-centered injection diagnostic.

    1. Query Horizons for Arrokoth on ``epoch``
    2. Sample the SD-MOC cell at that heliocentric position (optional neighbors)
    3. Propagate to ``epoch`` and ``epoch``+24 h; write sky + element CDF figure
    """
    info = fetch_arrokoth_ephemeris(epoch)
    config = OrbitPopulationConfig() if config is None else config.copy()
    if model_epoch_mjd is not None:
        config.model_epoch_mjd = float(model_epoch_mjd)
    else:
        # Own cells at the diagnostic epoch so ownership matches the plot time.
        config.model_epoch_mjd = float(info["obstime"].mjd)
    if density_override is not None:
        config.density = float(density_override)

    # Prefer Arrokoth's heliocentric state for cell selection (exact r).
    index = SDMocIndex(config)
    cell = cell_for_heliocentric_state(index, info["x_au"], info["y_au"], info["z_au"])
    cells = [cell]
    if include_neighbors:
        for nb in hp.get_all_neighbours(index.nside, cell.ipix, nest=True):
            if nb >= 0:
                cells.append(SDMocCell(int(nb), cell.dist_bin))

    orbits = sample_sdmoc_cells(cells, index, config=config)
    if len(orbits) == 0:
        orbits = sample_sdmoc_cell(cell, index, config=config)

    # Subsample orbits before propagation so both epochs share the same objects.
    if len(orbits) > max_plot_sources:
        rng = np.random.default_rng(int(config.master_seed))
        orbits = orbits[rng.choice(len(orbits), size=max_plot_sources, replace=False)]

    sky = propagate_orbits_to_sky(orbits, info["obstime"])

    out = Path(output_path)
    plot_injection_diagnostics(
        sky,
        arrokoth=info,
        trail_hours=trail_hours,
        output_path=out,
        title=(
            f"SD-MOC cell ({cell.ipix}, bin {cell.dist_bin}) near Arrokoth "
            f"{epoch}  [r={info['r_au']:.2f} AU]"
        ),
    )
    return sky, info, out
