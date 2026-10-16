"""
Tests for E.4 — aimed shots, targeting-computer modes, and the fire-path
wiring of the missile / ammo-mode modules.

References:
- mech.combat.c:96-125 (mech_target), 1580-1598 / 1671-1805 (dispatch)
- mech.hitloc.c:2977-3147 (FindTCHitLoc / FindAimHitLoc)
- mech.bth.c:161-180, 221-230, 257-267, 284-288, 324-349 (BTH terms)
- mech.damage.c:167-191 (AP crit-through-armor)
- mech.utils.c:1301-1386, 2569-2699 (ammo gof/nogof filters)
- mech.combat.missile.c:231-260, 325-371 (AMS / inferno / NARC routing)
"""

import unittest
from unittest.mock import patch

from core.game_loop import GameEngine
from entities.map import GameMap
from entities.mech import (
    AeroLocation, AmmoMode, CritStatus, FireMode, Location, Mech,
    MechStatus, NUM_SECTIONS, Specials, UnitType, VehicleLocation,
)
from entities.weapon import (
    CL_STREAK_SRM6, IS_AC10, IS_LRM10, IS_MEDIUM_LASER, IS_NARC, IS_SRM6,
    get_weapon,
)
from systems.combat import (
    HitGroup, TARGCOMP_AA, TARGCOMP_LONG, TARGCOMP_MULTI, TARGCOMP_SHORT,
    calculate_bth, find_aim_hit_loc, find_ammo_for_weapon, find_tc_hit_loc,
    fire_weapon, resolve_attack,
)
from systems.damage import ap_crit_slots, check_ap_critical
from systems.missile import (
    AMSDefense, AMSFireResult, INARC_HAYWIRE_ATTACHED,
    INARC_HOMING_ATTACHED, NARC_ATTACHED,
)
from systems.targeting import set_aim


def _pair(target_started=True, target_facing=0):
    """Attacker due north of the target: ad == (0 - facing) % 360."""
    attacker = Mech.create_test_mech(name="Attacker")
    attacker.set_status(MechStatus.STARTED)
    attacker.set_hex_position(50, 45)
    attacker.facing = 0
    target = Mech.create_test_mech(name="Target")
    if target_started:
        target.set_status(MechStatus.STARTED)
    target.set_hex_position(50, 50)
    target.facing = target_facing
    return attacker, target


class TestSetAim(unittest.TestCase):
    """Port of mech_target (mech.combat.c:96-125)."""

    def setUp(self):
        self.engine = GameEngine()
        self.map = GameMap(60, 60)
        self.mech = Mech.create_test_mech(name="Shooter")
        self.other = Mech.create_test_mech(name="Victim")
        for m in (self.mech, self.other):
            m.set_status(MechStatus.STARTED)
            self.map.add_mech(m)

    def test_disable_with_none(self):
        """Test '-' disables aiming, sic double-t (mech.combat.c:108-111)."""
        self.mech.aim = int(Location.RARM)
        ok, msg = set_aim(self.engine, self.mech, None)
        self.assertTrue(ok)
        self.assertEqual(msg, "Targetting disabled.")
        self.assertEqual(self.mech.aim, NUM_SECTIONS)

    def test_disable_works_without_a_lock(self):
        """Test the '-' branch runs before the lock gate (mech.combat.c:108)."""
        self.mech.target = -1
        ok, msg = set_aim(self.engine, self.mech, None)
        self.assertTrue(ok)

    def test_requires_a_mech_lock(self):
        """Test the lock gate message verbatim (mech.combat.c:113-116)."""
        self.mech.target = -1
        ok, msg = set_aim(self.engine, self.mech, Location.RARM)
        self.assertFalse(ok)
        self.assertEqual(msg, "Error: You need to be locked onto something "
                              "to target its part!")
        self.assertEqual(self.mech.aim, NUM_SECTIONS)

    def test_stale_lock_id_fails(self):
        """Test a lock on a unit not on the map fails the getMech probe
        (mech.combat.c:113-116)."""
        self.mech.target = 99999
        ok, msg = set_aim(self.engine, self.mech, Location.RARM)
        self.assertFalse(ok)

    def test_sets_aim_and_aim_type(self):
        """Test aim + aim_type stored, sic "targetted" (mech.combat.c:122-124)."""
        self.mech.target = self.other._id
        ok, msg = set_aim(self.engine, self.mech, Location.RARM)
        self.assertTrue(ok)
        self.assertEqual(self.mech.aim, int(Location.RARM))
        self.assertEqual(self.mech.aim_type, int(UnitType.MECH))
        self.assertTrue(msg.endswith(" targetted."))

    def test_invalid_location(self):
        """Test out-of-range section is invalid (mech.combat.c:117-121)."""
        self.mech.target = self.other._id
        ok, msg = set_aim(self.engine, self.mech, 42)
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid location!")
        ok, msg = set_aim(self.engine, self.mech, "head")
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid location!")


