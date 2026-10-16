"""
Tests for systems/weapon_modes.py: the mode-toggle command family,
FindArtemisForWeapon, mech_ams, and the gof/nogof filter derivation.
"""

import unittest
from unittest.mock import patch

from entities.crittypes import Special, i2special, i2weapon
from entities.mech import (
    AmmoMode,
    CriticalSlot,
    FireMode,
    Location,
    Mech,
    MechStatus,
    Specials,
    UnitType,
    VehicleLocation,
    WeaponState,
)
from entities.weapon import Weapon, WeaponFlags, WeaponType, get_weapon
from systems.weapon_modes import (
    WEAPNUM_DESTROYED,
    WEAPNUM_ILLEGAL,
    WEAPNUM_RECHARGING,
    WEAPNUM_RELOADING,
    ammo_mode_filters,
    find_artemis_for_weapon,
    find_weapon_number_on_mech,
    mech_ams,
    mech_armorpiercing,
    mech_artemis,
    mech_atmexplosive,
    mech_atmrange,
    mech_caseless,
    mech_cluster,
    mech_explosive,
    mech_flamerheat,
    mech_flechette,
    mech_gattling,
    mech_hotload,
    mech_inarc_ammo,
    mech_incendiary,
    mech_inferno,
    mech_lbx,
    mech_mine,
    mech_narc,
    mech_precision,
    mech_rac,
    mech_rapidfire,
    mech_sguided,
    mech_smoke,
    mech_stinger,
    mech_swarm,
    mech_swarm1,
    mech_ultra,
    toggle_mode,
)


def make_mech_with(weapon_name: str, section: int = Location.LTORSO,
                   critical: int = 0):
    """A started test mech with one weapon as weapon #0."""
    mech = Mech.create_test_mech()
    mech.set_status(MechStatus.STARTED)
    weapon = get_weapon(weapon_name)
    slot = mech.sections[section].criticals[critical]
    for part in mech.sections[section].criticals[critical:critical + weapon.crits]:
        part.type = i2weapon(weapon.index)
    slot.data = 0
    slot.firemode = FireMode.NONE
    slot.ammomode = 0
    mech.weapons.append(WeaponState(
        section=int(section), critical=critical, weapon_idx=weapon.index))
    return mech, weapon, slot


