"""Measure aperture flux and refined centroid at a known sky position."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import lsst.geom as geom
from lsst.afw.detection import Footprint
from lsst.afw.geom import SpanSet
from lsst.afw.table import SourceCatalog, SourceTable
from lsst.meas.base import SingleFrameMeasurementConfig, SingleFrameMeasurementTask

_MEASUREMENT_TASK: Optional[SingleFrameMeasurementTask] = None


@dataclass(frozen=True)
class SourceMeasurement:
    """Pipeline flux and centroid measurement at a fixed location."""

    x: float
    y: float
    ra_deg: float
    dec_deg: float
    inst_flux: float
    inst_flux_err: float
    ap_flux: float
    ap_flux_err: float
    mag: float
    mag_err: float
    centroid_flag: bool
    flux_flag: bool
    init_x: float
    init_y: float


def _get_measurement_task() -> SingleFrameMeasurementTask:
    global _MEASUREMENT_TASK
    if _MEASUREMENT_TASK is None:
        schema = SourceTable.makeMinimalSchema()
        config = SingleFrameMeasurementConfig()
        _MEASUREMENT_TASK = SingleFrameMeasurementTask(schema=schema, config=config)
    return _MEASUREMENT_TASK


def _resolve_pixel_position(
    exposure,
    *,
    x: Optional[float],
    y: Optional[float],
    ra: Optional[float],
    dec: Optional[float],
) -> tuple[float, float]:
    has_xy = x is not None and y is not None
    has_radec = ra is not None and dec is not None

    if has_xy == has_radec:
        raise ValueError("Provide exactly one of (x, y) or (ra, dec).")

    if has_radec:
        sky = geom.SpherePoint(ra * geom.degrees, dec * geom.degrees)
        pixel = exposure.getWcs().skyToPixel(sky)
        return pixel.getX(), pixel.getY()

    return float(x), float(y)


def _footprint_half_size(aperture_radius: float) -> int:
    return max(int(math.ceil(3.0 * aperture_radius)), 30)


def _make_footprint(
    x: float,
    y: float,
    exposure,
    aperture_radius: float,
) -> Footprint:
    half_size = _footprint_half_size(aperture_radius)
    bbox = exposure.getBBox()
    ix = int(round(x))
    iy = int(round(y))

    min_x = max(bbox.getMinX(), ix - half_size)
    min_y = max(bbox.getMinY(), iy - half_size)
    max_x = min(bbox.getMaxX(), ix + half_size)
    max_y = min(bbox.getMaxY(), iy + half_size)

    if max_x <= min_x or max_y <= min_y:
        raise ValueError(
            f"Position ({x:.3f}, {y:.3f}) is outside exposure bbox {bbox}."
        )

    span_bbox = geom.Box2I(
        geom.Point2I(min_x, min_y),
        geom.Extent2I(max_x - min_x + 1, max_y - min_y + 1),
    )
    return Footprint(SpanSet(span_bbox))


def _flux_field_name(prefix: str, aperture_radius: float, suffix: str) -> str:
    radius_label = (
        f"{aperture_radius:.0f}"
        if float(aperture_radius).is_integer()
        else str(aperture_radius).replace(".", "_")
    )
    return f"{prefix}_{radius_label}{suffix}"


def _safe_float(value) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(result):
        return float("nan")
    return result


def measure_source_at(
    exposure,
    *,
    x: Optional[float] = None,
    y: Optional[float] = None,
    ra: Optional[float] = None,
    dec: Optional[float] = None,
    aperture_radius: float = 12.0,
) -> SourceMeasurement:
    """Measure compensated aperture flux and refined centroid at a location.

    Parameters
    ----------
    exposure : `lsst.afw.image.Exposure`
        Cutout or full-frame exposure to measure.
    x, y : float, optional
        Initial source position in exposure pixel coordinates.
    ra, dec : float, optional
        Initial source position in degrees; converted with the exposure WCS.
    aperture_radius : float, optional
        Aperture radius in pixels. Default is 12, matching pipeline SFM.

    Returns
    -------
    SourceMeasurement
        Structured measurement result.
    """
    init_x, init_y = _resolve_pixel_position(
        exposure, x=x, y=y, ra=ra, dec=dec
    )

    task = _get_measurement_task()
    schema = task.schema
    table = SourceTable.make(schema)
    catalog = SourceCatalog(table)
    record = catalog.addNew()
    record.set(schema["base_SdssCentroid_x"].asKey(), init_x)
    record.set(schema["base_SdssCentroid_y"].asKey(), init_y)
    record.setFootprint(_make_footprint(init_x, init_y, exposure, aperture_radius))

    task.callMeasure(record, exposure)

    centroid_flag = bool(record.get("base_SdssCentroid_flag"))
    if centroid_flag:
        record.set(schema["base_SdssCentroid_x"].asKey(), init_x)
        record.set(schema["base_SdssCentroid_y"].asKey(), init_y)

    centroid = record.getCentroid()
    final_x = float(centroid.getX())
    final_y = float(centroid.getY())

    inst_flux_name = _flux_field_name(
        "base_CompensatedTophatFlux", aperture_radius, "_instFlux"
    )
    inst_flux_err_name = _flux_field_name(
        "base_CompensatedTophatFlux", aperture_radius, "_instFluxErr"
    )
    ap_flux_name = _flux_field_name(
        "base_CircularApertureFlux", aperture_radius, "_0_instFlux"
    )
    ap_flux_err_name = _flux_field_name(
        "base_CircularApertureFlux", aperture_radius, "_0_instFluxErr"
    )
    flux_flag_name = _flux_field_name(
        "base_CompensatedTophatFlux", aperture_radius, "_flag"
    )

    inst_flux = _safe_float(record.get(inst_flux_name))
    inst_flux_err = _safe_float(record.get(inst_flux_err_name))
    ap_flux = _safe_float(record.get(ap_flux_name))
    ap_flux_err = _safe_float(record.get(ap_flux_err_name))
    flux_flag = bool(record.get(flux_flag_name))

    sky = exposure.getWcs().pixelToSky(centroid)
    ra_deg = sky.getRa().asDegrees()
    dec_deg = sky.getDec().asDegrees()

    mag = float("nan")
    mag_err = float("nan")
    if inst_flux > 0.0 and not math.isnan(inst_flux_err) and inst_flux_err >= 0.0:
        mag_result = exposure.getPhotoCalib().instFluxToMagnitude(
            inst_flux, inst_flux_err
        )
        mag = float(mag_result.value)
        mag_err = float(mag_result.error)

    return SourceMeasurement(
        x=final_x,
        y=final_y,
        ra_deg=ra_deg,
        dec_deg=dec_deg,
        inst_flux=inst_flux,
        inst_flux_err=inst_flux_err,
        ap_flux=ap_flux,
        ap_flux_err=ap_flux_err,
        mag=mag,
        mag_err=mag_err,
        centroid_flag=centroid_flag,
        flux_flag=flux_flag,
        init_x=init_x,
        init_y=init_y,
    )