class TestFindAimHitLoc(unittest.TestCase):
    """Port of FindAimHitLoc (mech.hitloc.c:3077-3147)."""

    def _aim(self, aim, facing=0, cover=False, unit_type=None):
        attacker, target = _pair(target_facing=facing)
        attacker.aim = int(aim)
        if cover:
            target.set_status(MechStatus.PARTIAL_COVER)
        if unit_type is not None:
            target.unit_type = unit_type
        return find_aim_hit_loc(attacker, target,
                                punch_roll=3, location_roll=7)

    def test_front_shot_connects_the_aim(self):
        """Test RARM aim connects from FRONT (mech.hitloc.c:3087-3090)."""
        loc, is_rear, is_crit = self._aim(Location.RARM, facing=0)
        self.assertEqual(loc, Location.RARM)
        self.assertFalse(is_rear)
        self.assertFalse(is_crit)

    def test_rarm_masked_on_leftside(self):
        """Test RARM is masked from LEFTSIDE (mech.hitloc.c:3087-3090):
        target facing 120 puts the attacker at ad 240 = LEFTSIDE."""
        loc, is_rear, _ = self._aim(Location.RARM, facing=120)
        # Falls to the normal table: LEFTSIDE roll 7 = LTORSO
        self.assertEqual(loc, Location.LTORSO)

    def test_larm_masked_on_rightside(self):
        """Test LARM masked from RIGHTSIDE (mech.hitloc.c:3091-3093):
        facing 240 -> ad 120 = RIGHTSIDE; roll 7 = RTORSO."""
        loc, _, _ = self._aim(Location.LARM, facing=240)
        self.assertEqual(loc, Location.RTORSO)

    def test_back_shot_sets_is_rear(self):
        """Test BACK hit group flags is_rear (mech.hitloc.c:3083-3084)."""
        loc, is_rear, _ = self._aim(Location.RARM, facing=180)
        self.assertEqual(loc, Location.RARM)   # BACK != LEFTSIDE: connects
        self.assertTrue(is_rear)

    def test_leg_connects_without_cover(self):
        """Test RLEG connects from FRONT sans cover (mech.hitloc.c:3094-3097)."""
        loc, _, _ = self._aim(Location.RLEG, facing=0)
        self.assertEqual(loc, Location.RLEG)

    def test_leg_masked_by_partial_cover(self):
        """Test PARTIAL_COVER masks the legs (mech.hitloc.c:3094-3101) and
        the covered-mech fallback is the punch table (:3143-3144)."""
        loc, _, _ = self._aim(Location.RLEG, facing=0, cover=True)
        # punch_roll 3 on the FRONT punch table = CTORSO
        self.assertEqual(loc, Location.CTORSO)

    def test_ctorso_and_head_always_connect(self):
        """Test CTORSO/HEAD have no side condition (mech.hitloc.c:3108-3111)."""
        for aim in (Location.CTORSO, Location.HEAD):
            for facing in (0, 120, 240, 180):
                loc, _, _ = self._aim(aim, facing=facing)
                self.assertEqual(loc, aim)

    def test_aero_returns_aim_unconditionally(self):
        """Test is_aero targets return MechAim outright (mech.hitloc.c:
        3114-3115), even from the masked side."""
        loc, _, _ = self._aim(AeroLocation.FUSELAGE, facing=0,
                              unit_type=UnitType.AERO)
        self.assertEqual(loc, int(AeroLocation.FUSELAGE))

    def test_vehicle_table(self):
        """Test the vehicle switch (mech.hitloc.c:3117-3141): FSIDE masked
        from BACK, TURRET always connects."""
        loc, _, _ = self._aim(VehicleLocation.FSIDE, facing=0,
                              unit_type=UnitType.VEH_GROUND)
        self.assertEqual(loc, int(VehicleLocation.FSIDE))
        # facing 180 -> ad 180 = BACK: FSIDE masked, falls to the table
        loc, is_rear, _ = self._aim(VehicleLocation.FSIDE, facing=180,
                                    unit_type=UnitType.VEH_GROUND)
        self.assertNotEqual(loc, int(VehicleLocation.FSIDE))
        self.assertTrue(is_rear)
        loc, _, _ = self._aim(VehicleLocation.TURRET, facing=180,
                              unit_type=UnitType.VEH_GROUND)
        self.assertEqual(loc, int(VehicleLocation.TURRET))


