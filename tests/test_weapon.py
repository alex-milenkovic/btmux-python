"""
Tests for the weapon module.

Tests cover:
- Weapon data structure
- Weapon catalog and lookup
- Range bracket calculation
- BTH modifiers from range
- Missile hit table
"""

import unittest
from entities.weapon import (
    Weapon,
    WeaponType,
    WeaponClass,
    WeaponFlags,
    RangeBracket,
    RANGE_BTH_MODIFIERS,
    WEAPON_CATALOG,
    get_weapon,
    get_weapon_by_index,
    get_all_weapons,
    get_weapons_by_type,
    get_weapons_by_class,
    get_clan_weapons,
    get_is_weapons,
    get_missiles_hit,
    MISSILE_HIT_TABLE,
    # Specific weapons for testing
    IS_MEDIUM_LASER,
    IS_AC10,
    IS_LRM10,
    IS_SRM6,
    IS_PPC,
    CL_ER_MEDIUM_LASER,
    CL_STREAK_SRM6,
)


class TestWeaponDataclass(unittest.TestCase):
    """Test basic Weapon dataclass functionality."""

    def test_create_weapon(self):
        """Test creating a basic weapon."""
        weapon = Weapon(
            name="Test.Laser",
            weapon_type=WeaponType.TBEAM,
            damage=5,
            heat=3,
            vrt=20,
        )
        self.assertEqual(weapon.name, "Test.Laser")
        self.assertEqual(weapon.damage, 5)
        self.assertEqual(weapon.heat, 3)
        self.assertEqual(weapon.vrt, 20)

    def test_default_values(self):
        """Test weapon default values."""
        weapon = Weapon(name="Test")
        self.assertEqual(weapon.weapon_type, WeaponType.TBEAM)
        self.assertEqual(weapon.weapon_class, WeaponClass.ENERGY)
        self.assertEqual(weapon.crits, 1)
        self.assertEqual(weapon.ammo_per_ton, 0)
        self.assertFalse(weapon.uses_ammo)
        self.assertEqual(weapon.missiles, 1)
        self.assertFalse(weapon.is_clan)

    def test_clan_flag_auto_set(self):
        """Test that is_clan is auto-set from special flags."""
        weapon = Weapon(name="CL.Test", special=WeaponFlags.CLAT)
        self.assertTrue(weapon.is_clan)

    def test_extreme_range_calculation(self):
        """Test extreme range is 1.5x long range."""
        weapon = Weapon(name="Test", range_long=15)
        self.assertEqual(weapon.extreme_range, 22)  # 15 * 1.5 = 22.5 -> 22

    def test_extreme_range_short(self):
        """Test extreme range for short-range weapon."""
        weapon = Weapon(name="Test", range_long=3)
        self.assertEqual(weapon.extreme_range, 4)  # 3 * 1.5 = 4.5 -> 4


class TestRangeBrackets(unittest.TestCase):
    """Test range bracket determination."""

    def setUp(self):
        """Create test weapon with known ranges."""
        # Medium Laser: 0/3/6/9, extreme = 13
        self.ml = IS_MEDIUM_LASER

    def test_short_range(self):
        """Test short range bracket."""
        self.assertEqual(self.ml.get_range_bracket(1), RangeBracket.SHORT)
        self.assertEqual(self.ml.get_range_bracket(3), RangeBracket.SHORT)

    def test_medium_range(self):
        """Test medium range bracket."""
        self.assertEqual(self.ml.get_range_bracket(4), RangeBracket.MEDIUM)
        self.assertEqual(self.ml.get_range_bracket(6), RangeBracket.MEDIUM)

    def test_long_range(self):
        """Test long range bracket."""
        self.assertEqual(self.ml.get_range_bracket(7), RangeBracket.LONG)
        self.assertEqual(self.ml.get_range_bracket(9), RangeBracket.LONG)

    def test_extreme_range(self):
        """Test extreme range bracket."""
        self.assertEqual(self.ml.get_range_bracket(10), RangeBracket.EXTREME)
        self.assertEqual(self.ml.get_range_bracket(13), RangeBracket.EXTREME)

    def test_out_of_range(self):
        """Test out of range."""
        self.assertEqual(self.ml.get_range_bracket(14), RangeBracket.OUT_OF_RANGE)
        self.assertEqual(self.ml.get_range_bracket(50), RangeBracket.OUT_OF_RANGE)

    def test_minimum_range(self):
        """Test minimum range with PPC (min=3)."""
        ppc = IS_PPC
        self.assertEqual(ppc.get_range_bracket(1), RangeBracket.MINIMUM)
        self.assertEqual(ppc.get_range_bracket(3), RangeBracket.MINIMUM)
        self.assertEqual(ppc.get_range_bracket(4), RangeBracket.SHORT)


