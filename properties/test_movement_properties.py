"""Finite-domain movement properties; run separately from normal unit discovery.

Each subtest provides its concrete counterexample. Local Random instances make
ice exploration reproducible without changing process-global random state.
"""
import copy
from itertools import product
import random
import unittest
from unittest.mock import patch

from core.events import EventType
from core.game_loop import GameEngine
from entities.map import GameMap, WATER, ICE, GRASSLAND, BRIDGE
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, Specials, CritStatus
from entities.pilot import Pilot
from physics import ice, orbital, collision
from physics.cargo import cargo_max_speed, CACHE_FLAGS
from systems import movement_commands as commands


def ready_unit():
    engine = GameEngine()
    unit = Mech.create_test_mech()
    unit.measured_mass = unit.tonnage * 1024
    unit.pilot = Pilot()
    unit.pilot.dodge_maneuver = True
    unit.set_status(S.STARTED)
    board = GameMap(3, 3)
    board.add_mech(unit)
    engine.register_entity(unit)
    return engine, unit


class MovementProperties(unittest.TestCase):
    def test_cargo_cache_matches_fresh_calculation_across_load_and_boost_changes(self):
        for tons, heat, tsm in product((20, 50, 100), (0, 9), (False, True)):
            _, unit = ready_unit()
            unit.tonnage = tons
            unit.measured_mass = tons * 1024
            unit.heat = heat
            if tsm:
                unit.specials |= Specials.TRIPLE_MYOMER_TECH
            for load, boost, sprint in product((0, 1024, 10 * 1024, 100 * 1024, 0),
                                               (S(0), S.MASC_ENABLED, S.SCHARGE_ENABLED),
                                               (False, True)):
                with self.subTest(tons=tons, heat=heat, tsm=tsm, load=load, boost=boost, sprint=sprint):
                    unit.carried_cargo = load
                    unit.clear_status(S.MASC_ENABLED | S.SCHARGE_ENABLED)
                    unit.set_status(boost)
                    unit.clear_status2(S2.SPRINTING)
                    if sprint:
                        unit.set_status2(S2.SPRINTING)
                    cached = cargo_max_speed(unit)
                    self.assertEqual(cached, cargo_max_speed(unit))
                    unit.clear_crit_status(CACHE_FLAGS)
                    self.assertEqual(cached, cargo_max_speed(unit))
                    self.assertGreaterEqual(cached, 0)

    def test_unboosted_speed_never_increases_with_added_cargo_or_tow_mass(self):
        for tons, mass_ratio in product((20, 50, 100), (.5, 1, 1.5)):
            _, unit = ready_unit()
            unit.tonnage = tons
            unit.measured_mass = int(tons * 1024 * mass_ratio)
            tow = Mech()
            tow.set_crit_status(CritStatus.OWEIGHT_OK)
            unit.towed_unit = tow
            for cargo in range(0, 100 * 1024 + 1, 5 * 1024):
                unit.carried_cargo = cargo
                previous = unit.max_speed
                for mass in range(0, 100 * 1024 + 1, 5 * 1024):
                    with self.subTest(tons=tons, mass_ratio=mass_ratio, cargo=cargo, tow=mass):
                        tow.measured_mass = mass
                        result = cargo_max_speed(unit)
                        self.assertLessEqual(result, previous)
                        self.assertGreaterEqual(result, 0)
                        previous = result
            unit.towed_unit = None
            previous = unit.max_speed
            for cargo in range(0, 100 * 1024 + 1, 1024):
                unit.carried_cargo = cargo
                result = cargo_max_speed(unit)
                self.assertLessEqual(result, previous)
                previous = result

    def test_ice_evolution_conserves_depth_and_unrelated_cells_and_reports_changes(self):
        for width, height, seed, melting, percent in product(
                (1, 2, 5), (1, 3, 4), range(4), (False, True), (-1, 0, 40, 100, 101)):
            with self.subTest(size=(width, height), seed=seed, melting=melting, percent=percent):
                draw = random.Random(seed)
                board = GameMap(width, height)
                cells = list(product(range(width), range(height)))
                for x, y in cells:
                    board.set_terrain(x, y, draw.choice((WATER, ICE, GRASSLAND, BRIDGE)))
                    board.set_elevation(x, y, draw.randrange(10))
                before = {(x, y): (board.terrain(x, y), board.elevation(x, y)) for x, y in cells}
                source, destination = (ICE, WATER) if melting else (WATER, ICE)
                with patch('physics.ice.random.randint', side_effect=draw.randint):
                    count = (ice.ice_melt if melting else ice.ice_growth)(board, percent)
                changed = 0
                for x, y in cells:
                    code, depth = before[x, y]
                    after = board.terrain(x, y)
                    self.assertEqual(depth, board.elevation(x, y))
                    self.assertNotEqual('1', after)
                    if code != after:
                        changed += 1
                        self.assertEqual((source, destination), (code, after))
                self.assertEqual(count, changed)
                if percent <= 0:
                    self.assertEqual(0, count)

    def test_hex_neighborhood_is_bounded_unique_and_reciprocal(self):
        for width, height in product(range(1, 8), repeat=2):
            board = GameMap(width, height)
            for cell in product(range(width), range(height)):
                with self.subTest(size=(width, height), cell=cell):
                    adjacent = list(ice.neighbors(board, *cell))
                    self.assertLessEqual(len(adjacent), 6)
                    self.assertEqual(len(adjacent), len(set(adjacent)))
                    self.assertNotIn(cell, adjacent)
                    for other in adjacent:
                        self.assertTrue(board.valid(*other))
                        self.assertIn(cell, list(ice.neighbors(board, *other)))

    def test_mode_command_sequences_preserve_exclusivity_and_queries_preserve_state(self):
        for sequence in product(('sprint', 'evade', 'dodge'), repeat=3):
            for delay in (0, 1, 30):
                engine, unit = ready_unit()
                for step, mode in enumerate(sequence):
                    with self.subTest(sequence=sequence, delay=delay, mode=mode):
                        success, message = commands.set_mode(engine, unit, mode)
                        if step == 0:
                            self.assertTrue(success, message)
                        engine.run_ticks(delay)
                        flags = unit.status2 & S2.MOVE_MODES
                        self.assertIn(flags, (0, S2.SPRINTING, S2.EVADING, S2.DODGING))
                        before = copy.copy(vars(unit))
                        commands.mode_locked(unit)
                        commands.target_mode_bth(unit)
                        self.assertEqual(before, vars(unit))
                engine.run_ticks(30)
                self.assertFalse(commands.pending(unit, '_mode_event'))

    def test_combat_safe_orbital_descent_terminates_and_touches_down_once(self):
        for altitude in range(1, 61):
            with self.subTest(altitude=altitude):
                engine, unit = ready_unit()
                unit.set_status(S.COMBAT_SAFE)
                self.assertTrue(orbital.initiate_ood(engine, unit, f'0 0 {altitude}')[0])
                previous = unit.z
                for _ in range(altitude + 2):
                    engine.run_ticks(1)
                    self.assertLessEqual(unit.z, previous)
                    self.assertGreaterEqual(unit.z, collision.mech_elevation(unit))
                    previous = unit.z
                self.assertEqual((0, 0), (unit.z, unit.cocoon))
                self.assertFalse(engine.has_event(EventType.OOD, unit))
                self.assertEqual(1, unit.movement_messages.count('Your unit touches down!'))
