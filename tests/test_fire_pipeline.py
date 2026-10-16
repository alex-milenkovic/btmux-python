"""
Tests for the weapon fire pipeline (heat + ammo + recycle).

Tests cover:
- fire_weapon post-fire state: weapon heat, recycle countdown, ammo decrement,
  FIRED status - hit or miss (mech.combat.c:1280, 1352-1401)
- The recycle gate ("still reloading", mech.utils.c:1186-1190) and refire once
  the crit data byte is cleared
- Out-of-ammo gate (mech.utils.c:2648) and energy weapons needing no bin
- find_ammo_for_weapon search order (mech.utils.c:1323-1386): desired bin
  location first, then the weapon's own section, then everywhere else

Reference:
- BTMux btech/src/btech/mech.combat.c - FireWeapon / FireWeaponNumber
- BTMux btech/src/btech/mech.utils.c lines 1300-1386 - ammo search
- BTMux btech/src/include/btconfig.h line 136 - WEAPON_TICK = 2
"""

import unittest

from data.templates import get_template, create_mech_from_template
from entities.crittypes import i2ammo
from entities.mech import FireMode, Location, MechStatus, SectionConfig
from entities.weapon import get_weapon_by_index
from systems.combat import (
    WEAPON_TICK,
    find_ammo_for_weapon,
    find_ammo_in_section,
    fire_weapon,
)


def make_attacker_and_target():
    """Build a started TestMech attacker facing a started AssaultMech target.

    TestMech weapon numbers: 0-1 = Medium Lasers (LARM, energy),
    2 = AC/10 (RTORSO, 10 rounds in an RTORSO bin).

    Positions put the attacker due north of the target with the target facing
    north, so the attack direction is FRONT and a location roll of 7 lands on
    center torso armor - no internal damage, no criticals, no extra dice.
    """
    attacker = create_mech_from_template(get_template("TestMech"), name="Attacker")
    attacker.set_status(MechStatus.STARTED)
    attacker.set_hex_position(50, 50)
    attacker.facing = 180

    target = create_mech_from_template(get_template("AssaultMech"), name="Target")
    target.set_status(MechStatus.STARTED)
    target.set_hex_position(50, 53)
    target.facing = 0

    return attacker, target


# Deterministic dice for a guaranteed armor-only hit: 12 always beats the BTH
# at short range and location 7 is center torso on every hit table.
SURE_HIT = dict(to_hit_roll=12, location_roll=7)
SURE_MISS = dict(to_hit_roll=2, location_roll=7)

ML_NUM = 0     # TestMech weapon 0: IS.MediumLaser (energy)
AC10_NUM = 2   # TestMech weapon 2: IS.AC/10 (ammo-using)


class TestFireHeat(unittest.TestCase):
    """Weapon heat after firing (mech.combat.c:1379)."""

    def setUp(self):
        self.attacker, self.target = make_attacker_and_target()

    def test_fire_adds_weapon_heat(self):
        """Test a hit adds the weapon's heat to weap_heat."""
        ml = get_weapon_by_index(self.attacker.weapons[ML_NUM].weapon_idx)
        result = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertTrue(result.hit)
        self.assertEqual(self.attacker.weap_heat, float(ml.heat))

    def test_miss_still_adds_weapon_heat(self):
        """Test heat applies hit or miss - the C tail runs either way."""
        ml = get_weapon_by_index(self.attacker.weapons[ML_NUM].weapon_idx)
        result = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_MISS)
        self.assertFalse(result.hit)
        self.assertEqual(self.attacker.weap_heat, float(ml.heat))

    def test_fired_status_set(self):
        """Test firing sets MechStatus.FIRED (mech.combat.c:1280)."""
        self.assertFalse(self.attacker.has_status(MechStatus.FIRED))
        fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertTrue(self.attacker.has_status(MechStatus.FIRED))