class TestRangeBTHModifiers(unittest.TestCase):
    """Test BTH modifiers from range."""

    def setUp(self):
        self.ml = IS_MEDIUM_LASER
        self.ppc = IS_PPC

    def test_short_range_modifier(self):
        """Test short range has no modifier."""
        self.assertEqual(self.ml.get_range_bth_modifier(3), 0)

    def test_medium_range_modifier(self):
        """Test medium range modifier (+2)."""
        self.assertEqual(self.ml.get_range_bth_modifier(5), 2)

    def test_long_range_modifier(self):
        """Test long range modifier (+4)."""
        self.assertEqual(self.ml.get_range_bth_modifier(8), 4)

    def test_extreme_range_modifier(self):
        """Test extreme range modifier (+8)."""
        self.assertEqual(self.ml.get_range_bth_modifier(12), 8)

    def test_out_of_range_modifier(self):
        """Test out of range returns 1000."""
        self.assertEqual(self.ml.get_range_bth_modifier(20), 1000)

    def test_minimum_range_modifier(self):
        """Test minimum range modifier (+1 per hex inside)."""
        # PPC has min range 3
        self.assertEqual(self.ppc.get_range_bth_modifier(3), 1)  # At min = +1
        self.assertEqual(self.ppc.get_range_bth_modifier(2), 2)  # 1 hex inside = +2
        self.assertEqual(self.ppc.get_range_bth_modifier(1), 3)  # 2 hexes inside = +3

    def test_can_fire_at_range(self):
        """Test can_fire_at_range helper."""
        self.assertTrue(self.ml.can_fire_at_range(5))
        self.assertTrue(self.ml.can_fire_at_range(13))  # Extreme range
        self.assertFalse(self.ml.can_fire_at_range(14))