class TestFindTCHitLoc(unittest.TestCase):
    """Port of FindTCHitLoc (mech.hitloc.c:2977-3075)."""

    def _tc(self, aim, roll=6, aim_type=None, facing=0, immobile=False,
            unit_type=None, cover=False):
        attacker, target = _pair(target_started=not immobile,
                                 target_facing=facing)
        attacker.aim = int(aim)
        if unit_type is not None:
            target.unit_type = unit_type
        attacker.aim_type = int(target.unit_type) if aim_type is None \
            else aim_type
        if cover:
            target.set_status(MechStatus.PARTIAL_COVER)
        return find_tc_hit_loc(attacker, target, success_roll=roll,
                               punch_roll=3, location_roll=7)

    def test_success_gate_roll(self):
        """Test the Number(1,6) >= 3 gate (mech.hitloc.c:2986)."""
        loc, _, _ = self._tc(Location.RARM, roll=3)
        self.assertEqual(loc, Location.RARM)
        loc, _, _ = self._tc(Location.RARM, roll=2)
        self.assertEqual(loc, Location.CTORSO)   # FRONT roll 7 fallback

    def test_aim_type_must_match(self):
        """Test a stale aim_type skips the whole table (mech.hitloc.c:2986)."""
        loc, _, _ = self._tc(Location.RARM, roll=6,
                             aim_type=int(UnitType.VEH_GROUND))
        self.assertEqual(loc, Location.CTORSO)

    def test_ctorso_side_condition_is_commented_out(self):
        """Test CTORSO connects even from a side arc — the C's condition is
        commented out (mech.hitloc.c:3016-3019)."""
        loc, _, _ = self._tc(Location.CTORSO, roll=6, facing=120)
        self.assertEqual(loc, Location.CTORSO)

    def test_head_only_against_immobile(self):
        """Test HEAD connects only when Immobile (mech.hitloc.c:3020-3022)."""
        loc, _, _ = self._tc(Location.HEAD, roll=6, immobile=True)
        self.assertEqual(loc, Location.HEAD)
        loc, _, _ = self._tc(Location.HEAD, roll=6, immobile=False)
        self.assertEqual(loc, Location.CTORSO)   # fallback

    def test_leg_masked_by_partial_cover(self):
        """Test the legs' PARTIAL_COVER mask (mech.hitloc.c:2996-3005) and
        the covered fallback punch table (:3070-3071)."""
        loc, _, _ = self._tc(Location.LLEG, roll=6, cover=True)
        self.assertEqual(loc, Location.CTORSO)   # punch_roll 3, FRONT

    def test_aero_fall_through_quirk(self):
        """Test the missing-break aero fall-through VERBATIM (mech.hitloc.c:
        3024-3043): a masked AERO_LWING aim (value 1) drops into the
        vehicle switch and resurrects as RSIDE (value 1).

        facing 240 -> ad 120 = RIGHTSIDE for a non-mech target; LWING is
        masked on RIGHTSIDE, but RSIDE only masks on LEFTSIDE."""
        loc, _, _ = self._tc(AeroLocation.LWING, roll=6, facing=240,
                             unit_type=UnitType.AERO)
        self.assertEqual(loc, int(VehicleLocation.RSIDE))

    def test_vehicle_switch(self):
        """Test the TC vehicle arm (mech.hitloc.c:3046-3066)."""
        loc, _, _ = self._tc(VehicleLocation.BSIDE, roll=6, facing=180,
                             unit_type=UnitType.VEH_GROUND)
        self.assertEqual(loc, int(VehicleLocation.BSIDE))  # BACK != FRONT
        loc, _, _ = self._tc(VehicleLocation.BSIDE, roll=6, facing=0,
                             unit_type=UnitType.VEH_GROUND)
        self.assertNotEqual(loc, int(VehicleLocation.BSIDE))


class TestAimDispatch(unittest.TestCase):
    """The resolve_attack dispatch matrix (mech.combat.c:1580-1598,
    1671-1805)."""

    def test_aim_hit_on_678_immobile_only(self):
        """Test aim_hit needs an immobile target and a 6/7/8 fresh roll
        (mech.combat.c:1585-1591)."""
        for roll, expect_aim in ((6, True), (7, True), (8, True),
                                 (5, False), (9, False)):
            attacker, target = _pair(target_started=False)
            attacker.aim = int(Location.RARM)
            result = resolve_attack(attacker, target, IS_MEDIUM_LASER, 3,
                                    to_hit_roll=12, aim_roll=roll,
                                    location_roll=7)
            self.assertTrue(result.hit)
            self.assertEqual(result.location,
                             Location.RARM if expect_aim else Location.CTORSO,
                             f"aim_roll {roll}")

    def test_no_aim_hit_against_mobile_target(self):
        """Test a mobile target never takes the aimed hit
        (mech.combat.c:1588 Immobile gate)."""
        attacker, target = _pair(target_started=True)
        attacker.aim = int(Location.RARM)
        result = resolve_attack(attacker, target, IS_MEDIUM_LASER, 3,
                                to_hit_roll=12, aim_roll=7, location_roll=7)
        self.assertEqual(result.location, Location.CTORSO)

    def test_tc_dispatch(self):
        """Test tUsingTC routes to FindTCHitLoc (mech.combat.c:1580-1584,
        1592-1595)."""
        attacker, target = _pair(target_started=True)
        attacker.aim = int(Location.RARM)
        attacker.aim_type = int(UnitType.MECH)
        result = resolve_attack(attacker, target, IS_MEDIUM_LASER, 3,
                                to_hit_roll=12, tc_roll=6, location_roll=7,
                                w_fire_mode=int(FireMode.ON_TC))
        self.assertEqual(result.location, Location.RARM)

    def test_tc_needs_matching_aim_type(self):
        """Test aim_type mismatch kills tUsingTC (mech.combat.c:1584)."""
        attacker, target = _pair(target_started=True)
        attacker.aim = int(Location.RARM)
        attacker.aim_type = int(UnitType.VEH_GROUND)
        result = resolve_attack(attacker, target, IS_MEDIUM_LASER, 3,
                                to_hit_roll=12, tc_roll=6, location_roll=7,
                                w_fire_mode=int(FireMode.ON_TC))
        self.assertEqual(result.location, Location.CTORSO)

    def test_tc_destroyed_kills_tc_dispatch(self):
        """Test TC_DESTROYED kills tUsingTC (mech.combat.c:1582)."""
        attacker, target = _pair(target_started=True)
        attacker.aim = int(Location.RARM)
        attacker.aim_type = int(UnitType.MECH)
        attacker.set_crit_status(CritStatus.TC_DESTROYED)
        result = resolve_attack(attacker, target, IS_MEDIUM_LASER, 3,
                                to_hit_roll=12, tc_roll=6, location_roll=7,
                                w_fire_mode=int(FireMode.ON_TC))
        self.assertEqual(result.location, Location.CTORSO)

    def test_missiles_never_use_tc(self):
        """Test IsMissile weapons are excluded from tUsingTC
        (mech.combat.c:1580-1581); the salvo lands via the normal table."""
        attacker, target = _pair(target_started=True)
        attacker.aim = int(Location.RARM)
        attacker.aim_type = int(UnitType.MECH)
        result = resolve_attack(attacker, target, IS_SRM6, 3,
                                to_hit_roll=12, tc_roll=6, cluster_roll=7,
                                location_rolls=[7, 7, 7, 7],
                                w_fire_mode=int(FireMode.ON_TC))
        self.assertEqual(result.location, Location.CTORSO)

    def test_multi_hit_missing_else_quirk(self):
        """Test the C's MISSING-ELSE quirk VERBATIM (mech.combat.c:
        1786-1795, Part 1 #13): in the multi-hit slug loop an aim_hit
        without a TC is immediately overwritten by FindTargetHitLoc, so
        aimed shots never steer slugs."""
        attacker, target = _pair(target_started=False)  # immobile
        attacker.aim = int(Location.RARM)
        weapon = get_weapon('IS.UltraAC/5')  # source cluster-table member
        result = resolve_attack(attacker, target, weapon, 3,
                                to_hit_roll=12, aim_roll=7, cluster_roll=12,
                                location_rolls=[7, 7],
                                w_fire_mode=int(FireMode.ULTRA_MODE))
        # 2 slugs, both on the normal table (CTORSO), NOT the aimed RARM
        self.assertEqual(result.location, Location.CTORSO)
        self.assertEqual(result.damage_dealt, 2 * weapon.damage)
        self.assertIn("%cgYou hit with 2 slugs!%c", result.messages)

    def test_single_hit_contrast_to_the_quirk(self):
        """Test the same aim DOES steer a single-hit shot
        (mech.combat.c:1592-1593)."""
        attacker, target = _pair(target_started=False)
        attacker.aim = int(Location.RARM)
        result = resolve_attack(attacker, target, IS_MEDIUM_LASER, 3,
                                to_hit_roll=12, aim_roll=7, location_roll=7)
        self.assertEqual(result.location, Location.RARM)


