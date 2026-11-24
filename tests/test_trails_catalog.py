# This file is part of sso_injection.
"""Tests for FOV-clipped injection catalogs retaining orbital elements."""

from __future__ import annotations

import unittest
from unittest import mock

import numpy as np
from astropy import units as u
from astropy.table import Table

try:
    from lsst.geom import Point2D

    from sso_injection.config import OrbitPopulationConfig
    from sso_injection.trails import (
        CATALOG_COLUMN_UNITS,
        _ORBIT_COLUMNS,
        _empty_injection_table,
        orbits_to_trail_catalog,
    )

    _HAVE_LSST = True
except ImportError:  # pragma: no cover - local env without Science Pipelines
    _HAVE_LSST = False


@unittest.skipUnless(_HAVE_LSST, "lsst Science Pipelines required")
class TrailsCatalogTestCase(unittest.TestCase):
    def test_empty_table_has_orbit_columns(self):
        table = _empty_injection_table("Trail")
        for col in _ORBIT_COLUMNS:
            self.assertIn(col, table.colnames)
        for col in (
            "injection_id",
            "population",
            "ra",
            "dec",
            "dra",
            "ddec",
            "rate",
            "delta",
            "r",
            "source_type",
            "mag",
            "trail_length",
            "beta",
        ):
            self.assertIn(col, table.colnames)
        self.assertEqual(table["inc"].unit, u.rad)
        self.assertEqual(table["dra"].unit, u.arcsec / u.hour)
        self.assertEqual(table["delta"].unit, u.au)

    def test_fov_catalog_retains_orbit_columns(self):
        n = 5
        orbits = Table(
            {
                "injection_id": np.arange(n, dtype=np.int64),
                "a": np.full(n, 40.0),
                "e": np.full(n, 0.1),
                "inc": np.full(n, 0.2),
                "Omega": np.full(n, 1.0),
                "omega": np.full(n, 0.5),
                "M": np.linspace(0.0, 5.0, n),
                "H": np.full(n, 8.0),
                "healpix": np.full(n, 123, dtype=np.int64),
                "dist_bin": np.zeros(n, dtype=np.int32),
            }
        )
        # rate=0.5 "/hr, 300 s, 0.168 "/pix → trail_length ≈ 0.248 (must not floor to 1).
        sky = Table(
            {
                "injection_id": orbits["injection_id"],
                "ra": np.array([10.0, 10.01, 50.0, 10.02, 80.0]),
                "dec": np.array([0.0, 0.01, 40.0, -0.01, -50.0]),
                "mag": np.full(n, 24.0),
                "rate": np.full(n, 0.5),
                "dra": np.full(n, 0.3),
                "ddec": np.full(n, 0.4),
                "angle": np.full(n, 45.0),
                "r": np.full(n, 40.0),
                "delta": np.full(n, 39.0),
                "H": orbits["H"],
            }
        )

        class _Angle:
            def __init__(self, deg):
                self._deg = deg

            def asDegrees(self):
                return self._deg

            def asArcseconds(self):
                return self._deg * 3600.0

        class _SkyPoint:
            def getRa(self):
                return _Angle(10.0)

            def getDec(self):
                return _Angle(0.0)

        class _Wcs:
            def pixelToSky(self, pt):
                return _SkyPoint()

            def getPixelScale(self, pt):
                return _Angle(0.168 / 3600.0)

            def skyToPixelArray(self, ra, dec, degrees=True):
                ra = np.asarray(ra, dtype=float)
                # Map sources near (10, 0) into the bbox; others far away.
                x = np.where(np.abs(ra - 10.0) < 1.0, 100.0, 1.0e6)
                y = np.full(ra.shape, 100.0)
                return x, y

        class _BBox:
            def getCenter(self):
                return Point2D(100.0, 100.0)

            def getWidth(self):
                return 200.0

            def getHeight(self):
                return 200.0

            def __iter__(self):
                return iter(())

        class _VisitInfo:
            def getExposureTime(self):
                return 300.0

        config = OrbitPopulationConfig()
        config.source_type = "Trail"

        fake_box = mock.Mock()
        fake_box.getMinX.return_value = 0.0
        fake_box.getMaxX.return_value = 200.0
        fake_box.getMinY.return_value = 0.0
        fake_box.getMaxY.return_value = 200.0
        fake_box.grow = mock.Mock()

        with (
            mock.patch("sso_injection.trails.propagate_to_visit", return_value=sky),
            mock.patch("sso_injection.trails.Box2D", return_value=fake_box),
            mock.patch("sso_injection.trails.Point2D", side_effect=lambda p: p),
        ):
            catalog = orbits_to_trail_catalog(
                orbits,
                _VisitInfo(),
                _Wcs(),
                _BBox(),
                config,
                pixel_scale_arcsec=0.168,
            )

        self.assertGreater(len(catalog), 0)
        self.assertLess(len(catalog), n)
        for col in _ORBIT_COLUMNS:
            self.assertIn(col, catalog.colnames)
        for col in ("dra", "ddec", "rate", "delta", "r", "trail_length", "beta"):
            self.assertIn(col, catalog.colnames)
        expected_trail = 0.5 * (300.0 / 3600.0) / 0.168
        np.testing.assert_allclose(catalog["trail_length"], expected_trail, rtol=1e-6)
        self.assertTrue(np.all(np.asarray(catalog["trail_length"]) < 1.0))
        self.assertEqual(catalog["inc"].unit, CATALOG_COLUMN_UNITS["inc"])
        self.assertEqual(catalog["dra"].unit, CATALOG_COLUMN_UNITS["dra"])
        np.testing.assert_array_equal(catalog["delta"], 39.0)
        # Surviving rows keep the orbit values from the input table.
        for iid, a in zip(catalog["injection_id"], catalog["a"], strict=True):
            self.assertEqual(float(a), 40.0)
            self.assertIn(int(iid), (0, 1, 3))


if __name__ == "__main__":
    unittest.main()
