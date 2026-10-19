"""FlexiCity scheduling model.

A one-day, hourly model of 24 flexible city electricity loads. It compares an
uncoordinated schedule (every load starts when it normally would) with a
coordinated one, where the shiftable part of each load is moved to hours with
low grid load and low price.

There is no GUI code in this file, so the model can be imported, tested and
benchmarked on its own. Flexi_City.py is the tkinter app built on top of it.

Units: power in kW, one-hour steps, so kW in one hour = kWh. Prices in c/kWh,
costs reported in EUR. CO2 intensity in kg/kWh.

The day is treated as repeating: a load whose window runs past midnight
(for example 22:00 to 08:00) puts its early-morning hours into hours 0 to 7 of
the same 24-hour array.
"""

import copy
from dataclasses import dataclass, field

NUM_HOURS = 24

# Hourly spot price in c/kWh: Nord Pool prices for the Helsinki area,
# recorded from the Helen website for one day in November 2025.
PRICE_PER_HOUR = [
    8.70, 8.48, 8.52, 8.61, 8.69, 8.69,
    9.56, 11.58, 12.72, 13.07, 15.65, 17.65,
    16.24, 15.55, 15.12, 16.64, 18.60, 21.53,
    22.68, 20.29, 17.09, 14.09, 12.81, 11.63,
]

# Hourly CO2 intensity of grid electricity in kg/kWh, based on Fingrid data:
# lowest around midday, highest in the evening.
CO2_PER_HOUR = [
    0.110, 0.105, 0.100, 0.095, 0.090, 0.085,
    0.080, 0.075, 0.065, 0.055, 0.045, 0.040,
    0.038, 0.035, 0.040, 0.050, 0.065, 0.085,
    0.110, 0.125, 0.120, 0.115, 0.115, 0.112,
]


def generate_base_load(num_hours=NUM_HOURS):
    """Load that cannot move, in kW: a flat 40 with morning and evening bumps."""
    base = []
    for h in range(num_hours):
        val = 40.0
        if 7 <= h <= 9:
            val += 25.0
        if 17 <= h <= 21:
            val += 35.0
        base.append(val)
    return base


BASE_LOAD = generate_base_load()

