# Completion and verification

The engine implements all sixteen simulation modules and the five-file Battlesheep controller port. Each simulation module completed implementation repair and independent C-source review. All **1,972 original behavioral findings** are verified closed; Battlesheep has **119/119 active source identities** verified, all nine review corrections closed, and all four radio/heartbeat integration claims closed.

Use [C to Python](C_TO_PYTHON.md) to locate a source function and its Python implementation, the [scenario guide](../running-scenarios.md) to explore complete encounters, and [getting started](../getting-started.md) to install and run the engine.

## Implemented scope

A **source identity** is an original `C file::function` entry. A **behavioral finding** records a specific missing or differing behavior within an identity. One function can produce several findings; shared functions can also have a separate historical Aerospace review. Neither count is a test count.

| Module | Implemented scope | Original findings now verified closed |
|---|---|---:|
| Utilities (`AUD-UTILS`) | Shared identity, geometry, parts, ammunition, mass and valuation helpers | 73 |
| Templates (`AUD-TEMPLATES`) | Unit definitions, template loading/search, construction consistency and editing | 91 |
| Maps (`AUD-MAPS`) | Terrain, objects, membership, weather, buildings and environmental persistence | 81 |
| Repair/economy (`PILOT-REPAIR`) | Technician work, stores, cargo, salvage, jobs, reports and transport | 334 |
| Pilots (`AUD-PILOTS`) | Characters, skills/XP, injury, consciousness, infantry and battle armor | 109 |
| Sensors (`AUD-SENSORS`) | Directed LOS, detection/retention, targeting, ECM, lights, spotting and TAG | 43 |
| Communications (`AUD-COMMS`) | Radios, relays, C3/C3i and built-in controller reception | 83 |
| Heat (`AUD-HEAT`) | Heat, dumping, fire, per-tick movement/cargo updates and stability | 100 |
| Movement (`AUD-MOVEMENT`) | Movement commands, posture/modes, ice, jumps, orbital descent and path costs | 143 |
| Damage (`AUD-DAMAGE`) | Damage transfer, criticals, equipment failures and destruction | 128 |
| Firing (`AUD-FIRING`) | Shot admission, to-hit, ammunition/modes, missiles, impacts and weapon groups | 92 |
| Physical combat (`AUD-PHYSICAL`) | Hit locations, melee, charges and death from above | 101 |
| Special combat (`AUD-SPECIAL-COMBAT`) | Advanced equipment, artillery, mines and explosive actions | 136 |
| Core (`AUD-CORE`) | Clocks, events, random statistics, startup/shutdown and controller services | 219 |
| Aerospace (`AUD-AEROSPACE`) | Historical six-location fighters, flight, bombing, DropShip bays/turrets and shared branches | 137 |
| HUD (`AUD-HUD`) | Status, armor/equipment, scans, contacts, tactical/navigation displays and HUD requests | 102 |
| **Total** | **All sixteen modules complete** | **1,972** |

The module passes verified 1,968 findings. The later AI review closed the remaining two Communications and two Core findings, producing the final counts above. The C index retains the 43 supplemental historical Aerospace source records with explicit profile labels.

Battlesheep implements queue and controller lifecycle, command persistence, A* paths, predictive steering, radio orders, sensor choice, weapon profiles, target selection, firing and physical attacks. It uses the normal gameplay services and tick/event paths. The [AI interface](../autopilot-cli.md) explains commands and snapshot continuation; the [AI encounters](../../examples/gameplay_scenarios/AI.md) demonstrate navigation, ground combat and historical Aerospace behavior.

## Review and subsequent corrections

Independent source reviews checked the implementation against the applicable C bodies, macros, helpers, callers and event sequences, including the effects of corrections on shared consumers. Those source reviews and executed checks are distinct forms of evidence. The final results above include the correction reviews, rather than the initial audit's missing/partial classifications.

Subsequent regression maintenance resolved **104 records**, with **three Windows symlink-capability skips**. The final missile correction preserves the original caller guard: an ordinary fired missile miss stops before AMS/pod/Swarm impact dispatch, while the launcher completes its normal firing costs. Direct helper misses and later Swarm hops retain their separate source behavior. The [missile checks](../../tests/test_combat_missiles_completion.py) exercise this distinction through both helpers and public commands.

