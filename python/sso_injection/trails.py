# This file is part of sso_injection.
"""Propagate orbits to a visit and build stock Trail injection catalogs."""

from __future__ import annotations

__all__ = ["propagate_to_visit", "orbits_to_trail_catalog"]

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


def propagate_to_visit(
    orbits: Table,
    visitInfo: VisitInfo,
    rate_dt: u.Quantity = 24 * u.hour,
) -> Table:
    """
    Propagate Keplerian orbits to the visit epoch and compute sky rates.

    Returns a table with ra, dec, mag, rate (arcsec/hour), angle (degree).
    """
    if len(orbits) == 0:
        return Table(
            names=("injection_id", "ra", "dec", "mag", "rate", "angle", "r", "delta", "H"),
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

    out = Table(
        {
            "injection_id": orbits_t["injection_id"],
            "ra": coordinates.ra.to_value(u.deg),
            "dec": coordinates.dec.to_value(u.deg),
            "mag": np.asarray(mag, dtype=float),
            "rate": rate.to_value(u.arcsec / u.hour),
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
    carry the Keplerian provenance columns from ``orbits``.
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

    # trail_length in pixels: (arcsec/hour * hours) / (arcsec/pixel)
    trail_length = (np.asarray(sky["rate"], dtype=float) * hours) / float(pixel_scale_arcsec)
    trail_length = np.maximum(trail_length, 1.0)

    source_type = config.source_type
    data = {
        "injection_id": sky["injection_id"],
        "ra": sky["ra"],
        "dec": sky["dec"],
        "source_type": np.full(len(sky), source_type),
        "mag": sky["mag"],
        "trail_length": trail_length,
        "beta": sky["angle"],
    }
    for col in _ORBIT_COLUMNS:
        data[col] = np.asarray(orbits_kept[col])

    table = Table(data)
    if source_type != "Trail":
        table.remove_column("trail_length")
        table.remove_column("beta")
    return table


def _empty_injection_table(source_type: str) -> Table:
    cols = {
        "injection_id": np.array([], dtype=np.int64),
        "ra": np.array([], dtype=float),
        "dec": np.array([], dtype=float),
        "source_type": np.array([], dtype=str),
        "mag": np.array([], dtype=float),
        "a": np.array([], dtype=float),
        "e": np.array([], dtype=float),
        "inc": np.array([], dtype=float),
        "Omega": np.array([], dtype=float),
        "omega": np.array([], dtype=float),
        "M": np.array([], dtype=float),
        "H": np.array([], dtype=float),
        "healpix": np.array([], dtype=np.int64),
        "dist_bin": np.array([], dtype=np.int32),
    }
    if source_type == "Trail":
        cols["trail_length"] = np.array([], dtype=float)
        cols["beta"] = np.array([], dtype=float)
    return Table(cols)
