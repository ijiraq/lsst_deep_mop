# This file is part of sso_injection.
"""
Validate cartesian ↔ Keplerian conversion against JPL Horizons (Arrokoth).

Requires network access and ``astroquery``. Skips cleanly when unavailable.
"""

from __future__ import annotations

import unittest

import numpy as np

try:
    from astroquery.jplhorizons import Horizons
except ImportError:  # pragma: no cover
    Horizons = None

from astropy.time import Time

from sso_injection.kepler import cartesian_to_keplerian, keplerian_to_cartesian

ARROKOTH_ID = "486958;"
EPOCH = "2022-06-20"


def _horizons_available() -> bool:
    if Horizons is None:
        return False
    try:
        obj = Horizons(
            id=ARROKOTH_ID,
            location="500@10",
            epochs=Time(EPOCH).tdb.jd,
            id_type="smallbody",
        )
        obj.vectors(refplane="ecliptic")
        return True
    except Exception:
        return False


@unittest.skipUnless(_horizons_available(), "astroquery / JPL Horizons unavailable")
class KeplerHorizonsTestCase(unittest.TestCase):
    """Compare our converters to heliocentric ecliptic Horizons products."""

    @classmethod
    def setUpClass(cls):
        cls.obstime = Time(EPOCH)
        obj = Horizons(
            id=ARROKOTH_ID,
            location="500@10",
            epochs=cls.obstime.tdb.jd,
            id_type="smallbody",
        )
        cls.vec = obj.vectors(refplane="ecliptic")
        cls.el = obj.elements(refplane="ecliptic")

    @staticmethod
    def _q(value) -> float:
        return float(np.asarray(value))

    def test_cartesian_to_keplerian_matches_horizons_elements(self):
        xyz = np.array(
            [
                [self._q(self.vec["x"][0])],
                [self._q(self.vec["y"][0])],
                [self._q(self.vec["z"][0])],
            ]
        )
        # Horizons vectors are AU / day; API expects AU / year.
        vxyz = (
            np.array(
                [
                    [self._q(self.vec["vx"][0])],
                    [self._q(self.vec["vy"][0])],
                    [self._q(self.vec["vz"][0])],
                ]
            )
            * 365.25
        )
        got = cartesian_to_keplerian(xyz, vxyz)

        self.assertAlmostEqual(got["a"][0], self._q(self.el["a"][0]), places=6)
        self.assertAlmostEqual(got["e"][0], self._q(self.el["e"][0]), places=8)
        self.assertAlmostEqual(
            np.rad2deg(got["inc"][0]), self._q(self.el["incl"][0]), places=8
        )
        self.assertAlmostEqual(
            np.rad2deg(got["Omega"][0]), self._q(self.el["Omega"][0]), places=6
        )
        self.assertAlmostEqual(
            np.rad2deg(got["omega"][0]), self._q(self.el["w"][0]), places=6
        )
        self.assertAlmostEqual(
            np.rad2deg(got["M"][0]), self._q(self.el["M"][0]), places=6
        )

    def test_keplerian_to_cartesian_matches_horizons_state(self):
        orb = dict(
            a=np.array([self._q(self.el["a"][0])]),
            e=np.array([self._q(self.el["e"][0])]),
            inc=np.deg2rad([self._q(self.el["incl"][0])]),
            Omega=np.deg2rad([self._q(self.el["Omega"][0])]),
            omega=np.deg2rad([self._q(self.el["w"][0])]),
            M=np.deg2rad([self._q(self.el["M"][0])]),
        )
        xyz, vxyz = keplerian_to_cartesian(**orb)
        jpl_xyz = np.array(
            [
                self._q(self.vec["x"][0]),
                self._q(self.vec["y"][0]),
                self._q(self.vec["z"][0]),
            ]
        )
        jpl_v = (
            np.array(
                [
                    self._q(self.vec["vx"][0]),
                    self._q(self.vec["vy"][0]),
                    self._q(self.vec["vz"][0]),
                ]
            )
            * 365.25
        )
        np.testing.assert_allclose(xyz[:, 0], jpl_xyz, rtol=0, atol=1e-9)
        # Velocity agrees to ~1e-5 relative; residual is mostly GM convention
        # (Horizons osculating GM vs our Gaussian solar GM).
        np.testing.assert_allclose(vxyz[:, 0], jpl_v, rtol=1e-4, atol=1e-6)

    def test_round_trip_state_to_elements_to_state(self):
        xyz = np.array(
            [
                [self._q(self.vec["x"][0])],
                [self._q(self.vec["y"][0])],
                [self._q(self.vec["z"][0])],
            ]
        )
        vxyz = (
            np.array(
                [
                    [self._q(self.vec["vx"][0])],
                    [self._q(self.vec["vy"][0])],
                    [self._q(self.vec["vz"][0])],
                ]
            )
            * 365.25
        )
        el = cartesian_to_keplerian(xyz, vxyz)
        xyz2, vxyz2 = keplerian_to_cartesian(
            a=el["a"],
            e=el["e"],
            inc=el["inc"],
            Omega=el["Omega"],
            omega=el["omega"],
            M=el["M"],
        )
        np.testing.assert_allclose(xyz2, xyz, atol=1e-9)
        np.testing.assert_allclose(vxyz2, vxyz, rtol=1e-4, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
