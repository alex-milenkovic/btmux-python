"""
Tests for the critical-slot type namespace (entities/crittypes.py).

Tests cover:
- Segment base indices as the C header computes them
- Predicate boundaries (inclusive low, exclusive high)
- Converter round-trips
- Special sub-index values
- crits_in_loc per unit/move type
"""

import unittest

from entities.crittypes import (
    AMMO_BASE_INDEX,
    BOMB_BASE_INDEX,
    CARGO_BASE_INDEX,
    EMPTY,
    NUM_BOMBS,
    NUM_WEAPONS,
    SPECIAL_BASE_INDEX,
    WEAPON_BASE_INDEX,
    Special,
    ammo2weapon_i,
    crits_in_loc,
    i2ammo,
    i2special,
    i2weapon,
    is_actuator,
    is_ammo,
    is_bomb,
    is_cargo,
    is_special,
    is_weapon,
    special2i,
    weapon2i,
)
from entities.mech import Location, Mech, MoveType, NUM_CRITICALS, UnitType


class TestBaseIndices(unittest.TestCase):
    """The segment bases, as computed in mech.h lines 104-113."""

    def test_values(self):
        self.assertEqual(NUM_WEAPONS, 192)
        self.assertEqual(NUM_BOMBS, 9)
        self.assertEqual(EMPTY, 0)
        self.assertEqual(WEAPON_BASE_INDEX, 1)
        self.assertEqual(AMMO_BASE_INDEX, 193)   # mech.h:109 comment says 193
        self.assertEqual(BOMB_BASE_INDEX, 385)   # mech.h:110 comment says 385
        self.assertEqual(SPECIAL_BASE_INDEX, 394)
        self.assertEqual(CARGO_BASE_INDEX, 512)


class TestPredicates(unittest.TestCase):
    """Range membership, matching the C's >= low && < high."""

    def test_empty_is_nothing(self):
        self.assertFalse(is_weapon(EMPTY))
        self.assertFalse(is_ammo(EMPTY))
        self.assertFalse(is_special(EMPTY))

    def test_weapon_range(self):
        self.assertTrue(is_weapon(WEAPON_BASE_INDEX))
        self.assertTrue(is_weapon(AMMO_BASE_INDEX - 1))
        self.assertFalse(is_weapon(AMMO_BASE_INDEX))

    def test_ammo_range(self):
        self.assertTrue(is_ammo(AMMO_BASE_INDEX))
        self.assertTrue(is_ammo(BOMB_BASE_INDEX - 1))
        self.assertFalse(is_ammo(BOMB_BASE_INDEX))

    def test_bomb_range(self):
        self.assertTrue(is_bomb(BOMB_BASE_INDEX))
        self.assertTrue(is_bomb(SPECIAL_BASE_INDEX - 1))
        self.assertFalse(is_bomb(SPECIAL_BASE_INDEX))

    def test_special_range(self):
        self.assertTrue(is_special(SPECIAL_BASE_INDEX))
        self.assertTrue(is_special(CARGO_BASE_INDEX - 1))
        self.assertFalse(is_special(CARGO_BASE_INDEX))

    def test_cargo_range(self):
        self.assertTrue(is_cargo(CARGO_BASE_INDEX))
        self.assertFalse(is_cargo(CARGO_BASE_INDEX - 1))

    def test_actuator_predicate(self):
        """The first four Special slots only (mech.h:127)."""
        for sub in (Special.SHOULDER_OR_HIP, Special.UPPER_ACTUATOR,
                    Special.LOWER_ACTUATOR, Special.HAND_OR_FOOT_ACTUATOR):
            self.assertTrue(is_actuator(i2special(sub)))
        self.assertFalse(is_actuator(i2special(Special.LIFE_SUPPORT)))
        self.assertFalse(is_actuator(EMPTY))
        self.assertFalse(is_actuator(i2weapon(0)))