class TestFireRecycle(unittest.TestCase):
    """Recycle countdown and the reloading gate."""

    def setUp(self):
        self.attacker, self.target = make_attacker_and_target()
        self.ws = self.attacker.weapons[ML_NUM]
        self.slot = self.attacker.sections[self.ws.section].criticals[self.ws.critical]

    def test_recycle_is_weapon_tick_times_vrt(self):
        """Test the crit data byte gets WEAPON_TICK * vrt (mech.combat.c:1353-1354)."""
        ml = get_weapon_by_index(self.ws.weapon_idx)
        self.assertEqual(self.slot.data, 0)
        fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertEqual(self.slot.data, WEAPON_TICK * ml.vrt)
        # The parallel WeaponState mirror is kept in step
        self.assertEqual(self.ws.recycle, WEAPON_TICK * ml.vrt)

    def test_second_fire_blocked_while_recycling(self):
        """Test an immediate second shot fails the recycle gate."""
        ml = get_weapon_by_index(self.ws.weapon_idx)
        first = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertTrue(first.hit)

        second = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertFalse(second.hit)
        self.assertIn("still reloading", second.messages[0])
        # The failed shot added no heat
        self.assertEqual(self.attacker.weap_heat, float(ml.heat))

    def test_zeroing_crit_data_allows_refire(self):
        """Test clearing the crit data byte (what mech_update does) re-arms it."""
        ml = get_weapon_by_index(self.ws.weapon_idx)
        fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.slot.data = 0

        result = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertTrue(result.hit)
        self.assertEqual(self.attacker.weap_heat, 2.0 * ml.heat)


class TestFireAmmo(unittest.TestCase):
    """Ammo consumption and the out-of-ammo gate."""

    def setUp(self):
        self.attacker, self.target = make_attacker_and_target()
        self.ws = self.attacker.weapons[AC10_NUM]

    def _drain_all_bins(self):
        """Zero every ammo bin for the AC/10 across all sections."""
        ammo_type = i2ammo(self.ws.weapon_idx)
        for section in self.attacker.sections:
            for crit in section.criticals:
                if crit.type == ammo_type:
                    crit.data = 0

    def test_fire_decrements_ammo_bin(self):
        """Test one round comes out of the bin (mech.combat.c:1400-1401)."""
        loc, slot_idx = find_ammo_for_weapon(
            self.attacker, self.ws.weapon_idx, self.ws.section, critical=self.ws.critical)
        bin_slot = self.attacker.sections[loc].criticals[slot_idx]
        self.assertEqual(bin_slot.data, 10)  # TestMech template loadout

        result = fire_weapon(self.attacker, self.target, AC10_NUM, 5.0, **SURE_HIT)
        self.assertTrue(result.hit)
        self.assertEqual(bin_slot.data, 9)
        # The WeaponState mirror records which bin fed the shot
        self.assertEqual(self.ws.ammo_section, int(loc))
        self.assertEqual(self.ws.ammo_critical, slot_idx)

    def test_out_of_ammo_blocks_fire(self):
        """Test an empty gun refuses to fire and pays no costs."""
        self._drain_all_bins()
        result = fire_weapon(self.attacker, self.target, AC10_NUM, 5.0, **SURE_HIT)
        self.assertFalse(result.hit)
        self.assertEqual("You don't have any ammo for that weapon stored on this mech!", result.messages[0])
        self.assertEqual(self.attacker.weap_heat, 0.0)
        self.assertFalse(self.attacker.has_status(MechStatus.FIRED))
        slot = self.attacker.sections[self.ws.section].criticals[self.ws.critical]
        self.assertEqual(slot.data, 0)  # no recycle started

    def test_energy_weapon_needs_no_bin(self):
        """Test an energy weapon fires with no ammo bin anywhere."""
        ml_ws = self.attacker.weapons[ML_NUM]
        ml = get_weapon_by_index(ml_ws.weapon_idx)
        self.assertFalse(ml.uses_ammo)
        # No ML ammo exists on the template; the shot must not be gated
        result = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertTrue(result.hit)


class TestFireGates(unittest.TestCase):
    """The pre-fire validation gates."""

    def setUp(self):
        self.attacker, self.target = make_attacker_and_target()
        self.ws = self.attacker.weapons[ML_NUM]

    def test_not_started_blocks_fire(self):
        """Test a shut-down mech cannot fire (cch(MECH_USUALO), mech.combat.c:352)."""
        self.attacker.clear_status(MechStatus.STARTED)
        result = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertFalse(result.hit)
        self.assertIn("Reactor is not online", result.messages[0])

    def test_destroyed_weapon_crit_blocks_fire(self):
        """Test a nonfunctional weapon crit fails (mech.utils.c:1182-1185)."""
        slot = self.attacker.sections[self.ws.section].criticals[self.ws.critical]
        slot.firemode |= FireMode.DESTROYED_MODE
        result = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertFalse(result.hit)
        self.assertIn("destroyed", result.messages[0])

    def test_destroyed_section_blocks_fire(self):
        """Test a weapon in a destroyed section fails (mech.combat.c:509-510)."""
        self.attacker.sections[self.ws.section].armor=0
        self.attacker.sections[self.ws.section].internal=0
        result = fire_weapon(self.attacker, self.target, ML_NUM, 3.0, **SURE_HIT)
        self.assertFalse(result.hit)
        self.assertIn("destroyed", result.messages[0])


