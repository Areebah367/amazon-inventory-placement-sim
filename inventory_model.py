"""Python port of the Forward dashboard's restricted allocation model.

No AWS or Amazon systems are connected. Inputs are illustrative planning data.
Quantities, response names, tolerances and RNG match the website model.js.
"""
import json
import math
from pathlib import Path


def default_scenario():
    return json.loads((Path(__file__).parent / 'data/default_scenario.json').read_text())


def validate(s):
    def number(v, low, high):
        return type(v) in (int, float) and math.isfinite(v) and low <= v <= high
    if not isinstance(s, dict) or s.get('version') != 1 or isinstance(s.get('version'), bool):
        raise ValueError('Use a version 1 scenario.')
    sites, cats = s.get('sites'), s.get('categories')
    if not isinstance(sites, list) or len(sites) != 7 or not isinstance(cats, list) or len(cats) != 8:
        raise ValueError('Use 7 sites and 8 categories for website compatibility.')
    for key in ('demand', 'current'):
        matrix = s.get(key)
        if (not isinstance(matrix, list) or len(matrix) != 8 or
            any(not isinstance(row, list) or len(row) != 7 or
                any(not number(v, 0, 1_000_000) for v in row) for row in matrix)):
            raise ValueError('Demand and current stock must be 8 by 7 numbers from 0 to 1,000,000.')
    for row in sites:
        if not isinstance(row, list) or len(row) != 4:
            raise ValueError('Each site needs name, capacity, cycle days and inbound limit.')
        name, cap, days, limit = row
        if (not isinstance(name, str) or len(name) > 80 or not number(cap, 0, 10000)
            or not number(days, .1, 30) or not number(limit, 0, 10_000_000)
            or limit != int(limit)):
            raise ValueError('Check site capacity, cycle and integer inbound limits.')
    for row in cats:
        if (not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str)
            or len(row[0]) > 80 or not number(row[1], .01, 10000)):
            raise ValueError('Category volume must be between 0.01 and 10,000 litres.')
    for key, low, high in [('multiplier', .1, 5), ('floor', 0, 1), ('holdingRate', 0, 100), ('cv', 0, 2)]:
        if not number(s.get(key), low, high):
            raise ValueError(f'{key} must be between {low} and {high}.')
    return s


def solve(s):
    """Maximise locally stocked units, independently at each forward pool.

    Reserve category coverage floors, then take smallest volume units first.
    Exact only for this equal-value, fixed-volume, independent-site formulation.
    """
    validate(s)
    results = []
    totals = dict.fromkeys(('demand', 'baseline', 'stock', 'volume', 'baseVolume', 'capacity', 'cost', 'baseCost'), 0)
    volumes = [c[1] / 1000 for c in s['categories']]
    order = sorted(range(8), key=lambda i: (volumes[i], i))
    for j, (name, cap, days, limit) in enumerate(s['sites']):
        d = [math.ceil(row[j] * s['multiplier'] * days) for row in s['demand']]
        q = [math.ceil(x * s['floor']) for x in d]
        used = sum(x * v for x, v in zip(q, volumes))
        required = used
        units = sum(q)
        feasible = used <= cap + 1e-9 and units <= limit
        if feasible:
            for i in order:
                add = max(0, min(d[i] - q[i], math.floor((cap - used + 1e-10) / volumes[i]), int(limit - units)))
                q[i] += add
                used += add * volumes[i]
                units += add
        else:
            q, used, units = None, 0, 0
        baseline = [min(x, math.floor((cap / 8 + 1e-10) / volumes[i]), math.floor(limit / 8)) for i, x in enumerate(d)]
        base_volume = sum(x * v for x, v in zip(baseline, volumes))
        base_units, total = sum(baseline), sum(d)
        cost = used * .5 * 35.3146667 * s['holdingRate']
        base_cost = base_volume * .5 * 35.3146667 * s['holdingRate']
        results.append(dict(name=name, d=d, q=q, baseline=baseline, used=used, cap=cap,
                            limit=limit, days=days, units=units, total=total,
                            coverage=units / total if total else 0, baseUnits=base_units,
                            baseVolume=base_volume, cost=cost, baseCost=base_cost,
                            feasible=feasible, requiredVolume=required))
        for key, value in [('demand', total), ('baseline', base_units), ('stock', units), ('volume', used),
                           ('baseVolume', base_volume), ('capacity', cap), ('cost', cost), ('baseCost', base_cost)]:
            totals[key] += value
    return dict(sites=results, totals=totals, feasible=all(r['feasible'] for r in results))


def simulate(s, n=1000):
    """Test fixed recommended/baseline stocks on identical random demand draws.

    Seed 42, unsigned 32-bit LCG and Box-Muller reproduce the JS algorithm.
    This estimates local unit coverage, not actual late deliveries.
    """
    r = solve(s)
    if not r['feasible']:
        raise ValueError('Resolve infeasible coverage floors first.')
    if type(n) is not int or not 1 <= n <= 10000:
        raise ValueError('n must be an integer between 1 and 10,000.')
    seed = 42
    def rand():
        nonlocal seed
        seed = (1664525 * seed + 1013904223) & 0xffffffff
        return (seed + .5) / 4294967296
    def normal():
        return math.sqrt(-2 * math.log(rand())) * math.cos(2 * math.pi * rand())
    recommended, baseline = [], []
    for _ in range(n):
        demand = served = base = 0
        for site in r['sites']:
            for i, mean in enumerate(site['d']):
                # JS Math.round rounds ties toward positive infinity.
                draw = max(0, math.floor(mean * (1 + s['cv'] * normal()) + .5))
                demand += draw
                served += min(draw, site['q'][i])
                base += min(draw, site['baseline'][i])
        recommended.append(served / demand if demand else 0)
        baseline.append(base / demand if demand else 0)
    def stats(values):
        values.sort()
        return dict(mean=sum(values) / n, p05=values[math.floor(.05 * n)], p95=values[math.floor(.95 * n)])
    return dict(recommended=stats(recommended), baseline=stats(baseline), n=n)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', type=Path)
    parser.add_argument('--simulate', action='store_true')
    args = parser.parse_args()
    scenario = json.loads(args.scenario.read_text()) if args.scenario else default_scenario()
    print(json.dumps(simulate(scenario) if args.simulate else solve(scenario), indent=2, allow_nan=False))