class TestWeaponNumberGates(unittest.TestCase):
    """Gate order and messages (mech.advanced.c:257-284)."""

    def test_illegal_weapon_number(self):
        mech, _, _ = make_mech_with("IS.LRM-20")
        result = mech_lbx(mech, 3)
        self.assertEqual(result.messages, [
            "The weapons system chirps: 'Illegal Weapon Number!'"])
        self.assertFalse(result.success)

    def test_destroyed_weapon(self):
        mech, _, slot = make_mech_with("IS.LRM-20")
        slot.firemode |= FireMode.DESTROYED_MODE
        result = mech_swarm(mech, 0)
        self.assertEqual(result.messages, [
            "The weapons system chirps: 'That Weapon has been destroyed!'"])

    def test_reloading_weapon(self):
        mech, _, slot = make_mech_with("IS.LRM-20")
        slot.data = 4
        result = mech_swarm(mech, 0)
        self.assertEqual(result.messages, [
            "The weapon system chirps: 'That weapon is still reloading!'"])

    def test_recharging_energy_weapon(self):
        mech, _, slot = make_mech_with("IS.MediumLaser")
        slot.data = 4
        result = mech_hotload(mech, 0)
        self.assertEqual(result.messages, [
            "The weapon system chirps: 'That weapon is still recharging!'"])

    def test_destroyed_beats_reloading(self):
        """Resolution codes run in the C's order."""
        mech, _, slot = make_mech_with("IS.LRM-20")
        slot.firemode |= FireMode.DESTROYED_MODE
        slot.data = 4
        result = mech_swarm(mech, 0)
        self.assertIn("destroyed", result.messages[0])

    def test_one_shot_refusal(self):
        mech, _, slot = make_mech_with("IS.LRM-20")
        slot.firemode |= FireMode.OS_MODE
        result = mech_hotload(mech, 0)
        self.assertEqual(result.messages,
                         ["One-shot weapons' mode cannot be altered!"])

    def test_rocket_refusal(self):
        """ROCKET-flagged weapons refuse all mode changes (:283-284)."""
        mech, _, _ = make_mech_with("IS.SRM-6")
        rocket = Weapon(name="TEST.RocketLauncher",
                        weapon_type=WeaponType.TMISSILE,
                        special=WeaponFlags.ROCKET)
        with patch('systems.weapon_modes.get_weapon_by_index',
                   return_value=rocket):
            result = mech_inferno(mech, 0)
        self.assertEqual(result.messages,
                         ["Rocket launchers' mode cannot be altered!"])

    def test_find_weapon_number_codes(self):
        mech, weapon, slot = make_mech_with("IS.LRM-20")
        self.assertEqual(find_weapon_number_on_mech(mech, 0)[0],
                         weapon.index)
        self.assertEqual(find_weapon_number_on_mech(mech, -1)[0],
                         WEAPNUM_ILLEGAL)
        self.assertEqual(find_weapon_number_on_mech(mech, 1)[0],
                         WEAPNUM_ILLEGAL)
        slot.data = 3
        self.assertEqual(find_weapon_number_on_mech(mech, 0)[0],
                         WEAPNUM_RELOADING)
        slot.data = 0
        slot.firemode |= FireMode.DESTROYED_MODE
        self.assertEqual(find_weapon_number_on_mech(mech, 0)[0],
                         WEAPNUM_DESTROYED)

    def test_find_weapon_number_recharging_is_energy_only(self):
        mech, _, slot = make_mech_with("IS.MediumLaser")
        slot.data = 3
        self.assertEqual(find_weapon_number_on_mech(mech, 0)[0],
                         WEAPNUM_RECHARGING)


class TestArtemisLinkage(unittest.TestCase):
    """FindArtemisForWeapon + the nspecisspec == 6 gate."""

    def _link_artemis(self, mech, art_section, weapon_critical,
                      art_slot=11):
        crit = mech.sections[art_section].criticals[art_slot]
        crit.type = i2special(Special.ARTEMIS_IV)
        crit.data = weapon_critical + 1
        return crit

    def test_artemis_gate_without_system(self):
        mech, _, _ = make_mech_with("IS.LRM-20")
        result = mech_artemis(mech, 0)
        self.assertEqual(result.messages, [
            "You do not have an Artemis system for that weapon."])

    def test_artemis_toggle_with_linked_system(self):
        mech, _, slot = make_mech_with("IS.LRM-20", Location.LTORSO, 0)
        self._link_artemis(mech, Location.LTORSO, 0)
        result = mech_artemis(mech, 0)
        self.assertTrue(result.success)
        self.assertEqual(slot.ammomode, int(AmmoMode.ARTEMIS_MODE))
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire Artemis IV compatible "
            "missiles."])
        # Toggle back off
        result = mech_artemis(mech, 0)
        self.assertEqual(slot.ammomode, 0)
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire normal missiles"])

    def test_artemis_link_requires_matching_data(self):
        """The Artemis crit's data must equal first_crit + 1."""
        mech, _, _ = make_mech_with("IS.LRM-20", Location.LTORSO, 0)
        crit = self._link_artemis(mech, Location.LTORSO, 0)
        crit.data = 5    # linked to some other slot
        self.assertFalse(
            find_artemis_for_weapon(mech, Location.LTORSO, 0))

    def test_artemis_link_ignores_nonfunctional(self):
        mech, _, _ = make_mech_with("IS.LRM-20", Location.LTORSO, 0)
        crit = self._link_artemis(mech, Location.LTORSO, 0)
        crit.firemode = FireMode.DESTROYED_MODE
        self.assertFalse(
            find_artemis_for_weapon(mech, Location.LTORSO, 0))

    def test_ct_launcher_served_from_head(self):
        """Mech CT launcher: search the head (mech.utils.c:1431-1437)."""
        mech, _, _ = make_mech_with("IS.LRM-20", Location.CTORSO, 0)
        self._link_artemis(mech, Location.HEAD, 0, art_slot=2)
        self.assertTrue(
            find_artemis_for_weapon(mech, Location.CTORSO, 0))

    def test_head_fallback_scans_first_six_slots_only(self):
        mech, _, _ = make_mech_with("IS.LRM-20", Location.CTORSO, 0)
        self._link_artemis(mech, Location.HEAD, 0, art_slot=7)
        self.assertFalse(
            find_artemis_for_weapon(mech, Location.CTORSO, 0))

    def test_head_fallback_is_mech_only(self):
        mech, _, _ = make_mech_with("IS.LRM-20", Location.CTORSO, 0)
        self._link_artemis(mech, Location.HEAD, 0, art_slot=2)
        mech.unit_type = UnitType.VEH_GROUND
        self.assertFalse(
            find_artemis_for_weapon(mech, Location.CTORSO, 0))

    def test_turret_launcher_served_from_bside(self):
        """Vehicle turret launcher: search BSIDE (mech.utils.c:1438-1444)."""
        mech, _, _ = make_mech_with("IS.LRM-20", VehicleLocation.TURRET, 0)
        mech.unit_type = UnitType.VEH_GROUND
        self._link_artemis(mech, VehicleLocation.BSIDE, 0, art_slot=2)
        self.assertTrue(
            find_artemis_for_weapon(mech, VehicleLocation.TURRET, 0))


