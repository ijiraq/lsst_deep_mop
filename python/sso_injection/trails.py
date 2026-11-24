# This file is part of sso_injection.
"""Propagate orbits to a visit and build stock Trail injection catalogs."""

from __future__ import annotations

__all__ = [
    "propagate_to_visit",
    "orbits_to_trail_catalog",
    "apply_catalog_units",
    "CATALOG_COLUMN_UNITS",
]

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.table import Table
from lsst.afw.geom import SkyWcs
from lsst.afw.image import VisitInfo
from lsst.geom import Box2D, Point2D

from .config import OrbitPopulationConfig
from .kepler import (
    apparent_magnitude,
    get_reference_frame,
    kepToHelioCartSkyCoord,
    propagate_orbits,
)

# Keplerian provenance columns carried into the written injection catalog.
_ORBIT_COLUMNS = ("a", "e", "inc", "Omega", "omega", "M", "H", "healpix", "dist_bin")

# Astropy units attached to written catalog columns (None ⇒ dimensionless / no unit).
# Angular orbital elements are stored in radians (see cartesian_to_keplerian).
CATALOG_COLUMN_UNITS: dict[str, u.Unit | None] = {
    "injection_id": None,
    "population": None,
    "ra": u.deg,
    "dec": u.deg,
    "dra": u.arcsec / u.hour,
    "ddec": u.arcsec / u.hour,
    "rate": u.arcsec / u.hour,
    "source_type": None,
    "mag": u.mag,
    "trail_length": u.pix,
    "beta": u.deg,
    "a": u.au,
    "e": None,
    "inc": u.rad,
    "Omega": u.rad,
    "omega": u.rad,
    "M": u.rad,
    "H": u.mag,
    "r": u.au,
    "delta": u.au,
    "healpix": None,
    "dist_bin": None,
}


def apply_catalog_units(table: Table) -> Table:
    """Attach ``CATALOG_COLUMN_UNITS`` to columns present on ``table`` (in place)."""
    for name, unit in CATALOG_COLUMN_UNITS.items():
        if name in table.colnames and unit is not None:
            table[name].unit = unit
    return table


def propagate_to_visit(
    orbits: Table,
    visitInfo: VisitInfo,
    rate_dt: u.Quantity = 24 * u.hour,
) -> Table:
    """
    Propagate Keplerian orbits to the visit epoch and compute sky rates.

    Returns a table with ra, dec, mag, rate, dra, ddec (arcsec/hour), angle
    (degree), heliocentric ``r`` and observer-centric ``delta`` (AU).
    """
    if len(orbits) == 0:
        return Table(
            names=(
                "injection_id",
                "ra",
                "dec",
                "mag",
                "rate",
                "dra",
                "ddec",
                "angle",
                "r",
                "delta",
                "H",
            ),
        )

    dt = rate_dt
    # Future epoch for finite-difference rate.
    frame2 = get_reference_frame(visitInfo, time_offset=dt)
    orbits2 = propagate_orbits(orbits.copy(), frame2.obstime.mjd)
    coordinates2, _ = kepToHelioCartSkyCoord(orbits2)
    coordinates2 = coordinates2.transform_to(frame2)
    coordinates2 = SkyCoord(
        coordinates2.ra,
        coordinates2.dec,
        distance=coordinates2.distance,
        obstime=coordinates2.obstime,
        frame="icrs",
    )

    frame = get_reference_frame(visitInfo)
    orbits_t = propagate_orbits(orbits.copy(), frame.obstime.mjd)
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

    rate = coordinates.separation(coordinates2) / dt
    position_angle = coordinates.position_angle(coordinates2)
    delta = coordinates.distance.to_value(u.au)
    mag = apparent_magnitude(np.asarray(r_helio), np.asarray(delta), 1.0, np.asarray(orbits_t["H"]))

    # On-sky rate components: PA is East of North.
    rate_asph = rate.to_value(u.arcsec / u.hour)
    pa_rad = position_angle.to_value(u.rad)
    dra = rate_asph * np.sin(pa_rad)
    ddec = rate_asph * np.cos(pa_rad)

    out = Table(
        {
            "injection_id": orbits_t["injection_id"],
            "ra": coordinates.ra.to_value(u.deg),
            "dec": coordinates.dec.to_value(u.deg),
            "mag": np.asarray(mag, dtype=float),
            "rate": rate_asph,
            "dra": np.asarray(dra, dtype=float),
            "ddec": np.asarray(ddec, dtype=float),
            "angle": position_angle.to_value(u.deg),
            "r": np.asarray(r_helio, dtype=float),
            "delta": np.asarray(delta, dtype=float),
            "H": orbits_t["H"],
        },
        meta={"day_obs": frame.obstime.isot},
    )
    return out


