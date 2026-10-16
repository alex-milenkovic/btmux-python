# Contributing

Use Python 3.12 for development and checks. The package supports Python 3.12 or
newer, and normal simulation has no third-party dependencies. Read the
[architecture](docs/architecture.md) and [Python API](docs/python-api.md) before
changing shared systems; the [C-to-Python guide](docs/porting/C_TO_PYTHON.md)
explains the behavior and source profiles being preserved.

## Set up a source checkout

The first-release source location is
[alex-milenkovic/btmux-python](https://github.com/alex-milenkovic/btmux-python).
Clone it and enter the repository root:

```sh
git clone https://github.com/alex-milenkovic/btmux-python.git
cd btmux-python
```

Create an environment:

```sh
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` in PowerShell or
`. .venv/bin/activate` in a POSIX shell, then install the editable package:

```sh
python -m pip install -e .
```

The standard-library tests and encounter runners need no additional packages.
For pytest, install the optional development extra:

```sh
python -m pip install -e ".[dev]"
```

Editable installation keeps the public top-level imports (`core`, `entities`,
`data`, `physics`, `systems` and `tools`) pointed at your source. Run source-based
tests from the repository root so their fixtures and subprocesses resolve
consistently. Use writable temporary directories for character, template, map
and economy data.

The original unit catalogue is optional. To use it, follow
[template catalogue setup and verification](docs/template-catalog-integration.md).
Setup is explicit; ordinary sessions do not fetch dependencies. Keep custom
templates and other writable stores separate from the catalogue.

## Make and check a focused change

Read [LICENSE](LICENSE) and [CREDITS.md](CREDITS.md), including the additional
file-specific notices. Preserve original credits and source references. Add a
prominent comment to each changed source file recording how and when you
changed it, and follow the custom license's modification-availability terms.
The repository name does not change the `btmux-engine` distribution or its
existing imports and CLI interfaces.

Find the command or callback that owns the behavior, then follow its calls into
the relevant production system. The [session adapter chain](docs/architecture.md#how-sessions-compose)
is useful for finding the actual command entry point. Change the shared behavior
there so Python callers, JSON scenarios and clients observe the same result.

Select tests around the changed rule or boundary. For example:

```sh
python -B -m unittest tests.test_core_geometry tests.test_core_cli
python -B -m unittest tests.test_heat tests.test_core_skills
python -B -m unittest tests.test_autopilot tests.test_autopilot_review_corrections
```

These are separate examples of focused selections; run the relevant one.
Existing free-function tests can use their script entry point or pytest; using
unittest on a module with only free functions can run zero tests. For example:

```sh
python -B tests/test_events.py
```

Use `rg` to find related test names and callers. Add a regression when changing
behavior, with assertions for the public result and affected state. For a
command change, include its actual session/CLI route when validation, actor
selection or serialization matters. Do not replace movement, damage or event
callbacks with expected outcomes in a gameplay test.

### Gameplay encounters

The retained collections exercise complete interactions using ordinary commands
and real ticks:

```sh
python -B -m tests.test_gameplay_scenarios
python -B -m tests.test_autopilot_scenarios
```

The first collection has 32 general/LOS encounters; the second has three
Battlesheep encounters and 40 milestones. Each runner also compares its
programmatic execution with an independent public stdin replay. Their own
temporary roots isolate persistent state.

For a single encounter and optional local output:

```sh
python -B -m tests.test_gameplay_scenarios --replay dfa_miss
python -B -m tests.test_autopilot_scenarios --replay ai_navigation
python -B -m tests.test_gameplay_scenarios --record tmp/gameplay-results
python -B -m tests.test_autopilot_scenarios --record tmp/ai-results
```

See [running scenarios](docs/running-scenarios.md), the
[encounter catalogue](examples/gameplay_scenarios/README.md), and
[AI encounters](examples/gameplay_scenarios/AI.md) for inputs and expectations.
The [manifest](examples/gameplay_scenarios/manifest.json) chooses the correct
core, maps, communications or Aerospace interface; AI inputs use `tools.autopilot`.
Direct CLI invocations use their configured/default storage roots.

For reproducible scenarios, specify the seed, options, object IDs and initial
state. Keep command and tick order stable. Finite named streams must supply every
reached consumer, including initialization; never silently extend an exhausted
stream. Observe existing state after commands instead of recalculating a sensor
decision or invoking a gameplay helper just to obtain an expected result.
Compare replays in independent storage directories: initialization writes and
retained inventory can otherwise make identical inputs differ.

## Optional acceptance and C-oracle checks

These checks are source-distribution tools with additional prerequisites, not
normal engine runtime requirements. [qa/README.md](qa/README.md) describes them.

The acceptance pipeline requires an external APS-compatible `gherkin-parser` on
PATH. Its command contract is `gherkin-parser FEATURE OUTPUT_JSON`; it is not
installed by the engine's development extra. With that prerequisite available:

```sh
python -B -m tools.run_acceptance --suite core_simulation
```

The runner creates `tmp/acceptance`, generates Python bindings from the selected
feature files and executes them. Use `--only FEATURE_STEM` to narrow a suite.
Feature definitions and executable bindings live in [features](features/) and
[acceptance](acceptance/).

Source-based QA needs the separately supplied original C checkout at
`btmux/btmux/btech/src/`. Compiled oracles also need a POSIX environment and `cc`.
Historical fighter checks use the six-location reference snapshot described in
the [fighter guide](docs/six-location-aerofighters-cli.md). Catalogue QA needs its
explicitly configured dependency. Consult the selected driver's help; some are
scripts and others are package entry points. For example, once the C/compiler
prerequisites are present:

```sh
python -B qa/core_simulation.py --only bv --workers 2
```

Document the selected checks and any missing prerequisite accurately. A test
requiring an unavailable compiler or reference checkout has not passed simply
because normal Python execution works.

## Preserve source conventions and current rules

Keep original C names, file/function references, notices and credits when editing
translated code. Use a nearby technical comment to explain a deliberate numerical
or behavioral compatibility choice. The structured references in [specs](specs/README.md)
help find original identities; their initial inventory status fields are not
current completion claims. Use the [completion guide](docs/porting/COMPLETION.md)
for current scope.

C integer truncation, unsigned wrapping, float32 operations, guard order, random
consumption, event timing and callback ownership can all affect observable
behavior. Preserve them where required by the mapped rule; avoid replacing them
with superficially equivalent Python arithmetic. Test boundary conditions and
the command caller as well as direct helper behavior.

Current compatibility choices include:

- Heat shutdown checks begin at 14, using ordinary fixed 2d6 targets for every
  pilot, including AI. No shutdown avoidance roll occurs below 14. The separate
  ammunition/overheat gate still begins at 10.
- Broad gunnery and piloting are defaults. Either expanded selection can be
  enabled independently; fixtures needing it should say so explicitly.
- Fighters use the historical six-location Aerospace model. DropShips retain
  their distinct rules and adapters.
- Battlesheep is built in and calls ordinary gameplay services. Source-disabled
  queue instructions retain their documented behavior; client-side shortcuts
  must not silently substitute a different executor.

See the [core interface](docs/core-simulation-cli.md),
[historical fighter guide](docs/six-location-aerofighters-cli.md) and
[AI interface](docs/autopilot-cli.md) for subsystem configuration and commands.

## Build and check packaging

Install the optional build frontend and build both distributions:

```sh
python -m pip install build
python -m build
```

The default build frontend isolates its backend requirements. Test the resulting
wheel in a separate virtual environment, from outside the source checkout:

```sh
python -m pip install path/to/btmux_engine-0.1.0-py3-none-any.whl
python -B -m tools.core_simulation --input path/to/scenario.json
```

Replace those paths with the built wheel and a copied scenario. This checks
installed imports and resources instead of accidentally importing the checkout.
Runtime module CLIs work from a wheel; examples, tests, QA, feature files and
documentation are source-checkout/source-distribution assets.

When adding packages or data, check [pyproject.toml](pyproject.toml) and
[MANIFEST.in](MANIFEST.in). Keep the root and packaged
`template-catalog.lock.json` files identical if updating the pin. Do not bundle
the optional C/template reference checkouts, caches or generated replay output.

## Update documentation with the interface

Update the relevant public schema guide when adding or changing a field,
command, refusal, default or save format. Update [Python examples](docs/python-api.md)
and [client integration](docs/client-integration.md) when the application
boundary changes. Run newly introduced executable examples with deterministic
inputs and temporary storage.

Use repository-relative Markdown links and portable commands. Explain behavior
for the reader using the engine; keep technical source references useful.
Before sharing a change, inspect its diff, run `git diff --check`, check links and
record the focused validation performed. Describe the concrete behavior change,
its reason, tests run and any remaining limitation in the change summary.