class TestCapabilityDispatch(unittest.TestCase):
    """The nspecisspec dispatch (mech.advanced.c:287-300)."""

    def test_lbx_on_lbx_ac(self):
        mech, _, slot = make_mech_with("IS.LB10-XAC")
        result = mech_lbx(mech, 0)
        self.assertTrue(result.success)
        self.assertEqual(slot.ammomode, int(AmmoMode.LBX_MODE))
        self.assertEqual(result.messages,
                         ["Weapon 0 has been set to LBX fire mode"])

    def test_lbx_on_non_lbx(self):
        mech, _, _ = make_mech_with("IS.LRM-20")
        result = mech_lbx(mech, 0)
        self.assertEqual(result.messages,
                         ["That weapon cannot be set LBX!"])

    def test_inferno_on_srm(self):
        """nspecisspec 4: short-range missile toggle."""
        mech, _, slot = make_mech_with("IS.SRM-6")
        result = mech_inferno(mech, 0)
        self.assertTrue(result.success)
        self.assertEqual(slot.ammomode, int(AmmoMode.INFERNO_MODE))

    def test_inferno_on_lrm_idf_dar_quirk(self):
        """The literal `.type & (IDF|DAR)` test is always 0, so the
        nspecisspec 4 arm matches EVERY missile - LRMs included
        (mech.advanced.c:291-292, verbatim quirk)."""
        mech, _, slot = make_mech_with("IS.LRM-20")
        result = mech_inferno(mech, 0)
        self.assertTrue(result.success)
        self.assertEqual(slot.ammomode, int(AmmoMode.INFERNO_MODE))

    def test_inferno_on_non_missile(self):
        mech, _, _ = make_mech_with("IS.AC/5")
        result = mech_inferno(mech, 0)
        self.assertEqual(result.messages, [
            "That weapon cannot be set to fire Inferno missiles!"])

    def test_swarm_on_lrm(self):
        """nspecisspec 2: IDF-and-not-DAR weapons (LRM class)."""
        mech, _, slot = make_mech_with("IS.LRM-20")
        result = mech_swarm(mech, 0)
        self.assertTrue(result.success)
        self.assertEqual(slot.ammomode, int(AmmoMode.SWARM_MODE))

    def test_swarm_on_srm_refused(self):
        mech, _, _ = make_mech_with("IS.SRM-6")
        result = mech_swarm(mech, 0)
        self.assertEqual(result.messages, [
            "That weapon cannot be set to fire Swarm missiles!"])

    def test_narc_on_plain_missile(self):
        """nspecisspec 0: type match, non-NARC weapons only."""
        mech, _, slot = make_mech_with("IS.SRM-6")
        result = mech_narc(mech, 0)
        self.assertTrue(result.success)
        self.assertEqual(slot.ammomode, int(AmmoMode.NARC_MODE))

    def test_narc_on_narc_launcher_refused(self):
        mech, _, _ = make_mech_with("IS.NarcBeacon")
        result = mech_narc(mech, 0)
        self.assertEqual(result.messages,
                         ["That weapon cannot be set NARC!"])

    def test_flamerheat(self):
        mech, _, slot = make_mech_with("IS.Flamer")
        result = mech_flamerheat(mech, 0)
        self.assertTrue(slot.firemode & FireMode.HEAT_MODE)
        self.assertEqual(result.messages,
                         ["Weapon 0 has been set to HEAT mode"])
        mech2, _, _ = make_mech_with("IS.MediumLaser")
        result = mech_flamerheat(mech2, 0)
        self.assertEqual(result.messages,
                         ["That weapon cannot be set HEAT!"])

    def test_ultra(self):
        mech, _, slot = make_mech_with("IS.UltraAC/5")
        result = mech_ultra(mech, 0)
        self.assertTrue(slot.firemode & FireMode.ULTRA_MODE)
        self.assertTrue(result.success)

    def test_gattling(self):
        mech, _, slot = make_mech_with("IS.MachineGun")
        result = mech_gattling(mech, 0)
        self.assertTrue(slot.firemode & FireMode.GATTLING_MODE)

    def test_rfac_ammo_family_bits(self):
        """Each RFAC ammo command sets its own AC_* bit."""
        cases = [
            (mech_armorpiercing, AmmoMode.AC_AP_MODE),
            (mech_flechette, AmmoMode.AC_FLECHETTE_MODE),
            (mech_incendiary, AmmoMode.AC_INCENDIARY_MODE),
            (mech_precision, AmmoMode.AC_PRECISION_MODE),
            (mech_caseless, AmmoMode.AC_CASELESS_MODE),
        ]
        for command, mode in cases:
            mech, _, slot = make_mech_with("IS.AC/5")
            result = command(mech, 0)
            self.assertTrue(result.success, command.__name__)
            self.assertEqual(slot.ammomode, int(mode), command.__name__)

    def test_rapidfire(self):
        mech, _, slot = make_mech_with("IS.AC/5")
        result = mech_rapidfire(mech, 0)
        self.assertTrue(slot.firemode & FireMode.RFAC_MODE)

    def test_missile_special_ammo_bits(self):
        """Missile-class ammo commands set their bits on an LRM."""
        cases = [
            (mech_stinger, AmmoMode.STINGER_MODE),
            (mech_swarm1, AmmoMode.SWARM1_MODE),
            (mech_sguided, AmmoMode.SGUIDED_MODE),
            (mech_atmrange, AmmoMode.ATM_ER_MODE),
            (mech_atmexplosive, AmmoMode.ATM_HE_MODE),
            (mech_smoke, AmmoMode.SMOKE_MODE),
            (mech_mine, AmmoMode.MINE_MODE),
        ]
        for command, mode in cases:
            mech, _, slot = make_mech_with("IS.LRM-20")
            result = command(mech, 0)
            self.assertTrue(result.success, command.__name__)
            self.assertEqual(slot.ammomode, int(mode), command.__name__)

    def test_hotload_toggle(self):
        mech, _, slot = make_mech_with("IS.LRM-20")
        result = mech_hotload(mech, 0)
        self.assertTrue(slot.firemode & FireMode.HOTLOAD_MODE)
        self.assertEqual(result.messages, [
            "Hotloading for weapon 0 has been toggled on."])
        result = mech_hotload(mech, 0)
        self.assertFalse(slot.firemode & FireMode.HOTLOAD_MODE)
        self.assertEqual(result.messages, [
            "Hotloading for weapon 0 has been toggled off."])

    def test_explosive_toggles_narc_launcher(self):
        mech, _, slot = make_mech_with("IS.NarcBeacon")
        result = mech_explosive(mech, 0)
        self.assertEqual(slot.ammomode, int(AmmoMode.NARC_MODE))
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire explosive rounds"])
        result = mech_explosive(mech, 0)
        self.assertEqual(slot.ammomode, 0)
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire NARC beacons"])


