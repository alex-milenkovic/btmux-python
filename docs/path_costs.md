# Path-cost port

The functions in `physics/path_costs.py` take `(game_map, fx, fy, tx, ty)` and
return an integer: zero means impassable. They price directed coordinate pairs
without changing the map or occupants and do not require adjacent endpoints.

| C function in btspath.c | Python function |
|---|---|
| MechTileCost | mech_tile_cost |
| HoverTankTileCost | hover_tank_tile_cost |
| TrackedTankTileCost | tracked_tank_tile_cost |

Both endpoints use `GameMap.base_elevation`; terrain charges use destination
`GameMap.rterrain`. WATER and ICE have negative floor elevations. Mechs allow
two levels of difference, vehicles one. Hover's flat water cost applies only
after that elevation gate. The original `ty >= XSIZE` destination guard is
preserved, including rejection of valid rows on tall maps. Either endpoint
outside the physical map safely returns zero before reading a cell; this is
a defined Python extension for the C's unsafe coordinate domain.

Decorated terrain is resolved through `GameMap.rterrain` and signed
`GameMap.base_elevation`; bare FIRE/SMOKE retains the raw-terrain fallback.

Pricing owns the structural `PathCostMap` interface: read-only width, coordinate
validation, signed floor elevation, and real terrain. `GameMap` satisfies it
without inheritance or a wrapper. Terrain constants remain shared domain values
from `entities.map`; pricing does not use concrete map storage or loader APIs.
The command and acceptance adapters select these same production functions and
present their results. Unit architecture checks guard these boundaries.

## Query command

```sh
python3 -m tools.path_cost --mode hover --size 4 4 --from 0 0 --to 1 0 --source GRASSLAND 0 --destination WATER 1
```

This prints `cost=1`. Run `python3 -m tools.path_cost --help` for inputs and
compatibility limits. All arguments are required; invalid inputs exit nonzero
with a diagnostic. Same-hex terrain and elevation inputs must agree.

## Verification

```sh
python -B -m unittest tests.test_path_costs tests.test_path_cost_command tests.test_path_cost_architecture tests.test_acceptance_pipeline tests.test_acceptance_generator
python -B qa/path_costs.py
```

The standalone QA driver above also requires the external `gherkin-parser`.
The acceptance feature pipeline and optional C-reference checks are described
in [qa/README.md](../qa/README.md). Finite property checks are under `properties/`.