class TestFindAmmoForWeapon(unittest.TestCase):
    """The FindAmmoForWeapon_sub search order (mech.utils.c:1323-1386)."""

    def setUp(self):
        self.attacker, _ = make_attacker_and_target()
        self.ws = self.attacker.weapons[AC10_NUM]
        self.ammo_type = i2ammo(self.ws.weapon_idx)
        # The template puts one 10-round bin in the AC/10's own section (RTORSO)
        self.own_loc, self.own_slot = find_ammo_for_weapon(
            self.attacker, self.ws.weapon_idx, self.ws.section, critical=self.ws.critical)

    def _add_bin(self, location: Location, rounds: int) -> int:
        """Drop an AC/10 bin into the first empty crit slot of a section."""
        for i, crit in enumerate(self.attacker.sections[location].criticals):
            if crit.type == 0:
                crit.type = self.ammo_type
                crit.data = rounds
                return i
        raise AssertionError(f"no free crit slot in {location.name}")

    def test_own_section_bin_found(self):
        """Test the template bin in the weapon's own section is found."""
        self.assertEqual(self.own_loc, Location(self.ws.section))
        bin_slot = self.attacker.sections[self.own_loc].criticals[self.own_slot]
        self.assertEqual(bin_slot.data, 10)

    def test_bin_in_other_section_found(self):
        """Test the hunt over other sections (mech.utils.c:1372-1384)."""
        # Drain the local bin, feed from the left torso instead
        self.attacker.sections[self.own_loc].criticals[self.own_slot].data = 0
        other_slot = self._add_bin(Location.LTORSO, 5)

        found = find_ammo_for_weapon(
            self.attacker, self.ws.weapon_idx, self.ws.section, critical=self.ws.critical)
        self.assertEqual(found, (Location.LTORSO, other_slot))

    def test_desired_ammo_loc_honored_first(self):
        """Test desired_ammo_loc wins over the weapon's own section
        (mech.utils.c:1338-1360)."""
        other_slot = self._add_bin(Location.LTORSO, 5)
        # Point the weapon's first crit slot at the left torso bin
        weap_crit = self.attacker.sections[self.ws.section].criticals[self.ws.critical]
        weap_crit.desired_ammo_loc = int(Location.LTORSO)

        found = find_ammo_for_weapon(
            self.attacker, self.ws.weapon_idx, self.ws.section, critical=self.ws.critical)
        self.assertEqual(found, (Location.LTORSO, other_slot))

    def test_empty_desired_loc_falls_back_to_own_section(self):
        """Test an empty desired bin falls through to the normal search."""
        weap_crit = self.attacker.sections[self.ws.section].criticals[self.ws.critical]
        weap_crit.desired_ammo_loc = int(Location.LTORSO)  # no bin there

        found = find_ammo_for_weapon(
            self.attacker, self.ws.weapon_idx, self.ws.section, critical=self.ws.critical)
        self.assertEqual(found, (self.own_loc, self.own_slot))

    def test_no_ammo_anywhere_returns_none(self):
        """Test the search returns None when every bin is dry."""
        self.attacker.sections[self.own_loc].criticals[self.own_slot].data = 0
        found = find_ammo_for_weapon(
            self.attacker, self.ws.weapon_idx, self.ws.section, critical=self.ws.critical)
        self.assertIsNone(found)

    def test_nonfunctional_bin_skipped(self):
        """Test a destroyed bin is skipped (PartIsNonfunctional, btmacros.h:324)."""
        bin_slot = self.attacker.sections[self.own_loc].criticals[self.own_slot]
        bin_slot.firemode |= FireMode.DESTROYED_MODE
        self.assertEqual(
            find_ammo_in_section(self.attacker, self.own_loc, self.ammo_type), -1)
        self.assertIsNone(find_ammo_for_weapon(
            self.attacker, self.ws.weapon_idx, self.ws.section, critical=self.ws.critical))


if __name__ == '__main__':
    unittest.main()