The current heat and skill rules were independently verified and committed in `23676f5`: heat shutdown starts at 14, and broad gunnery/piloting skills are the defaults, with independent opt-in to expanded modes. The associated cooling fixture now matches the unchanged binary32 calculation, and all four cooling acceptance examples pass. [Compatibility adaptations](C_TO_PYTHON.md#arithmetic-randomness-and-intentional-adaptations) also explains fixed equal-bound weather growth.

The source authority remains the general C reference plus recovered revision `96f2131705a7fe51c3c6f7da741930ff06a93644` for six-location Aerospace and related branches. Inactive source bodies, extraction artifacts and the excluded MUX host infrastructure remain explicitly classified in [C to Python](C_TO_PYTHON.md#simulation-scope-and-the-mux-host-boundary). Completion describes this simulation product and its supported interfaces.

## Recorded execution results

These are completed runs at their respective verification stages. They are separate selections with overlap, so their counts should not be added into a unique-test total.

| Check collection | Recorded result |
|---|---|
| Final missile caller/helper correction | 172/172 focused tests passed; two public JSON/stdio replays each passed 12/12 checks. |
| Heat and skill-default correction | 260 focused tests and five turret tests passed; 14/14 core-skill examples, 8/8 shutdown examples and three affected turret examples passed. The subsequent cooling fixture check passed all four examples. |
| [General/LOS encounters](../../examples/gameplay_scenarios/README.md) | 32/32 passed after repository preparation, including independent public-interface replay comparisons. |
| [Battlesheep encounters](../../examples/gameplay_scenarios/AI.md) | 3/3 passed after preparation, including 40 milestones and independent stdin replay comparisons. |
| Preparation's affected-test selection | 189 tests reported OK, with three Windows symlink-capability skips. |
| [Battle Value C-oracle collection](../../qa/core_simulation.py) | 302 cases passed with Python 3.12.3 and a C compiler in a POSIX environment. |
| [Legacy hex geometry](../../tests/test_hexmath.py) and [core geometry](../../tests/test_core_geometry.py) | 13/13 and 7/7 passed after aligning the east-bearing assertion with the original C arithmetic. |
| Editable and wheel installation | Both worked outside the checkout on Python 3.12.14. Core and AI file/stdin runs matched programmatic session execution in isolated storage directories. |
| Distribution build | Source distribution and wheel built successfully, including a wheel built from the source distribution. Runtime imports and packaged catalogue-pin access worked in the installed environment. |

Encounter drivers send ordinary commands and advance real ticks. They compare command results, final unit/map state, pending work and random draws against independent batch-CLI runs. The AI collection also checks controllers and occupants. Temporary storage isolates the runs; expected outcomes are observed rather than injected.

## Rerun the public checks

Use Python 3.12 or newer and install from a source checkout as described in [getting started](../getting-started.md). The examples, tests, features and QA tools are checkout/source-distribution assets; they are not installed as test collections in the runtime wheel.

Run the two encounter collections from the repository root:

```sh
python -B -m tests.test_gameplay_scenarios
python -B -m tests.test_autopilot_scenarios
```

To inspect one encounter or save timelines, use the existing drivers:

```sh
python -B -m tests.test_gameplay_scenarios --replay c3_maneuver_damage
python -B -m tests.test_autopilot_scenarios --replay ai_navigation
python -B -m tests.test_gameplay_scenarios --record tmp/gameplay-results
python -B -m tests.test_autopilot_scenarios --record tmp/ai-results
```

For focused controller and geometry checks:

```sh
python -B -m unittest tests.test_autopilot tests.test_autopilot_review_corrections
python -B tests/test_hexmath.py
python -B -m unittest tests.test_core_geometry
```

For the recorded missile caller/helper selection:

```sh
python -B -m unittest tests.test_aim tests.test_m4_battle tests.test_combat_impacts_completion tests.test_combat_missiles_completion tests.test_missile tests.test_firing_review_corrections
```

The recorded main heat/skill selection and turret suite can be rerun with:

```sh
python -B -m unittest tests.test_heat tests.test_heat_updates tests.test_heat_updates_cli tests.test_heat_dependency_edges tests.test_heat_architecture tests.test_core_skills tests.test_core_cli tests.test_piloting tests.test_pilot_characters tests.test_pilots_audit_repairs tests.test_character_awards
python -B -m unittest tests.test_aerospace_turrets
```

The executable [heat feature](../../features/heat_updates/heat.feature) contains the cooling and shutdown acceptance examples. Advanced feature execution requires the external APS-compatible `gherkin-parser`; [QA prerequisites](../../qa/README.md) explains that optional workflow. Compiled C-oracle checks additionally require the reference source, a C compiler and a POSIX environment. With those prerequisites in place, the recorded BV command is:

```sh
python3 -B qa/core_simulation.py --only bv --workers 2
```

Use [running scenarios](../running-scenarios.md) for fixture selection and command details, [contributing](../../CONTRIBUTING.md) for selecting checks for a change, and [optional C references](C_TO_PYTHON.md#obtain-optional-reference-checkouts) to obtain the original source. Direct subsystem CLIs use their configured persistent storage; choose disposable directories when comparing independent runs. The encounter drivers already supply them.
