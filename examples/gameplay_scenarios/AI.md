# Built-in AI encounters

These three encounters extend the existing 32-scenario collection. The original
fixtures and milestone checks remain unchanged. Each uses `tools.autopilot`,
registered built-in controllers, normal player radio/steering commands, and real
clock updates. Two reload active AI state. No action injects a hit, destination,
contact, callback or completed outcome.

| Input | Gameplay | Milestones |
|---|---|---:|
| [ai_navigation.json](ai_navigation.json) | 466 ticks: addressed/all radio, active reload, route around a ridge, replacement with follow, moving leader, arrival and cancellation | 16 |
| [ai_combat.json](ai_combat.json) | 151 ticks: autonomous contacts, EM/IR selection, repeated firing, ammo/heat/damage, shutdown/startup, replacement target | 12 |
| [ai_aerospace.json](ai_aerospace.json) | 140 ticks: historical callback chains, active reload/profile rebuilding, delayed sensor changes, gun off/on, real kill and retargeting | 12 |

```powershell
python -B -m tests.test_autopilot_scenarios
python -B -m tests.test_autopilot_scenarios --replay ai_navigation
python -B -m tests.test_autopilot_scenarios --record tmp/ai-results
python -B -m tools.autopilot --input examples/gameplay_scenarios/ai_combat.json
Get-Content -Raw examples/gameplay_scenarios/ai_aerospace.json | python -B -m tools.autopilot
```

The driver reuses `tests.test_gameplay_scenarios.observation` and
`tests.gameplay_los_support` for read-only positions, damage, sensors and contacts.
It samples normal ticks and independently replays every JSON input through public
stdin. It compares all named random draws, non-advance action results, final
units, maps, occupants, controllers and pending callbacks. Command-boundary
checks observe the completed tick before the next order changes state.

`--record tmp/ai-results` generates JSON containing compact frame evidence, delivered messages, actions,
checks and random draws; the accompanying Markdown files are concise timelines.
`summary.json` records the 40 milestone results and three public replay comparisons. Seeds reproduce draws through the engine RNG, including source
acknowledgment and reply-delay draws. Default direct CLI runs write snapshots
under the session's ordinary storage root; the test driver isolates both runs in
separate temporary directories.

Additional focused coverage lives in `tests/test_autopilot.py`: queue/codec
boundaries, malformed snapshot rejection, service overrides, source scores and
ties, navigation variants, physical attacks, towing, real hangar transfer,
containment cleanup and historical timing. The review-correction tests also cover
persistent neighbor slots, disembark identity, live callback guards, the running
speed margin, hiding beneath smoke/fire, preserved callback order, atomic name
validation, and non-player startup skills. Run both with:

```powershell
python -B -m unittest tests.test_autopilot tests.test_autopilot_review_corrections
```

See [the public AI interface](../../docs/autopilot-cli.md) for controller schemas,
radio syntax, source quirks and the scope of subsystem persistence.