# Each load:
#   power_kW      rated power while running
#   duration_h    run time per day
#   start_hour    first hour the load may run (0 to 23)
#   end_hour      hour the window closes (0 to 24, may be earlier than
#                 start_hour for windows that run past midnight)
#   variable      True if the run time can be split into separate hours
#                 (EV charging), False if it must run in one block (an oven)
#   flex_factor   share of the power that can be shifted without hurting service
#   usual_start   optional: the hour the load starts without coordination,
#                 when that is later than the window opening. The heat pumps
#                 normally start at 05:00 but may pre-heat from 02:00.
DEFAULT_ASSETS = [
    {"owner": "City EV fleet",        "appliance": "Fast chargers",          "power_kW": 80.0, "duration_h": 4, "start_hour": 17, "end_hour": 7,  "variable": True,  "enabled": True, "flex_factor": 0.95},
    {"owner": "Office block A",       "appliance": "HVAC pre-cooling",       "power_kW": 30.0, "duration_h": 3, "start_hour": 14, "end_hour": 22, "variable": True,  "enabled": True, "flex_factor": 0.90},
    {"owner": "Supermarket",          "appliance": "Fridge defrost cycles",  "power_kW": 20.0, "duration_h": 4, "start_hour": 0,  "end_hour": 24, "variable": False, "enabled": True, "flex_factor": 0.60},
    {"owner": "Residential block",    "appliance": "EV chargers",            "power_kW": 40.0, "duration_h": 6, "start_hour": 18, "end_hour": 7,  "variable": True,  "enabled": True, "flex_factor": 0.90},
    {"owner": "Apartment block 1",    "appliance": "Heat pumps",             "power_kW": 25.0, "duration_h": 5, "start_hour": 2,  "end_hour": 10, "variable": True,  "enabled": True, "flex_factor": 0.80, "usual_start": 5},
    {"owner": "Apartment block 2",    "appliance": "Heat pumps",             "power_kW": 30.0, "duration_h": 5, "start_hour": 2,  "end_hour": 10, "variable": True,  "enabled": True, "flex_factor": 0.80, "usual_start": 5},
    {"owner": "Tram depot",           "appliance": "Night chargers",         "power_kW": 60.0, "duration_h": 3, "start_hour": 0,  "end_hour": 6,  "variable": True,  "enabled": True, "flex_factor": 0.85},
    {"owner": "Metro station",        "appliance": "Ventilation",            "power_kW": 35.0, "duration_h": 4, "start_hour": 10, "end_hour": 22, "variable": True,  "enabled": True, "flex_factor": 0.85},
    {"owner": "Data center X",        "appliance": "Battery charging",       "power_kW": 70.0, "duration_h": 5, "start_hour": 0,  "end_hour": 24, "variable": True,  "enabled": True, "flex_factor": 1.0},
    {"owner": "Public swimming pool", "appliance": "Water heating",          "power_kW": 20.0, "duration_h": 4, "start_hour": 6,  "end_hour": 12, "variable": True,  "enabled": True, "flex_factor": 0.75},
    {"owner": "School A",             "appliance": "Ventilation",            "power_kW": 15.0, "duration_h": 3, "start_hour": 7,  "end_hour": 15, "variable": True,  "enabled": True, "flex_factor": 0.80},
    {"owner": "School B",             "appliance": "Ventilation",            "power_kW": 15.0, "duration_h": 3, "start_hour": 7,  "end_hour": 15, "variable": True,  "enabled": True, "flex_factor": 0.80},
    {"owner": "City hospital",        "appliance": "Laundry machines",       "power_kW": 25.0, "duration_h": 4, "start_hour": 8,  "end_hour": 18, "variable": False, "enabled": True, "flex_factor": 0.70},
    {"owner": "Bakery",               "appliance": "Oven preheat",           "power_kW": 10.0, "duration_h": 2, "start_hour": 3,  "end_hour": 7,  "variable": False, "enabled": True, "flex_factor": 0.50},
    {"owner": "Street lighting",      "appliance": "Early dimming",          "power_kW": 10.0, "duration_h": 4, "start_hour": 18, "end_hour": 24, "variable": True,  "enabled": True, "flex_factor": 1.0},
    {"owner": "Downtown chargers",    "appliance": "Public EV charging",     "power_kW": 50.0, "duration_h": 5, "start_hour": 17, "end_hour": 7,  "variable": True,  "enabled": True, "flex_factor": 0.85},
    {"owner": "University labs",      "appliance": "Freezer defrost",        "power_kW": 8.0,  "duration_h": 3, "start_hour": 1,  "end_hour": 7,  "variable": False, "enabled": True, "flex_factor": 0.55},
    {"owner": "Logistics warehouse",  "appliance": "Pre-chill cooling",      "power_kW": 22.0, "duration_h": 4, "start_hour": 12, "end_hour": 22, "variable": True,  "enabled": True, "flex_factor": 0.85},
    {"owner": "Office block B",       "appliance": "Server backup charging", "power_kW": 18.0, "duration_h": 3, "start_hour": 0,  "end_hour": 8,  "variable": True,  "enabled": True, "flex_factor": 1.0},
    {"owner": "City gym",             "appliance": "Sauna heaters",          "power_kW": 12.0, "duration_h": 3, "start_hour": 15, "end_hour": 22, "variable": False, "enabled": True, "flex_factor": 0.65},
    {"owner": "Central library",      "appliance": "HVAC",                   "power_kW": 10.0, "duration_h": 4, "start_hour": 8,  "end_hour": 22, "variable": True,  "enabled": True, "flex_factor": 0.85},
    {"owner": "Small shops",          "appliance": "Refrigeration",          "power_kW": 18.0, "duration_h": 6, "start_hour": 8,  "end_hour": 23, "variable": True,  "enabled": True, "flex_factor": 0.65},
    {"owner": "Residential solar",    "appliance": "Battery charging",       "power_kW": 15.0, "duration_h": 5, "start_hour": 10, "end_hour": 22, "variable": True,  "enabled": True, "flex_factor": 1.0},
    {"owner": "Electric bus depot",   "appliance": "Overnight charging",     "power_kW": 90.0, "duration_h": 6, "start_hour": 22, "end_hour": 8,  "variable": True,  "enabled": True, "flex_factor": 0.95},
]

# Repeat the placement until no load moves, at most this many times.
MAX_PASSES = 5


def default_assets():
    """A fresh copy of the 24 default loads."""
    return copy.deepcopy(DEFAULT_ASSETS)


def get_window_hours(start_hour, end_hour):
    """Hours in the window [start_hour, end_hour), wrapping past midnight."""
    sh, eh = int(start_hour), int(end_hour)
    if sh == eh:
        return []
    if sh < eh:
        return list(range(sh, eh))
    return list(range(sh, NUM_HOURS)) + list(range(0, eh))


