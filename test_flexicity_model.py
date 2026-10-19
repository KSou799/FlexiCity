"""Tests for the FlexiCity model. Run with:  python -m unittest -v

No GUI is opened, only flexicity_model is imported.
"""

import random
import unittest

import flexicity_model as m


class SchedulerRules(unittest.TestCase):
    """Rules every schedule must follow, checked over many random slider settings."""

    @classmethod
    def setUpClass(cls):
        cls.assets = m.default_assets()
        rng = random.Random(7)
        settings = [(0.0, 0.5), (1.0, 0.0), (1.0, 1.0), (1.0, 0.5)]
        settings += [(rng.random(), rng.random()) for _ in range(300)]
        cls.results = [m.simulate(cls.assets, f, p) for f, p in settings]

    def test_energy_is_conserved(self):
        for r in self.results:
            self.assertAlmostEqual(sum(r.before_load), sum(r.after_load), places=6)

    def test_loads_stay_in_their_window_and_keep_their_run_time(self):
        for r in self.results:
            for i, a in enumerate(self.assets):
                window = set(m.asset_window(a))
                self.assertTrue(set(r.after_hours[i]) <= window, a["owner"])
                self.assertEqual(len(set(r.after_hours[i])), a["duration_h"], a["owner"])

    def test_fixed_loads_run_in_one_block(self):
        for r in self.results:
            for i, a in enumerate(self.assets):
                if a["variable"]:
                    continue
                window = m.asset_window(a)
                idx = sorted(window.index(h) for h in r.after_hours[i])
                self.assertEqual(idx, list(range(idx[0], idx[0] + len(idx))), a["owner"])

    def test_no_participation_changes_nothing(self):
        r = m.simulate(self.assets, 0.0, 0.5)
        self.assertEqual(r.before_load, r.after_load)
        self.assertAlmostEqual(r.cost_before, r.cost_after)

    def test_price_only_puts_variable_loads_in_their_cheapest_hours(self):
        r = m.simulate(self.assets, 1.0, 1.0)
        for i, a in enumerate(self.assets):
            if not a["variable"]:
                continue
            prices = sorted(m.PRICE_PER_HOUR[h] for h in m.asset_window(a))
            chosen = sorted(m.PRICE_PER_HOUR[h] for h in r.after_hours[i])
            self.assertEqual(chosen, prices[:a["duration_h"]], a["owner"])

    def test_cost_never_rises_when_only_price_counts(self):
        r = m.simulate(self.assets, 1.0, 1.0)
        self.assertLessEqual(r.cost_after, r.cost_before)


class Baseline(unittest.TestCase):

    def test_loads_start_at_their_usual_hour(self):
        a = {"owner": "x", "appliance": "y", "power_kW": 10.0, "duration_h": 3,
             "start_hour": 22, "end_hour": 6, "variable": True, "flex_factor": 1.0}
        self.assertEqual(m.usual_hours(a), [22, 23, 0])
        a["usual_start"] = 1
        self.assertEqual(m.usual_hours(a), [1, 2, 3])

    def test_heat_pumps_run_from_05_without_coordination(self):
        r = m.simulate(m.default_assets(), 1.0, 0.5)
        for i, a in enumerate(m.default_assets()):
            if a["appliance"] == "Heat pumps":
                self.assertEqual(r.before_hours[i], [5, 6, 7, 8, 9])


class Validation(unittest.TestCase):

    def base(self, **kw):
        a = {"owner": "x", "appliance": "y", "power_kW": 10.0, "duration_h": 2,
             "start_hour": 8, "end_hour": 12, "variable": True, "flex_factor": 1.0}
        a.update(kw)
        return a

    def test_rejects_bad_loads(self):
        for kw in ({"start_hour": 8, "end_hour": 8}, {"duration_h": 5},
                   {"power_kW": 0}, {"flex_factor": 1.5}, {"start_hour": 24},
                   {"usual_start": 11}, {"usual_start": 3}):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    m.validate_asset(self.base(**kw))

    def test_accepts_a_window_past_midnight(self):
        m.validate_asset(self.base(start_hour=22, end_hour=2, duration_h=4))


class DefaultResults(unittest.TestCase):
    """The numbers quoted in the README. If the model changes, update both."""

    def test_default_settings(self):
        r = m.simulate(m.default_assets(), 1.0, 0.5)
        self.assertAlmostEqual(r.peak_before, 306.0)
        self.assertAlmostEqual(r.peak_after, 278.0)
        self.assertAlmostEqual(r.cost_before, 432.57, places=2)
        self.assertAlmostEqual(r.cost_after, 383.71, places=2)
        self.assertAlmostEqual(r.peak_reduction_pct, 9.15, places=2)
        self.assertAlmostEqual(r.cost_saving_pct, 11.29, places=2)
        self.assertAlmostEqual(r.co2_saving_pct, 6.06, places=2)

    def test_one_pass_matches_the_original_scheduler(self):
        """With one pass and the old heat pump window, the model gives the
        results of the first published version (peak 276.5 kW, 387.21 EUR)."""
        assets = m.default_assets()
        for a in assets:
            if a["appliance"] == "Heat pumps":
                a["start_hour"] = 5
                del a["usual_start"]
        r = m.simulate(assets, 1.0, 0.5, max_passes=1)
        self.assertAlmostEqual(r.peak_after, 276.5)
        self.assertAlmostEqual(r.cost_after, 387.21, places=2)


class Optimisers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.assets = m.default_assets()
        cls.best = {obj: m.optimise(cls.assets, obj) for obj in m.OBJECTIVES}

    def test_each_optimiser_wins_on_its_own_metric(self):
        _, _, peak = self.best["peak"]
        _, _, cost = self.best["cost"]
        _, _, co2 = self.best["co2"]
        default = m.simulate(self.assets, 1.0, 0.5)
        self.assertLessEqual(peak.peak_after, default.peak_after)
        self.assertLessEqual(cost.cost_after, default.cost_after)
        self.assertLessEqual(co2.co2_after, default.co2_after)

    def test_combined_optimiser_makes_nothing_worse(self):
        _, _, r = self.best["all"]
        self.assertLessEqual(r.peak_after, r.peak_before)
        self.assertLessEqual(r.cost_after, r.cost_before)
        self.assertLessEqual(r.co2_after, r.co2_before)

    def test_optimiser_results_quoted_in_readme(self):
        expected = {"peak": (63, 1), "cost": (100, 100), "co2": (99, 5), "all": (65, 10)}
        for obj, (flex, price) in expected.items():
            with self.subTest(obj=obj):
                self.assertEqual(self.best[obj][:2], (flex, price))


if __name__ == "__main__":
    unittest.main()
