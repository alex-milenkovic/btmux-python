"""Focused source-table and event integration tests for equipment failures."""
import unittest
from core.randomness import use_source
from core.game_loop import GameEngine
from entities.mech import Mech, MechStatus, MoveType, Location
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from systems import failures
from systems.enhanced_crits import part_temp_nuke


class Draws:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []

    def __call__(self, name, low, high, fallback):
        value = self.values.pop(0)
        assert low <= value <= high, (name, low, high, value)
        self.calls.append((name, low, high, value))
        return value


class FailuresTest(unittest.TestCase):
    def test_computer_shutdown_delivers_refusals_to_unit_actor_once(self):
        from entities.mech import UnitType
        from entities.pilot import Pilot
        for kind, refusal in ((UnitType.MW, 'You snore for a while.. and then _start_ yourself back up.'), (UnitType.DS, 'No shutdowns in mid-air! Are you suicidal?'), (UnitType.MECH, None)):
            with self.subTest(kind=kind):
                self.setUp()
                self.unit.unit_type = kind
                self.unit.pilot = Pilot()
                self.unit.set_status(MechStatus.STARTED)
                failures.apply_failure(self.unit, 24, 6)
                if refusal:
                    self.assertTrue(self.unit.is_started)
                    self.assertEqual([refusal], self.unit.inbox)
                    self.assertEqual([dict(recipient=self.unit._id, message=refusal, applied=True)], self.unit.admin_requests)
                else:
                    self.assertFalse(self.unit.is_started)
                    self.assertEqual(1, self.unit.movement_messages.count('Mech has been shutdown!'))
                    self.assertEqual([], getattr(self.unit, 'admin_requests', []))


    def setUp(self):
        self.unit = Mech.create_test_mech()
        self.engine = GameEngine()
        self.engine.register_entity(self.unit)
        self.unit._engine = self.engine
        self.weapon = get_weapon('IS.MediumLaser')
        self.slot = self.unit.sections[Location.RARM].criticals[4]
        self.slot.type = i2weapon(self.weapon.index)
        self.slot.brand = 1

    def test_display_brand_and_reliability_use_distinct_source_indices(self):
        self.assertEqual('Hesperus', failures.get_part_brand_name(self.slot.type, 2))
        self.slot.brand = 2
        with use_source(Draws(9, 81, 1)):
            result = failures.check_weapon_failed(self.unit, Location.RARM, 4)
        self.assertEqual(('DAMAGE', 0), (result.type, result.modifier))

    def test_early_exits_do_not_consume_later_draws(self):
        for values in ((8,), (9, 80)):
            stream = Draws(*values)
            with use_source(stream):
                self.assertEqual('NONE', failures.check_weapon_failed(self.unit, Location.RARM, 4).type)
            self.assertEqual([], stream.values)

    def test_six_is_rerolled_only_once_and_permanent_spike_has_no_timer(self):
        stream = Draws(9, 100, 6, 6)
        with use_source(stream):
            result = failures.check_weapon_failed(self.unit, Location.RARM, 4)
        self.assertEqual('POWER_SPIKE', result.type)
        self.assertEqual(5, part_temp_nuke(self.slot))
        self.assertEqual(0, self.slot.data)
        self.assertEqual(4, len(stream.calls))

    def test_nested_radio_duration_draw_and_additive_recovery(self):
        self.unit.radio_range = 20
        stream = Draws(40, 40)
        with use_source(stream):
            failures.apply_failure(self.unit, 30, 3)
        self.assertEqual(5, self.unit.radio_range)
        self.assertEqual([(40, 200), (30, 40)], [(c[1], c[2]) for c in stream.calls])
        self.engine.events.set_tick(40)
        self.engine.events.run_events()
        self.assertEqual(20, self.unit.radio_range)
        self.assertFalse(any('operational again' in n for n in self.unit.movement_messages))

    def test_scanner_recovery_assigns_full_encoded_range_even_destroyed(self):
        self.unit.lrs_range = 30
        with use_source(Draws(40, 40)):
            failures.apply_failure(self.unit, 24, 3)
        self.assertEqual(0, self.unit.lrs_range)
        self.unit.set_status(MechStatus.DESTROYED)
        self.engine.events.set_tick(40)
        self.engine.events.run_events()
        self.assertEqual(286, self.unit.lrs_range)
        self.assertFalse(any('operational again' in n for n in self.unit.movement_messages))

    def test_target_prerequisite_and_turn_boundary(self):
        from systems.stability import update_pilot_skill_rolls
        self.unit.target = 7
        self.unit.computer = 1
        self.unit.set_status(MechStatus.STARTED)
        self.unit.move_type = MoveType.BIPED
        self.engine.events.set_tick(30)
        with use_source(Draws(42, 100, 1)):
            update_pilot_skill_rolls(self.engine, self.unit)
        self.assertEqual(-1, self.unit.target)
        self.unit.target = 0
        with use_source(Draws(42, 100, 1)):
            failures.check_generic_fail(self.unit, -1)
        self.assertEqual(0, self.unit.target)

class FiringFailureTest(unittest.TestCase):
    def setUp(self):
        from entities.mech import WeaponState
        from entities.crittypes import i2ammo
        self.unit = Mech.create_test_mech()
        self.target = Mech.create_test_mech()
        self.unit.set_status(MechStatus.STARTED)
        self.weapon = get_weapon('IS.AC/5')
        self.unit.weapons = [WeaponState(weapon_idx=self.weapon.index, section=Location.RARM, critical=4)]
        self.slot = self.unit.sections[Location.RARM].criticals[4]
        for crit in range(4, 4 + self.weapon.crits):
            self.unit.sections[Location.RARM].criticals[crit].type = i2weapon(self.weapon.index)
        self.slot.type, self.slot.brand = i2weapon(self.weapon.index), 1
        self.ammo = self.unit.sections[Location.RTORSO].criticals[8]
        self.ammo.type, self.ammo.data = i2ammo(self.weapon.index), 10

    def test_dud_and_jam_consume_round_but_spike_does_not(self):
        from systems.combat import fire_weapon
        for outcome in (2, 3):
            with self.subTest(outcome=outcome):
                self.slot.brand, self.slot.data, self.ammo.data = 1, 0, 10
                with use_source(Draws(9, 100, outcome, 20)):
                    result = fire_weapon(self.unit, self.target, 0, 1, to_hit_roll=12, location_roll=7)
                self.assertTrue(result.shot_aborted)
                self.assertEqual(9, self.ammo.data)
                self.assertEqual(0, result.damage_dealt)

    def test_damaged_barrel_is_permanent_until_repair_and_does_not_spend_ammo(self):
        from systems.combat import fire_weapon
        from systems.enhanced_crits import WEAP_DAM_BALL_BARREL
        from entities.mech import FireMode
        self.slot.firemode |= FireMode.DAMAGED_MODE
        self.slot.weap_damage_flags = WEAP_DAM_BALL_BARREL
        with use_source(Draws(8)):
            result = fire_weapon(self.unit, self.target, 0, 1, to_hit_roll=2)
        self.assertTrue(result.shot_aborted)
        self.assertEqual(7, part_temp_nuke(self.slot))
        self.assertEqual(10, self.ammo.data)
        self.assertEqual(0, self.slot.data)
        with use_source(Draws()):
            again = fire_weapon(self.unit, self.target, 0, 1)
        self.assertFalse(again.hit)
        self.assertIn('failure', again.messages[0])
