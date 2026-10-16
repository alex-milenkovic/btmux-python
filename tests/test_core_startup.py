"""Ordinary source lifecycle, separate from overheat shutdown consequences."""
import unittest
from unittest.mock import patch

from core.game_loop import GameEngine
from core.events import EventType as E
from entities.map import GameMap, WATER
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, UnitType as U, MoveType as M, Location as L, Specials
from entities.pilot import Pilot
from systems import startup


def fixture(kind=U.MECH):
    engine, board = GameEngine(), GameMap(12, 12)
    unit = Mech.create_test_mech()
    unit.unit_type, unit.x, unit.y = kind, 3, 3
    unit.status = S.NONE
    actor = Pilot()
    board._id = 100
    engine.register_entity(board)
    board.add_mech(unit)
    engine.register_entity(unit)
    return engine, unit, actor


class StartupTest(unittest.TestCase):
    def test_six_deadlines_then_completion_effects(self):
        engine, unit, actor = fixture()
        unit.turn_damage, unit.num_seen, unit.vertical_speed = 22, 9, 7
        unit.prefs = 3
        unit.specials |= Specials.SS_ABILITY
        unit.sections[L.HEAD].recycle = 50
        unit.sections[L.LARM].recycle = 50
        ok, _ = startup.startup(engine, unit, caller=actor)
        self.assertTrue(ok)
        self.assertIs(actor, unit.pilot)
        self.assertEqual((50, 0), (unit.sections[L.HEAD].recycle, unit.sections[L.LARM].recycle))
        for tick in range(1, 31):
            engine.process_tick()
            self.assertEqual(tick // 5, len(unit.boot_messages))
            self.assertEqual(tick == 30, unit.is_started)
        self.assertEqual((0, 0, 0, 2, 30), (unit.turn_damage, unit.num_seen, unit.vertical_speed, unit.prefs, unit.last_startup))
        self.assertFalse(unit.specials & Specials.SS_ABILITY)
        self.assertTrue(engine.has_event(E.PLOS, unit))
        self.assertFalse(engine.has_event(E.STARTUP, unit))

    def test_heat_and_override_do_not_roll(self):
        for heat, arg, wizard, accepted, due in ((9, '', False, True, 5), (14, '', False, True, 5),
                (30, '', False, True, 5), (30.1, '', False, False, None),
                (0, ' oVeR', True, True, 1), (0, 'over', False, False, None),
                (0, 'overrideX', False, True, 5), (0, 'over ', False, True, 5)):
            with self.subTest(heat=heat, arg=arg):
                engine, unit, actor = fixture()
                unit.heat = heat
                result = engine.inject_command(unit, lambda: startup.startup(engine, unit, arg, caller=actor, wizard=wizard))
                self.assertEqual(accepted, result[0])
                self.assertEqual(due, unit._startup_event.tick if accepted else None)
                self.assertEqual(0, engine.randomness.mt.words_consumed)

    def test_source_guards_leave_pilot_and_recycle_unchanged(self):
        for name, value in (('repair_remaining', 1), ('pilot_owner', object()), ('alive', False)):
            engine, unit, actor = fixture()
            unit.in_character = name == 'pilot_owner'
            setattr(actor if name == 'alive' else unit, name, value)
            if name == 'repair_remaining':
                from systems.repair_jobs import EVENT_TYPES
                engine.schedule_event(1, EVENT_TYPES[43], lambda e: None, data=unit, data2=0)
            unit.sections[L.LARM].recycle = 8
            self.assertFalse(startup.startup(engine, unit, caller=actor)[0])
            self.assertIsNone(unit.pilot)
            self.assertEqual(8, unit.sections[L.LARM].recycle)

    def test_class_timing_and_second_stage_flood(self):
        for kind, proof, dies, final in ((U.BSUIT, False, True, 2), (U.VEH_GROUND, False, True, 10),
                (U.VEH_GROUND, True, False, 30), (U.MECH, False, False, 30),
                (U.VEH_NAVAL, False, False, 30), (U.SPHEROID_DS, False, False, 30)):
            with self.subTest(kind=kind, proof=proof):
                engine, unit, actor = fixture(kind)
                unit.terrain, unit.elev, unit.z = WATER, 2, -2
                unit.specials2 = 0x100000 if proof else 0
                startup.startup(engine, unit, caller=actor)
                for _ in range(final): engine.process_tick()
                self.assertEqual(dies, unit.is_destroyed)
                self.assertEqual(not dies, unit.is_started)
                self.assertFalse(engine.has_event(E.STARTUP, unit))

    def test_abort_preserves_other_state_and_restart_has_only_new_sequence(self):
        engine, unit, actor = fixture()
        startup.startup(engine, unit, caller=actor)
        for _ in range(5): engine.process_tick()
        unit.speed, unit.target = 12, 7
        unit.status2 |= S2.ECM_ENABLED
        self.assertTrue(startup.shutdown(engine, unit)[0])
        self.assertEqual((12, 7, S2.ECM_ENABLED), (unit.speed, unit.target, unit.status2))
        self.assertIsNone(unit.pilot)
        startup.startup(engine, unit, caller=actor)
        for _ in range(30): engine.process_tick()
        self.assertTrue(unit.is_started)
        self.assertEqual(7, len(unit.boot_messages))
        self.assertEqual(35, unit.last_startup)

    def test_callback_has_no_extra_heat_or_destroyed_guard(self):
        engine, unit, actor = fixture(U.MW)
        startup.startup(engine, unit, caller=actor)
        unit.heat, unit.status = 80, S.DESTROYED
        engine.process_tick()
        self.assertTrue(unit.is_started)
        self.assertEqual(1, len(unit.boot_messages))


class ShutdownTest(unittest.TestCase):
    def test_heat_and_destruction_share_macro_cleanup(self):
        from systems.heat import apply_shutdown
        from systems.damage import destroy_mech
        for action in (apply_shutdown,lambda unit:destroy_mech(unit,unit,showboom=False)):
            engine,unit,actor = fixture()
            unit.status,unit.pilot,unit.target = S.STARTED,actor,17
            unit.charge_target,unit.masc_counter = 18,4
            engine.schedule_event(20,E.HIDE,lambda event:None,data=unit)
            action(unit)
            self.assertEqual((None,-1,-1,0),(unit.pilot,unit.target,unit.charge_target,unit.masc_counter))
            self.assertFalse(engine.has_event(E.HIDE,unit))

    def test_signed_speed_threshold_invokes_real_fall(self):
        for speed, falls in ((-21.5, 0), (10.75, 0), (10.76, 1)):
            engine, unit, actor = fixture()
            unit.pilot, unit.status, unit.speed = actor, S.STARTED | S.COMBAT_SAFE, speed
            with patch('physics.jump.mech_falls', wraps=__import__('physics.jump', fromlist=['mech_falls']).mech_falls) as fall:
                engine.inject_command(unit, lambda: startup.shutdown(engine, unit))
                self.assertEqual(falls, fall.call_count)
            self.assertEqual((0, 0), (unit.speed, unit.desired_speed))
            self.assertEqual(bool(falls), unit.is_fallen)

    def test_airborne_branch_keeps_fall_event_during_cleanup(self):
        for kind, movement, jumping, wizard, started, due in (
                (U.MECH, M.BIPED, True, False, False, 3),
                (U.VTOL, M.VTOL, False, False, False, 3),
                (U.VEH_NAVAL, M.HULL, False, False, False, None),
                (U.DS, M.FLY, False, False, True, None),
                (U.DS, M.FLY, False, True, False, 3)):
            engine, unit, actor = fixture(kind)
            unit.move_type, unit.z, unit.pilot = movement, 5, actor
            unit.status = S.STARTED | (S.JUMPING if jumping else S.NONE)
            startup.shutdown(engine, unit, wizard=wizard)
            self.assertEqual(started, unit.is_started)
            self.assertEqual(due, engine.events.time_until_type_data(E.FALL, unit))

    def test_shutdown_cancels_exact_chains_and_clears_macro_fields(self):
        engine, unit, actor = fixture()
        unit.pilot, unit.status = actor, S.STARTED | S.MASC_ENABLED | S.TORSO_LEFT
        unit.status2 = S2.SPRINTING | S2.ECM_ENABLED | S2.SLITE_ON
        unit.masc_counter, unit.scharge_counter, unit.charge_target, unit.target = 3, 4, 8, 9
        for kind in (E.MOVE, E.JUMP, E.STAND, E.STARTUP, E.PLOS, E.FALL, E.MASC_FAIL, E.MASC_REGEN, E.SCHARGE_FAIL):
            engine.schedule_event(9, kind, lambda e: None, data=unit)
        # No startup chain: full shutdown, not command-abort branch.
        engine.cancel_events_of_type(E.STARTUP, unit)
        startup.shutdown(engine, unit)
        self.assertEqual((None, -1, -1, 0, 0), (unit.pilot, unit.target, unit.charge_target, unit.masc_counter, unit.scharge_counter))
        self.assertFalse(unit.status & (S.STARTED | S.MASC_ENABLED | S.TORSO_LEFT))
        self.assertEqual(0, unit.status2)
        for kind in (E.MOVE, E.JUMP, E.STAND, E.MASC_FAIL): self.assertFalse(engine.has_event(kind, unit))
        for kind in (E.PLOS, E.FALL, E.MASC_REGEN, E.SCHARGE_FAIL): self.assertTrue(engine.has_event(kind, unit))


if __name__ == '__main__': unittest.main()
