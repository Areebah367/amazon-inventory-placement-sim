# Forward — UAE Inventory Python Model

Python reference implementation of the allocation and Monte Carlo simulation used in the Forward UAE inventory dashboard.

**Relationship to the website:** the published ChatGPT Site currently calculates in browser-side JavaScript. These Python files are a new, tested port of that logic; they are not connected to or running behind the live site. The reference API is ready for local integration. No AWS or Amazon systems are connected.

## Run

Python 3.10+; no packages to install.

```bash
python3 inventory_model.py
python3 inventory_model.py --simulate
python3 inventory_model.py --scenario data/default_scenario.json
python3 -m unittest discover -s tests -v
python3 server.py
```

The API listens on `127.0.0.1:8000` by default. It is a local development server without authentication, persistence or production deployment configuration.

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

- `sites`: seven rows of `[name, usable_capacity_m3, replenishment_days, inbound_units_per_cycle]`.
- `categories`: eight rows of `[name, packaged_litres_per_unit]`.
- `demand`: 8 category × 7 site matrix of expected daily units.
- `current`: same shape, illustrative current inventory; used by the frontend for stock adjustments, not by the allocation objective.
- `multiplier`, `floor`, `holdingRate`, `cv`: demand multiplier, minimum category coverage, USD/ft³/month cost proxy and assumed demand variation.

## Model

At each site, maximise the sum of integer category quantities. Cycle demand is daily demand × multiplier × site days, rounded up. Quantities cannot exceed cycle demand. Total packaged volume cannot exceed usable capacity; total units cannot exceed the inbound allowance. Each category receives at least `ceil(cycle_demand × floor)` units.

After reserving these floors, fill remaining capacity in increasing unit-volume order. This is exact for this restricted equal-value objective with independent sites, fixed unit volumes and the stated constraints. It is not a full multi-echelon inventory optimiser or a replication of Target's algorithm.

Baseline: equal eighths of each site's space and inbound allowance, capped by demand, without redistributing unused shares or enforcing the optional floor. Holding proxy: target volume × 0.5 × 35.3146667 × monthly USD/ft³ rate. The 0.5 assumes uniform stock depletion. The default $0.87 is a supplied US example, not a measured UAE operating cost.

Simulation keeps each policy fixed and evaluates it on the same rounded, non-negative normal demand draws. Seed 42 and the JS random-number generator are reproduced for comparison.

## Evidence and limits

All default demand, capacity, product volume and current-stock figures are illustrative. Seven representative pools cover areas in Dubai, Sharjah and Abu Dhabi; locations are not verified Amazon facilities. No measured UAE demand data or late-delivery rate is provided. Catalogue counts do not establish sales velocity.

Local coverage is stocked units divided by expected units, not on-time delivery, order-level fill rate or late-delivery reduction. The model omits shared central stock constraints, delivery travel times, transfers, expiry, cold chain, lead-time uncertainty and shelf geometry. No classifier or predictive demand model has been trained in this repository.

Conceptual references: [Target inventory optimisation](https://tech.target.com/blog/math-behind-inventory-delivery-optimization), [Amazon Now UAE](https://www.aboutamazon.com/news/innovation/amazon-now-delivery-uae). These do not provide the illustrative numeric inputs.

## Frontend integration

A future integration can send the dashboard scenario to `/api/allocate` and use its response in place of `InventoryModel.solve(state)`. The simulation request wraps that same scenario with `n`. Response fields retain the JavaScript model's names. Host the frontend and API behind an appropriate production server, and add authentication and resource limits before operational use. The existing website remains unchanged.

## Verification

Tests cover baseline totals, coverage floors, infeasibility, zero inputs, invalid numeric data, an exhaustive small allocation comparison, deterministic simulations and HTTP endpoints. `tests/website_reference.json` records outputs from the original website JavaScript for default and edge scenarios; parity tests compare all response fields, including Monte Carlo summaries, with numerical tolerance.
