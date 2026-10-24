"""Tests for the FlexiCity model. Run with:  python -m unittest -v

No GUI is opened, only flexicity_model is imported. The checks against the
exact solver (ExactSolverFloor) need PuLP and are skipped without it.
"""

import random
import unittest

import flexicity_model as m

try:
    import benchmark_milp  # needs PuLP
except ImportError:
    benchmark_milp = None


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

    def test_moved_share_of_fixed_loads_runs_in_one_block(self):
        """A fixed load is a group of machines: the share that moves runs as
        one block, the rest keeps its usual hours."""
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

    def test_evening(self):
        """Energy and peak from 17:00 to 22:00 (hours 17 to 21)."""
        r = m.simulate(m.default_assets(), 1.0, 0.5)
        evening = range(17, 22)
        self.assertAlmostEqual(sum(r.before_load[h] for h in evening), 1157.0)
        self.assertAlmostEqual(sum(r.after_load[h] for h in evening), 634.5)
        self.assertAlmostEqual(max(r.before_load[h] for h in evening), 255.0)
        self.assertAlmostEqual(max(r.after_load[h] for h in evening), 175.0)

    def test_quoted_settings_settle_within_three_rounds(self):
        for flex, price in ((100, 50), (63, 1), (100, 100), (99, 5), (65, 10), (100, 12)):
            with self.subTest(flex=flex, price=price):
                r = m.simulate(m.default_assets(), flex / 100, price / 100)
                self.assertLessEqual(r.passes, 3)

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


@unittest.skipIf(benchmark_milp is None, "PuLP is not installed")
class ExactSolverFloor(unittest.TestCase):
    """The greedy scheduler against the relaxed exact problem, where loads may
    run fractions of an hour. The relaxed problem solves in under a second."""

    @classmethod
    def setUpClass(cls):
        cls.assets = m.default_assets()
        cls.peak_floor = benchmark_milp.solve(cls.assets, "peak", relax=True)[0]
        cls.cost_floor = benchmark_milp.solve(cls.assets, "cost", relax=True)[1]

    def test_floors_quoted_in_readme(self):
        self.assertAlmostEqual(self.peak_floor, 184.6, delta=0.05)
        self.assertAlmostEqual(self.cost_floor, 339.05, places=2)

    def test_no_setting_beats_the_floor(self):
        """The floors are computed at 100% participation but hold at any
        participation: a partly moved load is a fractional schedule."""
        rng = random.Random(11)
        settings = [(0.63, 0.01), (0.65, 0.10), (1.0, 0.12), (1.0, 0.5)]
        settings += [(rng.random(), rng.random()) for _ in range(200)]
        for flex, price in settings:
            r = m.simulate(self.assets, flex, price)
            self.assertGreaterEqual(r.peak_after, self.peak_floor - 1e-6)
            self.assertGreaterEqual(r.cost_after, self.cost_floor - 1e-6)

    def test_greedy_finds_the_cheapest_schedule(self):
        r = m.simulate(self.assets, 1.0, 1.0)
        self.assertAlmostEqual(r.cost_after, self.cost_floor, places=2)


if __name__ == "__main__":
    unittest.main()