def orbits_to_trail_catalog(
    orbits: Table,
    visitInfo: VisitInfo,
    wcs: SkyWcs,
    bbox,
    config: OrbitPopulationConfig,
    pixel_scale_arcsec: float | None = None,
) -> Table:
    """
    Build a stock ``source_injection`` catalog (Trail or Star) for one detector.

    Selects objects that fall inside ``bbox`` on ``wcs``. FOV-clipped rows also
    carry Keplerian provenance, on-sky rates, and observer distance.
    """
    sky = propagate_to_visit(orbits, visitInfo)
    if len(sky) == 0:
        return _empty_injection_table(config.source_type)

    pad = 50.0
    box = Box2D(bbox)
    box.grow(pad)

    center = Point2D(bbox.getCenter())
    if pixel_scale_arcsec is None:
        pixel_scale_arcsec = wcs.getPixelScale(center).asArcseconds()

    # Coarse angular pre-cut so only nearby sources hit the WCS.
    sky_center = wcs.pixelToSky(center)
    ra0 = sky_center.getRa().asDegrees()
    dec0 = sky_center.getDec().asDegrees()
    radius_pix = 0.5 * float(np.hypot(bbox.getWidth(), bbox.getHeight())) + pad
    radius_deg = (radius_pix * float(pixel_scale_arcsec)) / 3600.0
    # Small margin for WCS distortion / flat-sky approximation.
    radius_deg *= 1.25

    ra = np.asarray(sky["ra"], dtype=float)
    dec = np.asarray(sky["dec"], dtype=float)
    cos_dec0 = np.cos(np.deg2rad(dec0))
    sep2 = ((ra - ra0) * cos_dec0) ** 2 + (dec - dec0) ** 2
    cand = sep2 <= radius_deg**2

    keep = np.zeros(len(sky), dtype=bool)
    if np.any(cand):
        cand_idx = np.flatnonzero(cand)
        try:
            x, y = wcs.skyToPixelArray(ra[cand], dec[cand], degrees=True)
        except TypeError:
            # Older afw: skyToPixelArray expects radians.
            x, y = wcs.skyToPixelArray(np.deg2rad(ra[cand]), np.deg2rad(dec[cand]))
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        inside = (
            (x >= box.getMinX())
            & (x <= box.getMaxX())
            & (y >= box.getMinY())
            & (y <= box.getMaxY())
            & np.isfinite(x)
            & np.isfinite(y)
        )
        keep[cand_idx[inside]] = True

    sky = sky[keep]
    if len(sky) == 0:
        return _empty_injection_table(config.source_type)

    # propagate_to_visit preserves row order, so the same mask applies to orbits.
    orbits_kept = orbits[keep]

    exptime_s = visitInfo.getExposureTime()
    if config.trail_dt_hours is not None:
        hours = float(config.trail_dt_hours)
    else:
        hours = float(exptime_s) / 3600.0 if exptime_s and exptime_s > 0 else 1.0 / 60.0

    # Physical trail length in pixels; slow movers are often sub-pixel (do not floor to 1).
    trail_length = (np.asarray(sky["rate"], dtype=float) * hours) / float(pixel_scale_arcsec)
    trail_length = np.maximum(trail_length, 0.0)

    source_type = config.source_type
    data = {
        "injection_id": sky["injection_id"],
        "ra": sky["ra"],
        "dec": sky["dec"],
        "dra": sky["dra"],
        "ddec": sky["ddec"],
        "rate": sky["rate"],
        "source_type": np.full(len(sky), source_type),
        "mag": sky["mag"],
        "trail_length": trail_length,
        "beta": sky["angle"],
        "r": sky["r"],
        "delta": sky["delta"],
    }
    for col in _ORBIT_COLUMNS:
        data[col] = np.asarray(orbits_kept[col])

    table = Table(data)
    if source_type != "Trail":
        table.remove_column("trail_length")
        table.remove_column("beta")
    return apply_catalog_units(table)


def _empty_injection_table(source_type: str) -> Table:
    cols = {
        "injection_id": np.array([], dtype=np.int64),
        "population": np.array([], dtype=str),
        "ra": np.array([], dtype=float),
        "dec": np.array([], dtype=float),
        "dra": np.array([], dtype=float),
        "ddec": np.array([], dtype=float),
        "rate": np.array([], dtype=float),
        "source_type": np.array([], dtype=str),
        "mag": np.array([], dtype=float),
        "a": np.array([], dtype=float),
        "e": np.array([], dtype=float),
        "inc": np.array([], dtype=float),
        "Omega": np.array([], dtype=float),
        "omega": np.array([], dtype=float),
        "M": np.array([], dtype=float),
        "H": np.array([], dtype=float),
        "r": np.array([], dtype=float),
        "delta": np.array([], dtype=float),
        "healpix": np.array([], dtype=np.int64),
        "dist_bin": np.array([], dtype=np.int32),
    }
    if source_type == "Trail":
        cols["trail_length"] = np.array([], dtype=float)
        cols["beta"] = np.array([], dtype=float)
    return apply_catalog_units(Table(cols))
