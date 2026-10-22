# Forward — UAE Inventory Placement

Illustrative planning demo: recommends which product categories to keep at each Forward Site and how many units to stock, within each site's space and replenishment limits.

**Live demo:** https://amazon-inventory-placement-sim.vercel.app — the dashboard (`web/dashboard.html`, served at `/`) calls this repository's Python API (`/api/defaults`, `/api/allocate`) for every result it shows. The API reference is at `/docs`. The project deploys to Vercel from `main`. No AWS or Amazon systems are connected.

The model is a tested Python port of the original prototype's browser-side JavaScript; `tests/website_reference.json` keeps it numerically identical for the default and edge scenarios.

## Dashboard

1. The recommendation, coverage against an equal-space-per-category baseline, and the holding-cost difference, all calculated from the API response.
2. A policy switch: protect every category with a 20% minimum, or no category minimum.
3. A collapsed scenario editor for a Forward Site's capacity, replenishment cycle, inbound allowance and daily demand by category, plus **Add Forward Site**. Edits stay in the visitor's browser session; the shared default data is never changed.
4. The "What to stock, and where" heatmap (recommended units, coverage % or expected cycle demand), Forward Site summaries, a map of illustrative delivery areas, and a short scaling note.

## Run

Python 3.10+; no packages to install.

```bash
python3 inventory_model.py
python3 inventory_model.py --simulate
python3 inventory_model.py --scenario data/default_scenario.json
python3 -m unittest discover -s tests -v
python3 server.py
```

Locally, the server listens on `127.0.0.1:8000` by default; open it in a browser for the dashboard. The API has no authentication or persistence, and the public deployment serves synthetic demo data only.

| Endpoint | Request | Response |
| --- | --- | --- |
| `GET /health` | none | health status |
| `GET /api/defaults` | none | editable illustrative scenario |
| `POST /api/allocate` | scenario JSON | site recommendations, baseline, cost and feasibility |
| `POST /api/simulate` | `{"scenario": {...}, "n": 1000}` | fixed-policy coverage mean and 5th–95th percentile range |

```bash
curl -X POST http://127.0.0.1:8000/api/allocate \
  -H 'Content-Type: application/json' \
  --data-binary @data/default_scenario.json
```

Allocation returns HTTP 422 when a coverage floor cannot fit site constraints; invalid inputs return 400. Payloads are limited to 1 MB and simulations to 10,000 draws per request.

## Inputs

`data/default_scenario.json` uses the website's version 1 JSON format. It can also accept a scenario exported by the dashboard.

- `sites`: 1–30 rows of `[name, usable_capacity_m3, replenishment_days, inbound_units_per_cycle]`, with unique names. The default has seven hypothetical site profiles.
- `categories`: 1–30 rows of `[name, packaged_litres_per_unit]`. The default has eight.
- `demand`: category × site matrix of expected daily units (one row per category, one column per site).
- `current`: same shape, illustrative current inventory; used by the frontend for stock adjustments, not by the allocation objective.
- `multiplier`, `floor`, `holdingRate`, `cv`: demand multiplier, minimum category coverage, USD/ft³/month cost proxy and assumed demand variation.

## Model

At each site, maximise the sum of integer category quantities. Cycle demand is daily demand × multiplier × site days, rounded up. Quantities cannot exceed cycle demand. Total packaged volume cannot exceed usable capacity; total units cannot exceed the inbound allowance. Each category receives at least `ceil(cycle_demand × floor)` units.

After reserving these floors, fill remaining capacity in increasing unit-volume order. This is exact for this restricted equal-value objective with independent sites, fixed unit volumes and the stated constraints. It is not a full multi-echelon inventory optimiser or a replication of Target's algorithm.

Baseline: equal space per category — each category gets an equal share (1/number of categories) of each site's space and inbound allowance, capped by demand, without redistributing unused shares or enforcing the optional floor. Holding proxy: target volume × 0.5 × 35.3146667 × monthly USD/ft³ rate. The 0.5 assumes uniform stock depletion. The default $0.87 is a supplied US example, not a measured UAE operating cost.

Simulation keeps each policy fixed and evaluates it on the same rounded, non-negative normal demand draws. Seed 42 and the JS random-number generator are reproduced for comparison.

## Evidence and limits

All default demand, capacity, product volume and current-stock figures are illustrative. The seven default Forward Site profiles are hypothetical groupings of areas in Dubai, Sharjah and Abu Dhabi; they are not verified Amazon facilities, service boundaries or one site per emirate. Delivery-area dots on the map are approximate area centres, and coverage is calculated per Forward Site, not per area. No measured UAE demand data or late-delivery rate is provided. Catalogue counts do not establish sales velocity.

Local coverage is stocked units divided by expected units, not on-time delivery, order-level fill rate or late-delivery reduction. The model omits shared central stock constraints, delivery travel times, transfers, expiry, cold chain, lead-time uncertainty and shelf geometry. No classifier or predictive demand model has been trained in this repository.

Conceptual references: [Target inventory optimisation](https://tech.target.com/blog/math-behind-inventory-delivery-optimization), [Amazon Now UAE](https://www.aboutamazon.com/news/innovation/amazon-now-delivery-uae). These do not provide the illustrative numeric inputs.

## Scaling to another city

Every Forward Site uses the same data structure, so a new city or site needs its capacity, replenishment cycle, inbound allowance and daily category demand, not a new algorithm. Matrix dimensions, allocation loops and validation are derived from the supplied site and category lists. Before operational use, add authentication and resource limits to the API.

## Verification

Tests cover baseline totals, coverage floors, infeasibility, zero inputs, invalid numeric data, variable site and category counts, an exhaustive small allocation comparison, deterministic simulations, HTTP endpoints and the dashboard pages. `tests/website_reference.json` records outputs from the original website JavaScript for default and edge scenarios; parity tests compare all response fields, including Monte Carlo summaries, with numerical tolerance.