class TestToggleSemantics(unittest.TestCase):
    """Clear-group-then-set, already-set, quirks (mech.advanced.c:301-357)."""

    def test_clear_group_then_set(self):
        """A new ammo mode clears the whole AMMO_MODES word first."""
        mech, _, slot = make_mech_with("IS.LRM-20")
        mech_swarm(mech, 0)
        self.assertEqual(slot.ammomode, int(AmmoMode.SWARM_MODE))
        mech_inferno(mech, 0)
        self.assertEqual(slot.ammomode, int(AmmoMode.INFERNO_MODE))

    def test_already_set_clears_with_offmsg(self):
        mech, _, slot = make_mech_with("IS.LB10-XAC")
        mech_lbx(mech, 0)
        result = mech_lbx(mech, 0)
        self.assertEqual(slot.ammomode, 0)
        self.assertEqual(result.messages,
                         ["Weapon 0 has been set to normal fire mode"])

    def test_artillery_already_special_guard(self):
        """Artillery set to one special round refuses another (:301-305)."""
        mech, _, slot = make_mech_with("IS.LongTom")
        slot.ammomode = int(AmmoMode.SMOKE_MODE)
        result = mech_cluster(mech, 0)
        self.assertEqual(result.messages, [
            "That weapon has already been set to fire special rounds!"])
        self.assertEqual(slot.ammomode, int(AmmoMode.SMOKE_MODE))

    def test_artillery_guard_allows_same_mode_off(self):
        """The guard exempts the already-set mode itself, which then
        toggles off normally."""
        mech, _, slot = make_mech_with("IS.LongTom")
        mech_cluster(mech, 0)
        self.assertEqual(slot.ammomode, int(AmmoMode.CLUSTER_MODE))
        result = mech_cluster(mech, 0)
        self.assertEqual(slot.ammomode, 0)
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire normal rounds"])

    def test_rac_rate_select_and_group_clear(self):
        mech, _, slot = make_mech_with("IS.RotaryAC/5")
        result = mech_rac(mech, 0, '2')
        self.assertTrue(slot.firemode & FireMode.RAC_TWOSHOT_MODE)
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire two shots at a time."])
        # Switching rates clears the group first
        mech_rac(mech, 0, '4')
        self.assertEqual(slot.firemode & FireMode.RAC_MODES,
                         FireMode.RAC_FOURSHOT_MODE)
        # Rate 1 = group-clear arm (:306-313)
        result = mech_rac(mech, 0, '1')
        self.assertEqual(slot.firemode & FireMode.FIRE_MODES,
                         FireMode.NONE)
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire one shot at a time."])
        result = mech_rac(mech, 0, '1')
        self.assertEqual(result.messages, [
            "Weapon 0 is already set to fire one shot at a time."])

    def test_rac_keep_current_quirk(self):
        """Re-selecting the current RAC rate KEEPS it set (Fitz quirk,
        mech.advanced.c:326-330)."""
        mech, _, slot = make_mech_with("IS.RotaryAC/5")
        mech_rac(mech, 0, '2')
        result = mech_rac(mech, 0, '2')
        self.assertTrue(slot.firemode & FireMode.RAC_TWOSHOT_MODE)
        self.assertEqual(result.messages, [
            "Weapon 0 is already set to fire two shots at a time."])

    def test_rac_cant_suppressed(self):
        """A capability miss stays silent for RAC (mech.advanced.c:355)."""
        mech, _, _ = make_mech_with("IS.LRM-20")
        result = mech_rac(mech, 0, '2')
        self.assertEqual(result.messages, [])
        self.assertFalse(result.success)

    def test_inarc_pod_select_and_keep_current(self):
        mech, _, slot = make_mech_with("IS.iNarcBeacon")
        result = mech_inarc_ammo(mech, 0, 'X')
        self.assertEqual(slot.ammomode, int(AmmoMode.INARC_EXPLO_MODE))
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire INARC Explosive pods"])
        # Re-selecting the current pod keeps it (Fitz quirk, :334-338)
        result = mech_inarc_ammo(mech, 0, 'X')
        self.assertEqual(slot.ammomode, int(AmmoMode.INARC_EXPLO_MODE))
        self.assertEqual(result.messages, [
            "Weapon 0 is already set to fire INARC Explosive pods"])

    def test_inarc_homing_group_clear(self):
        """Homing (mode 0) clears the ammo word (:314-322)."""
        mech, _, slot = make_mech_with("IS.iNarcBeacon")
        mech_inarc_ammo(mech, 0, 'Y')
        self.assertEqual(slot.ammomode, int(AmmoMode.INARC_HAYWIRE_MODE))
        result = mech_inarc_ammo(mech, 0, 'H')
        self.assertEqual(slot.ammomode, 0)
        self.assertEqual(result.messages, [
            "Weapon 0 has been set to fire INARC Homing pods"])
        result = mech_inarc_ammo(mech, 0, 'H')
        self.assertEqual(result.messages, [
            "Weapon 0 is already set to fire INARC Homing pods"])

    def test_no_bin_check_no_desired_ammo_loc_change(self):
        """The toggle flips the mode word only: no ammo-bin existence
        check, no desired_ammo_loc change."""
        mech, _, slot = make_mech_with("IS.LB10-XAC")
        self.assertEqual(slot.desired_ammo_loc, -1)
        result = mech_lbx(mech, 0)      # no LBX ammo anywhere on the mech
        self.assertTrue(result.success)
        self.assertEqual(slot.desired_ammo_loc, -1)


