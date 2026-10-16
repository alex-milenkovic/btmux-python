#!/usr/bin/env python3
"""
Real-Time Integration Test Harness for BTMux Python Reimplementation.

This harness runs the simulation in real-time (1 tick = 1 second) while
allowing you to input commands. This replicates the actual BTMux experience
where time flows continuously.

Engine wiring matches the C server (wire_standard_systems): heat and the
FIRED clear run on the dispatch clock's MECH object update, weapon recycle
counts down on the heartbeat clock, movement is per-mech and event-driven
(start_move_event, armed by the speed/heading commands), and every player
command routes through engine.inject_command (clock 3).

Usage:
    python -m tests.realtime_harness

The simulation runs automatically. Type commands at the prompt while
watching mechs move, heat change, and weapons recycle in real-time.
"""

import sys
import os
import asyncio
import threading
import time
from queue import Queue, Empty

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Optional

from core.game_loop import GameEngine, wire_standard_systems
from physics.hexmath import hex_distance, hex_bearing
from physics.movement import start_move_event
from systems.heat import get_heat_indicator
from systems.combat import calculate_bth, fire_weapon
from systems.piloting import find_pilot_gunnery
from entities.crittypes import i2ammo
from entities.mech import Mech, MechStatus, Location, WeaponState
from entities.weapon import get_weapon_by_index
from data.templates import (
    TEST_MECH_TEMPLATE, ASSAULT_MECH_TEMPLATE, LIGHT_MECH_TEMPLATE,
    create_mech_from_template, MechTemplate
)


# ANSI escape codes for terminal control
CLEAR_LINE = "\033[2K"
MOVE_UP = "\033[1A"
SAVE_CURSOR = "\033[s"
RESTORE_CURSOR = "\033[u"
CLEAR_SCREEN = "\033[2J"
HOME = "\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


# =============================================================================
# WeaponState helpers - authoritative state lives on the mech: mech.weapons
# plus the weapon's first crit slot data byte (the recycle countdown,
# mech.h:599-608), counted down by the engine's heartbeat clock.
# =============================================================================

def weapon_recycle_remaining(mech: Mech, ws: WeaponState) -> int:
    """Seconds until the weapon finishes recycling (0 = ready)."""
    return mech.sections[ws.section].criticals[ws.critical].data


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


@dataclass
class CombatUnit:
    """A named mech; weapons live on the mech itself (mech.weapons)."""
    mech: Mech
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = self.mech.name


