# Getting started

Run a saved encounter, inspect its outcome, then write a small scenario of your
own. The engine is headless: these steps produce JSON and text, with no graphical
application required.

[Project overview](../README.md) · [Running scenarios](running-scenarios.md) ·
[Python API](python-api.md)

## Contents

- [Install from source](#install-from-source)
- [Run a saved encounter](#run-a-saved-encounter)
- [Write a complete small encounter](#write-a-complete-small-encounter)
- [Understand time and results](#understand-time-and-results)
- [Use the same scenario from Python](#use-the-same-scenario-from-python)
- [Install a wheel](#install-a-wheel)
- [Optional development and build tools](#optional-development-and-build-tools)
- [Add original unit templates](#add-original-unit-templates)
- [Troubleshooting](#troubleshooting)

## Install from source

Use **Python 3.12 or newer**. Python 3.12 is the validated runtime for
`btmux-engine==0.1.0`. Normal simulation has no third-party runtime dependencies.
You need a source checkout or an extracted source distribution for the example
files and encounter runners below. Git is only needed for Git checkout
operations and the optional original template catalogue.

Open a terminal **in the engine directory**, beside `pyproject.toml`,
`README.md`, `tools/` and `examples/`.

### PowerShell

Use your Python 3.12 interpreter to create the environment. If that interpreter
is selected by `python`:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

If you use the Windows Python launcher, `py -3.12 -m venv .venv` can replace
the environment-creation command. After activation, `python` refers to the
environment's interpreter.

### POSIX shell

On Linux or macOS, use your Python 3.12 interpreter:

```sh
python3.12 --version
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

If your suitable interpreter is named `python3` or `python`, use that name
for the first two commands. The activation command above works in POSIX shells;
Bash and Zsh also accept `source .venv/bin/activate`.

An editable installation makes this checkout importable from other working
directories. Confirm the selected distribution and interpreter:

```sh
python --version
python -m pip show btmux-engine
```

The package metadata should show version `0.1.0`. Its public imports keep their
existing names, such as `core`, `systems` and `tools`; there is no
`btmux_engine` import required.

## Run a saved encounter

Stay in the engine directory. This example runs a missed **death from above
(DFA)** jump attack, followed by standing and movement. Create an output
directory and save the CLI's stdout.

PowerShell:

```powershell
New-Item -ItemType Directory -Force tmp | Out-Null
python -B -m tools.core_simulation --input examples/gameplay_scenarios/dfa_miss.json | Set-Content -Encoding utf8 tmp/dfa-result.json
```

POSIX shell:

```sh
mkdir -p tmp
python -B -m tools.core_simulation --input examples/gameplay_scenarios/dfa_miss.json > tmp/dfa-result.json
```

The command executes all actions, emits one JSON document and exits. `-B`
avoids creating Python bytecode caches; it does not change simulation behavior.
The engine does not create the result filename itself: the shell saves stdout.
Without the final pipe or redirection, the JSON appears in your terminal.

Read a small part of that result with the same command in either shell:

```sh
python -c "import json; r=json.load(open('tmp/dfa-result.json', encoding='utf-8-sig')); print(r['state']['time'], r['state']['units']['Attacker']['damage_taken'], r['state']['units']['Target']['damage_taken'])"
```

Expected output:

```text
140 10 0
```

Those numbers are final simulation time, attacker damage and target damage.
The attacker fell on the missed landing, then stood and walked away; its final
`fallen` value is `false`. Intermediate `inspect` actions preserve earlier
states in `results`. The full result can also be formatted for reading:

```sh
python -c "import json; print(json.dumps(json.load(open('tmp/dfa-result.json', encoding='utf-8-sig')), indent=2))"
```

For a small, human-readable timeline with milestone checks, use the source
encounter runner:

```sh
python -B -m tests.test_gameplay_scenarios --replay dfa_miss --record tmp/gameplay-results
```

A successful run reports one test and `OK`. Open
`tmp/gameplay-results/dfa_miss.md`; detailed observations are in the adjacent
`dfa_miss.json`, and `summary.json` records the check count and replay match.
The [scenario guide](running-scenarios.md#replay-and-record-encounters) explains
the difference between these records and raw CLI output.

## Write a complete small encounter

Save the following as **`tmp/first-encounter.json`**, using UTF-8 without a
byte-order mark. It contains everything this encounter needs; no template
catalogue or external map is required.

```json
{
  "map": {"size": [12, 12]},
  "random": {"seed": 2},
  "units": [
    {
      "name": "Shooter",
      "contact_id": "SS",
      "at": [3, 5, 0],
      "team": 1,
      "facing": 0,
      "weapons": [
        {"name": "IS.MediumLaser", "section": "LA", "critical": 4}
      ]
    },
    {
      "name": "Target",
      "contact_id": "TT",
      "at": [3, 3, 0],
      "team": 2,
      "facing": 180
    }
  ],
  "actions": [
    {"op": "command", "unit": "Shooter", "name": "lock", "args": ["TT"]},
    {"op": "advance", "seconds": 8},
    {"op": "command", "unit": "Shooter", "name": "fire", "args": [0]},
    {"op": "advance", "seconds": 30},
    {"op": "inspect"}
  ]
}
```

Run it and save its result.

PowerShell:

```powershell
python -B -m tools.core_simulation --input tmp/first-encounter.json | Set-Content -Encoding utf8 tmp/first-result.json
```

POSIX shell:

```sh
python -B -m tools.core_simulation --input tmp/first-encounter.json > tmp/first-result.json
```

The same adapter accepts the complete input document on stdin. These alternatives
print the full result to your terminal:

```powershell
Get-Content -Raw tmp/first-encounter.json | python -B -m tools.core_simulation
```

```sh
python -B -m tools.core_simulation < tmp/first-encounter.json
```

For stdin, send one complete JSON document and then end the input. Each invocation
creates a session, executes the entire action list and exits; it does not wait
for a stream of subsequent player commands.

### What the scenario creates

The clear map is 12 by 12 hexes. Each `at` is `[x, y, z]`: a hex position and
altitude. The units begin two hexes apart on opposing teams. `name` selects a
unit in actions, while the two-character `contact_id` is used by targeting
commands. Heading 0 faces north; 180 faces south.

Omitted unit fields use the core adapter's defaults: started, piloted 50-ton
Mechs with armor, internal structure and actuators. Default gunnery is 4 and
piloting is 5. The shooter mounts one Medium Laser in its left arm (`LA`);
`critical: 4` selects its installation slot. Weapon number `0` selects the
first enumerated mounted weapon. The laser needs no ammunition bin.

Initialization creates the world and performs initial contact acquisition before
the action list. `random.seed` sets the engine's random generator so this
unchanged input reproduces its outcome.

### What the actions do

| Action | Effect |
|---|---|
| `lock TT` | Select the visible target; start the default eight-tick lock delay |
| `advance 8` | Process eight seconds of simulation, including lock completion |
| `fire 0` | Fire the shooter's first weapon through ordinary combat rules |
| `advance 30` | Continue events, cooling and weapon recovery for another 30 seconds |
| `inspect` | Return the current state without advancing time |

Read the shot reply, final time and target damage:

```sh
python -c "import json; r=json.load(open('tmp/first-result.json', encoding='utf-8-sig')); print(r['results'][2]['text']); print(r['state']['time']); print(r['state']['units']['Target']['damage_taken'])"
```

Expected output:

```text
Attack hit! (rolled 5 vs BTH 4)
38
5
```

**BTH** is the base-to-hit target number: the attack roll must meet it. Here a
roll of 5 beats a target number of 4 and deals 5 armor damage. These values apply
to the complete example as written, including its seed and action order.

## Understand time and results

Normal simulation ticks are one second; a combat turn is 30 ticks.
`advance` processes that many simulated seconds without waiting that long in
real time. Orders such as speed, heading, startup or sensor changes may schedule
work. Allow time for them to take effect before checking the outcome.

Core and autopilot CLI output has three top-level fields:

| Field | How to use it |
|---|---|
| `results` | One entry per action, in the same order. Read command acceptance, messages and any attack details. An `inspect` entry is a snapshot. |
| `state` | The final snapshot: time, units, maps, pending events and subsystem state exposed by the adapter |
| `draws` | Named random requests and their consumed values, useful when comparing replays |

For the small example, `results[2]` is the firing result and
`state.units.Target.damage_taken` is cumulative target damage.
`state.units.Shooter.weapons` and `heat` expose weapon condition and heat;
`state.events` shows work still pending when the action list ends.

An ordinary gameplay refusal, such as firing a recycling weapon, can return
`accepted: false` while the CLI exits successfully. Some inherited replies use
`ok: false`. Read the accompanying text and attack details as well as the
acceptance flag: accepting an order does not promise a hit or completed movement.
Malformed JSON or invalid core/AI session setup produces a nonzero exit and a
diagnostic on stderr. Some extended actions report errors in their result entries.

A result document is an observation of the run. Keep the original input to
replay it. Persistent subsystem saves have their own load operations; a final
`state` object is not itself a complete scenario input.

Direct sessions can create map, template, character or economy files under
their configured roots. Relative roots are resolved from your **working
directory**, not the input file's directory. The source runners use independent
temporary storage; for manual comparisons, use the
[storage isolation examples](running-scenarios.md#choose-storage-for-direct-sessions).

## Use the same scenario from Python

With the package installed, this code can run from any directory containing the
`tmp/first-encounter.json` you saved:

```python
import json
from tools.core_simulation import CoreSession

with open("tmp/first-encounter.json", encoding="utf-8") as source:
    document = json.load(source)

session = CoreSession(document)
for action in document["actions"]:
    reply = session.action(action)

print(session.snapshot()["units"]["Target"]["damage_taken"])  # 5
```

Constructing a session initializes the world; your program executes its actions.
Keep that session to issue later orders and take more snapshots.
[Python API](python-api.md) covers session use, and
[client integration](client-integration.md) covers a live application connection.

## Install a wheel

A wheel installs the runtime packages and CLI modules. You can use it outside a
source checkout with your own JSON, the complete example above, or copied
encounter inputs.

In a writable directory containing a supplied
`btmux_engine-0.1.0-py3-none-any.whl`, create a separate environment and install
the local file.

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install ./btmux_engine-0.1.0-py3-none-any.whl
New-Item -ItemType Directory -Force tmp | Out-Null
```

POSIX shell:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install ./btmux_engine-0.1.0-py3-none-any.whl
mkdir -p tmp
```

Save the small JSON example as `tmp/first-encounter.json`, then run:

```sh
python -B -m tools.core_simulation --input tmp/first-encounter.json
```

The command and result are the same as for the editable installation.

| Asset | Source checkout / extracted source distribution | Installed wheel |
|---|---|---|
| Runtime packages and `tools.*` CLI modules | Included | Included |
| Examples, encounter runners, tests, feature files and docs | Included | Supply separately from source |
| Original template catalogue and C reference trees | Separate optional inputs | Separate optional inputs |

Run `tests.test_gameplay_scenarios` and `tests.test_autopilot_scenarios` from
the source directory. Wheel-only users run their JSON directly through the
matching `tools.*` module.

## Optional development and build tools

These commands run from the source directory with its environment active.
The standard-library encounter runners need no additional test package:

```sh
python -B -m tests.test_gameplay_scenarios
python -B -m tests.test_autopilot_scenarios
```

The first runs 32 general/line-of-sight encounters, the second three Battlesheep
encounters. Both check gameplay milestones and independently replay inputs
through their public CLIs. Ordinary `unittest` checks also work without pytest.

To add pytest through the optional development extra:

```sh
python -m pip install -e ".[dev]"
```

To build source and wheel distributions:

```sh
python -m pip install build
python -m build
```

The build creates `dist/btmux_engine-0.1.0.tar.gz` and
`dist/btmux_engine-0.1.0-py3-none-any.whl`. In a separate activated environment,
install the wheel with:

```sh
python -m pip install dist/btmux_engine-0.1.0-py3-none-any.whl
```

Advanced acceptance workflows require an external APS-compatible
`gherkin-parser` executable. Source-oracle checks may also require C sources,
a compiler and a POSIX environment. These are optional development requirements;
follow [QA prerequisites](../qa/README.md) and [contributing](../CONTRIBUTING.md)
when you need them.

## Add original unit templates

The small example and saved encounter collection work without the original
unit-template catalogue. To use those designs, Git and explicit setup are
required. From your chosen working directory, these commands select a writable
catalogue location:

```sh
python -m tools.template_catalog setup --path ./tmp/btmux-mechs
python -m tools.template_catalog verify --path ./tmp/btmux-mechs
```

Enable the same path with a string `construction.catalog` value, or set
`BTMUX_TEMPLATE_CATALOG` and use `construction.catalog: true`.
Keep custom writable templates under a separate `construction.root`.
The [catalogue guide](template-catalog-integration.md) explains the pinned
revision, verification, configuration and loading commands. Ordinary simulation
startup does not fetch the catalogue.

## Troubleshooting

| Symptom | Next step |
|---|---|
| `python` is missing or selects an older version | Use the installed Python 3.12 interpreter to create the environment; activate it and check `python --version`. |
| PowerShell blocks activation | Invoke `.\.venv\Scripts\python.exe` in place of `python`; activation is a convenience, and no execution-policy change is required. |
| `No module named tools...` | Install with that environment's `python -m pip`; confirm `python -m pip show btmux-engine`. |
| Input file cannot be found | Check the working directory and the path passed to `--input`. |
| JSON input is rejected | Use one complete JSON document, UTF-8 without a byte-order mark, and the correct adapter. The [core interface](core-simulation-cli.md) lists accepted fields. |
| A command is refused | Read its reply, unit state and pending events; check contact, range, readiness and elapsed time using the [scenario result guide](running-scenarios.md#read-the-results) and the command's subsystem interface. |
| A repeated run differs | Keep the same inputs, seed, action order and initial storage; see [deterministic replays](running-scenarios.md#make-deterministic-replays-and-variants). |

Continue with [Running scenarios](running-scenarios.md) to explore terrain,
sensing, combat and AI orders.