class TestWeaponCatalog(unittest.TestCase):
    """Test weapon catalog functionality."""

    def test_catalog_not_empty(self):
        """Test that catalog is populated."""
        self.assertGreater(len(WEAPON_CATALOG), 0)
        self.assertGreater(len(get_all_weapons()), 20)

    def test_get_weapon_by_name(self):
        """Test looking up weapon by name."""
        ml = get_weapon("IS.MediumLaser")
        self.assertIsNotNone(ml)
        self.assertEqual(ml.damage, 5)
        self.assertEqual(ml.heat, 3)

    def test_get_weapon_not_found(self):
        """Test looking up nonexistent weapon."""
        self.assertIsNone(get_weapon("NonexistentWeapon"))

    def test_get_weapon_by_index(self):
        """Test looking up weapon by index."""
        weapon = get_weapon_by_index(0)
        self.assertIsNotNone(weapon)

    def test_get_weapon_by_index_invalid(self):
        """Test invalid index returns None."""
        self.assertIsNone(get_weapon_by_index(-1))
        self.assertIsNone(get_weapon_by_index(9999))

    def test_every_weapon_knows_its_own_index(self):
        """weapon.index round-trips through get_weapon_by_index.

        The index is the C's subscript into MechWeapons[] - the thing a crit
        slot actually stores as I2Weapon(index) (mech.h:156).
        """
        from entities.weapon import WEAPON_INDEX, get_all_weapons

        for weapon in get_all_weapons():
            self.assertGreaterEqual(weapon.index, 0)
            self.assertIs(get_weapon_by_index(weapon.index), weapon)

        self.assertEqual(len(WEAPON_INDEX), len(get_all_weapons()))

    def test_indices_are_sequential_and_unique(self):
        """Indices are handed out 0..n-1 in registration order."""
        from entities.weapon import WEAPON_INDEX

        self.assertEqual([w.index for w in WEAPON_INDEX],
                         list(range(len(WEAPON_INDEX))))

    def test_indices_fit_the_c_weapon_segment(self):
        """All indices must fit in NUM_WEAPONS so ammo stays below BOMB_BASE.

        Reference: mech.h:104,109-110 - the ammo segment is only NUM_WEAPONS
        (192) entries wide.
        """
        from entities.crittypes import NUM_WEAPONS, is_ammo, is_weapon, i2ammo, i2weapon
        from entities.weapon import WEAPON_INDEX

        self.assertLessEqual(len(WEAPON_INDEX), NUM_WEAPONS)
        for weapon in WEAPON_INDEX:
            self.assertTrue(is_weapon(i2weapon(weapon.index)))
            self.assertTrue(is_ammo(i2ammo(weapon.index)))

    def test_get_weapons_by_type_energy(self):
        """Test filtering by weapon type."""
        energy = get_weapons_by_type(WeaponType.TBEAM)
        self.assertGreater(len(energy), 0)
        for w in energy:
            self.assertEqual(w.weapon_type, WeaponType.TBEAM)

    def test_get_weapons_by_type_missile(self):
        """Test filtering missile weapons."""
        missiles = get_weapons_by_type(WeaponType.TMISSILE)
        self.assertGreater(len(missiles), 0)
        for w in missiles:
            self.assertEqual(w.weapon_type, WeaponType.TMISSILE)

    def test_get_weapons_by_class(self):
        """Test filtering by weapon class."""
        ballistic = get_weapons_by_class(WeaponClass.BALLISTIC)
        self.assertGreater(len(ballistic), 0)
        for w in ballistic:
            self.assertEqual(w.weapon_class, WeaponClass.BALLISTIC)

    def test_get_clan_weapons(self):
        """Test filtering Clan weapons."""
        clan = get_clan_weapons()
        self.assertGreater(len(clan), 0)
        for w in clan:
            self.assertTrue(w.is_clan)

    def test_get_is_weapons(self):
        """Test filtering IS weapons."""
        inner_sphere = get_is_weapons()
        self.assertGreater(len(inner_sphere), 0)
        for w in inner_sphere:
            self.assertFalse(w.is_clan)


class TestSpecificWeapons(unittest.TestCase):
    """Test specific weapon definitions match BTMux."""

    def test_is_medium_laser(self):
        """Test IS Medium Laser stats."""
        ml = IS_MEDIUM_LASER
        self.assertEqual(ml.damage, 5)
        self.assertEqual(ml.heat, 3)
        self.assertEqual(ml.vrt, 20)
        self.assertEqual(ml.range_short, 3)
        self.assertEqual(ml.range_medium, 6)
        self.assertEqual(ml.range_long, 9)
        self.assertFalse(ml.uses_ammo)

    def test_is_ac10(self):
        """Test IS AC/10 stats."""
        ac = IS_AC10
        self.assertEqual(ac.damage, 10)
        self.assertEqual(ac.heat, 3)
        self.assertEqual(ac.vrt, 25)
        self.assertEqual(ac.ammo_per_ton, 10)
        self.assertTrue(ac.uses_ammo)
        self.assertEqual(ac.range_short, 5)
        self.assertEqual(ac.range_medium, 10)
        self.assertEqual(ac.range_long, 15)

    def test_is_srm6(self):
        """Test IS SRM-6 stats."""
        srm = IS_SRM6
        self.assertEqual(srm.missiles, 6)
        self.assertEqual(srm.damage_per_missile, 2)
        self.assertEqual(srm.heat, 4)
        self.assertTrue(srm.uses_ammo)
        self.assertEqual(srm.range_short, 3)
        self.assertEqual(srm.range_long, 9)

    def test_is_lrm10(self):
        """Test IS LRM-10 stats."""
        lrm = IS_LRM10
        self.assertEqual(lrm.missiles, 10)
        self.assertEqual(lrm.damage_per_missile, 1)
        self.assertEqual(lrm.heat, 4)
        self.assertEqual(lrm.range_min, 6)  # LRM min range
        self.assertTrue(lrm.special & WeaponFlags.IDF)

    def test_is_ppc(self):
        """Test IS PPC stats."""
        ppc = IS_PPC
        self.assertEqual(ppc.damage, 10)
        self.assertEqual(ppc.heat, 10)
        self.assertEqual(ppc.range_min, 3)
        self.assertEqual(ppc.range_long, 18)

    def test_clan_er_medium_laser(self):
        """Test Clan ER Medium Laser stats."""
        erml = CL_ER_MEDIUM_LASER
        self.assertEqual(erml.damage, 7)  # More than IS
        self.assertEqual(erml.heat, 5)
        self.assertTrue(erml.is_clan)
        self.assertEqual(erml.range_long, 15)  # Extended range

    def test_clan_streak_srm6(self):
        """Test Clan Streak SRM-6."""
        ssrm = CL_STREAK_SRM6
        self.assertTrue(ssrm.special & WeaponFlags.STREAK)
        self.assertTrue(ssrm.is_clan)
        self.assertEqual(ssrm.missiles, 6)


