# Gameplay encounters

The [built-in AI companion](AI.md) adds three Battlesheep encounters, 40 milestones,
and three independent public stdin replays.

From the engine root, run all 32 variants (18 original and 14 LOS encounters):

```powershell
python -B -m tests.test_gameplay_scenarios
```

The test driver sends ordinary commands and advances real ticks. Each encounter
also runs independently through the existing public stdio interface, comparing
command replies, final units/maps, pending events, and every named random draw.
Temporary character/template/map storage keeps runs independent. The collection
also works with ordinary unittest discovery.

```powershell
python -B -m tests.test_gameplay_scenarios --replay c3_maneuver_damage
python -B -m tests.test_gameplay_scenarios --record tmp/gameplay-results
```

`--replay` prints detailed JSON; `--record` saves JSON evidence and concise
Markdown timelines. Combine them to record one encounter. Failed milestones
remain failing tests, with their recorded observations; no expected-failure
markers hide discrepancies.

`manifest.json` maps the fixtures to their existing public interfaces. Each JSON
is also directly replayable, for example:

```powershell
python -B -m tools.communications --input examples/gameplay_scenarios/c3_maneuver_damage.json
python -B -m tools.aerospace --input examples/gameplay_scenarios/bay_crowded.json
python -B -m tools.core_simulation --input examples/gameplay_scenarios/dfa_miss.json
python -B -m tools.maps_environment --input examples/gameplay_scenarios/fire_smoke.json
```

Direct CLI invocations use the interface's default storage directories; the test
runner substitutes temporary directories. Replays use only commands, clock
advances, and read-only inspections after setup. There is no outcome assignment,
damage injection, callback scheduling, or diagnostic simulation substitute.
Scalar MT seeds reproduce the encounters; C3 additionally supplies finite named
random inputs for the hardware criticals. No weapon metadata is overridden.

The inputs and fractional-position observations can also be consumed by a
separate Godot presentation client.

| Family | Replay input |
|---|---|
| C3 | [c3_maneuver_damage](c3_maneuver_damage.json) |
| DFA | [dfa_hit](dfa_hit.json), [dfa_hit_fall](dfa_hit_fall.json), [dfa_miss](dfa_miss.json) |
| Unloading | [bay_orderly](bay_orderly.json), [bay_crowded](bay_crowded.json) |
| Stacking | [stack_2](stack_2.json), [stack_3](stack_3.json), [stack_dropship](stack_dropship.json) |
| Ledges | [ledge_stop](ledge_stop.json), [ledge_collision](ledge_collision.json), [ledge_fall](ledge_fall.json) |
| Ice | [ice_intact](ice_intact.json), [ice_break](ice_break.json) |
| Artillery | [artillery_hit](artillery_hit.json), [artillery_scatter](artillery_scatter.json) |
| Reactor | [reactor](reactor.json) |
| Fire/smoke | [fire_smoke](fire_smoke.json) |

## LOS and difficult terrain

The new encounters use the same collection command and public JSON interfaces.
Their timelines separate both observers' contact flags/displays, locks, sight/BTH,
weapon recycling/ammunition, real damage, and subsequent movement. Observations
read the cached directed LOS matrix; they never call the sensor decision or LOS
calculation to force an outcome. Actor inboxes are retained in the JSON evidence.

Infantry uses the supported **MW personal-combat class**, a stock
`PC.IntekLaserRifle`, and 45 charges. Battle suits are four live members with a
stock `CL.ERSmallLaser`. Mechs use normal 50-ton section durability. Named streams
are finite, contain only consumed inputs, and exercise real detection, hit,
personal-damage conversion and location rolls. The smoke encounter uses MT seed 1.
The fixtures contain no preassigned contacts, hidden states, diagnostic actions,
sensor overrides or modified weapon metadata.

| Encounter | Replay input |
|---|---|
| Infantry: clear / light / heavy woods | [los_woods_mw_clear](los_woods_mw_clear.json), [los_woods_mw_light](los_woods_mw_light.json), [los_woods_mw_heavy](los_woods_mw_heavy.json) |
| Battle suits: clear / light / heavy woods | [los_woods_bsuit_clear](los_woods_bsuit_clear.json), [los_woods_bsuit_light](los_woods_bsuit_light.json), [los_woods_bsuit_heavy](los_woods_bsuit_heavy.json) |
| Hiding at five / strictly under three hexes | [los_hidden_five](los_hidden_five.json), [los_hidden_three](los_hidden_three.json) |
| Stealth suit and active probes | [los_hidden_probe](los_hidden_probe.json) |
| Asymmetric combat, hex targeting and sensor arcs | [los_asymmetric_sensors](los_asymmetric_sensors.json) |
| Open ground, woods, lost locks and reacquisition | [los_cover_transitions](los_cover_transitions.json) |
| Ridge ascent, partial cover and posture | [los_ridge_cover](los_ridge_cover.json) |
| Darkness, light-amp and searchlight firefight | [los_night_searchlight](los_night_searchlight.json) |
| Moving fight through fire and smoke | [los_smoke_maneuver](los_smoke_maneuver.json) |

For example, replay the asymmetric fight with detailed evidence:

```powershell
python -B -m tests.test_gameplay_scenarios --replay los_asymmetric_sensors
```

Or use an existing public CLI directly:

```powershell
python -B -m tools.core_simulation --input examples/gameplay_scenarios/los_asymmetric_sensors.json
python -B -m tools.communications --input examples/gameplay_scenarios/los_hidden_three.json
python -B -m tools.maps_environment --input examples/gameplay_scenarios/los_smoke_maneuver.json
```

The short woods ranges come from **intervening woods points**, not a universal
infantry range cap: three points block visual detection; target woods are excluded
from that count and separately affect BTH. Thus the first visible occupied-hex
separation on the straight test lane is three in light woods and two in heavy
woods. Fractional range at a crossing can be larger (3.45 / 2.47 here).
Unhidden small units can be detected at seven on clear ground. Hiding instead
adds a five-hex acquisition gate, with automatic detection strictly inside three
only after the other gates pass. Infrared excludes both small classes; EM excludes
MW but can detect suits. These differences explain the demonstrated one-way fights.
