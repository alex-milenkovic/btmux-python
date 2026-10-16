# BTMux Engine

BTMux Engine is a headless combat and physics engine for BattleTech-style
encounters, reimplemented in Python from the BTMux C simulation. Give it a map,
units and orders; it advances the simulation and returns command replies, damage,
positions, contacts and other state as JSON. Use it to explore encounters, drive
a graphical client or build simulations directly in Python.

The engine supports biped and quad Mechs, tracked/wheeled/hover vehicles, VTOL
aircraft, naval units, Aerospace fighters, DropShips, dismounted pilots and
battle armor. Movement, terrain, heat, sensors, weapons, physical attacks,
critical damage, radio networks, transport and repair interact through a shared
clock. Fighters use the historical **six-location Aerospace** model: Nose, Left
Wing, Right Wing, Fuselage, Cockpit and Engine.

**Battlesheep** is the built-in AI. Its controllers take queued or radio orders,
navigate, follow other units, select sensors and fire through the same gameplay
systems. The engine runs locally without a MUX server or a graphical client;
rendering and a client's live transport belong to the application using it.

## Run your first encounter

Use **Python 3.12 or newer**; Python 3.12 is the validated runtime for version
0.1.0. Normal simulation uses only the Python standard library.

The first-release source repository is
[alex-milenkovic/btmux-python](https://github.com/alex-milenkovic/btmux-python).
With Git installed, obtain the source and enter its directory:

```sh
git clone https://github.com/alex-milenkovic/btmux-python.git
cd btmux-python
```

The repository name is `btmux-python`; the installed distribution remains
`btmux-engine` version `0.1.0`, with the existing Python imports and module CLIs.
From the source root, beside `pyproject.toml`, create an environment with your
Python 3.12 interpreter:

```sh
python -m venv .venv
```

Activate it with `.\.venv\Scripts\Activate.ps1` in PowerShell, or
`. .venv/bin/activate` in a POSIX shell. Then run:

```sh
python -m pip install -e .
python -B -m tools.core_simulation --input examples/gameplay_scenarios/dfa_miss.json
```

This encounter attempts a **death from above (DFA)** jump attack, misses, then
stands the attacker up and moves it away. The command prints one JSON document
and exits. Among its final fields are these values (excerpt):

```json
{
  "state": {
    "time": 140,
    "units": {
      "Attacker": {"damage_taken": 10, "fallen": false, "at": [3, 3, 0]},
      "Target": {"damage_taken": 0, "fallen": false, "at": [3, 4, 0]}
    }
  }
}
```

The full output also contains ordered `results` and named random `draws`.
A command's reply and the resulting state tell you what happened; an accepted
order can complete later as time advances.

[Getting started](docs/getting-started.md) walks through both shells, installation
from a wheel, saving output and a complete small laser encounter. Wheel users
supply or copy their JSON inputs; the example collection is a source-checkout
and source-distribution asset.

## Explore the engine

| I want to... | Start here |
|---|---|
| Install, run and understand a first scenario | [Getting started](docs/getting-started.md) |
| Try combat, ice, smoke, asymmetric sensing or AI orders | [Running scenarios](docs/running-scenarios.md) |
| Browse the 32 general/LOS and three AI encounters | [Encounter collection](examples/gameplay_scenarios/README.md) and [Battlesheep encounters](examples/gameplay_scenarios/AI.md) |
| Embed sessions in Python or connect a client | [Python API](docs/python-api.md) and [client integration](docs/client-integration.md) |
| Understand the design or contribute | [Architecture](docs/architecture.md), [contributing](CONTRIBUTING.md) and [QA prerequisites](qa/README.md) |
| Understand C compatibility and implementation scope | [C-to-Python guide](docs/porting/C_TO_PYTHON.md) and [completion guide](docs/porting/COMPLETION.md) |

The [core JSON interface](docs/core-simulation-cli.md) documents scenario fields
and commands; the [autopilot interface](docs/autopilot-cli.md) adds controllers,
radio orders and AI persistence. Both CLIs read one complete JSON document from
`--input` or stdin and exit after its actions. Python session objects let an
application issue actions and inspect state across an ongoing session.

For original unit designs, follow the optional
[template catalogue setup and verification guide](docs/template-catalog-integration.md).
Catalogue setup is explicit; ordinary startup never downloads it.

## Find your way around

| Location | Contents |
|---|---|
| [`core/`](core/) | Simulation loop, events, randomness and shared services |
| [`entities/`](entities/), [`data/`](data/) | Units, maps, equipment data and loaders |
| [`physics/`](physics/), [`systems/`](systems/) | Geometry, motion and gameplay rules |
| [`tools/`](tools/) | Python session adapters and `python -m tools...` CLIs |
| [`examples/gameplay_scenarios/`](examples/gameplay_scenarios/) | Runnable JSON encounters and their interface manifest |
| [`tests/`](tests/), [`features/`](features/), [`acceptance/`](acceptance/), [`qa/`](qa/) | Tests, executable feature descriptions and behavioral checks |
| [`docs/`](docs/) | Installation, scenario, interface, API and compatibility guides |

Original C function/file references and source credit remain in the code.
The compatibility guides explain the general BTMux and historical Aerospace
sources, including their distinct behavior. Optional C reference trees and the
original template catalogue are separate from the Python distribution.

## License and provenance

This Python simulation engine derives from BTMux and its contributors. It uses
the general C source and historical Aerospace revision described in
[CREDITS.md](CREDITS.md) and the [source guide](docs/porting/C_TO_PYTHON.md).
Client presentation remains separate from the original MUX host infrastructure.

[LICENSE](LICENSE) preserves the exact **3030MUX Artistic License**, a custom
license distinct from standard Artistic 1.0 or 2.0. Keep original copyright
notices and disclaimers when copying source. Changes require prominent notices
in each changed file stating how and when it changed, and modifications must
be made freely available under section 3(a), or covered by arrangements with
the copyright holder under section 3(b). For object-code or executable
redistribution, section 4 sets the permitted routes, including accompanying
the package with its modified machine-readable source.

You may not charge for the package itself. Section 5 permits a reasonable
copying fee, any fee for support, and inclusion in a larger commercial
distribution if the package is not advertised as your own product. Generated
scripts and data are addressed separately in section 6. The full license and
the additional [original notices](CREDITS.md#retained-notices) govern; author
names do not confer endorsement, and the warranty disclaimers remain intact.
The historical BattleTech/WizKids statement in LICENSE comes from the upstream
release.