class TestWeaponFlags(unittest.TestCase):
    """Test weapon special flags."""

    def test_pulse_flag(self):
        """Test PULSE flag detection."""
        from entities.weapon import IS_MEDIUM_PULSE_LASER
        self.assertTrue(IS_MEDIUM_PULSE_LASER.special & WeaponFlags.PULSE)
        self.assertFalse(IS_MEDIUM_LASER.special & WeaponFlags.PULSE)

    def test_lbx_flag(self):
        """Test LBX flag."""
        from entities.weapon import CL_LBX10
        self.assertTrue(CL_LBX10.special & WeaponFlags.LBX)

    def test_streak_flag(self):
        """Test STREAK flag."""
        self.assertTrue(CL_STREAK_SRM6.special & WeaponFlags.STREAK)
        self.assertFalse(IS_SRM6.special & WeaponFlags.STREAK)

    def test_idf_flag(self):
        """Test IDF (indirect fire) flag."""
        self.assertTrue(IS_LRM10.special & WeaponFlags.IDF)
        self.assertFalse(IS_MEDIUM_LASER.special & WeaponFlags.IDF)

    def test_gauss_flag(self):
        """Test GAUSS flag."""
        from entities.weapon import IS_GAUSS_RIFLE
        self.assertTrue(IS_GAUSS_RIFLE.special & WeaponFlags.GAUSS)


class TestMissileHitTable(unittest.TestCase):
    """Test missile hit table lookups."""

    def test_table_structure(self):
        """Test table has all 2d6 rolls."""
        for roll in range(2, 13):
            self.assertIn(roll, MISSILE_HIT_TABLE)

    def test_table_has_standard_sizes(self):
        """Test table has standard rack sizes."""
        for roll in range(2, 13):
            self.assertIn(2, MISSILE_HIT_TABLE[roll])
            self.assertIn(6, MISSILE_HIT_TABLE[roll])
            self.assertIn(10, MISSILE_HIT_TABLE[roll])
            self.assertIn(20, MISSILE_HIT_TABLE[roll])

    def test_get_missiles_hit_srm6(self):
        """Test SRM-6 hit counts."""
        # Roll of 2-3: 2 missiles
        self.assertEqual(get_missiles_hit(2, 6), 2)
        self.assertEqual(get_missiles_hit(3, 6), 2)
        # Roll of 7: 4 missiles
        self.assertEqual(get_missiles_hit(7, 6), 4)
        # Roll of 12: all 6
        self.assertEqual(get_missiles_hit(12, 6), 6)

    def test_get_missiles_hit_lrm20(self):
        """Test LRM-20 hit counts."""
        # Roll of 2: 6 missiles
        self.assertEqual(get_missiles_hit(2, 20), 6)
        # Roll of 7: 12 missiles
        self.assertEqual(get_missiles_hit(7, 20), 12)
        # Roll of 12: all 20
        self.assertEqual(get_missiles_hit(12, 20), 20)

    def test_get_missiles_hit_srm2(self):
        """Test SRM-2 hit counts."""
        # Roll of 2-7: 1 missile (from BTMux weapons.h)
        self.assertEqual(get_missiles_hit(2, 2), 1)
        self.assertEqual(get_missiles_hit(6, 2), 1)
        self.assertEqual(get_missiles_hit(7, 2), 1)
        # Roll of 8+: 2 missiles
        self.assertEqual(get_missiles_hit(8, 2), 2)
        self.assertEqual(get_missiles_hit(12, 2), 2)

    def test_get_missiles_hit_clamped(self):
        """Test roll is clamped to valid range."""
        # Rolls outside 2-12 are clamped
        self.assertEqual(get_missiles_hit(1, 6), get_missiles_hit(2, 6))
        self.assertEqual(get_missiles_hit(15, 6), get_missiles_hit(12, 6))


