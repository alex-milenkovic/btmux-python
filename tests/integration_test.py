#!/usr/bin/env python3
"""
Integration Test Harness for BTMux Python Reimplementation.

This module provides a text-based command interface for testing the complete
combat simulation with two mechs on an empty map. It integrates all systems
through the M1 engine wiring:

- Clock 1 (dispatch): MECH special-object updates (heat, FIRED clear) via
  wire_standard_systems, plus per-mech event-driven movement
  (physics.movement.start_move_event)
- Clock 2 (heartbeat): weapon recycle countdown (recycle_weaponry)
- Clock 3 (commands): every player command routes through
  engine.inject_command, exactly like the C's between-tick command execution

Weapons are fired through systems.combat.fire_weapon against the mech's own
weapon list (mech.weapons); heat, ammo and recycle are all handled by the
engine - the harness adds nothing out-of-band.

Usage:
    python -m tests.integration_test

Or in interactive mode:
    python -m tests.integration_test --interactive

Commands:
    status [mech]           - Show mech status (position, heat, armor, weapons)
    move <mech> <speed>     - Set mech's desired speed (KPH)
    heading <mech> <deg>    - Set mech's desired facing (degrees)
    fire <mech> <weapon#> [target]  - Fire a weapon at target
    tick [n]                - Advance simulation by N ticks (default 1)
    run <n>                 - Run simulation for N ticks with status updates
    weapons <mech>          - List mech's weapons and status
    armor <mech>            - Show detailed armor status
    help                    - Show this help
    quit                    - Exit the harness
"""

import sys
import os
import readline  # Enable arrow keys and history in input

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Optional

from core.game_loop import GameEngine, wire_standard_systems
from physics.hexmath import hex_distance, hex_bearing
from physics.movement import start_move_event
from systems.heat import get_heat_indicator
from systems.combat import (
    WEAPON_TICK,
    calculate_bth, check_for_critical, determine_hit_group,
    estimate_hit_chance, find_ammo_for_weapon, fire_weapon,
)
from systems.piloting import find_pilot_gunnery
from entities.crittypes import i2ammo
from entities.mech import Mech, MechStatus, Location, WeaponState
from entities.weapon import get_weapon_by_index
from data.templates import (
    TEST_MECH_TEMPLATE, ASSAULT_MECH_TEMPLATE, LIGHT_MECH_TEMPLATE,
    create_mech_from_template,
    get_template, list_templates, MechTemplate
)


# =============================================================================
# WeaponState helpers
#
# The authoritative weapon state lives on the mech itself: mech.weapons is
# the per-mech weapon list (WeaponState) and the recycle countdown is the
# weapon's first crit slot's data byte (mech.h:599-608), counted down by the
# engine's heartbeat clock.
# =============================================================================

def weapon_crit_slot(mech: Mech, ws: WeaponState):
    """The weapon's first crit slot - holds the recycle countdown."""
    return mech.sections[ws.section].criticals[ws.critical]


def weapon_recycle_remaining(mech: Mech, ws: WeaponState) -> int:
    """Seconds until the weapon finishes recycling (0 = ready)."""
    return weapon_crit_slot(mech, ws).data


def weapon_is_ready(mech: Mech, ws: WeaponState) -> bool:
    """Ready = not recycling and not destroyed."""
    return weapon_recycle_remaining(mech, ws) == 0 and not ws.destroyed


def weapon_ammo_rounds(mech: Mech, ws: WeaponState) -> int:
    """Total rounds in the mech's bins for this weapon (-1 = energy/infinite)."""
    weapon = get_weapon_by_index(ws.weapon_idx)
    if not weapon.uses_ammo:
        return -1
    ammo_type = i2ammo(ws.weapon_idx)
    total = 0
    for section in mech.sections:
        for crit in section.criticals:
            if crit.type == ammo_type:
                total += crit.data
    return total


