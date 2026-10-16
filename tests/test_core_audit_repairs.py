"""Focused Core callback regressions from the recorded C obligations."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tests.test_core_startup import fixture
from core.events import EventType as E
from core.randomness import RandomState, number, use_source
from entities.mech import MechStatus as S, MechStatus2 as S2, CritStatus as C, UnitType as U
from systems import piloting, targeting, stagger, vehicle_combat
from physics import jump


class CoreAuditRepairs(unittest.TestCase):
    def test_high_count_float_operand_and_detached_equal_bound(self):
        state = RandomState(1)
        state.total_rolls = 16777225
        self.assertEqual(2796203, state.stat_rows()[5]['optimal_count'])
        self.assertEqual(0, number(7, 7))

    def test_overdue_failed_recovery_extends_from_now(self):
        engine, unit, actor = fixture()
        unit.pilot, unit.pilot_hits = actor, 4
        piloting.prolong_uncon(unit, 10)
        engine.events.set_tick(20)
        with patch.object(piloting, 'roll_skilled', return_value=2):
            engine.events.run_by_type(E.RECOVERY)
        self.assertEqual(30, engine.events.last_time_until_type_data(E.RECOVERY, unit))

    def test_registration_migrates_recovery_without_duplicates(self):
        engine, unit, _ = fixture()
        engine.unregister_entity(unit)
        unit._engine = None
        piloting.prolong_uncon(unit, 17)
        engine.register_entity(unit)
        engine.register_entity(unit)
        self.assertEqual(1, len(engine.events.pending_events(E.RECOVERY, unit)))
        self.assertEqual(17, engine.events.last_time_until_type_data(E.RECOVERY, unit))
        self.assertEqual(0, unit.uncon_recovery_countdown)

    def test_callback_status_words_preserve_reserved_bits(self):
        engine, unit, actor = fixture()
        unit.pilot = actor
        unit.status = S(0x80000000 | int(S.STARTED | S.UNCONSCIOUS))
        with patch.object(piloting, 'roll_skilled', return_value=12):
            piloting.recovery_event(SimpleNamespace(data=unit))
        self.assertEqual(0x80000000 | int(S.STARTED), int(unit.status))
        unit.status2 = S2(0x80000000 | int(S2.SPRINTING))
        unit.clear_status2(S2.SPRINTING)
        unit.crit_status = C(0x80000000 | int(C.OWEIGHT_OK))
        unit.clear_crit_status(C.OWEIGHT_OK)
        self.assertEqual((0x80000000, 0x80000000), (int(unit.status2), int(unit.crit_status)))

    def test_stale_map_identity_stops_plos_and_los_marker(self):
        from systems.ecm import mark_for_los_update
        engine, unit, _ = fixture()
        board = unit.map
        unit.status, unit.mapindex = S.STARTED, -1
        before = board.moves
        mark_for_los_update(unit)
        targeting.plos_event(SimpleNamespace(data=unit, data2=engine))
        self.assertEqual(before, board.moves)
        self.assertFalse(engine.has_event(E.PLOS, unit))

    def test_lock_uses_global_target_then_identity_and_printf(self):
        engine, unit, _ = fixture()
        other = type(unit).create_test_mech()
        other._id, other.name = 909, 'Remote'
        engine.register_entity(other)
        unit.target = 909
        with patch.object(targeting, 'in_line_of_sight', return_value=True), \
             patch('systems.notifications.identity', return_value='something [ZZ]'), \
             patch('systems.notifications.mech_printf') as notice:
            targeting.lock_event(SimpleNamespace(data=unit))
        self.assertEqual('something [ZZ]', notice.call_args.args[-1])

    def test_battlesuit_stabilization_uses_owner_queue_and_three_ticks(self):
        engine, unit, _ = fixture(U.BSUIT)
        jump._schedule_stabilization(unit)
        self.assertEqual(3, engine.events.time_until_type_data(E.JUMPSTABIL, unit))

    def test_legacy_stagger_stop_resets_before_return(self):
        engine, unit, _ = fixture()
        unit.status, unit.stagger_damage, unit.last_stagger_notify = S.FALLEN, 25, 99
        stagger.check_stagger_event(SimpleNamespace(data=unit))
        self.assertEqual((0, 0), (unit.stagger_damage, unit.last_stagger_notify))

    def test_crew_notice_observes_stun_before_bit_clear(self):
        from entities.vehicle import TankCritStatus
        engine, unit, _ = fixture(U.VEH_GROUND)
        unit.tank_crit_status = TankCritStatus(0x40 | int(TankCritStatus.CREW_STUNNED))
        observed = []
        with patch('systems.movement_commands.notify',
                   side_effect=lambda *a: observed.append(int(unit.tank_crit_status))):
            vehicle_combat.unstun_crew(SimpleNamespace(data=unit))
        self.assertEqual([0x40 | int(TankCritStatus.CREW_STUNNED)], observed)
        self.assertEqual(0x40, int(unit.tank_crit_status))

    def test_fixture_free_fuel_does_not_override_source_predicate(self):
        from physics.heights import aero_free_fuel
        _, unit, _ = fixture(U.AERO)
        unit.free_fuel = True
        self.assertFalse(aero_free_fuel(unit))

    def test_stale_jump_callback_still_moves_and_cancels_rearm(self):
        engine, unit, _ = fixture()
        with patch('physics.movement.move_mech') as move:
            jump._jump_event_callback(SimpleNamespace(data=unit))
            move.assert_called_once_with(unit)
        self.assertFalse(engine.has_event(E.JUMP, unit))

    def test_startup_blindness_whitespace_and_security_are_separate(self):
        from systems.startup import startup
        for argument, due in (('override', 1), ('\x1coverride', 5)):
            engine, unit, actor = fixture()
            unit.status = S.BLINDED
            actor.security = True
            self.assertTrue(startup(engine, unit, argument, caller=actor)[0])
            self.assertEqual(due, engine.events.time_until_type_data(E.STARTUP, unit))

    def test_startup_reads_live_repair_service_each_attempt(self):
        from systems.startup import startup
        engine, unit, actor = fixture()
        service = SimpleNamespace(latest=lambda u: 20)
        engine.repair_jobs = service
        self.assertFalse(startup(engine, unit, caller=actor)[0])
        service.latest = lambda u: 0
        unit.repair_remaining = 99
        self.assertTrue(startup(engine, unit, caller=actor)[0])

    def test_startup_ownership_and_health_use_configured_records(self):
        from data.characters import CharacterStore
        from core.attributes import AttributeStore
        from systems.characters import set_value
        from systems.startup import startup
        engine, unit, actor = fixture()
        actor._id = 101
        store = engine.character_store = CharacterStore()
        store.create(101, 'AssignedPilot')
        set_value(store, 101, 'Build', 5)
        set_value(store, 101, 'Bruise', 20)
        engine.attributes = AttributeStore()
        engine.attributes.set(unit._id, 'A_PILOTNUM', '#101')
        unit.in_character = True
        self.assertTrue(startup(engine, unit, caller=actor)[0])
        self.assertEqual(2, unit.pilot_hits)

    def test_boot_initializes_detached_character_adapter_and_preserves_specials(self):
        from systems.startup import complete_startup
        from entities.mech import Specials
        engine, unit, actor = fixture(U.MW)
        actor._id, actor.sixth_sense, actor.build = 0, True, 5
        unit.pilot = actor
        unit.specials = Specials(0x80000000 | int(Specials.SS_ABILITY))
        unit.crit_status |= C.OWEIGHT_OK
        complete_startup(engine, unit)
        self.assertEqual(31, unit.sections[0].internal)
        self.assertTrue(unit.has_crit_status(C.PC_INITIALIZED))
        self.assertFalse(unit.has_crit_status(C.OWEIGHT_OK))
        self.assertEqual(0x80000000, int(unit.specials))

    def test_shutdown_abort_notice_precedes_pilot_and_event_clear(self):
        from systems import startup
        engine, unit, actor = fixture()
        startup.startup(engine, unit, caller=actor)
        seen = []
        with patch.object(startup, 'notify', side_effect=lambda u,m,*a: seen.append((u.pilot, engine.has_event(E.STARTUP,u))) or m):
            startup.shutdown(engine, unit)
        self.assertEqual([(actor, True)], seen)

    def test_destroy_retains_history_and_stops_legacy_stagger(self):
        from systems.damage import destroy_state
        engine, unit, _ = fixture()
        unit.stagger_damage_list = [dict(amount=20, occurred_at=0, counted=False)]
        unit.stagger_damage, unit.last_stagger_notify, unit.turn_damage = 20, 3, 7
        destroy_state(unit, engine)
        self.assertEqual([dict(amount=20, occurred_at=0, counted=False)], unit.stagger_damage_list)
        self.assertEqual((0, 0, 7), (unit.stagger_damage, unit.last_stagger_notify, unit.turn_damage))

    def test_pc_long_zero_integer_and_unsigned_internal(self):
        from systems.personal_damage import initialize_pc
        engine, unit, actor = fixture(U.MW)
        actor._id, actor.build, actor.bruise = 101, 1, 50
        actor.pcequip = '1234 - - ' + '0' * 4300 + '3'
        initialize_pc(actor, unit)
        self.assertEqual(248, unit.sections[0].internal)
        self.assertEqual(1, unit.sections[7].armor)

    def test_auto_profile_guard_and_services_are_live_after_sensor(self):
        engine, unit, _ = fixture()
        auto = SimpleNamespace(mymech=unit, weaplist=None)
        seen = []
        def sensor(a):
            seen.append('sensor')
            a.weaplist = []
            engine.auto_services['gun'] = lambda a: seen.append('new gun')
        engine.auto_services = dict(sensor=sensor, profile=lambda a: seen.append('profile'))
        engine.global_tick = 1
        engine.auto_heartbeat(auto)
        self.assertEqual(['sensor', 'new gun'], seen)
        seen.clear()
        engine.global_tick = 180
        engine.auto_heartbeat(auto)
        self.assertEqual(['sensor', 'profile', 'new gun'], seen)


if __name__ == '__main__':
    unittest.main()