class RealTimeHarness:
    """
    Real-time simulation harness.

    Runs the game loop at actual speed (1 tick/second) while accepting
    commands from the user.
    """

    def __init__(self, tick_duration: float = 1.0):
        """
        Initialize the harness.

        Args:
            tick_duration: Seconds per tick (default 1.0 for real-time)
        """
        self.engine = GameEngine(tick_duration=tick_duration)
        self.units: dict[str, CombatUnit] = {}
        self.running = False
        self.paused = False

        # Command queue for thread-safe command passing
        self.command_queue: Queue[str] = Queue()

        # Output queue for messages to display
        self.output_queue: Queue[str] = Queue()

        # Display mode
        self.show_status_bar = True
        self.last_status_lines = 0

        # Standard engine wiring: MECH object updates (heat / FIRED clear)
        # on the dispatch clock, recycle on the heartbeat clock.  Movement
        # is event-driven per mech - armed by the speed/heading commands.
        wire_standard_systems(self.engine)

    def spawn_mech(
        self,
        name: str,
        template: MechTemplate,
        x: int = 50,
        y: int = 50,
        facing: int = 0,
    ) -> CombatUnit:
        """Spawn a mech from a template."""
        mech = create_mech_from_template(template, name=name)
        mech.set_hex_position(x, y)
        mech.facing = facing
        mech.desired_facing = facing
        mech.set_status(MechStatus.STARTED)

        unit = CombatUnit(mech=mech, name=name)

        self.engine.register_entity(mech)
        self.units[name.lower()] = unit

        return unit

    def spawn_default_mechs(self) -> None:
        """Spawn Alpha and Bravo for testing."""
        self.spawn_mech("Alpha", TEST_MECH_TEMPLATE, x=50, y=50, facing=0)
        self.spawn_mech("Bravo", ASSAULT_MECH_TEMPLATE, x=50, y=55, facing=180)

    def _get_unit(self, name: str) -> Optional[CombatUnit]:
        """Get a combat unit by name."""
        return self.units.get(name.lower())

    # =========================================================================
    # Status Display
    # =========================================================================

    def get_status_bar(self) -> str:
        """Generate the status bar showing all mechs."""
        lines = []
        tick = self.engine.tick

        # Header
        state = "PAUSED" if self.paused else "RUNNING"
        lines.append(f"=== Tick {tick:5d} [{state}] ===")
        lines.append("")

        for name, unit in self.units.items():
            m = unit.mech

            # Heat indicator
            heat_ind = get_heat_indicator(m.heat)
            heat_sym = {"green": " ", "yellow": "!", "red": "!!"}.get(heat_ind, " ")

            # Ready weapons
            ready = sum(1 for ws in m.weapons
                        if weapon_is_ready(m, ws) and weapon_has_ammo(m, ws))
            total = len(m.weapons)

            # Position and movement
            pos_str = f"({m.x:3d},{m.y:3d})"
            spd_str = f"{m.speed:5.1f}/{m.desired_speed:5.1f}"
            hdg_str = f"{m.facing:3d}°->{m.desired_facing:3d}°"

            lines.append(f"{unit.name:8s} {pos_str} | Spd:{spd_str} | Hdg:{hdg_str} | "
                        f"Heat:{m.heat:4.1f}{heat_sym} | Wpn:{ready}/{total}")

        lines.append("")
        lines.append("Commands: move/heading/stop/fire/status/weapons/pause/quit")

        return "\n".join(lines)

    def print_output(self, msg: str) -> None:
        """Queue a message for output."""
        self.output_queue.put(msg)

    # =========================================================================
    # Commands (all injected as clock-3 player commands)
    # =========================================================================

    def cmd_move(self, unit_name: str, speed: float) -> None:
        unit = self._get_unit(unit_name)
        if not unit:
            self.print_output(f"Unknown mech: {unit_name}")
            return
        mech = unit.mech

        def command():
            mech.set_desired_speed(speed)
            start_move_event(self.engine, mech)

        self.engine.inject_command(unit.name, command, f"move {speed:g}")
        self.print_output(f"{unit.name}: Speed -> {speed:.1f} KPH")

    def cmd_heading(self, unit_name: str, heading: int) -> None:
        unit = self._get_unit(unit_name)
        if not unit:
            self.print_output(f"Unknown mech: {unit_name}")
            return
        mech = unit.mech

        def command():
            mech.set_desired_facing(heading)
            start_move_event(self.engine, mech)

        self.engine.inject_command(unit.name, command, f"heading {heading}")
        self.print_output(f"{unit.name}: Heading -> {heading}°")

    def cmd_stop(self, unit_name: str) -> None:
        unit = self._get_unit(unit_name)
        if not unit:
            self.print_output(f"Unknown mech: {unit_name}")
            return
        mech = unit.mech

        def command():
            mech.stop()
            start_move_event(self.engine, mech)

        self.engine.inject_command(unit.name, command, "stop")
        self.print_output(f"{unit.name}: Stopping")

    def cmd_fire(self, attacker_name: str, weapon_idx: int, target_name: Optional[str] = None) -> None:
        attacker_unit = self._get_unit(attacker_name)
        if not attacker_unit:
            self.print_output(f"Unknown mech: {attacker_name}")
            return

        # Default target
        if target_name is None:
            for name in self.units:
                if name != attacker_name.lower():
                    target_name = name
                    break

        target_unit = self._get_unit(target_name) if target_name else None
        if not target_unit:
            self.print_output("No target found")
            return

        attacker = attacker_unit.mech
        target = target_unit.mech

        if weapon_idx < 0 or weapon_idx >= len(attacker.weapons):
            self.print_output(f"Invalid weapon index: {weapon_idx}")
            return

        ws = attacker.weapons[weapon_idx]
        weapon = get_weapon_by_index(ws.weapon_idx)
        distance = hex_distance(attacker.x, attacker.y, target.x, target.y)

        bth = calculate_bth(attacker, target, weapon, distance,
                            gunnery_skill=find_pilot_gunnery(attacker, weapon),
                            section=Location(ws.section))

        # Fire through the engine pipeline: gates, heat, ammo and recycle
        # are all handled by fire_weapon (nothing out-of-band here).
        result = self.engine.inject_command(
            attacker_unit.name,
            lambda: fire_weapon(attacker, target, weapon_idx, distance),
            f"fire {weapon_idx} -> {target_unit.name}",
        )

        if not result.hit and not result.roll:
            # Gate failure (recycling / no ammo / destroyed / not started)
            self.print_output(f"{attacker.name}: {result.messages[0]}")
            return

        # Build output
        hit_str = "HIT" if result.hit else "MISS"
        self.print_output(f"{attacker.name} fires {weapon.name} -> {target.name}: "
                         f"{hit_str} (roll {result.roll} vs BTH {bth.total})")

        if result.hit:
            self.print_output(f"  {result.location.name} for {result.damage_dealt} damage")

    def cmd_status(self, unit_name: Optional[str] = None) -> None:
        """Show detailed status."""
        if unit_name:
            unit = self._get_unit(unit_name)
            if unit:
                self._print_unit_detail(unit)
        else:
            for unit in self.units.values():
                self._print_unit_detail(unit)

    def _print_unit_detail(self, unit: CombatUnit) -> None:
        m = unit.mech
        self.print_output(f"=== {unit.name} ({m.mech_type}) ===")
        self.print_output(f"  Pos: ({m.x},{m.y}) Float:({m.fx:.0f},{m.fy:.0f})")
        self.print_output(f"  Speed: {m.speed:.1f}/{m.desired_speed:.1f} KPH (max {m.max_speed:.1f})")
        self.print_output(f"  Facing: {m.facing}° -> {m.desired_facing}°")
        self.print_output(f"  Heat: {m.heat:.1f} (+{m.plus_heat:.1f} -{m.minus_heat:.1f})")

        armor = sum(s.armor + s.rear for s in m.sections)
        internal = sum(s.internal for s in m.sections)
        self.print_output(f"  Armor: {armor} | Internal: {internal}")

    def cmd_weapons(self, unit_name: str) -> None:
        unit = self._get_unit(unit_name)
        if not unit:
            self.print_output(f"Unknown mech: {unit_name}")
            return

        m = unit.mech
        self.print_output(f"=== {unit.name} Weapons ===")
        for i, ws in enumerate(m.weapons):
            w = get_weapon_by_index(ws.weapon_idx)
            recycle = weapon_recycle_remaining(m, ws)
            if ws.destroyed:
                status = "DESTROYED"
            elif recycle > 0:
                status = f"CYCLING ({recycle}s)"
            else:
                status = "READY"

            rounds = weapon_ammo_rounds(m, ws)
            ammo = "inf" if rounds == -1 else str(rounds)
            self.print_output(f"  [{i}] {w.name} - {status} - {ammo} ammo")

    def process_command(self, line: str) -> bool:
        """Process a command. Returns False if should quit."""
        parts = line.strip().split()
        if not parts:
            return True

        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ('quit', 'exit', 'q'):
                return False

            elif cmd == 'pause' or cmd == 'p':
                self.paused = not self.paused
                state = "PAUSED" if self.paused else "RUNNING"
                self.print_output(f"Simulation {state}")

            elif cmd == 'move':
                if len(args) >= 2:
                    self.cmd_move(args[0], float(args[1]))
                else:
                    self.print_output("Usage: move <mech> <speed>")

            elif cmd == 'heading' or cmd == 'hdg':
                if len(args) >= 2:
                    self.cmd_heading(args[0], int(args[1]))
                else:
                    self.print_output("Usage: heading <mech> <degrees>")

            elif cmd == 'stop':
                if args:
                    self.cmd_stop(args[0])
                else:
                    self.print_output("Usage: stop <mech>")

            elif cmd == 'fire' or cmd == 'f':
                if len(args) >= 2:
                    target = args[2] if len(args) > 2 else None
                    self.cmd_fire(args[0], int(args[1]), target)
                else:
                    self.print_output("Usage: fire <mech> <weapon#> [target]")

            elif cmd == 'status' or cmd == 's':
                self.cmd_status(args[0] if args else None)

            elif cmd == 'weapons' or cmd == 'w':
                if args:
                    self.cmd_weapons(args[0])
                else:
                    self.print_output("Usage: weapons <mech>")

            elif cmd == 'help' or cmd == '?':
                self.print_output("Commands: move <mech> <spd>, heading <mech> <deg>, "
                                 "stop <mech>, fire <mech> <#>, status, weapons <mech>, "
                                 "pause, quit")

            else:
                self.print_output(f"Unknown: {cmd}")

        except Exception as e:
            self.print_output(f"Error: {e}")

        return True

    # =========================================================================
    # Main Loop
    # =========================================================================

    async def simulation_loop(self):
        """Run the simulation in real-time."""
        while self.running:
            tick_start = time.time()

            if not self.paused:
                self.engine.process_tick()

            # Sleep for remainder of tick
            elapsed = time.time() - tick_start
            sleep_time = self.engine.tick_duration - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    async def display_loop(self):
        """Update the display periodically."""
        while self.running:
            # Clear and redraw status
            print(HOME + CLEAR_SCREEN, end='')
            print(self.get_status_bar())

            # Print any queued output
            output_lines = []
            while True:
                try:
                    msg = self.output_queue.get_nowait()
                    output_lines.append(msg)
                except Empty:
                    break

            if output_lines:
                print("\n--- Messages ---")
                for line in output_lines[-10:]:  # Last 10 messages
                    print(line)

            print(f"\n> ", end='', flush=True)

            await asyncio.sleep(0.1)  # 10 Hz display refresh

    def input_thread(self):
        """Read input in a separate thread."""
        while self.running:
            try:
                line = input()
                self.command_queue.put(line)
            except EOFError:
                self.command_queue.put("quit")
                break

    async def command_loop(self):
        """Process commands from the queue."""
        while self.running:
            try:
                line = self.command_queue.get_nowait()
                if not self.process_command(line):
                    self.running = False
            except Empty:
                pass
            await asyncio.sleep(0.05)

    async def run(self):
        """Run the real-time harness."""
        print(CLEAR_SCREEN + HOME)
        print("=== BTMux Real-Time Harness ===")
        print("Starting simulation...")
        print()

        self.spawn_default_mechs()
        self.running = True

        # Start input thread
        input_thread = threading.Thread(target=self.input_thread, daemon=True)
        input_thread.start()

        # Run async loops
        try:
            await asyncio.gather(
                self.simulation_loop(),
                self.display_loop(),
                self.command_loop(),
            )
        except asyncio.CancelledError:
            pass
        finally:
            print(SHOW_CURSOR)
            print("\nSimulation ended.")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="BTMux Real-Time Harness")
    parser.add_argument("--speed", "-s", type=float, default=1.0,
                       help="Tick duration in seconds (default 1.0)")
    args = parser.parse_args()

    harness = RealTimeHarness(tick_duration=args.speed)

    try:
        asyncio.run(harness.run())
    except KeyboardInterrupt:
        print("\nInterrupted.")


if __name__ == "__main__":
    main()