def asset_window(asset):
    return get_window_hours(asset["start_hour"], asset["end_hour"])


def usual_hours(asset):
    """Hours the load runs without coordination: its run time from its usual start."""
    window = asset_window(asset)
    start = asset.get("usual_start", asset["start_hour"])
    i = window.index(start)
    return window[i:i + asset["duration_h"]]


def validate_asset(asset):
    """Raise ValueError with a readable message if a load cannot be scheduled."""
    if not (0 <= asset["start_hour"] < NUM_HOURS):
        raise ValueError("Start hour must be between 0 and 23")
    if not (0 <= asset["end_hour"] <= NUM_HOURS):
        raise ValueError("End hour must be between 0 and 24")
    window = asset_window(asset)
    if not window:
        raise ValueError("Start and end hour cannot be the same (empty window)")
    if asset["power_kW"] <= 0:
        raise ValueError("Power must be positive")
    if asset["duration_h"] <= 0:
        raise ValueError("Duration must be positive")
    if not (0.0 <= asset.get("flex_factor", 1.0) <= 1.0):
        raise ValueError("Flexibility must be between 0.0 and 1.0")
    if asset["duration_h"] > len(window):
        raise ValueError(
            f"Duration ({asset['duration_h']}h) exceeds window length ({len(window)}h). "
            f"Widen the start-end window or reduce the duration."
        )
    start = asset.get("usual_start", asset["start_hour"])
    if start not in window or window.index(start) + asset["duration_h"] > len(window):
        raise ValueError("The usual start must leave the full run time inside the window")


@dataclass
class Result:
    """One simulated day. Hour lists are aligned with the input asset list."""
    participation: float
    price_weight: float
    before_load: list
    after_load: list
    before_hours: list
    after_hours: list
    cost_before: float          # EUR, flexible loads only
    cost_after: float
    co2_before: float           # kg, flexible loads only
    co2_after: float
    passes: int = 0
    moved_power: list = field(default_factory=list)

    @property
    def peak_before(self):
        return max(self.before_load)

    @property
    def peak_after(self):
        return max(self.after_load)

    @property
    def peak_reduction_pct(self):
        return _pct(self.peak_before, self.peak_after)

    @property
    def cost_saving_pct(self):
        return _pct(self.cost_before, self.cost_after)

    @property
    def co2_saving_pct(self):
        return _pct(self.co2_before, self.co2_after)


def _pct(before, after):
    return (before - after) / before * 100 if before > 0 else 0.0


def _flex_cost_and_co2(assets, power_at):
    """Cost (EUR) and CO2 (kg) of the flexible loads, from (asset index, hour) -> kW."""
    cost = sum(kw * PRICE_PER_HOUR[h] for (_, h), kw in power_at.items()) / 100.0
    co2 = sum(kw * CO2_PER_HOUR[h] for (_, h), kw in power_at.items())
    return cost, co2


def prepare(assets):
    """Check the loads and work out everything that does not depend on the sliders.

    simulate() calls this itself. optimise() calls it once and reuses the
    result for all 10,201 schedules, which keeps the search fast.
    """
    prep = []
    for i, a in enumerate(assets):
        if not a.get("enabled", True):
            continue
        validate_asset(a)
        window = asset_window(a)
        prices = [PRICE_PER_HOUR[h] for h in window]
        lo, hi = min(prices), max(prices)
        prep.append({
            "index": i,
            "power": a["power_kW"],
            "flex": a.get("flex_factor", 1.0),
            "variable": a.get("variable", True),
            "duration": a["duration_h"],
            "window": window,
            "usual": usual_hours(a),
            # price scaled 0 to 1 within the window
            "price_n": [(p - lo) / (hi - lo) if hi > lo else 0.0 for p in prices],
        })
    # largest loads are placed first
    prep.sort(key=lambda p: -p["power"])
    return prep