class TestNewISWeapons(unittest.TestCase):
    """Test newly added IS weapon definitions."""

    def test_is_er_large_laser(self):
        """Test IS ER Large Laser stats."""
        from entities.weapon import IS_ER_LARGE_LASER
        self.assertEqual(IS_ER_LARGE_LASER.damage, 8)
        self.assertEqual(IS_ER_LARGE_LASER.heat, 12)
        self.assertEqual(IS_ER_LARGE_LASER.range_long, 19)
        self.assertFalse(IS_ER_LARGE_LASER.is_clan)

    def test_is_lbx10(self):
        """Test IS LB 10-X AC stats."""
        from entities.weapon import IS_LBX10
        self.assertEqual(IS_LBX10.damage, 10)
        self.assertTrue(IS_LBX10.special & WeaponFlags.LBX)
        self.assertTrue(IS_LBX10.uses_ammo)

    def test_is_ultra_ac5(self):
        """Test IS Ultra AC/5 stats."""
        from entities.weapon import IS_ULTRA_AC5
        self.assertEqual(IS_ULTRA_AC5.damage, 5)
        self.assertTrue(IS_ULTRA_AC5.special & WeaponFlags.ULTRA)

    def test_is_rotary_ac2(self):
        """Test IS Rotary AC/2 stats."""
        from entities.weapon import IS_ROTARY_AC2
        self.assertEqual(IS_ROTARY_AC2.damage, 2)
        self.assertTrue(IS_ROTARY_AC2.special & WeaponFlags.RAC)

    def test_is_mrm20(self):
        """Test IS MRM-20 stats."""
        from entities.weapon import IS_MRM20
        self.assertEqual(IS_MRM20.missiles, 20)
        self.assertEqual(IS_MRM20.damage_per_missile, 1)
        self.assertTrue(IS_MRM20.special & WeaponFlags.MRM)

    def test_is_streak_srm4(self):
        """Test IS Streak SRM-4 stats."""
        from entities.weapon import IS_STREAK_SRM4
        self.assertEqual(IS_STREAK_SRM4.missiles, 4)
        self.assertTrue(IS_STREAK_SRM4.special & WeaponFlags.STREAK)

    def test_is_narc_beacon(self):
        """Test IS NARC Beacon stats."""
        from entities.weapon import IS_NARC
        self.assertTrue(IS_NARC.special & WeaponFlags.NARC)
        self.assertTrue(IS_NARC.uses_ammo)

    def test_is_thunderbolt15(self):
        """Test IS Thunderbolt-15 stats."""
        from entities.weapon import IS_THUNDERBOLT15
        self.assertEqual(IS_THUNDERBOLT15.damage, 15)
        self.assertEqual(IS_THUNDERBOLT15.missiles, 1)
        self.assertEqual(IS_THUNDERBOLT15.damage_per_missile, 15)

    def test_is_light_gauss(self):
        """Test IS Light Gauss Rifle."""
        from entities.weapon import IS_LIGHT_GAUSS_RIFLE
        self.assertEqual(IS_LIGHT_GAUSS_RIFLE.damage, 8)
        self.assertTrue(IS_LIGHT_GAUSS_RIFLE.special & WeaponFlags.GAUSS)

    def test_is_heavy_ppc(self):
        """Test IS Heavy PPC."""
        from entities.weapon import IS_HEAVY_PPC
        self.assertEqual(IS_HEAVY_PPC.damage, 15)
        self.assertEqual(IS_HEAVY_PPC.heat, 15)

    def test_is_arrow_iv(self):
        """Test IS Arrow IV System."""
        from entities.weapon import IS_ARROW_IV
        self.assertEqual(IS_ARROW_IV.damage, 20)
        self.assertTrue(IS_ARROW_IV.special & WeaponFlags.DAR)