def weapon_has_ammo(mech: Mech, ws: WeaponState) -> bool:
    """Can the weapon feed? (energy weapons always can)"""
    return weapon_ammo_rounds(mech, ws) != 0


# =============================================================================
# Combat Unit - thin naming wrapper around a Mech
# =============================================================================

@dataclass
class CombatUnit:
    """A named mech; weapons live on the mech itself (mech.weapons)."""
    mech: Mech
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = self.mech.name


# =============================================================================
# Integration Test Harness
# =============================================================================

class IntegrationTestHarness:
    """
    Text-based command interface for testing the BTMux simulation.

    This harness creates two mechs on an empty map and allows the user
    to control them via commands, observing the behavior of all systems.
    """

    def __init__(self, tick_duration: float = 0.0):
        """
        Initialize the test harness.

        Args:
            tick_duration: Seconds per tick (0 = instant, no delays)
        """
        self.engine = GameEngine(tick_duration=tick_duration)
        self.units: dict[str, CombatUnit] = {}
        self.running = False
        self.verbose = True
        self.auto_advance = False  # Auto-advance ticks every second

        # Standard engine wiring: MECH object updates (heat / FIRED clear)
        # on the dispatch clock, recycle on the heartbeat clock.  Movement
        # is event-driven per mech - armed by the speed/heading commands.
        wire_standard_systems(self.engine)

    # =========================================================================
    # Mech Spawning
    # =========================================================================

    def spawn_mech(
        self,
        name: str,
        template: MechTemplate,
        x: int = 50,
        y: int = 50,
        facing: int = 0,
    ) -> CombatUnit:
        """
        Spawn a mech from a template.

        Args:
            name: Unique name for this mech
            template: MechTemplate to create from
            x, y: Starting hex position
            facing: Initial facing (degrees)

        Returns:
            CombatUnit wrapping the mech
        """
        # Create mech from template (weapons + pilot included)
        mech = create_mech_from_template(template, name=name)
        mech.set_hex_position(x, y)
        mech.facing = facing
        mech.desired_facing = facing
        mech.set_status(MechStatus.STARTED)

        # Create combat unit
        unit = CombatUnit(mech=mech, name=name)

        # Register with engine
        self.engine.register_entity(mech)
        self.units[name.lower()] = unit

        return unit

    def spawn_default_mechs(self) -> None:
        """Spawn two mechs for testing: Alpha (TestMech) and Bravo (AssaultMech)."""
        self.spawn_mech("Alpha", TEST_MECH_TEMPLATE, x=50, y=50, facing=0)
        self.spawn_mech("Bravo", ASSAULT_MECH_TEMPLATE, x=50, y=55, facing=180)

        print("Spawned mechs:")
        print(f"  Alpha (TestMech) at (50, 50) facing North")
        print(f"  Bravo (AssaultMech) at (50, 55) facing South")
        print(f"  Distance: {hex_distance(50, 50, 50, 55):.1f} hexes")

    # =========================================================================
    # Status Display
    # =========================================================================

    def show_status(self, unit_name: Optional[str] = None) -> None:
        """Show status of one or all mechs."""
        if unit_name:
            unit = self._get_unit(unit_name)
            if unit:
                self._print_unit_status(unit)
        else:
            for unit in self.units.values():
                self._print_unit_status(unit)
                print()

    def _print_unit_status(self, unit: CombatUnit) -> None:
        """Print detailed status for a combat unit."""
        m = unit.mech

        # Header
        print(f"=== {unit.name} ({m.mech_type}) ===")
        print(f"  Tonnage: {m.tonnage}t | Status: {m.status_string()}")

        # Position
        print(f"  Position: Hex ({m.x}, {m.y}) | Float ({m.fx:.1f}, {m.fy:.1f})")
        print(f"  Facing: {m.facing}° (desired: {m.desired_facing}°)")

        # Movement
        print(f"  Speed: {m.speed:.1f} KPH (desired: {m.desired_speed:.1f}) | Max: {m.max_speed:.1f}")

        # Heat
        heat_color = get_heat_indicator(m.heat)
        heat_display = f"{m.heat:.1f}"
        if heat_color == "yellow":
            heat_display += " [WARM]"
        elif heat_color == "red":
            heat_display += " [HOT!]"
        print(f"  Heat: {heat_display} | +{m.plus_heat:.1f} / -{m.minus_heat:.1f} | Sinks: {m.effective_heat_sinks}")

        # Armor summary
        total_armor = sum(s.armor + s.rear for s in m.sections)
        total_internal = sum(s.internal for s in m.sections)
        print(f"  Armor: {total_armor} | Internal: {total_internal}")

        # Weapons summary
        ready_weapons = sum(1 for ws in m.weapons
                            if weapon_is_ready(m, ws) and weapon_has_ammo(m, ws))
        total_weapons = len(m.weapons)
        print(f"  Weapons: {ready_weapons}/{total_weapons} ready")

    def show_weapons(self, unit_name: str) -> None:
        """Show weapon status for a mech."""
        unit = self._get_unit(unit_name)
        if not unit:
            return

        m = unit.mech
        print(f"=== {unit.name} Weapons ===")
        for i, ws in enumerate(m.weapons):
            w = get_weapon_by_index(ws.weapon_idx)
            status_parts = []

            # Ready status
            recycle = weapon_recycle_remaining(m, ws)
            if ws.destroyed:
                status_parts.append("DESTROYED")
            elif recycle > 0:
                status_parts.append(f"CYCLING ({recycle}s)")
            else:
                status_parts.append("READY")

            # Ammo
            rounds = weapon_ammo_rounds(m, ws)
            if rounds == -1:
                ammo_str = "infinite"
            elif rounds == 0:
                ammo_str = "NO AMMO"
                status_parts.append("!")
            else:
                ammo_str = f"{rounds} shots"

            # Location
            loc_name = Location(ws.section).name

            # Range
            range_str = f"S:{w.range_short}/M:{w.range_medium}/L:{w.range_long}"

            status = " ".join(status_parts)
            print(f"  [{i}] {w.name} ({loc_name}) - {status}")
            print(f"       Dmg: {w.damage} | Heat: {w.heat} | Ammo: {ammo_str}")
            print(f"       Range: {range_str} | VRT: {w.vrt}s")

    def show_armor(self, unit_name: str) -> None:
        """Show detailed armor status for a mech."""
        unit = self._get_unit(unit_name)
        if not unit:
            return

        m = unit.mech
        print(f"=== {unit.name} Armor Status ===")

        # Define display order and names
        locations = [
            (Location.HEAD, "Head"),
            (Location.CTORSO, "Center Torso"),
            (Location.LTORSO, "Left Torso"),
            (Location.RTORSO, "Right Torso"),
            (Location.LARM, "Left Arm"),
            (Location.RARM, "Right Arm"),
            (Location.LLEG, "Left Leg"),
            (Location.RLEG, "Right Leg"),
        ]

        for loc, name in locations:
            section = m.sections[loc]

            # Calculate percentages
            armor_pct = (section.armor / section.armor_orig * 100) if section.armor_orig > 0 else 0
            int_pct = (section.internal / section.internal_orig * 100) if section.internal_orig > 0 else 0

            # Status
            if section.internal <= 0:
                status = "DESTROYED"
            elif section.armor <= 0:
                status = "BREACHED"
            elif armor_pct < 50:
                status = "DAMAGED"
            else:
                status = "OK"

            # Rear armor (torsos only)
            rear_str = ""
            if loc in (Location.CTORSO, Location.LTORSO, Location.RTORSO):
                rear_str = f" | Rear: {section.rear}/{section.rear_orig}"

            print(f"  {name:14} Armor: {section.armor:2}/{section.armor_orig:2} ({armor_pct:3.0f}%)"
                  f" | Int: {section.internal:2}/{section.internal_orig:2} ({int_pct:3.0f}%)"
                  f"{rear_str} [{status}]")

    # =========================================================================
    # Movement Commands (clock 3 - injected between ticks)
    # =========================================================================

    def cmd_move(self, unit_name: str, speed: float) -> None:
        """Set a mech's desired speed and arm its movement event."""
        unit = self._get_unit(unit_name)
        if not unit:
            return

        m = unit.mech
        old_speed = m.desired_speed

        def command():
            m.set_desired_speed(speed)
            start_move_event(self.engine, m)

        self.engine.inject_command(unit.name, command, f"move {speed:g}")

        print(f"{unit.name}: Desired speed set to {m.desired_speed:.1f} KPH (was {old_speed:.1f})")
        if abs(speed) > m.max_speed:
            print(f"  (clamped to max speed {m.max_speed:.1f})")

    def cmd_heading(self, unit_name: str, heading: int) -> None:
        """Set a mech's desired facing and arm its movement event."""
        unit = self._get_unit(unit_name)
        if not unit:
            return

        m = unit.mech
        old_heading = m.desired_facing

        def command():
            m.set_desired_facing(heading)
            start_move_event(self.engine, m)

        self.engine.inject_command(unit.name, command, f"heading {heading}")

        print(f"{unit.name}: Desired heading set to {m.desired_facing}° (was {old_heading}°)")

    def cmd_stop(self, unit_name: str) -> None:
        """Stop a mech (it decelerates via its movement event chain)."""
        unit = self._get_unit(unit_name)
        if not unit:
            return

        m = unit.mech

        def command():
            m.stop()
            start_move_event(self.engine, m)

        self.engine.inject_command(unit.name, command, "stop")
        print(f"{unit.name}: Stopping")

    # =========================================================================
    # Combat Commands
    # =========================================================================

    def cmd_fire(self, attacker_name: str, weapon_idx: int, target_name: Optional[str] = None) -> None:
        """Fire a weapon at a target through the engine's fire pipeline."""
        attacker_unit = self._get_unit(attacker_name)
        if not attacker_unit:
            return

        # Default target: the other mech
        if target_name is None:
            for name, unit in self.units.items():
                if name != attacker_name.lower():
                    target_name = name
                    break

        target_unit = self._get_unit(target_name) if target_name else None
        if not target_unit:
            print(f"Error: No target found")
            return

        attacker = attacker_unit.mech
        target = target_unit.mech

        # Validate weapon index
        if weapon_idx < 0 or weapon_idx >= len(attacker.weapons):
            print(f"Error: Invalid weapon index {weapon_idx}")
            print(f"  {attacker_unit.name} has {len(attacker.weapons)} weapons (0-{len(attacker.weapons)-1})")
            return

        ws = attacker.weapons[weapon_idx]
        weapon = get_weapon_by_index(ws.weapon_idx)

        # Calculate distance and show the BTH analysis
        distance = hex_distance(attacker.x, attacker.y, target.x, target.y)
        bth = calculate_bth(attacker, target, weapon, distance,
                            gunnery_skill=find_pilot_gunnery(attacker, weapon),
                            section=Location(ws.section))
        hit_chance = estimate_hit_chance(bth.total)

        print(f"\n{attacker.name} fires {weapon.name} at {target.name}!")
        print(f"  Distance: {distance:.1f} hexes")
        print(f"  BTH: {bth.total} (Base:{bth.base} Range:+{bth.range_mod} "
              f"AtkMove:+{bth.attacker_move} TgtMove:+{bth.target_move} "
              f"Heat:+{bth.heat_mod} Weapon:{bth.weapon_mod:+d})")
        print(f"  Hit Chance: {hit_chance:.1f}%")

        # Fire through the engine pipeline (gates, heat, ammo, recycle all
        # handled by fire_weapon) as an injected player command.
        result = self.engine.inject_command(
            attacker_unit.name,
            lambda: fire_weapon(attacker, target, weapon_idx, distance),
            f"fire {weapon_idx} -> {target_unit.name}",
        )

        # Print results
        print()
        for msg in result.messages:
            print(f"  {msg}")

        if result.hit:
            print(f"\n  Location: {result.location.name}")
            print(f"  Damage dealt: {result.damage_dealt}")
            if result.armor_damage > 0:
                print(f"    Armor damage: {result.armor_damage}")
            if result.internal_damage > 0:
                print(f"    Internal damage: {result.internal_damage}")
            if result.criticals_rolled > 0:
                print(f"    Critical hits: {result.criticals_rolled}")

        print()

    def cmd_target_info(self, attacker_name: str, target_name: str) -> None:
        """Show targeting information between two mechs."""
        attacker_unit = self._get_unit(attacker_name)
        target_unit = self._get_unit(target_name)
        if not attacker_unit or not target_unit:
            return

        attacker = attacker_unit.mech
        target = target_unit.mech

        distance = hex_distance(attacker.x, attacker.y, target.x, target.y)
        bearing = hex_bearing(attacker.x, attacker.y, target.x, target.y)
        hit_group = determine_hit_group(attacker, target)

        print(f"\n=== {attacker.name} -> {target.name} ===")
        print(f"  Distance: {distance:.1f} hexes")
        print(f"  Bearing: {bearing}°")
        print(f"  Hit Arc: {hit_group.name}")
        print()

        print("  Weapon BTH Analysis:")
        for i, ws in enumerate(attacker.weapons):
            w = get_weapon_by_index(ws.weapon_idx)
            if not weapon_is_ready(attacker, ws) or not weapon_has_ammo(attacker, ws):
                status = "UNAVAILABLE"
                bth_str = "N/A"
            elif not w.can_fire_at_range(distance):
                status = "OUT OF RANGE"
                bth_str = "N/A"
            else:
                bth = calculate_bth(attacker, target, w, distance,
                                    gunnery_skill=find_pilot_gunnery(attacker, w),
                                    section=Location(ws.section))
                hit_chance = estimate_hit_chance(bth.total)
                status = f"BTH {bth.total}"
                bth_str = f"{hit_chance:.1f}% hit"

            print(f"    [{i}] {w.name}: {status} ({bth_str})")
        print()

    # =========================================================================
    # Simulation Control
    # =========================================================================

    def tick(self, count: int = 1, verbose: bool = True) -> None:
        """Advance the simulation by N ticks (dispatch + heartbeat each)."""
        for i in range(count):
            self.engine.process_tick()

            if verbose and self.verbose:
                self._print_tick_summary(self.engine.tick)

    def run_simulation(self, ticks: int, status_interval: int = 5) -> None:
        """
        Run the simulation for N ticks with periodic status updates.

        Args:
            ticks: Number of ticks to run
            status_interval: Show status every N ticks
        """
        print(f"\nRunning simulation for {ticks} ticks...")
        print("-" * 60)

        for i in range(ticks):
            self.engine.process_tick()
            current_tick = self.engine.tick

            # Print summary
            self._print_tick_summary(current_tick)

            # Periodic full status
            if (i + 1) % status_interval == 0:
                print()
                self.show_status()
                print("-" * 60)

        print(f"\nSimulation complete. Final tick: {self.engine.tick}")

    def _print_tick_summary(self, tick: int) -> None:
        """Print a one-line summary for a tick."""
        parts = [f"Tick {tick:4d}:"]

        for name, unit in self.units.items():
            m = unit.mech
            parts.append(f"{unit.name}[({m.x},{m.y}) spd:{m.speed:.0f} hdg:{m.facing}° heat:{m.heat:.0f}]")

        print(" ".join(parts))

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_unit(self, name: str) -> Optional[CombatUnit]:
        """Get a combat unit by name (case-insensitive)."""
        unit = self.units.get(name.lower())
        if not unit:
            print(f"Error: Unknown mech '{name}'")
            print(f"  Available: {', '.join(u.name for u in self.units.values())}")
        return unit

    # =========================================================================
    # Interactive Command Loop
    # =========================================================================

    def print_help(self) -> None:
        """Print help text."""
        print("""
BTMux Integration Test Harness - Commands:

  status [mech]           - Show mech status (all if no name given)
  move <mech> <speed>     - Set desired speed in KPH
  heading <mech> <deg>    - Set desired facing in degrees
  stop <mech>             - Stop the mech

  weapons <mech>          - List weapons and their status
  armor <mech>            - Show detailed armor status
  target <atk> <tgt>      - Show targeting info and BTH
  fire <mech> <wpn#> [tgt]- Fire weapon # at target

  tick [n]                - Advance simulation by N ticks (default 1)
  run <n>                 - Run N ticks with status updates

  verbose                 - Toggle verbose tick output
  help                    - Show this help
  quit / exit             - Exit the harness

Examples:
  move alpha 40           - Set Alpha's speed to 40 KPH
  heading bravo 90        - Turn Bravo to face East
  fire alpha 0            - Fire Alpha's weapon 0 at default target
  run 30                  - Run 30 ticks of simulation
""")

    def run_interactive(self) -> None:
        """Run the interactive command loop."""
        import select
        import sys

        print("=" * 60)
        print("BTMux Python Reimplementation - Integration Test Harness")
        print("=" * 60)
        print()

        # Spawn default mechs
        self.spawn_default_mechs()
        print()
        self.show_status()
        print()
        print("Type 'help' for commands, 'quit' to exit.")
        print("Type 'auto' to toggle real-time mode (1 tick/second).")
        print()

        self.running = True
        while self.running:
            try:
                if self.auto_advance:
                    # Wait up to 1 second for input, no prompt spam
                    ready, _, _ = select.select([sys.stdin], [], [], 1.0)

                    if ready:
                        line = sys.stdin.readline().strip()
                        if line:
                            self._process_command(line)
                    else:
                        # No input - advance tick silently (recycle counts
                        # down via the engine's heartbeat, nothing extra)
                        self.engine.process_tick()
                else:
                    line = input(f"[Tick {self.engine.tick}]> ").strip()
                    if not line:
                        continue
                    self._process_command(line)

            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print("\nInterrupted. Type 'quit' to exit.")

    def _process_command(self, line: str) -> None:
        """Process a single command line."""
        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ('quit', 'exit', 'q'):
                self.running = False
                print("Goodbye!")

            elif cmd == 'help':
                self.print_help()

            elif cmd == 'status':
                self.show_status(args[0] if args else None)

            elif cmd == 'move':
                if len(args) < 2:
                    print("Usage: move <mech> <speed>")
                else:
                    self.cmd_move(args[0], float(args[1]))

            elif cmd == 'heading':
                if len(args) < 2:
                    print("Usage: heading <mech> <degrees>")
                else:
                    self.cmd_heading(args[0], int(args[1]))

            elif cmd == 'stop':
                if not args:
                    print("Usage: stop <mech>")
                else:
                    self.cmd_stop(args[0])

            elif cmd == 'weapons':
                if not args:
                    print("Usage: weapons <mech>")
                else:
                    self.show_weapons(args[0])

            elif cmd == 'armor':
                if not args:
                    print("Usage: armor <mech>")
                else:
                    self.show_armor(args[0])

            elif cmd == 'target':
                if len(args) < 2:
                    print("Usage: target <attacker> <target>")
                else:
                    self.cmd_target_info(args[0], args[1])

            elif cmd == 'fire':
                if len(args) < 2:
                    print("Usage: fire <mech> <weapon#> [target]")
                else:
                    target = args[2] if len(args) > 2 else None
                    self.cmd_fire(args[0], int(args[1]), target)

            elif cmd == 'tick':
                count = int(args[0]) if args else 1
                self.tick(count)

            elif cmd == 'run':
                if not args:
                    print("Usage: run <ticks>")
                else:
                    self.run_simulation(int(args[0]))

            elif cmd == 'verbose':
                self.verbose = not self.verbose
                print(f"Verbose mode: {'ON' if self.verbose else 'OFF'}")

            elif cmd == 'auto':
                self.auto_advance = not self.auto_advance
                print(f"Auto-advance: {'ON (1 tick/sec)' if self.auto_advance else 'OFF'}")

            else:
                print(f"Unknown command: {cmd}")
                print("Type 'help' for available commands.")

        except (ValueError, IndexError) as e:
            print(f"Error: {e}")
            print("Type 'help' for command usage.")


