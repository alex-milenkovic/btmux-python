# Friday AeroFighter

Friday is a purpose-built four-location AeroFighter fixture. It exercises the
template loader's compatibility with explicit layouts. Historical fighter
gameplay uses the six-location profile described in the
[fighter guide](../../../docs/six-location-aerofighters-cli.md).

The design deliberately specifies 50 tons, maximum speed64.50, SI20, fuel1000,
and ten single heat sinks. The source engine formula
`rint((2 * max_speed / 10.75) / 3) * tons` gives rating200. Armor is40/30/30/20
and internals10 in Nose/Left Wing/Right Wing/Aft Side. These are explicit QA
design choices, not a conversion of six historical locations or online data.

`mech.utils.c`'s `aero_locs` supplies the four supported names.
`mech.build.c:FillDefaultCriticals` supplies aft engine criticals3/11 and ten
remaining heat-sink criticals. Friday writes them explicitly, because file
loading does not imply editor-default insertion. The nose has a real Medium
Laser, Sensors, Cockpit and LifeSupport; the nose and wings carry one each of
10_Standard,10_Inferno,10_Cluster. Part identifiers resolve through the actual
construction catalog. Each bomb weighs1020 internal weight units according to
`aero.bomb.c`/`mech.utils.c:GetPartWeight` and the part-weight consumer. Startup computes
cargo3060; releasing the first bomb leaves2040. The actual effective maximum
before release is64.5*51200/(51200+3060); launch desired speed uses raw64.5*2/3.

The template includes SI explicitly. The loader's `SI` and `Fuel` fields set
current/original values; tests inspect loaded SI, engine, sinks, armor, internals
and criticals before startup. No post-load repair, SI injection, success flag or
loader alias is used. A failed/partial load is a test failure.

Replay with `python3 qa/aerospace.py --only procedures/Friday --workers 4`.
The flight case starts, taxis, launches, sets thrust/heading/climb/dive, advances
the ordinary clock, consumes fuel and lands. The bombing case launches, climbs,
lists/aims/releases a physical bomb and resolves the timed impact. Replays and
assertion results are in `tmp/qa-aerospace/procedures/Friday-*`.