class TestNewClanWeapons(unittest.TestCase):
    """Test newly added Clan weapon definitions."""

    def test_cl_er_small_laser(self):
        """Test Clan ER Small Laser stats."""
        from entities.weapon import CL_ER_SMALL_LASER
        self.assertEqual(CL_ER_SMALL_LASER.damage, 5)
        self.assertTrue(CL_ER_SMALL_LASER.is_clan)

    def test_cl_heavy_large_laser(self):
        """Test Clan Heavy Large Laser stats."""
        from entities.weapon import CL_HEAVY_LARGE_LASER
        self.assertEqual(CL_HEAVY_LARGE_LASER.damage, 16)
        self.assertTrue(CL_HEAVY_LARGE_LASER.special & WeaponFlags.HVYW)

    def test_cl_lbx20(self):
        """Test Clan LB 20-X AC stats."""
        from entities.weapon import CL_LBX20
        self.assertEqual(CL_LBX20.damage, 20)
        self.assertTrue(CL_LBX20.special & WeaponFlags.LBX)
        self.assertTrue(CL_LBX20.is_clan)

    def test_cl_rotary_ac5(self):
        """Test Clan Rotary AC/5 stats."""
        from entities.weapon import CL_ROTARY_AC5
        self.assertEqual(CL_ROTARY_AC5.damage, 5)
        self.assertTrue(CL_ROTARY_AC5.special & WeaponFlags.RAC)

    def test_cl_atm6(self):
        """Test Clan ATM-6 stats."""
        from entities.weapon import CL_ATM6
        self.assertEqual(CL_ATM6.missiles, 6)
        self.assertEqual(CL_ATM6.damage_per_missile, 2)
        self.assertTrue(CL_ATM6.is_clan)

    def test_cl_streak_lrm10(self):
        """Test Clan Streak LRM-10 stats."""
        from entities.weapon import CL_STREAK_LRM10
        self.assertEqual(CL_STREAK_LRM10.missiles, 10)
        self.assertTrue(CL_STREAK_LRM10.special & WeaponFlags.STREAK)

    def test_cl_machine_gun(self):
        """Test Clan Machine Gun stats."""
        from entities.weapon import CL_MACHINE_GUN
        self.assertEqual(CL_MACHINE_GUN.tonnage, 0.25)  # Lighter than IS
        self.assertTrue(CL_MACHINE_GUN.is_clan)


