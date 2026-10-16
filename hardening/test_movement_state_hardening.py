"""Independent state boundaries shared by movement commands and combat."""
import unittest
from types import SimpleNamespace
from entities.map import WATER, ICE, BRIDGE, GRASSLAND
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, Location
from entities.vehicle import Vehicle
from systems import movement_commands as state


class TestMovementStateHardening(unittest.TestCase):
    def test_water_requires_a_waterlike_surface_and_negative_height(self):
        unit = Mech.create_test_mech()
        for terrain in (WATER, ICE, BRIDGE, GRASSLAND):
            for height in (-1, 0, 1):
                unit.terrain, unit.z = terrain, height
                with self.subTest(terrain=terrain, height=height):
                    self.assertEqual(terrain != GRASSLAND and height == -1, state.in_water(unit))

    def test_posture_feedback_and_expired_events(self):
        unit = Mech.create_test_mech()
        self.assertFalse(state.pending(unit, '_absent_event'))
        unit.set_status(S.HULLDOWN)
        self.assertEqual('You can not move while hulldown', state.posture_guard(unit))
        unit.clear_status(S.HULLDOWN)
        unit._hulldown_event = SimpleNamespace(zombie=False)
        self.assertEqual('You are busy changing your hulldown mode', state.posture_guard(unit))
        unit._hulldown_event.zombie = True
        self.assertIsNone(state.posture_guard(unit))

    def test_weapon_recycling_is_scoped_to_requested_limbs(self):
        unit = Mech.create_test_mech()
        weapon = SimpleNamespace(section=Location.LARM, recycle=1)
        unit.weapons = [weapon]
        self.assertTrue(state.limb_busy(unit))
        self.assertFalse(state.limb_busy(unit, weapons=False))
        self.assertFalse(state.limb_busy(unit, (Location.RARM,)))
        weapon.recycle = 0
        self.assertFalse(state.limb_busy(unit, (Location.LARM,)))
        vehicle = Vehicle.create_test_vehicle()
        vehicle.sections = dict(enumerate(vehicle.sections))
        for section in vehicle.sections.values():
            section.recycle = 0
        vehicle.weapons = []
        self.assertFalse(state.limb_busy(vehicle))
        next(iter(vehicle.sections.values())).recycle = 1
        self.assertTrue(state.limb_busy(vehicle))

    def test_stand_time_clamps_both_ends_of_the_c_denominator(self):
        unit = Mech.create_test_mech()
        for speed, seconds in ((0, 30), (10.75, 30), (21.5, 30), (64.5, 10), (700, 1)):
            unit.max_speed = speed
            with self.subTest(speed=speed):
                self.assertEqual(seconds, state.stand_time(unit))

    def test_mode_lock_accepts_a_lock_bit_or_a_nondodge_transition(self):
        unit = Mech.create_test_mech()
        unit.status2 = S2.SPRINTING
        self.assertTrue(state.mode_locked(unit))
        unit.status2 = 0
        unit._mode_event = SimpleNamespace(zombie=False)
        self.assertTrue(state.mode_locked(unit))
        unit.status2 = S2.DODGING
        self.assertFalse(state.mode_locked(unit))
        unit.status2 = 0
        unit._mode_event.zombie = True
        self.assertFalse(state.mode_locked(unit))