def simulate(assets, participation, price_weight, max_passes=MAX_PASSES, prep=None):
    """Simulate one day.

    participation  share of each load's flexible part that is moved, 0 to 1
    price_weight   0 = schedule by grid load only, 1 = by price only

    BEFORE: every load runs its run time from its usual start.
    AFTER:  each load's moved power (power * participation * flex_factor) is
            placed in the hours with the lowest score inside its window,
            score = (1 - w) * load + w * price, both scaled 0 to 1 within the
            window. Loads are placed largest first, against the demand curve
            as it stands at that moment. The placement is repeated until no
            load moves (at most max_passes times), because in the first pass
            big loads avoid hours that smaller loads have not left yet.
    """
    if prep is None:
        prep = prepare(assets)

    n = len(assets)
    before_hours = [[] for _ in range(n)]
    before_load = BASE_LOAD[:]
    for p in prep:
        before_hours[p["index"]] = p["usual"]
        for h in p["usual"]:
            before_load[h] += p["power"]

    moved = [0.0] * n
    for p in prep:
        moved[p["index"]] = p["power"] * participation * p["flex"]

    after_hours = [list(hs) for hs in before_hours]
    after_load = before_load[:]
    passes = 0
    w = price_weight

    if participation > 0:
        for passes in range(1, max_passes + 1):
            changed = False
            for p in prep:
                i = p["index"]
                mv = moved[i]
                if mv <= 0:
                    continue
                window = p["window"]
                duration = p["duration"]

                for h in after_hours[i]:
                    after_load[h] -= mv

                loads = [after_load[h] for h in window]
                lo, hi = min(loads), max(loads)
                span = hi - lo
                if span > 0:
                    score = [(1 - w) * ((l - lo) / span) + w * pn
                             for l, pn in zip(loads, p["price_n"])]
                else:
                    score = [w * pn for pn in p["price_n"]]

                if p["variable"]:
                    # lowest-scoring hours, ties broken by window order
                    picks = sorted(range(len(window)), key=score.__getitem__)[:duration]
                    chosen = [window[k] for k in picks]
                else:
                    # best continuous block, first one wins a tie
                    best_k, best_s = 0, None
                    for k in range(len(window) - duration + 1):
                        s = sum(score[k:k + duration])
                        if best_s is None or s < best_s:
                            best_k, best_s = k, s
                    chosen = window[best_k:best_k + duration]

                for h in chosen:
                    after_load[h] += mv
                if not changed and sorted(chosen) != sorted(after_hours[i]):
                    changed = True
                after_hours[i] = chosen
            if not changed:
                break

    before_power = {}
    after_power = {}
    for p in prep:
        i = p["index"]
        full = p["power"]
        for h in before_hours[i]:
            before_power[(i, h)] = before_power.get((i, h), 0.0) + full
            after_power[(i, h)] = after_power.get((i, h), 0.0) + full - moved[i]
        for h in after_hours[i]:
            after_power[(i, h)] = after_power.get((i, h), 0.0) + moved[i]
    cost_before, co2_before = _flex_cost_and_co2(assets, before_power)
    cost_after, co2_after = _flex_cost_and_co2(assets, after_power)

    return Result(participation, price_weight, before_load, after_load,
                  before_hours, after_hours, cost_before, cost_after,
                  co2_before, co2_after, passes, moved)


OBJECTIVES = ("peak", "cost", "co2", "all")


def optimise(assets, objective, max_passes=MAX_PASSES):
    """Try every slider setting in 1% steps (101 x 101 = 10,201 schedules).

    Returns (participation %, price weight %, Result) for the best setting, or
    None for "all" when no setting improves peak, cost and CO2 together.

    peak  lowest peak, ties broken by cost
    cost  lowest cost of the flexible loads, ties broken by peak
    co2   lowest CO2 of the flexible loads, ties broken by cost
    all   lowest average of the three, each scaled so 1.0 = uncoordinated.
          Any setting where one of them gets worse is rejected.
    """
    if objective not in OBJECTIVES:
        raise ValueError(f"objective must be one of {OBJECTIVES}")

    def key(r):
        if objective == "peak":
            return (r.peak_after, r.cost_after)
        if objective == "cost":
            return (r.cost_after, r.peak_after)
        if objective == "co2":
            return (r.co2_after, r.cost_after)
        parts = []
        for after, before in ((r.peak_after, r.peak_before),
                              (r.cost_after, r.cost_before),
                              (r.co2_after, r.co2_before)):
            if before > 0:
                ratio = after / before
                if ratio > 1.0 + 1e-6:
                    return (float("inf"),)
                parts.append(ratio)
        return (sum(parts) / len(parts),) if parts else (float("inf"),)

    prep = prepare(assets)
    best = None
    for flex in range(101):
        for price in range(101):
            r = simulate(assets, flex / 100, price / 100, max_passes, prep)
            k = key(r)
            if best is None or k < best[0]:
                best = (k, flex, price, r)

    k, flex, price, r = best
    if objective == "all" and k[0] >= 1.0 - 1e-9:
        return None
    return flex, price, r
