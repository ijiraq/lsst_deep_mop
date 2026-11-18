# This file is part of sso_injection.
"""Basic SD-MOC index and sampling tests (healpy + astropy required)."""

from __future__ import annotations

import unittest

import numpy as np
from astropy.coordinates import EarthLocation
from astropy.time import Time

from sso_injection.config import OrbitPopulationConfig, equal_r2_distance_edges
from sso_injection.kepler import icrs_los_to_heliocentric
from sso_injection.sample import sample_sdmoc_cell
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
        self.assertGreater(float(helio.distance.to_value("au")), 30.0)
        self.assertLess(float(helio.distance.to_value("au")), 50.0)

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


if __name__ == "__main__":
    unittest.main()