# =============================================================================
# Quick Test Functions (for automated testing)
# =============================================================================

def test_movement() -> bool:
    """Test that event-driven movement works."""
    harness = IntegrationTestHarness()
    harness.spawn_mech("Test", TEST_MECH_TEMPLATE, x=50, y=50, facing=0)

    unit = harness.units["test"]
    mech = unit.mech

    # Set speed via the command path (arms the per-mech MOVE event)
    harness.cmd_move("test", 40.0)

    start_y = mech.fy
    harness.tick(10, verbose=False)

    # Mech should have moved
    moved = abs(mech.fy - start_y) > 0.1

    print(f"Movement test: {'PASS' if moved else 'FAIL'}")
    print(f"  Start Y: {start_y:.1f}, End Y: {mech.fy:.1f}")

    return moved


def test_heat() -> bool:
    """Test that heat system works (via the MECH object update)."""
    harness = IntegrationTestHarness()
    harness.spawn_mech("Test", TEST_MECH_TEMPLATE, x=50, y=50, facing=0)

    unit = harness.units["test"]
    mech = unit.mech

    # Add weapon heat
    mech.weap_heat = 15.0

    start_heat = mech.heat
    harness.tick(10, verbose=False)

    # Heat should have changed
    heat_changed = abs(mech.heat - start_heat) > 0.1

    print(f"Heat test: {'PASS' if heat_changed else 'FAIL'}")
    print(f"  Start heat: {start_heat:.1f}, End heat: {mech.heat:.1f}")

    return heat_changed


