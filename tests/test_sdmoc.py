# This file is part of sso_injection.
"""Basic SD-MOC index and sampling tests (healpy + astropy required)."""

from __future__ import annotations

import time
import unittest

import healpy as hp
import numpy as np
from astropy.coordinates import EarthLocation
from astropy.time import Time

from sso_injection.config import OrbitPopulationConfig, equal_r2_distance_edges
from sso_injection.kepler import icrs_los_to_heliocentric
from sso_injection.sample import sample_sdmoc_cell, sample_sdmoc_cells
from sso_injection.sdmoc import SDMocCell, SDMocIndex


class SdmocTestCase(unittest.TestCase):
    def setUp(self):
        self.config = OrbitPopulationConfig()
        self.config.density = 100.0  # keep tests light
        self.config.healpix_order = 4
        self.config.distance_inner_au = 30.0
        self.config.distance_outer_au = 50.0
        self.config.n_distance_bins = 2
        self.config.distance_bin_edges_au = []
        self.config.model_epoch_mjd = 60000.0
        self.index = SDMocIndex(self.config)

    def test_equal_r2_edges_and_weights(self):
        edges = equal_r2_distance_edges(30.0, 50.0, 2)
        np.testing.assert_allclose(np.diff(np.asarray(edges) ** 2), np.diff(np.asarray(edges) ** 2)[0])
        # Equal-r^2 bins ⇒ equal object counts per bin for a fixed HEALPix pixel.
        n0 = self.index.n_objects_per_cell(0)
        n1 = self.index.n_objects_per_cell(1)
        self.assertEqual(n0, n1)

    def test_cell_counts(self):
        n0 = self.index.n_objects_per_cell(0)
        self.assertGreaterEqual(n0, 0)

    def test_visit_cells_nonempty_geocenter(self):
        # Small patch near ecliptic; observer defaults to geocenter.
        ras = np.array([10.0, 10.5, 10.5, 10.0])
        decs = np.array([-1.0, -1.0, 1.0, 1.0])
        cells = self.index.cells_for_visit(ras, decs, visit_mjd=60000.0)
        self.assertGreater(len(cells), 0)
        self.assertTrue(all(isinstance(c, SDMocCell) for c in cells))

    def test_visit_cells_with_observatory_location(self):
        ras = np.array([10.0, 10.5, 10.5, 10.0])
        decs = np.array([-1.0, -1.0, 1.0, 1.0])
        # Subaru / Maunakea-ish geodetic site
        location = EarthLocation.from_geodetic(-155.476, 19.825, 4139.0)
        cells = self.index.cells_for_visit(ras, decs, visit_mjd=60000.0, location=location)
        self.assertGreater(len(cells), 0)

    def test_icrs_los_transform_returns_heliocentric(self):
        obstime = Time(60000.0, format="mjd")
        helio = icrs_los_to_heliocentric(10.0, 0.0, 40.0, obstime=obstime)
        self.assertEqual(helio.frame.name, "heliocentrictrueecliptic")
        dist_au = float(np.asarray(helio.distance.to_value("au")).ravel()[0])
        self.assertGreater(dist_au, 30.0)
        self.assertLess(dist_au, 50.0)

    def test_sample_cell_deterministic(self):
        cell = SDMocCell(ipix=0, dist_bin=0)
        t1 = sample_sdmoc_cell(cell, self.index)
        t2 = sample_sdmoc_cell(cell, self.index)
        if len(t1) == 0:
            self.skipTest("pixel 0 produced zero objects at this density")
        np.testing.assert_array_equal(t1["injection_id"], t2["injection_id"])
        np.testing.assert_allclose(t1["a"], t2["a"])

    def test_mean_anomaly_not_pinned_to_apoapsis(self):
        """Regression: tangential |v|<v_circ sampling collapsed M to ~180 deg."""
        self.config.density = 5000.0
        index = SDMocIndex(self.config)
        # Use a mid-latitude-ish pixel that is usually populated.
        cell = SDMocCell(ipix=100, dist_bin=0)
        table = sample_sdmoc_cell(cell, index, config=self.config)
        if len(table) < 50:
            self.skipTest("too few samples in test pixel")
        m_deg = np.rad2deg(np.asarray(table["M"]))
        frac_near_180 = np.mean((m_deg > 170.0) & (m_deg < 190.0))
        self.assertLess(frac_near_180, 0.15)

    def test_sampled_positions_stay_in_cell(self):
        """Every object maps back to its ownership HEALPix pixel and distance shell."""
        self.config.density = 2000.0
        index = SDMocIndex(self.config)
        cells = [SDMocCell(ipix=100, dist_bin=0), SDMocCell(ipix=200, dist_bin=1)]
        table = sample_sdmoc_cells(cells, index, config=self.config)
        self.assertGreater(len(table), 0)

        # Reconstruct heliocentric direction from Keplerian state at T0 via a,e,M → r,ν.
        # Ownership uses the sampled position; healpix/dist_bin columns are authoritative.
        for cell in cells:
            rows = table[table["healpix"] == cell.ipix]
            rows = rows[rows["dist_bin"] == cell.dist_bin]
            self.assertGreater(len(rows), 0)
            # Positions are owned by the cell: verify healpix column matches ang2pix of
            # a circular proxy at the drawn r from a(1-e^2)/(1+e cos ν).
            e = np.asarray(rows["e"], dtype=float)
            M = np.asarray(rows["M"], dtype=float)
            a = np.asarray(rows["a"], dtype=float)
            from sso_injection.kepler import true_anomaly_from_mean

            nu = true_anomaly_from_mean(e, M)
            r = a * (1.0 - e**2) / (1.0 + e * np.cos(nu))
            r_lo = index.distance_edges[cell.dist_bin]
            r_hi = index.distance_edges[cell.dist_bin + 1]
            self.assertTrue(np.all(r >= r_lo - 1e-6))
            self.assertTrue(np.all(r <= r_hi + 1e-6))
            np.testing.assert_array_equal(rows["healpix"], cell.ipix)

            # Direction of the orbital position at T0 should lie in the cell pixel.
            # Build unit vector from Ω, i, ω, ν (standard perifocal → ecliptic).
            Omega = np.asarray(rows["Omega"], dtype=float)
            omega = np.asarray(rows["omega"], dtype=float)
            inc = np.asarray(rows["inc"], dtype=float)
            cos_O, sin_O = np.cos(Omega), np.sin(Omega)
            cos_w, sin_w = np.cos(omega + nu), np.sin(omega + nu)
            cos_i, sin_i = np.cos(inc), np.sin(inc)
            x = cos_O * cos_w - sin_O * sin_w * cos_i
            y = sin_O * cos_w + cos_O * sin_w * cos_i
            z = sin_w * sin_i
            ipix = hp.vec2pix(index.nside, x, y, z, nest=True)
            np.testing.assert_array_equal(ipix, cell.ipix)

    def test_single_cell_matches_batch(self):
        """A cell sampled alone equals that cell's rows inside a multi-cell batch."""
        self.config.density = 500.0
        index = SDMocIndex(self.config)
        cells = [
            SDMocCell(ipix=50, dist_bin=0),
            SDMocCell(ipix=51, dist_bin=0),
            SDMocCell(ipix=52, dist_bin=1),
        ]
        target = cells[1]
        alone = sample_sdmoc_cell(target, index, config=self.config)
        batch = sample_sdmoc_cells(cells, index, config=self.config)
        if len(alone) == 0:
            self.skipTest("target cell produced zero objects")
        alone_ids = set(np.asarray(alone["injection_id"]))
        batch_ids = set(np.asarray(batch["injection_id"]))
        self.assertTrue(alone_ids.issubset(batch_ids))
        matched = batch[np.isin(batch["injection_id"], alone["injection_id"])]
        matched = matched[np.argsort(matched["injection_id"])]
        alone_sorted = alone[np.argsort(alone["injection_id"])]
        np.testing.assert_array_equal(matched["injection_id"], alone_sorted["injection_id"])
        for col in ("a", "e", "inc", "Omega", "omega", "M", "H"):
            np.testing.assert_allclose(matched[col], alone_sorted[col], rtol=1e-12, atol=1e-12)

    def test_inclination_respects_limit(self):
        """Inclinations satisfy i <= max(i_max, |lat|) including a tiny i_max."""
        self.config.density = 2000.0
        self.config.inclination_max_deg = 0.01
        index = SDMocIndex(self.config)
        # Pixel near ecliptic so |lat| can be below i_max for some draws.
        cell = SDMocCell(ipix=100, dist_bin=0)
        table = sample_sdmoc_cell(cell, index, config=self.config)
        if len(table) == 0:
            self.skipTest("empty cell")
        i_max = np.deg2rad(self.config.inclination_max_deg)
        e = np.asarray(table["e"], dtype=float)
        M = np.asarray(table["M"], dtype=float)
        a = np.asarray(table["a"], dtype=float)
        Omega = np.asarray(table["Omega"], dtype=float)
        omega = np.asarray(table["omega"], dtype=float)
        inc = np.asarray(table["inc"], dtype=float)
        from sso_injection.kepler import true_anomaly_from_mean

        nu = true_anomaly_from_mean(e, M)
        cos_O, sin_O = np.cos(Omega), np.sin(Omega)
        cos_w, sin_w = np.cos(omega + nu), np.sin(omega + nu)
        cos_i, sin_i = np.cos(inc), np.sin(inc)
        z = sin_w * sin_i
        # |lat| from z of unit position vector.
        lat = np.arcsin(np.clip(z, -1.0, 1.0))
        allowed = np.maximum(i_max, np.abs(lat))
        self.assertTrue(np.all(inc <= allowed + 1e-9))

    def test_sample_cells_is_fast(self):
        """A few hundred cells should sample in well under a second."""
        self.config.density = 100.0
        self.config.healpix_order = 6
        index = SDMocIndex(self.config)
        cells = [SDMocCell(ipix=i, dist_bin=i % 2) for i in range(300)]
        t0 = time.perf_counter()
        table = sample_sdmoc_cells(cells, index, config=self.config)
        elapsed = time.perf_counter() - t0
        self.assertGreater(len(table), 0)
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    unittest.main()