class TestMechAms(unittest.TestCase):
    """mech_ams (mech.advanced.c:207-218)."""

    def test_no_ams_tech(self):
        mech = Mech.create_test_mech()
        result = mech_ams(mech)
        self.assertEqual(result.messages,
                         ["This mech is not equipped with AMS"])
        self.assertFalse(mech.has_status(MechStatus.AMS_ENABLED))

    def test_toggle_on_off(self):
        mech = Mech.create_test_mech()
        mech.specials |= Specials.CL_ANTI_MISSILE_TECH
        result = mech_ams(mech)
        self.assertEqual(result.messages,
                         ["Anti-Missile System turned ON"])
        self.assertTrue(mech.has_status(MechStatus.AMS_ENABLED))
        result = mech_ams(mech)
        self.assertEqual(result.messages,
                         ["Anti-Missile System turned OFF"])
        self.assertFalse(mech.has_status(MechStatus.AMS_ENABLED))


class TestAmmoModeFilters(unittest.TestCase):
    """(nogof, gof) derivation per FindAndCheckAmmo
    (mech.utils.c:2647-2676)."""

    def test_no_special_mode(self):
        slot = CriticalSlot()
        self.assertEqual(ammo_mode_filters(slot),
                         (int(AmmoMode.AMMO_MODES), 0))

    def test_special_mode(self):
        slot = CriticalSlot(ammomode=int(AmmoMode.LBX_MODE))
        nogof, gof = ammo_mode_filters(slot)
        self.assertEqual(gof, int(AmmoMode.LBX_MODE))
        self.assertEqual(nogof,
                         int(AmmoMode.AMMO_MODES & ~AmmoMode.LBX_MODE))

    def test_artillery_nogof_uses_artillery_modes(self):
        slot = CriticalSlot(ammomode=int(AmmoMode.CLUSTER_MODE))
        longtom = get_weapon("IS.LongTom")
        nogof, gof = ammo_mode_filters(slot, longtom)
        self.assertEqual(gof, int(AmmoMode.CLUSTER_MODE))
        self.assertEqual(
            nogof,
            int(AmmoMode.ARTILLERY_MODES & ~AmmoMode.CLUSTER_MODE))


if __name__ == '__main__':
    unittest.main()