def test_combat() -> bool:
    """Test that combat system works (fire_weapon pipeline)."""
    harness = IntegrationTestHarness()
    harness.spawn_default_mechs()

    alpha = harness.units["alpha"]
    bravo = harness.units["bravo"]

    # Get initial armor
    start_armor = bravo.mech.total_armor()

    # Fire a weapon
    harness.cmd_fire("alpha", 0, "bravo")

    # Check if damage was dealt (might miss, but BTH calculation should work)
    ws = alpha.mech.weapons[0]
    bth = calculate_bth(
        alpha.mech, bravo.mech,
        get_weapon_by_index(ws.weapon_idx),
        hex_distance(alpha.mech.x, alpha.mech.y, bravo.mech.x, bravo.mech.y)
    )

    # Test passes if BTH calculation is reasonable (not infinity)
    bth_valid = 2 <= bth.total <= 12

    print(f"Combat test: {'PASS' if bth_valid else 'FAIL'}")
    print(f"  BTH: {bth.total}, Start armor: {start_armor}, End armor: {bravo.mech.total_armor()}")

    return bth_valid


def test_weapon_recycle() -> bool:
    """Test that weapon recycle works via the heartbeat clock."""
    harness = IntegrationTestHarness()
    harness.spawn_default_mechs()

    alpha = harness.units["alpha"]
    bravo = harness.units["bravo"]
    mech = alpha.mech
    ws = mech.weapons[0]
    weapon = get_weapon_by_index(ws.weapon_idx)
    distance = hex_distance(mech.x, mech.y, bravo.mech.x, bravo.mech.y)

    # Fire the weapon through the engine pipeline
    initial_ready = weapon_is_ready(mech, ws)
    harness.engine.inject_command(
        alpha.name, lambda: fire_weapon(mech, bravo.mech, 0, distance), "fire 0")
    fired_ready = weapon_is_ready(mech, ws)
    fired_recycle = weapon_recycle_remaining(mech, ws)

    # Run ticks until the heartbeat counts the recycle down to 0
    recycle_seconds = WEAPON_TICK * weapon.vrt
    harness.tick(recycle_seconds, verbose=False)

    final_ready = weapon_is_ready(mech, ws)

    # Test: was ready, became not ready after firing, became ready again
    test_pass = initial_ready and not fired_ready and final_ready

    print(f"Weapon recycle test: {'PASS' if test_pass else 'FAIL'}")
    print(f"  Initial ready: {initial_ready}, After fire: {fired_ready} (recycle={fired_recycle}), "
          f"After {recycle_seconds}s: {final_ready}")

    return test_pass


