# This file is part of lsst_deep_mop.
"""Config tests for multi-population GenerateSsoInjectionCatalogTask."""

from __future__ import annotations

import unittest

from sso_injection.config import OrbitPopulationConfig
from sso_injection.generateSsoInjectionCatalog import (
    GenerateSsoInjectionCatalogConfig,
    _mix_population_seed,
)


def _resolve_populations(config: GenerateSsoInjectionCatalogConfig):
    """Mirror GenerateSsoInjectionCatalogTask._resolve_populations for unit tests."""
    named = dict(config.populations.items())
    if named:
        return list(named.items())
    return [("default", config.population)]


class GenerateSsoInjectionCatalogConfigTestCase(unittest.TestCase):
    def test_populations_round_trip(self):
        config = GenerateSsoInjectionCatalogConfig()
        self.assertEqual(len(config.populations), 0)

        centaur = OrbitPopulationConfig()
        centaur.density = 600.0
        centaur.distance_inner_au = 5.0
        centaur.distance_outer_au = 20.0
        config.populations["centaur"] = centaur

        tno = OrbitPopulationConfig()
        tno.density = 1200.0
        tno.distance_inner_au = 30.0
        tno.distance_outer_au = 50.0
        config.populations["tno"] = tno

        self.assertEqual(set(config.populations.keys()), {"centaur", "tno"})
        self.assertEqual(config.populations["centaur"].density, 600.0)
        self.assertEqual(config.populations["tno"].density, 1200.0)

    def test_population_fallback_when_populations_empty(self):
        config = GenerateSsoInjectionCatalogConfig()
        config.population.density = 42.0
        resolved = _resolve_populations(config)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0][0], "default")
        self.assertEqual(resolved[0][1].density, 42.0)

    def test_populations_override_fallback(self):
        config = GenerateSsoInjectionCatalogConfig()
        config.population.density = 1.0
        a = OrbitPopulationConfig()
        a.density = 99.0
        b = OrbitPopulationConfig()
        b.density = 100.0
        config.populations["a"] = a
        config.populations["b"] = b
        resolved = _resolve_populations(config)
        self.assertEqual([name for name, _ in resolved], ["a", "b"])
        self.assertEqual(resolved[0][1].density, 99.0)
        self.assertEqual(resolved[1][1].density, 100.0)

    def test_mix_population_seed_stable_and_distinct(self):
        a = _mix_population_seed(20240611, "centaur")
        b = _mix_population_seed(20240611, "tno")
        a2 = _mix_population_seed(20240611, "centaur")
        self.assertEqual(a, a2)
        self.assertNotEqual(a, b)
        self.assertGreaterEqual(a, 0)
        self.assertLessEqual(a, 0x7FFFFFFF)


if __name__ == "__main__":
    unittest.main()
