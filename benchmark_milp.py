"""How good is the greedy scheduler? Compare it with the exact best schedule.

The same day, loads and rules as flexicity_model, solved exactly as a
mixed-integer linear program (MILP):

  variables   which hours each variable load runs in (one 0/1 per hour),
              which block each fixed load starts in (one 0/1 per start)
  constraints each load runs exactly its run time inside its window,
              demand in every hour <= peak
  objective   lowest peak, or lowest cost, optionally with a cap on the other

All loads move their full flexible share (participation 100%), like the
greedy scheduler at 100%.

Needs PuLP, which brings its own CBC solver (tested with PuLP 2.9):
    pip install "pulp>=2.7,<3"
    python benchmark_milp.py
"""

import pulp

import flexicity_model as m

# Peak problems are hard to prove optimal (many near-equal schedules), so each
# solve stops after this many seconds and reports how close it got.
TIME_LIMIT_S = 60


def solve(assets, objective, peak_cap=None, cost_cap=None, participation=1.0,
          relax=False, time_limit=TIME_LIMIT_S):
    """Best schedule. Returns (peak kW, flexible-load cost EUR, proven best).

    proven best is False when the solver ran out of time: the schedule is
    then the best one found, and the relaxed problem (relax=True, where a
    load may run a fraction of an hour) gives a floor nobody can beat.
    """
    cat = "Continuous" if relax else "Binary"
    prob = pulp.LpProblem("flexicity", pulp.LpMinimize)
    usual = {i: m.usual_hours(a) for i, a in enumerate(assets) if a.get("enabled", True)}
    moved = {i: assets[i]["power_kW"] * participation * assets[i].get("flex_factor", 1.0) for i in usual}

    # runs[(i, h)] is 1 if the moved part of load i runs in hour h
    runs = {}
    for i in usual:
        a = assets[i]
        window = m.asset_window(a)
        d = a["duration_h"]
        if a.get("variable", True):
            x = {h: pulp.LpVariable(f"x_{i}_{h}", 0, 1, cat) for h in window}
            prob += pulp.lpSum(x.values()) == d
            for h in window:
                runs[(i, h)] = x[h]
        else:
            starts = range(len(window) - d + 1)
            s = {k: pulp.LpVariable(f"s_{i}_{k}", 0, 1, cat) for k in starts}
            prob += pulp.lpSum(s.values()) == 1
            for j, h in enumerate(window):
                runs[(i, h)] = pulp.lpSum(s[k] for k in starts if k <= j < k + d)

    peak = pulp.LpVariable("peak")
    for h in range(m.NUM_HOURS):
        fixed = m.BASE_LOAD[h] + sum(assets[i]["power_kW"] - moved[i] for i in usual if h in usual[i])
        shifted = pulp.lpSum(moved[i] * runs[(i, h)] for i in usual if (i, h) in runs)
        prob += fixed + shifted <= peak

    cost_cents = (
        pulp.lpSum(moved[i] * m.PRICE_PER_HOUR[h] * runs[(i, h)] for (i, h) in runs)
        + sum((assets[i]["power_kW"] - moved[i]) * m.PRICE_PER_HOUR[h] for i in usual for h in usual[i])
    )
    if peak_cap is not None:
        prob += peak <= peak_cap
    if cost_cap is not None:
        prob += cost_cents <= cost_cap * 100
    prob += peak if objective == "peak" else cost_cents

    prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=time_limit))
    if prob.sol_status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        raise RuntimeError(f"no schedule found: {pulp.LpSolution[prob.sol_status]}")
    proven = prob.sol_status == pulp.LpSolutionOptimal
    return pulp.value(peak), pulp.value(cost_cents) / 100, proven


def pct(before, after):
    return (before - after) / before * 100


def main():
    assets = m.default_assets()
    default = m.simulate(assets, 1.0, 0.5)
    p0, c0 = default.peak_before, default.cost_before

    # greedy at 100% participation, best price weight for each target
    greedy = [m.simulate(assets, 1.0, w / 100) for w in range(101)]
    g_peak = min(greedy, key=lambda r: (r.peak_after, r.cost_after))
    g_cost = min(greedy, key=lambda r: (r.cost_after, r.peak_after))

    def kw(peak):
        return f"{peak:.1f} kW (-{pct(p0, peak):.1f}%)"

    def eur(cost):
        return f"{cost:.2f} EUR (-{pct(c0, cost):.1f}%)"

    def exact(objective, fmt, **caps):
        """Best schedule found, marked * if not proven best, plus the floor."""
        peak, cost, proven = solve(assets, objective, **caps)
        value = peak if objective == "peak" else cost
        text = fmt(value) + ("" if proven else " *")
        lp_peak, lp_cost, _ = solve(assets, objective, relax=True, **caps)
        floor = lp_peak if objective == "peak" else lp_cost
        return text, fmt(floor)

    print("Solving, this takes a few minutes...\n")
    rows = [
        ("Lowest peak", kw(g_peak.peak_after), *exact("peak", kw)),
        ("Lowest cost", eur(g_cost.cost_after), *exact("cost", eur)),
        ("Lowest peak at the default cost", kw(default.peak_after),
         *exact("peak", kw, cost_cap=default.cost_after)),
        ("Lowest cost at the default peak", eur(default.cost_after),
         *exact("cost", eur, peak_cap=default.peak_after)),
    ]

    print(f"Uncoordinated: peak {p0:.1f} kW, flexible-load cost {c0:.2f} EUR")
    print(f"Default greedy (100% participation, 50/50): peak {default.peak_after:.1f} kW, "
          f"cost {default.cost_after:.2f} EUR\n")
    print(f"{'Target':<34}{'Greedy':<22}{'MILP':<24}{'Nothing can beat'}")
    for target, g, e, floor in rows:
        print(f"{target:<34}{g:<22}{e:<24}{floor}")
    print(f"\n* stopped after {TIME_LIMIT_S} s, best schedule found but not proven best")


if __name__ == "__main__":
    main()