def run_all_tests() -> bool:
    """Run all automated tests."""
    print("=" * 60)
    print("Running Integration Tests")
    print("=" * 60)
    print()

    results = []

    results.append(("Movement", test_movement()))
    print()
    results.append(("Heat", test_heat()))
    print()
    results.append(("Combat", test_combat()))
    print()
    results.append(("Weapon Recycle", test_weapon_recycle()))
    print()

    print("=" * 60)
    print("Test Summary:")
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    print(f"Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 60)

    return all_passed


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="BTMux Integration Test Harness"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Run automated tests"
    )
    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run a quick demo"
    )

    args = parser.parse_args()

    if args.test:
        success = run_all_tests()
        sys.exit(0 if success else 1)

    elif args.demo:
        # Quick demo: movement, heat, ammo and criticals in one pass
        print("=== BTMux Demo ===\n")
        harness = IntegrationTestHarness()
        harness.spawn_default_mechs()
        print()

        # Show initial status
        harness.show_status()
        print()

        # Set up some movement
        print("Setting Alpha to move at 40 KPH...")
        harness.cmd_move("alpha", 40)
        print()

        # Run a few ticks
        print("Running 5 ticks...")
        harness.run_simulation(5, status_interval=5)
        print()

        # Fire an energy weapon: heat activity
        print("\nAlpha fires medium laser at Bravo...")
        harness.cmd_fire("alpha", 0, "bravo")

        # Bravo alpha-strikes: heat activity (20 weapon heat vs 15 sinks)
        # plus ammo activity from the LRM-10
        bravo = harness.units["bravo"]
        lrm_ws = bravo.mech.weapons[3]
        print(f"Bravo LRM-10 ammo before: {weapon_ammo_rounds(bravo.mech, lrm_ws)} rounds")
        print("Bravo alpha-strikes Alpha (PPC + 2x ML + LRM-10)...")
        for weapon_number in range(4):
            harness.cmd_fire("bravo", weapon_number, "alpha")
        print(f"Bravo LRM-10 ammo after: {weapon_ammo_rounds(bravo.mech, lrm_ws)} rounds")
        print(f"Bravo weapon heat after alpha strike: {bravo.mech.weap_heat:.1f}")

        # Force a critical hit: crit activity (crit.c HandleCritical path)
        alpha = harness.units["alpha"]
        print("\nForcing a critical hit on Alpha's center torso...")
        crits, crit_results = check_for_critical(
            alpha.mech, Location.CTORSO, 1, bravo.mech)
        for cr in crit_results:
            print(f"  CRITICAL: {cr.message}")

        # Let heat dissipate and weapons recycle a bit
        print("\nRunning 6 more ticks (heat decays, weapons recycle)...")
        harness.run_simulation(6, status_interval=6)

        print("\nBravo's weapons after firing:")
        harness.show_weapons("bravo")

        # Final status
        print("\nFinal Status:")
        harness.show_status()

    else:
        # Default: interactive mode
        harness = IntegrationTestHarness()
        harness.run_interactive()


if __name__ == "__main__":
    main()
