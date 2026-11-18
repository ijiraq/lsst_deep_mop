# This file is part of sso_injection.
"""Keplerian orbit utilities (moved from lsst.source.injection.utils.sso)."""

from __future__ import annotations

import numpy as np
from astropy import units
from astropy.coordinates import (
    GCRS,
    EarthLocation,
    HeliocentricTrueEcliptic,
    SkyCoord,
    solar_system_ephemeris,
)
from astropy.table import Table
from astropy.time import Time
from lsst.afw.image import VisitInfo

BOWELL_G = -0.12
NEWTON_ITERS = 20
# Gaussian gravitational constant squared in AU^3 / day^2 (solar masses).
GM_SUN_AU3_DAY2 = 0.0002959122082855911


def apparent_magnitude(
    r: np.ndarray | float,
    delta: np.ndarray | float,
    robs: np.ndarray | float,
    h: np.ndarray | float,
    g: float = BOWELL_G,
) -> np.ndarray | float:
    """Compute apparent magnitude (Bowell H-G) from observing circumstances."""
    denom = 2 * r * delta
    cos_alpha = (-(robs**2) + delta**2 + r**2) / denom
    if isinstance(cos_alpha, np.ndarray):
        cos_alpha = np.clip(cos_alpha, -1.0, 1.0)
    else:
        cos_alpha = float(np.clip(cos_alpha, -1.0, 1.0))
    alpha = np.arccos(cos_alpha)
    phi1 = np.exp(-3.33 * (np.tan(alpha / 2.0)) ** 0.63)
    phi2 = np.exp(-1.87 * (np.tan(alpha / 2.0)) ** 1.22)
    mag = 5.0 * np.log10(r * delta) + h - 2.5 * np.log10((1.0 - g) * phi1 + g * phi2)
    if isinstance(r, float) and isinstance(mag, np.ndarray):
        mag = mag[0]
    return mag


