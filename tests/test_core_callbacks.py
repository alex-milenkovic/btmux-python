"""Event list visibility and callback effects that cannot be countdown substitutes."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tests.test_core_startup import fixture
from core.events import EventType as E
from entities.mech import MechStatus as S, CritStatus as C, UnitType as U
from systems import piloting, vehicle_combat, hit_locations, stagger
from physics import jump


class RecoveryTest(unittest.TestCase):
    def test_prolong_uses_latest_queued_deadline_and_event_clock(self):
        engine, unit, actor = fixture()
        unit.pilot = actor
        piloting.prolong_uncon(unit, 30)
        engine.events.schedule(40, E.RECOVERY, piloting.recovery_event, unit)
        engine.skip_seconds(100)
        engine.heartbeat()
        self.assertEqual(30, engine.events.time_until_type_data(E.RECOVERY, unit))
        piloting.prolong_uncon(unit, 5)
        self.assertEqual(1, engine.events.count_type(E.RECOVERY))
        self.assertEqual(45, engine.events.time_until_type_data(E.RECOVERY, unit))
        for _ in range(45):
            with patch.object(piloting, 'roll_skilled', return_value=12): engine.events.muxevent_run()
        self.assertFalse(unit.is_unconscious)
        self.assertEqual(0, engine.events.count_type(E.RECOVERY))

    def test_failed_recovery_rearms_once_without_periodic_double_execution(self):
        engine, unit, actor = fixture()
        unit.pilot, unit.pilot_hits = actor, 4
        piloting.prolong_uncon(unit, 1)
        with patch.object(piloting, 'roll_skilled', return_value=2) as roll:
            engine.process_tick()
            piloting.piloting_periodic(engine)
            self.assertEqual(1, roll.call_count)
        self.assertEqual(30, engine.events.time_until_type_data(E.RECOVERY, unit))
        self.assertTrue(unit.is_unconscious)

    def test_crew_multiplicity_and_cancelled_later_event(self):
        for deadlines, cancel in (((5, 5), False), ((5, 10), False), ((5, 10), True)):
            engine, unit, _ = fixture(U.VEH_GROUND)
            unit.crew_stunned = True
            for index, delay in enumerate(deadlines):
                event = engine.events.schedule(delay, E.UNSTUN_CREW, vehicle_combat.unstun_crew, unit)
                if index == 1 and cancel: event.cancel()
            for _ in range(5): engine.process_tick()
            self.assertEqual(deadlines == (5, 10) and not cancel, unit.crew_stunned)
            for _ in range(5): engine.process_tick()
            self.assertFalse(unit.crew_stunned)
            self.assertEqual(1, sum('Your head clears' in m for m in unit.movement_messages))

    def test_mech_stun_callback_guard_notices(self):
        for status, count in ((S.STARTED, 1), (S.NONE, 0), (S.STARTED | S.DESTROYED, 0)):
            _, unit, _ = fixture()
            unit.status, unit.crit_status = status, C.MECH_STUNNED
            hit_locations.crewstun_recovery(SimpleNamespace(data=unit))
            self.assertFalse(unit.has_crit_status(C.MECH_STUNNED))
            self.assertEqual(count, len(unit.movement_messages))


class MovementCallbackTest(unittest.TestCase):
    def test_configured_fusion_vtol_has_free_fuel_but_ice_does_not(self):
        from physics.heights import fuel_check
        from entities.mech import Specials
        engine,unit,actor = fixture(U.VTOL)
        unit.status,unit.pilot,unit.fuel,unit.speed = S.STARTED,actor,4,30
        engine.nofusion_vtol_fuel = True
        fuel_check(unit)
        self.assertEqual(4,unit.fuel)
        unit.specials |= Specials.ICE_TECH
        fuel_check(unit)
        self.assertEqual(3,unit.fuel)

    def test_idle_fuel_consumption_then_real_queued_free_fall(self):
        from physics.heights import fuel_check
        from core.randomness import use_source
        engine, unit, actor = fixture(U.VTOL)
        unit.pilot, unit.status, unit.fuel, unit.z = actor, S.STARTED, 1, 5
        with use_source(lambda name, low, high, fallback: 1):
            engine.heartbeat()
            self.assertEqual(0, unit.fuel)
            self.assertFalse(engine.has_event(E.FALL, unit))
            engine.heartbeat()
            self.assertEqual(-1, unit.fuel)
            self.assertEqual(3, engine.events.time_until_type_data(E.FALL, unit))
            self.assertEqual(1, engine.events.count_type(E.FALL))
            self.assertTrue(fuel_check(unit))
            self.assertEqual(1, engine.events.count_type(E.FALL))

    def test_aero_callback_boundaries_and_local_fallen_vector(self):
        from physics.movement import aero_move_event
        engine, unit, _ = fixture(U.AERO)
        unit.status, unit.fuel, unit.start_fz = S.STARTED | S.FALLEN, 100, 3
        from entities.mech import MoveType
        unit.move_type = MoveType.FLY
        unit.set_hex_position(3, 3)
        unit.z, unit.fz = 10, 10 * 64.5
        engine.events.schedule(1, E.MOVE, aero_move_event, unit)
        engine.process_tick()
        # Real speed update first brakes the vector to zero; Fallen then subtracts one.
        self.assertEqual(-1, unit.start_fz)
        self.assertEqual(1, engine.events.count_type(E.MOVE))
        self.assertLess(unit.fz, 10 * 64.5)
        self.assertFalse(getattr(unit, 'external_effects', []))

    def test_lateral_rearms_sideslip_and_real_failed_roll_stops_motion(self):
        from systems import maneuver
        from core.randomness import use_source
        engine, unit, actor = fixture(U.VEH_GROUND)
        unit.pilot, unit.status, unit.speed, unit.desired_speed = actor, S.STARTED, 10, 12
        unit.facing = 350
        maneuver.lateral_event(SimpleNamespace(data=unit, data2=60))
        self.assertEqual(1, engine.events.time_until_type_data(E.SIDESLIP, unit))
        with patch('systems.piloting.make_piloting_roll', return_value=SimpleNamespace(success=False)):
            with use_source(lambda name, low, high, fallback: 1): engine.process_tick()
        self.assertEqual((0, 0, 0, 50, 50), (unit.speed, unit.desired_speed, unit.lateral, unit.facing, unit.desired_facing))
        self.assertFalse(engine.has_event(E.SIDESLIP, unit))

    def test_stand_event_clears_current_fallen_state_and_marks_los(self):
        _, unit, _ = fixture()
        unit.status, unit.mapflag = S.FALLEN, 0
        jump._stand_done(SimpleNamespace(data=unit))
        self.assertFalse(unit.is_fallen)
        self.assertEqual(1, unit.mapflag & 1)
        self.assertIn('You have finally finished standing up.', unit.movement_messages)

    def test_stabilization_notice_is_started_filtered(self):
        from systems.occupants import Personnel
        from data.characters import CharacterStore
        engine, unit, _ = fixture()
        store = CharacterStore()
        world = Personnel(engine, store)
        store.create(101, 'Pilot', location=unit._id)
        actor = world.add(store.actor(101), unit._id)
        jump._jumpstabil_callback(SimpleNamespace(data=unit))
        self.assertEqual([], getattr(actor, 'notification_requests', []))
        unit.status |= S.STARTED
        jump._jumpstabil_callback(SimpleNamespace(data=unit))
        self.assertEqual(1, len(actor.notification_requests))
        self.assertEqual('%cgYou have finally stabilized after your jump.%c',
                         actor.notification_requests[0]['message'])

    def test_jump_rearms_before_movement_and_cancels_when_landed(self):
        for ends in (False, True):
            engine, unit, _ = fixture()
            unit.status |= S.JUMPING
            unit._jump_queue = engine.events
            observed = []
            def move(mech):
                observed.append(engine.events.count_type(E.JUMP))
                if ends: unit.clear_status(S.JUMPING)
                return not ends
            engine.events.schedule(1, E.JUMP, jump._jump_event_callback, unit)
            with patch('physics.movement.move_mech', side_effect=move): engine.process_tick()
            self.assertEqual([2], observed)
            self.assertEqual(0 if ends else 1, engine.events.count_type(E.JUMP))


class StaggerCallbackTest(unittest.TestCase):
    def test_legacy_modifiers_and_terminal_buffer(self):
        for tons, wanted in ((35, 2), (36, 1), (55, 1), (56, 0), (75, 0), (76, -1)):
            engine, unit, actor = fixture()
            unit.pilot, unit.status, unit.tonnage, unit.stagger_damage = actor, S.STARTED, tons, 20
            self.assertEqual(wanted, stagger.legacy_modifier(unit))
            engine.events.schedule(1, E.CHECK_STAGGER, stagger.check_stagger_event, unit)
            engine.events.schedule(5, E.CHECK_STAGGER, stagger.check_stagger_event, unit)
            with patch.object(stagger, 'make_piloting_roll', return_value=SimpleNamespace(success=True)) as psr:
                engine.process_tick()
                self.assertEqual(1, psr.call_count)
                self.assertEqual(wanted, psr.call_args.args[1])
            self.assertEqual(-10, unit.stagger_damage)
            self.assertEqual(0, engine.events.count_type(E.CHECK_STAGGER))

    def test_jump_keeps_other_stagger_callbacks_but_fallen_cancels(self):
        for flag in (S.JUMPING, S.FALLEN):
            engine, unit, _ = fixture()
            unit.status, unit.stagger_damage = S.STARTED | flag, 20
            for delay in (1, 5): engine.events.schedule(delay, E.CHECK_STAGGER, stagger.check_stagger_event, unit)
            engine.process_tick()
            self.assertEqual(20 if flag == S.JUMPING else 0, unit.stagger_damage)
            self.assertEqual(1 if flag == S.JUMPING else 0, engine.events.count_type(E.CHECK_STAGGER))


if __name__ == '__main__': unittest.main()


class SourceModeCallbackTest(unittest.TestCase):
    def test_encoded_sprint_and_dodge_used_source_notices(self):
        from types import SimpleNamespace
        from entities.mech import Mech, MechStatus, MechStatus2
        from systems.movement_commands import _mode_complete
        unit = Mech.create_test_mech()
        unit.set_status(MechStatus.STARTED)
        unit.speed=-10
        _mode_complete(SimpleNamespace(data=unit,data2=0x2|0x4))
        self.assertTrue(unit.status2 & MechStatus2.SPRINTING)
        self.assertEqual(0,unit.desired_speed)
        self.assertTrue(any('backward momemtum' in m for m in unit.movement_messages))
        _mode_complete(SimpleNamespace(data=unit,data2=0x10|0x8|0x20))
        self.assertIn('Your dodge maneuver has been used and you are no longer braced for physicals.',unit.movement_messages)

    def test_lateral_null_guard_is_safe(self):
        from systems.maneuver import lateral_event
        from types import SimpleNamespace
        self.assertIsNone(lateral_event(SimpleNamespace(data=None,data2=0)))