class TestBTHTerms(unittest.TestCase):
    """The E.4 BTH terms (mech.bth.c:161-180, 221-230, 257-267, 284-288,
    324-349)."""

    def test_head_target_immobile(self):
        """Test HeadTarget +7 vs an immobile mech (mech.bth.c:327-328)."""
        attacker, target = _pair(target_started=False)
        attacker.aim = int(Location.HEAD)
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.aim_mod, 7)

    def test_head_target_mobile_fake(self):
        """Test HeadTarget-Fake +25 vs a mobile target (mech.bth.c:329-330)."""
        attacker, target = _pair(target_started=True)
        attacker.aim = int(Location.HEAD)
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.aim_mod, 25)

    def test_head_target_not_for_missiles(self):
        """Test the head block requires !IsMissile (mech.bth.c:325)."""
        attacker, target = _pair(target_started=False)
        attacker.aim = int(Location.HEAD)
        bth = calculate_bth(attacker, target, IS_SRM6, 3)
        self.assertEqual(bth.aim_mod, 0)

    def test_tc_minus_one(self):
        """Test ON_TC with no aim gives -1 (mech.bth.c:332-338)."""
        attacker, target = _pair()
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3,
                            w_fire_mode=int(FireMode.ON_TC))
        self.assertEqual(bth.aim_mod, -1)

    def test_tc_plus_three_aiming_at_mobile(self):
        """Test aiming a TC at a non-immobile target gives +3
        (mech.bth.c:335-336)."""
        attacker, target = _pair(target_started=True)
        attacker.aim = int(Location.RARM)
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3,
                            w_fire_mode=int(FireMode.ON_TC))
        self.assertEqual(bth.aim_mod, 3)

    def test_tc_term_gone_when_destroyed(self):
        """Test TC_DESTROYED kills the -1 (mech.bth.c:333)."""
        attacker, target = _pair()
        attacker.set_crit_status(CritStatus.TC_DESTROYED)
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3,
                            w_fire_mode=int(FireMode.ON_TC))
        self.assertEqual(bth.aim_mod, 0)

    def test_tc_excluded_under_lbx_mode(self):
        """Test LBX_MODE excludes the TC -1 (mech.bth.c:334)."""
        attacker, target = _pair()
        bth = calculate_bth(attacker, target, get_weapon("IS.LB10-XAC"), 3,
                            w_fire_mode=int(FireMode.ON_TC),
                            w_ammo_mode=int(AmmoMode.LBX_MODE))
        self.assertEqual(bth.aim_mod, 0)
        self.assertEqual(bth.ammo_mode_mod, -1)

    def test_short_bracket(self):
        """Test TARGCOMP_SHORT: -1 inside medium range, +1 beyond
        (mech.bth.c:161-180). ML medium range is 6."""
        attacker, target = _pair()
        attacker.targcomp = TARGCOMP_SHORT
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.targcomp_mod, -1)
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 8)
        self.assertEqual(bth.targcomp_mod, 1)

    def test_long_bracket(self):
        """Test TARGCOMP_LONG: -1 beyond medium range, +1 inside
        (mech.bth.c:170-179)."""
        attacker, target = _pair()
        attacker.targcomp = TARGCOMP_LONG
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 8)
        self.assertEqual(bth.targcomp_mod, -1)
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.targcomp_mod, 1)

    def test_bracket_has_no_tc_alive_check(self):
        """Test the bracket applies with NO ON_TC and a DESTROYED computer —
        the C block never checks either, VERBATIM QUIRK (mech.bth.c:161-180
        has no GetPartFireMode/TC_DESTROYED clause)."""
        attacker, target = _pair()
        attacker.targcomp = TARGCOMP_SHORT
        attacker.set_crit_status(CritStatus.TC_DESTROYED)
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.targcomp_mod, -1)

    def test_aa_vs_jumping(self):
        """Test TARGCOMP_AA vs a jumping target: -2, -3 with AA_TECH
        (mech.bth.c:257-260)."""
        attacker, target = _pair()
        attacker.targcomp = TARGCOMP_AA
        target.set_status(MechStatus.JUMPING)
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.targcomp_mod, -2)
        attacker.specials |= Specials.AA_TECH
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.targcomp_mod, -3)

    def test_aa_vs_ground(self):
        """Test TARGCOMP_AA vs a ground target: +1 (mech.bth.c:261-262)."""
        attacker, target = _pair()
        attacker.targcomp = TARGCOMP_AA
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.targcomp_mod, 1)

    def test_multi_side_arc(self):
        """Test TARGCOMP_MULTI: +1 when the lock point is outside
        FORWARDARC (mech.bth.c:284-288)."""
        engine = GameEngine()
        gamemap = GameMap(60, 60)
        attacker = Mech.create_test_mech(name="Multi")
        attacker.set_status(MechStatus.STARTED)
        attacker.set_hex_position(50, 50)
        attacker.facing = 0
        attacker.targcomp = TARGCOMP_MULTI
        behind = Mech.create_test_mech(name="Behind")
        behind.set_status(MechStatus.STARTED)
        behind.set_hex_position(50, 55)      # due south — rear arc
        for m in (attacker, behind):
            gamemap.add_mech(m)
        attacker.target = behind._id
        bth = calculate_bth(attacker, behind, IS_MEDIUM_LASER, 5)
        self.assertEqual(bth.targcomp_mod, 1)
        # Lock point ahead: no term
        behind.set_hex_position(50, 45)
        bth = calculate_bth(attacker, behind, IS_MEDIUM_LASER, 5)
        self.assertEqual(bth.targcomp_mod, 0)

    def test_armor_piercing_plus_one(self):
        """Test AC_AP_MODE +1 (mech.bth.c:221-222)."""
        attacker, target = _pair()
        bth = calculate_bth(attacker, target, IS_AC10, 3,
                            w_ammo_mode=int(AmmoMode.AC_AP_MODE))
        self.assertEqual(bth.ammo_mode_mod, 1)

    def test_lbx_minus_three_vs_vtol(self):
        """Test LBX -1, -3 vs a VTOL (mech.bth.c:265-267)."""
        attacker, target = _pair()
        lbx = get_weapon("IS.LB10-XAC")
        bth = calculate_bth(attacker, target, lbx, 3,
                            w_ammo_mode=int(AmmoMode.LBX_MODE))
        self.assertEqual(bth.ammo_mode_mod, -1)
        target.unit_type = UnitType.VTOL
        bth = calculate_bth(attacker, target, lbx, 3,
                            w_ammo_mode=int(AmmoMode.LBX_MODE))
        self.assertEqual(bth.ammo_mode_mod, -3)

    def test_precision_floor(self):
        """Test AC_PRECISION_MODE: target-move -2 floored at 0
        (mech.bth.c:347-349)."""
        attacker, target = _pair()
        target.speed = 70.0     # +3
        bth = calculate_bth(attacker, target, IS_AC10, 3,
                            w_ammo_mode=int(AmmoMode.AC_PRECISION_MODE))
        self.assertEqual(bth.target_move, 1)

    def test_precision_floor_wipes_immobile_bonus(self):
        """Test the MAX(0, ...) floor wipes the immobile -4 too — VERBATIM
        QUIRK: precision ammo is worse against an immobile target
        (mech.bth.c:347-349)."""
        attacker, target = _pair(target_started=False)   # immobile: -4
        bth = calculate_bth(attacker, target, IS_AC10, 3)
        self.assertEqual(bth.target_move, -4)
        bth = calculate_bth(attacker, target, IS_AC10, 3,
                            w_ammo_mode=int(AmmoMode.AC_PRECISION_MODE))
        self.assertEqual(bth.target_move, 0)

    def test_haywire_pod_on_attacker(self):
        """Test +1 while the attacker wears a haywire pod
        (mech.bth.c:224-225)."""
        attacker, target = _pair()
        attacker.sections[Location.CTORSO].specials |= \
            INARC_HAYWIRE_ATTACHED
        bth = calculate_bth(attacker, target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.pod_mod, 1)

    def test_homing_pod_minus_one(self):
        """Test -1 firing NARC_MODE missiles at a homing-pod target from a
        non-NARC launcher (mech.bth.c:227-230)."""
        attacker, target = _pair()
        target.sections[Location.CTORSO].specials |= INARC_HOMING_ATTACHED
        bth = calculate_bth(attacker, target, IS_LRM10, 7,
                            w_ammo_mode=int(AmmoMode.NARC_MODE))
        self.assertEqual(bth.pod_mod, -1)
        # The launcher itself being a NARC excludes the term
        bth = calculate_bth(attacker, target, IS_NARC, 3,
                            w_ammo_mode=int(AmmoMode.NARC_MODE))
        self.assertEqual(bth.pod_mod, 0)