class TestAdvancedWeaponModes(unittest.TestCase):
    """Test advanced weapon mode functions."""

    def test_is_pulse_weapon(self):
        """Test pulse weapon detection."""
        from entities.weapon import (
            is_pulse_weapon, IS_MEDIUM_PULSE_LASER, IS_MEDIUM_LASER
        )
        self.assertTrue(is_pulse_weapon(IS_MEDIUM_PULSE_LASER))
        self.assertFalse(is_pulse_weapon(IS_MEDIUM_LASER))

    def test_is_ultra_capable(self):
        """Test Ultra AC detection."""
        from entities.weapon import is_ultra_capable, IS_ULTRA_AC5, IS_AC10
        self.assertTrue(is_ultra_capable(IS_ULTRA_AC5))
        self.assertFalse(is_ultra_capable(IS_AC10))

    def test_is_rotary_capable(self):
        """Test Rotary AC detection."""
        from entities.weapon import is_rotary_capable, IS_ROTARY_AC2
        self.assertTrue(is_rotary_capable(IS_ROTARY_AC2))

    def test_is_lbx_capable(self):
        """Test LBX detection."""
        from entities.weapon import is_lbx_capable, IS_LBX10
        self.assertTrue(is_lbx_capable(IS_LBX10))

    def test_is_streak_weapon(self):
        """Test Streak detection."""
        from entities.weapon import is_streak_weapon, CL_STREAK_SRM6, IS_SRM6
        self.assertTrue(is_streak_weapon(CL_STREAK_SRM6))
        self.assertFalse(is_streak_weapon(IS_SRM6))

    def test_is_gauss_weapon(self):
        """Test Gauss detection."""
        from entities.weapon import is_gauss_weapon, IS_GAUSS_RIFLE
        self.assertTrue(is_gauss_weapon(IS_GAUSS_RIFLE))

    def test_pulse_bth_modifier(self):
        """Test pulse BTH modifier."""
        from entities.weapon import (
            get_pulse_bth_modifier, IS_MEDIUM_PULSE_LASER, IS_MEDIUM_LASER
        )
        self.assertEqual(get_pulse_bth_modifier(IS_MEDIUM_PULSE_LASER), -2)
        self.assertEqual(get_pulse_bth_modifier(IS_MEDIUM_LASER), 0)

    def test_mrm_bth_modifier(self):
        """Test MRM BTH modifier."""
        from entities.weapon import get_mrm_bth_modifier, IS_MRM20
        self.assertEqual(get_mrm_bth_modifier(IS_MRM20), 1)

    def test_heavy_weapon_bth_modifier(self):
        """Test heavy weapon BTH modifier."""
        from entities.weapon import (
            get_heavy_weapon_bth_modifier, CL_HEAVY_LARGE_LASER
        )
        self.assertEqual(get_heavy_weapon_bth_modifier(CL_HEAVY_LARGE_LASER), 1)

    def test_lbx_slug_mode(self):
        """Test LBX slug mode."""
        from entities.weapon import get_lbx_fire_mode, IS_LBX10
        result = get_lbx_fire_mode(IS_LBX10, cluster_mode=False)
        self.assertEqual(result.mode, "slug")
        self.assertEqual(result.damage, 10)
        self.assertEqual(result.pellets, 1)

    def test_lbx_cluster_mode(self):
        """Test LBX cluster mode."""
        from entities.weapon import get_lbx_fire_mode, IS_LBX10
        result = get_lbx_fire_mode(IS_LBX10, cluster_mode=True, target_moved=True)
        self.assertEqual(result.mode, "cluster")
        self.assertEqual(result.damage, 1)
        self.assertEqual(result.pellets, 10)
        self.assertEqual(result.bth_modifier, -1)


class TestMissileHitTableExtended(unittest.TestCase):
    """Test extended missile hit table for new weapon sizes."""

    def test_mrm_sizes_in_table(self):
        """Test MRM sizes (30, 40) are in table."""
        self.assertIn(30, MISSILE_HIT_TABLE[7])
        self.assertIn(40, MISSILE_HIT_TABLE[7])

    def test_atm_sizes_in_table(self):
        """Test ATM sizes (3, 9, 12) are in table."""
        self.assertIn(3, MISSILE_HIT_TABLE[7])
        self.assertIn(9, MISSILE_HIT_TABLE[7])
        self.assertIn(12, MISSILE_HIT_TABLE[7])

    def test_get_missiles_hit_mrm40(self):
        """Test MRM-40 hit counts."""
        # Roll of 12: all 40
        self.assertEqual(get_missiles_hit(12, 40), 40)

    def test_get_missiles_hit_atm9(self):
        """Test ATM-9 hit counts."""
        # Roll of 12: all 9
        self.assertEqual(get_missiles_hit(12, 9), 9)


class TestWeaponCatalogExpanded(unittest.TestCase):
    """Test expanded weapon catalog."""

    def test_catalog_has_expanded_weapons(self):
        """Test catalog has significantly more weapons."""
        all_weapons = get_all_weapons()
        self.assertGreater(len(all_weapons), 100)

    def test_all_is_weapons_count(self):
        """Test number of IS weapons."""
        is_weapons = get_is_weapons()
        self.assertGreater(len(is_weapons), 50)

    def test_all_clan_weapons_count(self):
        """Test number of Clan weapons."""
        clan_weapons = get_clan_weapons()
        self.assertGreater(len(clan_weapons), 30)

    def test_missile_weapons_count(self):
        """Test number of missile weapons."""
        missiles = get_weapons_by_type(WeaponType.TMISSILE)
        self.assertGreater(len(missiles), 30)


if __name__ == '__main__':
    unittest.main()
