# This file is part of sso_injection.
"""Space–Distance MOC (heliocentric HEALPix × distance shells)."""

from __future__ import annotations

__all__ = ["SDMocCell", "SDMocIndex"]

from dataclasses import dataclass

import numpy as np
from astropy.coordinates import EarthLocation
from astropy.time import Time
from lsst.afw.image import VisitInfo

from .config import OrbitPopulationConfig
from .kepler import (
    circular_mean_motion_rad_per_day,
    geocenter_location,
    icrs_los_to_heliocentric,
    observer_location_from_visit_info,
)

try:
    import healpy as hp
except ImportError as exc:  # pragma: no cover
    raise ImportError("sso_injection requires healpy for SD-MOC indexing") from exc


@dataclass(frozen=True, order=True)
class SDMocCell:
    """One ownership cell: heliocentric HEALPix pixel × distance bin."""

    ipix: int
    dist_bin: int

    def key(self) -> tuple[int, int]:
        return (self.ipix, self.dist_bin)


class SDMocIndex:
    """Encode / query SD-MOC cells for a population config."""

    def __init__(self, config: OrbitPopulationConfig):
        self.config = config
        self.order = int(config.healpix_order)
        self.nside = 2**self.order
        edges = np.asarray(config.resolve_distance_edges(), dtype=float)
        if edges.size < 2:
            raise ValueError("distance shell edges must have at least two values")
        if np.any(np.diff(edges) <= 0):
            raise ValueError("distance shell edges must be strictly increasing")
        self.distance_edges = edges
        self.n_dist_bins = len(edges) - 1
        # Weights are uniform in r^2 (sky-rate proxy: rate ~ r**(-1/2)).
        self._r2_edges = edges**2
        self._r2_widths = np.diff(self._r2_edges)
        self._r2_total = float(self._r2_widths.sum())

    def dist_bin_center(self, dist_bin: int) -> float:
        """Representative heliocentric r for a bin (midpoint in r^2)."""
        return float(np.sqrt(0.5 * (self._r2_edges[dist_bin] + self._r2_edges[dist_bin + 1])))

    def dist_bin_area_factor(self, dist_bin: int) -> float:
        """Relative weight of a bin in distance-squared (sky-rate) measure."""
        return float(self._r2_widths[dist_bin])

    def pixel_area_deg2(self) -> float:
        return float(hp.nside2pixarea(self.nside, degrees=True))

    def n_objects_per_cell(self, dist_bin: int) -> int:
        """Expected object count in one HEALPix pixel for one distance bin."""
        # Total density is over [r_inner, r_outer]; split uniformly in r^2.
        weight = self._r2_widths[dist_bin] / self._r2_total
        n = self.config.density * self.pixel_area_deg2() * weight
        return max(int(np.round(n)), 0)

    def dist_bin_of_heliocentric_r(self, r_au: np.ndarray | float) -> np.ndarray:
        """Map heliocentric distance(s) to bin indices; -1 if outside the grid."""
        r = np.asarray(r_au, dtype=float)
        # bins: [edge0, edge1), ..., last bin includes the final edge.
        idx = np.digitize(r, self.distance_edges) - 1
        idx = np.where((idx >= 0) & (idx < self.n_dist_bins), idx, -1)
        # Include exact outer edge in the last bin.
        idx = np.where(np.isclose(r, self.distance_edges[-1]), self.n_dist_bins - 1, idx)
        return idx

    def _observer_distance_samples(self) -> np.ndarray:
        """
        Observer-centric distances (AU) that span the configured heliocentric shells.

        Earth is ~1 AU from the Sun, so sampling slightly outside the heliocentric
        edges keeps LOS transforms from missing shell boundaries.
        """
        pad = 1.5  # AU; covers Earth–Sun offset for topocentric Δ ↔ heliocentric r
        lo = float(self.distance_edges[0] - pad)
        hi = float(self.distance_edges[-1] + pad)
        # Bin edges + centers, plus padded endpoints.
        samples = list(self.distance_edges)
        samples.extend(self.dist_bin_center(i) for i in range(self.n_dist_bins))
        samples.extend([lo, hi])
        return np.unique(np.asarray(samples, dtype=float))

    def cells_for_visit(
        self,
        ra_deg: np.ndarray,
        dec_deg: np.ndarray,
        visit_mjd: float | None = None,
        *,
        visitInfo: VisitInfo | None = None,
        location: EarthLocation | None = None,
    ) -> list[SDMocCell]:
        """
        Return T0 ownership cells that may contribute to a visit FOV.

        FOV samples are ICRS directions. Each is given observer-centric distances
        spanning the population shells, converted with ``SkyCoord`` transforms
        into heliocentric true ecliptic, then mapped to SD-MOC cells. Coverage is
        expanded by circular-orbit motion over ``|T - T0|`` plus e/i fuzz.

        Parameters
        ----------
        ra_deg, dec_deg
            FOV polygon vertices (or a dense boundary sample) in ICRS degrees.
        visit_mjd
            Visit epoch T (used when ``visitInfo`` is not given).
        visitInfo
            Preferred source of epoch and observatory location.
        location
            Observer ``EarthLocation`` override. Defaults to ``visitInfo``'s
            observatory, else the geocenter.
        """
        if visitInfo is not None:
            obstime = visitInfo.date.toAstropy()
            if location is None:
                location = observer_location_from_visit_info(visitInfo)
        else:
            if visit_mjd is None:
                raise ValueError("Provide visitInfo or visit_mjd")
            obstime = Time(visit_mjd, format="mjd")
            if location is None:
                location = geocenter_location()

        visit_mjd = float(obstime.mjd)
        dt_days = abs(visit_mjd - self.config.model_epoch_mjd)

        ra = np.asarray(ra_deg, dtype=float)
        dec = np.asarray(dec_deg, dtype=float)
        delta_samples = self._observer_distance_samples()

        # Broadcast every FOV sample against every observer-distance sample.
        ra_grid = np.repeat(ra, delta_samples.size)
        dec_grid = np.repeat(dec, delta_samples.size)
        dist_grid = np.tile(delta_samples, ra.size)

        helio = icrs_los_to_heliocentric(
            ra_grid,
            dec_grid,
            dist_grid,
            obstime=obstime,
            location=location,
        )
        # HEALPix index matches sampling frame: heliocentric true ecliptic lon/lat.
        lon = helio.lon.to_value("deg")
        lat = helio.lat.to_value("deg")
        r_helio = helio.distance.to_value("au")
        theta = np.deg2rad(90.0 - lat)
        phi = np.deg2rad(lon)
        ipix_all = hp.ang2pix(self.nside, theta, phi, nest=True)
        dist_bins = self.dist_bin_of_heliocentric_r(r_helio)

        base_by_bin: dict[int, set[int]] = {b: set() for b in range(self.n_dist_bins)}
        for ipix, db in zip(ipix_all.tolist(), dist_bins.tolist(), strict=True):
            if db < 0:
                continue
            base_by_bin[int(db)].add(int(ipix))

        # Neighbours of geometric FOV pixels for edge coverage.
        for db, pix_set in base_by_bin.items():
            fov_pix = set(pix_set)
            for p in list(pix_set):
                fov_pix.update(hp.get_all_neighbours(self.nside, p, nest=True).tolist())
            fov_pix.discard(-1)
            base_by_bin[db] = fov_pix

        cells: set[SDMocCell] = set()
        fuzz_rad = np.deg2rad(self.config.inclination_fuzz_deg)
        min_resol = hp.nside2resol(self.nside, arcmin=True) / 60.0 * np.pi / 180.0
        for dist_bin, fov_pix in base_by_bin.items():
            if not fov_pix:
                continue
            r = self.dist_bin_center(dist_bin)
            n_circ = circular_mean_motion_rad_per_day(r)
            expand_rad = float(n_circ * dt_days) * (1.0 + self.config.eccentricity_fuzz) + fuzz_rad
            expand_rad = max(expand_rad, min_resol)
            for p in fov_pix:
                vec = hp.pix2vec(self.nside, p, nest=True)
                disc = hp.query_disc(self.nside, vec, expand_rad, nest=True, inclusive=True)
                for ipix in disc:
                    cells.add(SDMocCell(int(ipix), int(dist_bin)))
        return sorted(cells)

    def bbox_corners_to_polygon(
        self,
        ra0: float,
        dec0: float,
        ra1: float,
        dec1: float,
        n_edge: int = 8,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Sample a RA/Dec rectangle boundary for HEALPix queries."""
        ras = []
        decs = []
        for f in np.linspace(0, 1, n_edge, endpoint=False):
            ras.extend([ra0 + f * (ra1 - ra0), ra1, ra1 - f * (ra1 - ra0), ra0])
            decs.extend([dec0, dec0 + f * (dec1 - dec0), dec1, dec1 - f * (dec1 - dec0)])
        return np.asarray(ras), np.asarray(decs)

    def cell_seed(self, cell: SDMocCell) -> int:
        """Deterministic per-cell seed derived from the master seed."""
        # Stable 64-bit mix without requiring extra deps.
        x = (
            int(self.config.master_seed) ^ (cell.ipix * 0x9E3779B97F4A7C15) ^ (cell.dist_bin << 32)
        ) & 0xFFFFFFFFFFFFFFFF
        x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
        x = (x ^ (x >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
        return int(x & 0x7FFFFFFF)