class TestTemplateOnTC(unittest.TestCase):
    """The template loader's ON_TC fill (template.c:2174-2181,
    TCAble at template.c:1539-1545)."""

    def _build(self):
        from data.templates import (
            MechTemplate, WeaponMount, create_mech_from_template,
        )
        tmpl = MechTemplate(
            name="TCMech", mech_type="TC-1", targeting_computer=True,
            weapons=[
                WeaponMount("IS.MediumLaser", Location.LARM),
                WeaponMount("IS.AC/10", Location.RTORSO, ammo=10),
                WeaponMount("IS.MachineGun", Location.RARM, ammo=100),
                WeaponMount("IS.SRM-6", Location.LTORSO, ammo=15),
            ])
        return create_mech_from_template(tmpl)

    def _slots_for(self, mech, weapon_name):
        from entities.crittypes import is_weapon, weapon2i
        from entities.weapon import get_weapon_by_index
        out = []
        for section in mech.sections:
            for crit in section.criticals:
                if not is_weapon(crit.type):
                    continue
                w = get_weapon_by_index(weapon2i(crit.type))
                if w is not None and w.name == weapon_name:
                    out.append(crit)
        return out

    def test_tc_crit_placed(self):
        """Test a TARGETING_COMPUTER crit lands (template.c:2174; TODO ceil
        sizing noted in _place_targeting_computer)."""
        from entities.crittypes import Special, i2special
        mech = self._build()
        tc_type = i2special(Special.TARGETING_COMPUTER)
        found = any(crit.type == tc_type
                    for section in mech.sections
                    for crit in section.criticals)
        self.assertTrue(found)

    def test_tcable_weapons_get_on_tc(self):
        """Test energy + ballistic weapons get ON_TC on every crit slot
        (template.c:2176-2181)."""
        mech = self._build()
        for name in ("IS.MediumLaser", "IS.AC/10"):
            for crit in self._slots_for(mech, name):
                self.assertTrue(crit.firemode & FireMode.ON_TC, name)

    def test_excluded_weapons_stay_clean(self):
        """Test MachineGun (TCAble name exclusion, template.c:1541-1544)
        and SRM (TMISSILE) never get ON_TC."""
        mech = self._build()
        for name in ("IS.MachineGun", "IS.SRM-6"):
            slots = self._slots_for(mech, name)
            self.assertTrue(slots, name)
            for crit in slots:
                self.assertFalse(crit.firemode & FireMode.ON_TC, name)

    def test_no_tc_by_default(self):
        """Test a plain template mounts nothing and flags nothing."""
        from data.templates import get_template, create_mech_from_template
        from entities.crittypes import Special, i2special
        mech = create_mech_from_template(get_template("TestMech"))
        tc_type = i2special(Special.TARGETING_COMPUTER)
        for section in mech.sections:
            for crit in section.criticals:
                self.assertNotEqual(crit.type, tc_type)
                self.assertFalse(crit.firemode & FireMode.ON_TC)


