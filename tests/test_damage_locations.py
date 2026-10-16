import unittest
from core.game_loop import GameEngine
from core.randomness import use_source
from entities.mech import Mech, Location as L, MoveType, UnitType, Specials
from systems.combat import get_punch_location, get_kick_location, HitGroup as H
from tests.test_damage_failures import Draws


class HitLocationsTest(unittest.TestCase):
    def test_quad_rear_punch_and_front_kick_use_correct_legs(self):
        u = Mech.create_test_mech()
        u.move_type = MoveType.QUAD
        self.assertEqual(L.LLEG, get_punch_location(u, H.BACK, 1))
        self.assertEqual(L.RLEG, get_punch_location(u, H.BACK, 5))
        self.assertEqual(L.RARM, get_kick_location(u, H.FRONT, 1))
        self.assertEqual(L.LARM, get_kick_location(u, H.FRONT, 6))

    def test_crittable_zero_original_precedes_vcrit_but_not_stationary_guard(self):
        from systems.hit_locations import crittable
        u = Mech.create_test_mech()
        u.unit_type = UnitType.VEH_GROUND
        u._engine = GameEngine()
        u._engine.vcrit = 0
        u.sections[0].armor_orig = 0
        with use_source(Draws()):
            self.assertTrue(crittable(u, 0, 100))
            u.move_type = MoveType.NONE
            self.assertFalse(crittable(u, 0, 100))

    def test_crittable_strict_threshold_and_full_armor_lucky_roll(self):
        from systems.hit_locations import crittable
        u = Mech.create_test_mech()
        u.sections[0].armor_orig = 100
        u.sections[0].armor = 50
        with use_source(Draws()):
            self.assertFalse(crittable(u, 0, 50))
        u.sections[0].armor = 49
        with use_source(Draws(6)):
            self.assertTrue(crittable(u, 0, 50))
        u.sections[0].armor = 100
        with use_source(Draws(23)):
            self.assertTrue(crittable(u, 0, 50))

    def test_live_suits_and_transfer_are_class_aware(self):
        from systems.hit_locations import live_suit_hit_location, transfer_target
        u = Mech.create_test_mech()
        u.unit_type = UnitType.BSUIT
        for section in u.sections:
            section.internal = 0
        self.assertEqual(-1, live_suit_hit_location(u))
        u.sections[4].internal = 1
        with use_source(Draws(0)):
            self.assertEqual(4, transfer_target(u, 0))
        u.unit_type = UnitType.VEH_GROUND
        self.assertEqual(-1, transfer_target(u, L.LARM))