def compute_E(e: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Eccentric anomaly from mean anomaly via Newton–Raphson."""
    E = M + 0.85 * np.sign(np.sin(M)) * e
    i = 0
    while True:
        sin_e = e * np.sin(E)
        f = E - sin_e - M
        iterate = np.fabs(f) > 1e-14
        if iterate.sum() > 0:
            cos_e = e[iterate] * np.cos(E[iterate])
            fp = 1 - cos_e
            fpp = sin_e[iterate]
            fppp = cos_e
            de = -f[iterate] / fp
            de = -f[iterate] / (fp + de * fpp / 2)
            de = -f[iterate] / (fp + de * fpp / 2 + de * de * fppp / 6)
            E[iterate] = E[iterate] + de
            i += 1
            if i < NEWTON_ITERS:
                continue
            raise ValueError(f"No convergence after {i} iterations")
        break
    return E


def true_anomaly_from_mean(e: np.ndarray, M: np.ndarray) -> np.ndarray:
    """True anomaly ν from eccentricity and mean anomaly (radians)."""
    E = compute_E(np.asarray(e, dtype=float), np.asarray(M, dtype=float) % (2 * np.pi))
    return (
        2.0
        * np.arctan2(
            np.sqrt(np.maximum(1.0 + e, 0.0)) * np.sin(E / 2.0),
            np.sqrt(np.maximum(1.0 - e, 0.0)) * np.cos(E / 2.0),
        )
    ) % (2 * np.pi)


def keplerian_to_cartesian(**orbits) -> tuple[np.ndarray, np.ndarray]:
    """Cartesian position (AU) and velocity (AU/yr) from Keplerian elements."""
    M = orbits["M"] % (2 * np.pi)
    signe = np.sign(orbits["a"])
    cos_i = np.cos(orbits["inc"])
    sin_i = np.sqrt(1 - cos_i**2)
    delau1 = M
    delau2 = np.cos(orbits["omega"])
    delau3 = np.sin(orbits["omega"])
    delau4 = np.cos(orbits["Omega"])
    delau5 = np.sin(orbits["Omega"])
    delau6 = signe * np.sqrt(orbits["a"] * signe)
    delau7 = np.abs(delau6) * np.sqrt((1 - orbits["e"] ** 2) * signe)

    E = compute_E(orbits["e"], delau1)
    cos_E = np.cos(E)
    sin_E = np.sin(E)
    q_vec = np.zeros((2, cos_E.shape[0]))
    q_vec[0, :] = (cos_E - orbits["e"]) * (delau6**2)
    q_vec[1, :] = delau7 * delau6 * sin_E

    p_vec = np.zeros((2, cos_E.shape[0]))
    tmp = 1 / (delau6 * (1 - orbits["e"] * cos_E))
    p_vec[0, :] = -sin_E * tmp
    p_vec[1, :] = delau7 * cos_E * tmp / delau6

    mat = np.zeros((3, 2, cos_i.shape[0]))
    d53 = delau5 * delau3
    d42 = delau4 * delau2
    d52 = delau5 * delau2
    d43 = delau4 * delau3
    mat[0, 0, :] = d42 - cos_i * d53
    mat[0, 1, :] = -d43 - cos_i * d52
    mat[1, 0, :] = d52 + cos_i * d43
    mat[1, 1, :] = -d53 + cos_i * d42
    mat[2, 0, :] = sin_i * delau3
    mat[2, 1, :] = sin_i * delau2

    p = (mat * q_vec).sum(axis=1)
    # Internal Gaussian units use GM=1 with n = a**(-3/2); convert to AU/year
    # where Kepler's third law is P[yr] = a**(3/2) (i.e. multiply by 2π).
    v = (mat * p_vec).sum(axis=1) * (2.0 * np.pi)
    return p, v


def cartesian_to_keplerian(
    xyz: np.ndarray,
    vxyz: np.ndarray,
) -> dict[str, np.ndarray]:
    """
    Convert heliocentric ecliptic cartesian state to Keplerian elements.

    Parameters
    ----------
    xyz : array, shape (3, N)
        Position in AU.
    vxyz : array, shape (3, N)
        Velocity in AU/year.
    """
    # Convert velocity to AU/day for GM consistency, then express n in rad/day.
    v = vxyz / 365.25
    r = np.linalg.norm(xyz, axis=0)
    v2 = np.sum(v * v, axis=0)
    # Specific angular momentum
    hvec = np.cross(xyz, v, axis=0)
    h = np.linalg.norm(hvec, axis=0)
    # Inclination
    inc = np.arccos(np.clip(hvec[2] / h, -1.0, 1.0))
    # Node
    nvec = np.array([-hvec[1], hvec[0], np.zeros_like(h)])
    nmag = np.linalg.norm(nvec, axis=0)
    Omega = np.arctan2(nvec[1], nvec[0])
    Omega = np.where(nmag > 0, Omega % (2 * np.pi), 0.0)
    # Eccentricity vector
    mu = GM_SUN_AU3_DAY2
    evec = (np.cross(v, hvec, axis=0) / mu) - (xyz / r)
    e = np.linalg.norm(evec, axis=0)
    # Argument of periapsis
    cos_omega = np.sum(nvec * evec, axis=0) / np.maximum(nmag * e, 1e-15)
    omega = np.arccos(np.clip(cos_omega, -1.0, 1.0))
    omega = np.where(evec[2] < 0, (2 * np.pi - omega) % (2 * np.pi), omega)
    omega = np.where(e > 1e-12, omega, 0.0)
    # True anomaly
    cos_nu = np.sum(evec * xyz, axis=0) / np.maximum(e * r, 1e-15)
    nu = np.arccos(np.clip(cos_nu, -1.0, 1.0))
    nu = np.where(np.sum(xyz * v, axis=0) < 0, (2 * np.pi - nu) % (2 * np.pi), nu)
    # Semi-major axis
    a = 1.0 / (2.0 / r - v2 / mu)
    # Eccentric / mean anomaly
    E = 2 * np.arctan2(
        np.sqrt(np.maximum(1 - e, 0)) * np.sin(nu / 2),
        np.sqrt(np.maximum(1 + e, 0)) * np.cos(nu / 2),
    )
    M = (E - e * np.sin(E)) % (2 * np.pi)
    return {
        "a": a,
        "e": e,
        "inc": inc,
        "Omega": Omega % (2 * np.pi),
        "omega": omega % (2 * np.pi),
        "M": M,
    }


def kepToHelioCartSkyCoord(orbits: Table) -> tuple[SkyCoord, units.Quantity]:
    """SkyCoord (heliocentric true ecliptic) and velocity from orbit table."""
    xyz, v_xyz = keplerian_to_cartesian(**orbits["a", "e", "inc", "Omega", "omega", "M"])
    obstime = Time(str(orbits.meta["day_obs"]))
    pos = SkyCoord(
        x=xyz[0],
        y=xyz[1],
        z=xyz[2],
        unit="au",
        obstime=obstime,
        frame="heliocentrictrueecliptic",
        representation_type="cartesian",
    )
    return pos, v_xyz * units.au / units.year


def propagate_orbits(orbits: Table, mjd: float) -> Table:
    """Propagate mean anomaly from orbits.meta['day_obs'] to ``mjd``."""
    orbtime = Time(str(orbits.meta["day_obs"]))
    obstime = Time(mjd, format="mjd")
    delta_time = obstime - orbtime
    orbits = orbits.copy()
    orbits["M"] = orbits["M"] + delta_time * 2 * np.pi / (orbits["a"] ** (3 / 2) * units.year)
    orbits.meta["day_obs"] = obstime.isot
    return orbits


def geocenter_location() -> EarthLocation:
    """Earth geocenter as an ``EarthLocation``."""
    return EarthLocation.from_geocentric(0.0, 0.0, 0.0, unit=units.m)


def observer_location_from_visit_info(visitInfo: VisitInfo | None = None) -> EarthLocation:
    """
    Observatory ``EarthLocation`` from ``visitInfo``.

    Falls back to the geocenter when ``visitInfo`` is missing or the observatory
    cannot be read.
    """
    if visitInfo is None:
        return geocenter_location()
    try:
        observatory = visitInfo.getObservatory()
        lon = observatory.getLongitude().asDegrees()
        lat = observatory.getLatitude().asDegrees()
        height = observatory.getElevation()
        return EarthLocation.from_geodetic(
            lon=lon * units.deg,
            lat=lat * units.deg,
            height=(0.0 if height is None else float(height)) * units.m,
        )
    except Exception:
        return geocenter_location()


def get_reference_frame(
    visitInfo: VisitInfo | None = None,
    time_offset=0 * units.day,
    *,
    obstime: Time | None = None,
    location: EarthLocation | None = None,
) -> GCRS:
    """
    GCRS frame at the visit observatory and time.

    If ``visitInfo`` / ``location`` are omitted, the observer is the geocenter.
    """
    offset = units.Quantity(0.0, units.day) if time_offset is None else units.Quantity(time_offset)
    if obstime is None:
        if visitInfo is None:
            raise ValueError("Either visitInfo or obstime must be provided")
        obstime = visitInfo.date.toAstropy() + offset
    elif offset.to_value(units.day) != 0.0:
        obstime = obstime + offset
    if location is None:
        location = observer_location_from_visit_info(visitInfo)
    obsgeoloc, obsgeovel = location.get_gcrs_posvel(obstime)
    with solar_system_ephemeris.set("builtin"):
        return GCRS(obstime=obstime, obsgeoloc=obsgeoloc, obsgeovel=obsgeovel)


def icrs_los_to_heliocentric(
    ra_deg: np.ndarray | float,
    dec_deg: np.ndarray | float,
    distance_au: np.ndarray | float,
    obstime: Time,
    location: EarthLocation | None = None,
) -> SkyCoord:
    """
    Map observer-centric ICRS lines of sight + distance into heliocentric ecliptic.

    Builds ``SkyCoord`` directions in ICRS (as from a visit WCS), transforms them
    into the observer ``GCRS`` frame (observatory from ``location``, else
    geocenter), attaches the observer–object distance, then uses Astropy
    transforms into ``heliocentrictrueecliptic``.

    Parameters
    ----------
    ra_deg, dec_deg
        Observed ICRS direction(s) in degrees (e.g. detector FOV samples).
    distance_au
        Distance from the observer to the point along each LOS (AU). Broadcasts
        against ``ra_deg`` / ``dec_deg``.
    obstime
        Epoch of the observation.
    location
        Observer ``EarthLocation``. Defaults to the geocenter.

    Returns
    -------
    helio : `astropy.coordinates.SkyCoord`
        Positions in ``heliocentrictrueecliptic`` at ``obstime``.
    """
    if location is None:
        location = geocenter_location()
    ra = np.atleast_1d(np.asarray(ra_deg, dtype=float))
    dec = np.atleast_1d(np.asarray(dec_deg, dtype=float))
    dist = np.atleast_1d(np.asarray(distance_au, dtype=float))
    ra_b, dec_b, dist_b = np.broadcast_arrays(ra, dec, dist)

    with solar_system_ephemeris.set("builtin"):
        gcrs_frame = get_reference_frame(obstime=obstime, location=location)
        # WCS provides ICRS directions; move into the observer GCRS before
        # attaching topocentric/geocentric distance along that LOS.
        icrs_dir = SkyCoord(
            ra=ra_b * units.deg,
            dec=dec_b * units.deg,
            obstime=obstime,
            frame="icrs",
        )
        gcrs_dir = icrs_dir.transform_to(gcrs_frame)
        observer_coord = SkyCoord(
            ra=gcrs_dir.ra,
            dec=gcrs_dir.dec,
            distance=dist_b * units.au,
            frame=gcrs_frame,
        )
        return observer_coord.transform_to(HeliocentricTrueEcliptic(obstime=obstime))


def circular_mean_motion_rad_per_day(r_au: float | np.ndarray) -> float | np.ndarray:
    """Mean motion n = sqrt(GM/r^3) for a circular orbit at heliocentric r."""
    return np.sqrt(GM_SUN_AU3_DAY2 / np.asarray(r_au) ** 3)