class TestMissileWiring(unittest.TestCase):
    """The fire-path delegation to systems.missile
    (mech.combat.missile.c:191-371, mech.combat.h:17)."""

    def test_srm_rolls_a_location_per_missile(self):
        """Test SRMs (damage 2) have Clustersize 1 — one location per
        missile (mech.combat.h:17; mech.combat.missile.c:100-117)."""
        attacker, target = _pair()
        result = resolve_attack(attacker, target, IS_SRM6, 3,
                                to_hit_roll=12, cluster_roll=7,
                                location_rolls=[7, 7, 7, 7])
        # Row 7 on rack 6 = 4 missiles x 2 damage
        self.assertEqual(result.damage_dealt, 8)
        self.assertIn("%cgYou hit with 4 missiles!%c", result.messages)
        self.assertEqual(target.sections[Location.CTORSO].armor, 16 - 8)

    def test_lrm_clusters_in_fives(self):
        """Test LRMs (damage 1, IDF) have Clustersize 5 (mech.combat.h:17):
        6 hitting missiles land as a 5-group and a 1-group."""
        attacker, target = _pair()
        result = resolve_attack(attacker, target, IS_LRM10, 7,
                                to_hit_roll=12, cluster_roll=7,
                                location_rolls=[7, 12])
        # Row 7 on rack 10 = 6 missiles: 5 to CT, 1 to HEAD
        self.assertEqual(result.damage_dealt, 6)
        self.assertEqual(target.sections[Location.CTORSO].armor, 16 - 5)
        self.assertEqual(target.sections[Location.HEAD].armor, 9 - 1)

    def test_streak_all_or_nothing(self):
        """Test Streak launchers land the full rack regardless of the
        cluster roll (mech.combat.missile.c:169-172)."""
        attacker, target = _pair()
        result = resolve_attack(attacker, target, CL_STREAK_SRM6, 3,
                                to_hit_roll=12, cluster_roll=2,
                                location_rolls=[7] * 6)
        self.assertEqual(result.damage_dealt, 12)

    def test_ams_applied_after_cluster_roll(self):
        """Test AMS kills subtract from the cluster-rolled hit count, not
        the rack (mech.combat.missile.c:337-358): 4 cluster hits - 3 shot
        down = 1, not 6 - 3 = 3."""
        attacker, target = _pair()
        defense = AMSDefense(weapon=IS_MEDIUM_LASER, section=0, critical=0,
                             ammo_section=0, ammo_critical=0)
        with patch('systems.missile.locate_ams_defenses',
                   return_value=defense), \
                patch('systems.missile.ams_missiles',
                      return_value=AMSFireResult(shot_down=3)) as ams:
            result = resolve_attack(attacker, target, IS_SRM6, 3,
                                    to_hit_roll=12, cluster_roll=7,
                                    location_rolls=[7])
        self.assertTrue(ams.called)
        # missiles_did_hit threading (mech.combat.missile.c:239)
        self.assertTrue(ams.call_args[0][7])
        self.assertEqual(result.damage_dealt, 2)     # 1 missile x 2
        self.assertIn("The target shoots down 3 of your missiles!",
                      result.messages)

    def test_fired_missile_miss_skips_ams(self):
        """HitTarget rejects the fired miss before AMS (mech.combat.c:1730-1734)."""
        attacker, target = _pair()
        defense = AMSDefense(weapon=IS_MEDIUM_LASER, section=0, critical=0,
                             ammo_section=0, ammo_critical=0)
        with patch('systems.missile.locate_ams_defenses',
                   return_value=defense), \
                patch('systems.missile.ams_missiles',
                      return_value=AMSFireResult(shot_down=0)) as ams:
            result = resolve_attack(attacker, target, IS_SRM6, 3,
                                    to_hit_roll=2)
        self.assertFalse(result.hit)
        ams.assert_not_called()
        self.assertEqual(result.damage_dealt, 0)
        self.assertFalse(any("Anti-Missile System activates" in text for text in result.messages))

    def test_inferno_routes_to_jelly_not_damage(self):
        """Test INFERNO_MODE salvos call Inferno_Hit instead of doing
        damage (mech.combat.missile.c:362-364)."""
        engine = GameEngine()
        attacker, target = _pair()
        armor_before = target.sections[Location.CTORSO].armor
        result = resolve_attack(attacker, target, IS_SRM6, 3,
                                to_hit_roll=12, cluster_roll=7,
                                w_ammo_mode=int(AmmoMode.INFERNO_MODE),
                                engine=engine)
        self.assertTrue(result.hit)
        self.assertEqual(result.damage_dealt, 0)
        self.assertEqual(target.sections[Location.CTORSO].armor,
                         armor_before)
        self.assertTrue(target.has_crit_status(CritStatus.JELLIED))

    def test_narc_pod_attaches(self):
        """Test NARC launchers route to narc_attach
        (mech.combat.missile.c:242-300)."""
        attacker, target = _pair()
        result = resolve_attack(attacker, target, IS_NARC, 3,
                                to_hit_roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertEqual(result.damage_dealt, 0)
        tagged = any(section.specials & NARC_ATTACHED
                     for section in target.sections)
        self.assertTrue(tagged)

    def test_fired_narc_miss_skips_pod_handling(self):
        """The firing caller returns before NARC's direct-helper miss notice."""
        attacker, target = _pair()
        result = resolve_attack(attacker, target, IS_NARC, 3, to_hit_roll=2)
        self.assertFalse(result.hit)
        tagged = any(section.specials & NARC_ATTACHED
                     for section in target.sections)
        self.assertFalse(tagged)
        self.assertEqual(result.damage_dealt, 0)
        self.assertFalse(any("flies off" in m for m in result.messages))
        self.assertTrue(any(text.startswith("Attack missed") for text in result.messages))


class TestLBXAndAmmoModes(unittest.TestCase):
    """LBX pellets and the gof/nogof ammo filters."""

    def test_lbx_pellet_path(self):
        """Test LBX_MODE fires cluster pellets of 1 damage with "pellet"
        wording (mech.combat.c:1760-1772)."""
        attacker, target = _pair()
        lbx = get_weapon("IS.LB10-XAC")
        result = resolve_attack(attacker, target, lbx, 6, to_hit_roll=12,
                                cluster_roll=7, location_rolls=[7] * 6,
                                w_ammo_mode=int(AmmoMode.LBX_MODE))
        # Row 7 on rack 10 = 6 pellets x 1 damage
        self.assertEqual(result.damage_dealt, 6)
        self.assertIn("%cgYou hit with 6 pellets!%c", result.messages)

    def test_out_of_special_ammo_message(self):
        """Test firing a special mode with no matching bin gives the
        special-ammo message (mech.utils.c:2673-2676)."""
        from data.templates import get_template, create_mech_from_template
        attacker = create_mech_from_template(get_template("TestMech"))
        attacker.set_status(MechStatus.STARTED)
        attacker.set_hex_position(50, 45)
        target = Mech.create_test_mech(name="Target")
        target.set_status(MechStatus.STARTED)
        target.set_hex_position(50, 50)

        ws = attacker.weapons[2]     # the AC/10
        slot = attacker.sections[ws.section].criticals[ws.critical]
        slot.ammomode = int(AmmoMode.AC_AP_MODE)

        result = fire_weapon(attacker, target, 2, 3.0, to_hit_roll=10)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["You don't have any ammo for that weapon stored on this mech!"])

        # Flip the bin into the same mode: the weapon fires again
        found = find_ammo_for_weapon(attacker, ws.weapon_idx, ws.section,
                                     nogof=0, gof=0)
        self.assertIsNotNone(found)
        ammo_loc, ammo_crit = found
        attacker.sections[ammo_loc].criticals[ammo_crit].ammomode = \
            int(AmmoMode.AC_AP_MODE)
        result = fire_weapon(attacker, target, 2, 3.0, to_hit_roll=12,
                             location_roll=7)
        self.assertTrue(result.hit)

    def test_out_of_ammo_message(self):
        """Test the plain out-of-ammo message when mod == 0
        (mech.utils.c:2652-2654)."""
        from data.templates import get_template, create_mech_from_template
        attacker = create_mech_from_template(get_template("TestMech"))
        attacker.set_status(MechStatus.STARTED)
        target = Mech.create_test_mech(name="Target")

        ws = attacker.weapons[2]     # the AC/10
        found = find_ammo_for_weapon(attacker, ws.weapon_idx, ws.section)
        self.assertIsNotNone(found)
        ammo_loc, ammo_crit = found
        attacker.sections[ammo_loc].criticals[ammo_crit].data = 0

        result = fire_weapon(attacker, target, 2, 3.0, to_hit_roll=10)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["You don't have any ammo for that weapon stored on this mech!"])

    def test_normal_fire_skips_special_bins(self):
        """Test a mode-0 shot may not draw from a special-mode bin —
        nogof = AMMO_MODES (mech.utils.c:2649-2651, 1308-1312)."""
        from data.templates import get_template, create_mech_from_template
        attacker = create_mech_from_template(get_template("TestMech"))
        attacker.set_status(MechStatus.STARTED)
        target = Mech.create_test_mech(name="Target")

        ws = attacker.weapons[2]
        found = find_ammo_for_weapon(attacker, ws.weapon_idx, ws.section)
        ammo_loc, ammo_crit = found
        attacker.sections[ammo_loc].criticals[ammo_crit].ammomode = \
            int(AmmoMode.LBX_MODE)

        result = fire_weapon(attacker, target, 2, 3.0, to_hit_roll=10)
        self.assertFalse(result.hit)
        self.assertEqual(result.messages,
                         ["You don't have any ammo for that weapon stored on this mech!"])