class TestConverters(unittest.TestCase):
    """The *2I / I2* arithmetic (mech.h lines 148-159)."""

    def test_weapon_round_trip(self):
        self.assertEqual(i2weapon(0), 1)
        self.assertEqual(weapon2i(i2weapon(37)), 37)

    def test_ammo_round_trip(self):
        self.assertEqual(i2ammo(0), 193)
        self.assertEqual(ammo2weapon_i(i2ammo(37)), 37)

    def test_special_round_trip(self):
        self.assertEqual(i2special(Special.GYRO), 394 + 8)
        self.assertEqual(special2i(i2special(Special.GYRO)), Special.GYRO)

    def test_ammo_shares_weapon_numbering(self):
        """A weapon and its ammo differ by exactly AMMO_BASE_INDEX - 1."""
        self.assertEqual(i2ammo(5) - i2weapon(5),
                         AMMO_BASE_INDEX - WEAPON_BASE_INDEX)


class TestSpecialSubIndices(unittest.TestCase):
    """Spot-check the sub-index values against mech.h lines 164-215."""

    def test_known_values(self):
        self.assertEqual(Special.SHOULDER_OR_HIP, 0)
        self.assertEqual(Special.UPPER_ACTUATOR, 1)
        self.assertEqual(Special.LOWER_ACTUATOR, 2)
        self.assertEqual(Special.HAND_OR_FOOT_ACTUATOR, 3)
        self.assertEqual(Special.LIFE_SUPPORT, 4)
        self.assertEqual(Special.SENSORS, 5)
        self.assertEqual(Special.COCKPIT, 6)
        self.assertEqual(Special.ENGINE, 7)
        self.assertEqual(Special.GYRO, 8)
        self.assertEqual(Special.HEAT_SINK, 9)
        self.assertEqual(Special.JUMP_JET, 10)
        self.assertEqual(Special.CASE, 11)
        self.assertEqual(Special.TARGETING_COMPUTER, 15)
        self.assertEqual(Special.MASC, 16)
        self.assertEqual(Special.CASE_II, 33)
        self.assertEqual(Special.SPLIT_CRIT_LEFT, 49)
        self.assertEqual(Special.SPLIT_CRIT_RIGHT, 50)
        self.assertEqual(Special.HARDPOINT, 51)

    def test_all_specials_are_in_range(self):
        """Every sub-index has to land inside the special segment."""
        for sub in Special:
            self.assertTrue(is_special(i2special(sub)))


class TestCritsInLoc(unittest.TestCase):
    """Reference: mech.utils.c lines 151-166 (CritsInLoc)."""

    def setUp(self):
        self.mech = Mech()

    def test_head_and_legs_have_six(self):
        for loc in (Location.HEAD, Location.LLEG, Location.RLEG):
            self.assertEqual(crits_in_loc(self.mech, loc), 6)

    def test_biped_arms_and_torsos_have_twelve(self):
        for loc in (Location.LARM, Location.RARM, Location.LTORSO,
                    Location.RTORSO, Location.CTORSO):
            self.assertEqual(crits_in_loc(self.mech, loc), NUM_CRITICALS)

    def test_quad_arms_have_six(self):
        """A quad's front legs are legs (mech.utils.c:159-162)."""
        self.mech.move_type = MoveType.QUAD
        for loc in (Location.LARM, Location.RARM):
            self.assertEqual(crits_in_loc(self.mech, loc), 6)

    def test_mechwarrior_has_two(self):
        """CLASS_MW returns 2 for every location (mech.utils.c:163-164)."""
        self.mech.unit_type = UnitType.MW
        for loc in Location:
            self.assertEqual(crits_in_loc(self.mech, loc), 2)

    def test_vehicle_gets_full_array(self):
        """Non-mech, non-MW falls through to NUM_CRITICALS."""
        self.mech.unit_type = UnitType.VEH_GROUND
        self.assertEqual(crits_in_loc(self.mech, Location.HEAD), NUM_CRITICALS)

    def test_array_is_still_twelve_wide(self):
        """crits_in_loc is a loop bound, not an allocation size."""
        self.assertEqual(len(self.mech.sections[Location.HEAD].criticals),
                         NUM_CRITICALS)


if __name__ == '__main__':
    unittest.main()
