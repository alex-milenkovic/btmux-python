"""Vehicle critical consequences must reach live slots, commands and events."""
import unittest
from core.game_loop import GameEngine, recycle_weaponry
from core.events import EventType
from core.randomness import use_source
from entities.mech import Mech, MechStatus, MoveType, UnitType, VehicleLocation, WeaponState
from entities.weapon import get_weapon
from entities.crittypes import i2weapon
from systems import vehicle_combat as vc
from systems.enhanced_crits import part_temp_nuke
from tests.test_damage_failures import Draws


class VehicleCompletionTest(unittest.TestCase):
    def setUp(self):
        self.unit = Mech.create_test_mech()
        self.unit.unit_type = UnitType.VEH_GROUND
        self.unit.move_type = MoveType.TRACK
        self.unit.set_status(MechStatus.STARTED)
        self.engine = GameEngine()
        self.engine.register_entity(self.unit)

    def test_jam_uses_slot_and_normal_recycler(self):
        weapon = get_weapon('IS.AC/5')
        self.unit.weapons = [WeaponState(weapon_idx=weapon.index, section=0, critical=0)]
        slot = self.unit.sections[0].criticals[0]
        slot.type = i2weapon(weapon.index)
        with use_source(Draws(0, 60)):
            vc.handle_weapon_jam(self.unit, 0)
        self.assertEqual((1, 60), (part_temp_nuke(slot), slot.data))
        self.engine.events.set_tick(60)
        recycle_weaponry(self.engine, self.unit)
        self.assertEqual((0, 0), (part_temp_nuke(slot), slot.data))

    def test_overlapping_stuns_do_not_recover_early_or_cap_current_speed(self):
        self.unit.max_speed = 64.5
        self.unit.speed = self.unit.desired_speed = 60
        vc.handle_crew_stunned(self.unit)
        self.assertEqual(60, self.unit.speed)
        self.assertAlmostEqual(42.5666666667, self.unit.desired_speed)
        self.engine.events.set_tick(30)
        vc.handle_crew_stunned(self.unit)
        self.engine.events.set_tick(60)
        self.engine.events.run_events()
        self.assertTrue(self.unit.crew_stunned)
        self.engine.events.set_tick(90)
        self.engine.events.run_events()
        self.assertFalse(self.unit.crew_stunned)

    def test_rotor_loss_schedules_crash_without_immediate_death(self):
        self.unit.unit_type = UnitType.VTOL
        self.unit.move_type = MoveType.VTOL
        self.unit.max_speed = 10.75
        self.unit.z = 10
        vc.handle_rotor_damaged(self.unit)
        self.assertEqual(0, self.unit.max_speed)
        self.assertFalse(self.unit.is_destroyed)
        self.assertEqual(0, self.unit.sections[VehicleLocation.ROTOR].internal)
        self.assertEqual(1, self.engine.events.count_type(EventType.FALL))

    def test_weighted_main_weapon_keeps_first_tie_and_rejects_zero(self):
        weapon = get_weapon('IS.MediumLaser')
        self.unit.weapons = [WeaponState(weapon_idx=weapon.index, section=loc, critical=4) for loc in (0, 1)]
        for ws in self.unit.weapons:
            self.unit.sections[ws.section].criticals[4].type = i2weapon(weapon.index)
        with use_source(Draws(0, 0)):
            self.assertIsNone(vc.jam_main_weapon(self.unit))
        with use_source(Draws(9, 9)):
            self.assertIs(self.unit.weapons[0], vc.jam_main_weapon(self.unit))
        self.assertEqual(5, part_temp_nuke(self.unit.sections[0].criticals[4]))
        self.assertEqual(0, self.unit.sections[0].criticals[4].data)