class TestAPCritThroughArmor(unittest.TestCase):
    """AP ammo crit-through-armor (mech.damage.c:167-191)."""

    def test_weapon_size_penalties(self):
        """Test each AC size penalty on a rolled 12 (mech.damage.c:
        176-190): AC/2 -4 -> 8 -> 1 crit; AC/5 -3 -> 9 -> 1; AC/10 -2 ->
        10 -> 2; AC/20 -1 -> 11 -> 2; anything else -10 -> 2 -> 0."""
        self.assertEqual(ap_crit_slots(get_weapon("IS.AC/2"), roll=12), 1)
        self.assertEqual(ap_crit_slots(get_weapon("IS.AC/5"), roll=12), 1)
        self.assertEqual(ap_crit_slots(get_weapon("IS.AC/10"), roll=12), 2)
        self.assertEqual(ap_crit_slots(get_weapon("IS.AC/20"), roll=12), 2)
        self.assertEqual(ap_crit_slots(IS_MEDIUM_LASER, roll=12), 0)

    def test_bracket_bounds(self):
        """Test the through-armor crit brackets under the penalty
        (mech.damage.c:171-191 into the standard table)."""
        ac20 = get_weapon("IS.AC/20")
        self.assertEqual(ap_crit_slots(ac20, roll=8), 0)     # 7
        self.assertEqual(ap_crit_slots(ac20, roll=9), 1)     # 8
        self.assertEqual(ap_crit_slots(ac20, roll=11), 2)    # 10

    def test_gate(self):
        """Test the tAPCritical gate (mech.damage.c:167-169): AP mode, no
        internal damage, no location crit, remaining armor < 50%."""
        target = Mech.create_test_mech()
        ct = target.sections[Location.CTORSO]
        ap = int(AmmoMode.AC_AP_MODE)
        ac10 = get_weapon("IS.AC/10")

        ct.armor = 4        # 4/16 = 25% < 50
        self.assertEqual(
            check_ap_critical(target, Location.CTORSO, ac10, ap,
                              False, 0, roll=12), 2)
        # >= 50% armor left: no crit
        ct.armor = 8
        self.assertEqual(
            check_ap_critical(target, Location.CTORSO, ac10, ap,
                              False, 0, roll=12), 0)
        ct.armor = 4
        # Internal damage this hit: the normal through-armor path owns it
        self.assertEqual(
            check_ap_critical(target, Location.CTORSO, ac10, ap,
                              False, 3, roll=12), 0)
        # Already a table critical: no double dip
        self.assertEqual(
            check_ap_critical(target, Location.CTORSO, ac10, ap,
                              True, 0, roll=12), 0)
        # Not in AP mode
        self.assertEqual(
            check_ap_critical(target, Location.CTORSO, ac10, 0,
                              False, 0, roll=12), 0)

    def test_wired_into_resolve_attack(self):
        """Test the AP arm fires from the damage path with the ammo mode
        threaded through (mech.damage.c:167-191)."""
        attacker, target = _pair()
        target.sections[Location.CTORSO].armor = 14   # 10 dmg -> 4/16 = 25%
        from systems.criticals import CriticalResult
        with patch('systems.damage.ap_crit_slots', return_value=2), \
                patch('systems.combat.check_for_critical',
                      return_value=(2, [CriticalResult(), CriticalResult()])) as cfc:
            result = resolve_attack(attacker, target, IS_AC10, 3,
                                    to_hit_roll=12, location_roll=7,
                                    w_ammo_mode=int(AmmoMode.AC_AP_MODE))
        self.assertTrue(result.hit)
        self.assertEqual(result.internal_damage, 0)
        cfc.assert_called_once_with(target, Location.CTORSO, 2, attacker, engine=None, los=1)
        self.assertEqual(result.criticals_rolled, 2)


if __name__ == '__main__':
    unittest.main()
