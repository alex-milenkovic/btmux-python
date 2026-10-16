"""
Tests for the combat module.

Tests cover:
- Dice rolling
- BTH calculation
- Hit location determination
- Damage application
- Critical hits
- Attack resolution
- Weapon recycle tracking
"""

import unittest
import random
from unittest.mock import patch
from entities.mech import (
    Mech, MechStatus, Location, CritStatus, MoveType, UnitType,
)
from entities.weapon import (
    IS_MEDIUM_LASER, IS_AC10, IS_SRM6, IS_LRM10, IS_PPC,
    CL_STREAK_SRM6, WeaponFlags,
)
from systems.combat import (
    # Dice
    roll_1d6, roll_2d6, roll_dice,
    # BTH
    calculate_bth,
    calculate_overheat_modifier,
    calculate_attacker_movement_modifier,
    calculate_target_movement_modifier,
    calculate_weapon_bth_modifier,
    is_target_immobile,
    BTHBreakdown,
    DEFAULT_GUNNERY,
    MP1, MP2, MP4, MP6, MP9,
    BTECH_EXTENDEDMOVEMOD,
    # Hit location
    HitGroup,
    determine_hit_group,
    find_attack_direction,
    get_hit_arc_half_widths,
    get_hit_location,
    get_punch_location,
    get_kick_location,
    MECH_HIT_LOCATIONS,
    TRANSFER_LOCATIONS,
    # Damage
    apply_damage_to_location,
    apply_damage_with_transfer,
    # Criticals
    check_for_critical,
    roll_critical_hits,
    # Attack
    resolve_attack,
    AttackResult,
    can_attack,
    estimate_hit_chance,
    # Weapon recycle (legacy shim - WeaponSlot goes away in a later workstream;
    # weapon_recycle_periodic was dead code replaced by the fire pipeline in
    # systems/combat.py and is no longer imported)
    WeaponSlot,
)


class TestDiceRolling(unittest.TestCase):
    """Test dice rolling functions."""

    def test_roll_1d6_range(self):
        """Test 1d6 rolls are in range 1-6."""
        for _ in range(100):
            roll = roll_1d6()
            self.assertGreaterEqual(roll, 1)
            self.assertLessEqual(roll, 6)

    def test_roll_2d6_range(self):
        """Test 2d6 rolls are in range 2-12."""
        for _ in range(100):
            roll = roll_2d6()
            self.assertGreaterEqual(roll, 2)
            self.assertLessEqual(roll, 12)

    def test_roll_dice_custom(self):
        """Test rolling custom dice."""
        # Roll 3d6
        for _ in range(50):
            roll = roll_dice(3, 6)
            self.assertGreaterEqual(roll, 3)
            self.assertLessEqual(roll, 18)


class TestOverheatModifier(unittest.TestCase):
    """Test heat-based BTH modifier."""

    def test_no_modifier_low_heat(self):
        """Test no modifier below heat 8."""
        self.assertEqual(calculate_overheat_modifier(0), 0)
        self.assertEqual(calculate_overheat_modifier(5), 0)
        self.assertEqual(calculate_overheat_modifier(7), 0)

    def test_plus_one_moderate_heat(self):
        """Test +1 modifier at heat 8-12."""
        self.assertEqual(calculate_overheat_modifier(8), 1)
        self.assertEqual(calculate_overheat_modifier(10), 1)
        self.assertEqual(calculate_overheat_modifier(12), 1)

    def test_plus_two_high_heat(self):
        """Test +2 modifier at heat 13-16."""
        self.assertEqual(calculate_overheat_modifier(13), 2)
        self.assertEqual(calculate_overheat_modifier(16), 2)

    def test_plus_three_very_high_heat(self):
        """Test +3 modifier at heat 17-23."""
        self.assertEqual(calculate_overheat_modifier(17), 3)
        self.assertEqual(calculate_overheat_modifier(23), 3)

    def test_plus_four_extreme_heat(self):
        """Test +4 modifier at heat 24+."""
        self.assertEqual(calculate_overheat_modifier(24), 4)
        self.assertEqual(calculate_overheat_modifier(30), 4)


class TestAttackerMovementModifier(unittest.TestCase):
    """Test attacker movement BTH modifier."""

    def test_stationary_no_modifier(self):
        """Test stationary mech has no modifier."""
        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.speed = 0
        self.assertEqual(calculate_attacker_movement_modifier(mech), 0)

    def test_walking_plus_one(self):
        """Test walking mech has +1 modifier."""
        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.speed = 20.0  # Walking
        self.assertEqual(calculate_attacker_movement_modifier(mech), 1)

    def test_running_plus_two(self):
        """Test running mech has +2 modifier."""
        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED)
        mech.speed = 60.0  # Running (above walking speed of ~43)
        self.assertEqual(calculate_attacker_movement_modifier(mech), 2)

    def test_jumping_plus_three(self):
        """Test jumping mech has +3 modifier."""
        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED | MechStatus.JUMPING)
        self.assertEqual(calculate_attacker_movement_modifier(mech), 3)

    def test_fallen_plus_two(self):
        """Test fallen mech has +2 modifier."""
        mech = Mech.create_test_mech()
        mech.set_status(MechStatus.STARTED | MechStatus.FALLEN)
        self.assertEqual(calculate_attacker_movement_modifier(mech), 2)


class TestTargetMovementModifier(unittest.TestCase):
    """
    Test target movement BTH modifier.

    Reference: mech.bth.c:721-796 TargetMovementMods(). The C cascade
    (mech.bth.c:764-782) compares the target's float KPH against MP2/MP4/MP6/MP9
    (mech.h:55-60) with contiguous <= tests; the pre-A6 port bracketed integer
    hex counts and so returned +0 for every speed in the gaps.

    All targets here are STARTED: Immobile() is `!Started(a) || ...`
    (btmacros.h:481) with no speed condition, so an unstarted target would take
    the -4 immobile bonus (mech.bth.c:785-786) on top of its speed modifier.
    """

    def _target(self, speed: float = 0.0) -> Mech:
        target = Mech.create_test_mech()
        target.set_status(MechStatus.STARTED)
        target.speed = speed
        return target

    def test_stationary_target(self):
        """Test stationary target (started but not moving) has +0 modifier."""
        self.assertEqual(calculate_target_movement_modifier(self._target(0), 5), 0)

    def test_mp2_boundary_is_inclusive(self):
        """Test exactly MP2 KPH is still +0 (mech.bth.c:764 - `<= MP2`)."""
        self.assertEqual(calculate_target_movement_modifier(self._target(MP2), 5), 0)

    def test_30_kph_target(self):
        """Test 30 KPH target has +1 (mech.bth.c:767 - 30 <= MP4 43.00).

        The old integer-hex bracket table scored 30 KPH (2.79 MP) as +0.
        """
        self.assertEqual(calculate_target_movement_modifier(self._target(30.0), 5), 1)

    def test_mp4_boundary_is_inclusive(self):
        """Test exactly MP4 KPH is +1 (mech.bth.c:767 - `<= MP4`)."""
        self.assertEqual(calculate_target_movement_modifier(self._target(MP4), 5), 1)

    def test_50_kph_target(self):
        """Test 50 KPH target has +2 (mech.bth.c:770 - 50 <= MP6 64.50)."""
        self.assertEqual(calculate_target_movement_modifier(self._target(50.0), 5), 2)

    def test_70_kph_target(self):
        """Test 70 KPH target has +3 (mech.bth.c:773 - 70 <= MP9 96.75)."""
        self.assertEqual(calculate_target_movement_modifier(self._target(70.0), 5), 3)

    def test_100_kph_target(self):
        """
        Test 100 KPH target has +3 at the C's default config.

        mech.bth.c:778-779 - above MP9 with mudconf.btech_extendedmovemod set
        (its shipped default is 1, src/conf.c:132) the modifier is
        `4 + (target_speed - 10 * MP1) / MP4` truncated to int, i.e.
        4 + (100 - 107.5)/43 = 3.826 -> 3. Speeds just past MP9 therefore score
        *below* the flat +4 cap; that oddity is the C's.
        """
        self.assertEqual(calculate_target_movement_modifier(self._target(100.0), 5), 3)

    def test_100_kph_target_without_extended_move_mod(self):
        """Test the flat +4 cap when btech_extendedmovemod is 0 (mech.bth.c:781)."""
        with patch('systems.combat.BTECH_EXTENDEDMOVEMOD', 0):
            self.assertEqual(
                calculate_target_movement_modifier(self._target(100.0), 5), 4)
            self.assertEqual(
                calculate_target_movement_modifier(self._target(200.0), 5), 4)

    def test_extended_move_mod_is_the_c_default(self):
        """Test the port ships the C's default (src/conf.c:132 - `= 1`)."""
        self.assertEqual(BTECH_EXTENDEDMOVEMOD, 1)

    def test_negative_speed_uses_magnitude(self):
        """Test reversing target is rated on |speed| (mech.bth.c:746 - fabs)."""
        self.assertEqual(calculate_target_movement_modifier(self._target(-70.0), 5), 3)

    def test_extended_move_mod_truncates_like_c(self):
        """
        Test btech_extendedmovemod uses the C's float->int truncation.

        mech.bth.c:779 - `returnValue = 4 + (target_speed - 10 * MP1) / MP4;`
        assigns a float to an int, so 100 KPH gives 4 + (100 - 107.5)/43 =
        3.826 -> 3, and 200 KPH gives 4 + 92.5/43 = 6.15 -> 6.
        """
        with patch('systems.combat.BTECH_EXTENDEDMOVEMOD', 1):
            self.assertEqual(
                calculate_target_movement_modifier(self._target(100.0), 5), 3)
            self.assertEqual(
                calculate_target_movement_modifier(self._target(200.0), 5), 6)

    def test_immobile_target_bonus(self):
        """Test unstarted target is Immobile: -4 (btmacros.h:481)."""
        target = Mech.create_test_mech()
        target.speed = 30.0  # +1 from the cascade
        self.assertFalse(target.is_started)
        self.assertEqual(calculate_target_movement_modifier(target, 5), 1 - 4)

    def test_unconscious_pilot_is_immobile(self):
        """Test unconscious pilot makes the target Immobile (btmacros.h:481)."""
        target = self._target(0)
        target.set_status(MechStatus.UNCONSCIOUS)
        self.assertTrue(is_target_immobile(target))
        self.assertEqual(calculate_target_movement_modifier(target, 5), -4)

    def test_move_none_is_immobile(self):
        """Test MechMove == MOVE_NONE is Immobile (btmacros.h:481, mech.h:741)."""
        target = self._target(0)
        target.move_type = MoveType.NONE
        self.assertTrue(is_target_immobile(target))
        self.assertEqual(calculate_target_movement_modifier(target, 5), -4)

    def test_blinded_target_is_immobile(self):
        """Test Blinded target is Immobile (btmacros.h:481, mech.h:1083)."""
        target = self._target(0)
        target.set_status(MechStatus.BLINDED)
        self.assertTrue(is_target_immobile(target))

    def test_fallen_mech_is_not_immobile(self):
        """
        Test a fallen mech is not Immobile.

        btmacros.h:481 only counts FALLEN as immobilising for units that are
        neither CLASS_MECH nor CLASS_MW.
        """
        target = self._target(0)
        target.set_status(MechStatus.FALLEN)
        self.assertFalse(is_target_immobile(target))

    def test_destroyed_is_not_a_clause_of_the_macro(self):
        """
        Test DESTROYED alone does not make a target Immobile.

        btmacros.h:481 has no Destroyed(a) term even though Destroyed is defined
        at btmacros.h:476, and it needs none: Destroy() (btmacros.h:531-543)
        calls Shutdown(), which clears STARTED (btmacros.h:512-514), before
        setting DESTROYED - so in the C a wreck is Immobile via !Started. A
        target flagged DESTROYED while still STARTED is a state the C cannot
        reach, and the macro gives it no -4.
        """
        target = self._target(30.0)  # +1 from the cascade
        target.set_status(MechStatus.DESTROYED)
        self.assertFalse(is_target_immobile(target))
        self.assertEqual(calculate_target_movement_modifier(target, 5), 1)

        # Shut it down as the C's Destroy() does, and the -4 comes back.
        target.clear_status(MechStatus.STARTED)
        self.assertTrue(is_target_immobile(target))
        self.assertEqual(calculate_target_movement_modifier(target, 5), 1 - 4)

    def test_fallen_target_close(self):
        """Test fallen target at close range has -2 (mech.bth.c:788-790)."""
        target = self._target(0)
        target.set_status(MechStatus.FALLEN)
        self.assertEqual(calculate_target_movement_modifier(target, 1), -2)

    def test_fallen_target_far(self):
        """Test fallen target at range >1 has +1 (mech.bth.c:790)."""
        target = self._target(0)
        target.set_status(MechStatus.FALLEN)
        self.assertEqual(calculate_target_movement_modifier(target, 5), 1)

    def test_jumping_target(self):
        """Test jumping target has +1 (mech.bth.c:792-793)."""
        target = self._target(0)
        target.set_status(MechStatus.JUMPING)
        # Base 0 (no jump jets -> MechJumpSpeed 0) + 1 (jumping)
        self.assertEqual(calculate_target_movement_modifier(target, 5), 1)

    def test_jumping_target_uses_jump_speed(self):
        """
        Test a jumping target is rated on its jump speed, not ground speed.

        mech.bth.c:736-737 - `if(Jumping(target)) target_speed =
        JumpSpeed(target, map);`. JumpSpeed reads MechJumpSpeed
        (btmacros.h:701-702), which is `MP1 * jjs` (mech.utils.c:1937), so a
        5-jet mech is rated at 53.75 KPH -> +2 (<= MP6, mech.bth.c:770).
        """
        target = self._target(0)
        target.set_status(MechStatus.JUMPING)
        target.jump_mp = 5
        target.jump_speed = 53.75
        self.assertEqual(calculate_target_movement_modifier(target, 5), 2 + 1)

    def test_jumping_target_ignores_ground_speed(self):
        """Test ground speed is not consulted while jumping (mech.bth.c:736)."""
        target = self._target(90.0)  # would be +3 on the ground
        target.set_status(MechStatus.JUMPING)
        target.jump_mp = 0
        self.assertEqual(calculate_target_movement_modifier(target, 5), 0 + 1)

    def test_jumping_target_speed_is_the_static_capability(self):
        """
        Test the jump BTH does not vary with the length of the jump in progress.

        MechJumpSpeed is a static capability set once at build time
        (mech.utils.c:1937 `MechJumpSpeed(mech) = MP1 * jjs;`) and changed only
        by jump-jet criticals (crit.c:1943, map.conditions.c:224) - it is never
        rewritten per jump. The reviewed `mech.jump_speed` field stores this
        capability and must be initialized along with the jet count.
        """
        from physics.jump import mech_jump

        short, long = self._target(0), self._target(0)
        for target in (short, long):
            target.jump_mp = 5
            target.jump_speed = 53.75
            from entities.map import GameMap
            from core.game_loop import GameEngine
            engine = GameEngine()
            board = GameMap(100, 100)
            board._id = 1000
            engine.register_entity(board)
            board.add_mech(target)
            engine.register_entity(target)
            target.set_hex_position(50, 50)

        mech_jump(short, 51, 50)   # 1 hex
        mech_jump(long, 55, 50)    # 5 hexes
        self.assertTrue(short.is_jumping and long.is_jumping)
        # C jump speed is persistent capability, independent of jump distance.
        self.assertAlmostEqual(short.jump_speed, long.jump_speed, places=1)
        # ...but MP1 * 5 jets = 53.75 KPH rates both at +2, plus +1 for jumping.
        self.assertEqual(calculate_target_movement_modifier(short, 5), 3)
        self.assertEqual(calculate_target_movement_modifier(long, 5), 3)

    def test_jump_jet_loss_lowers_the_jumping_modifier(self):
        """
        Test losing jets lowers the jump speed, as the C's JJ crit does.

        crit.c:1943 / map.conditions.c:224 - `MechJumpSpeed(wounded) -= MP1;`
        floored at 0; systems/criticals.py:596 decrements jump_mp the same way.
        """
        target = self._target(0)
        target.set_status(MechStatus.JUMPING)
        target.jump_mp = 5
        target.jump_speed = 53.75
        self.assertEqual(calculate_target_movement_modifier(target, 5), 2 + 1)
        target.jump_mp = 2
        target.jump_speed = 21.5  # critical producer updates the persistent speed
        self.assertEqual(calculate_target_movement_modifier(target, 5), 0 + 1)


class TestWeaponBTHModifier(unittest.TestCase):
    """Test weapon-specific BTH modifiers."""

    def test_standard_weapon_no_modifier(self):
        """Test standard weapon has no modifier."""
        self.assertEqual(calculate_weapon_bth_modifier(IS_MEDIUM_LASER), 0)
        self.assertEqual(calculate_weapon_bth_modifier(IS_AC10), 0)

    def test_pulse_laser_bonus(self):
        """Test pulse laser has -2 modifier."""
        from entities.weapon import IS_MEDIUM_PULSE_LASER
        self.assertEqual(calculate_weapon_bth_modifier(IS_MEDIUM_PULSE_LASER), -2)


class TestBTHCalculation(unittest.TestCase):
    """Test complete BTH calculation."""

    def setUp(self):
        """Create test mechs."""
        self.attacker = Mech.create_test_mech(name="Attacker")
        from entities.pilot import Pilot
        self.attacker.pilot = Pilot(gunnery=4)
        self.attacker.set_status(MechStatus.STARTED)
        self.attacker.set_hex_position(50, 50)
        self.attacker.facing = 0

        self.target = Mech.create_test_mech(name="Target")
        self.target.set_status(MechStatus.STARTED)
        self.target.set_hex_position(50, 55)  # 5 hexes away
        self.target.facing = 180

    def test_basic_bth_calculation(self):
        """Test basic BTH with stationary mechs at short range."""
        # Use distance 3 for short range (ML is 0/3/6/9)
        bth = calculate_bth(self.attacker, self.target, IS_MEDIUM_LASER, 3)
        # Base 4 + 0 range (short) + 0 move + 0 target + 0 heat + 0 weapon
        self.assertEqual(bth.base, 4)
        self.assertEqual(bth.range_mod, 0)  # Short range (3 hexes)
        self.assertEqual(bth.attacker_move, 0)  # Stationary
        self.assertEqual(bth.target_move, 0)  # Stationary
        self.assertEqual(bth.total, 4)

    def test_bth_with_movement(self):
        """Test BTH with attacker running."""
        self.attacker.speed = 60.0  # Running
        bth = calculate_bth(self.attacker, self.target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.attacker_move, 2)  # Running modifier
        self.assertEqual(bth.total, 6)  # 4 base + 2 running

    def test_bth_medium_range(self):
        """Test BTH at medium range."""
        bth = calculate_bth(self.attacker, self.target, IS_MEDIUM_LASER, 5)
        # 5 hexes is within short range (3) so it's actually medium range
        self.assertEqual(bth.range_mod, 2)  # Medium range for ML
        self.assertEqual(bth.total, 6)  # 4 + 2 range

    def test_bth_long_range(self):
        """Test BTH at long range."""
        bth = calculate_bth(self.attacker, self.target, IS_MEDIUM_LASER, 8)
        self.assertEqual(bth.range_mod, 4)  # Long range
        self.assertEqual(bth.total, 8)

    def test_bth_out_of_range(self):
        """Test BTH out of range."""
        bth = calculate_bth(self.attacker, self.target, IS_MEDIUM_LASER, 20)
        self.assertEqual(bth.range_mod, 1000)  # Out of range

    def test_bth_with_heat(self):
        """Test BTH with overheating attacker."""
        self.attacker.heat = 17.0
        bth = calculate_bth(self.attacker, self.target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.heat_mod, 3)  # +3 at heat 17


class TestSectionBTH(unittest.TestCase):
    """
    Test the per-section basetohit term.

    Reference: mech.bth.c:97-101 - FindNormalBTH adds the mech-wide MechBTH
    ("MechBTHMod", mech.bth.c:98) and then the firing section's own
    MechSections(mech)[section].basetohit ("MechLocBTHMod", mech.bth.c:101).
    The section comes from FindNormalBTH's `section` parameter
    (mech.bth.c:42-47), i.e. the mount of the weapon being fired.
    """

    def setUp(self):
        self.attacker = Mech.create_test_mech(name="Attacker")
        self.attacker.set_status(MechStatus.STARTED)
        self.attacker.set_hex_position(50, 50)
        self.attacker.facing = 0

        self.target = Mech.create_test_mech(name="Target")
        self.target.set_status(MechStatus.STARTED)
        self.target.set_hex_position(50, 53)
        self.target.facing = 180

    def test_no_section_means_no_section_mod(self):
        """Test omitting section leaves section_mod at 0 (backwards compat)."""
        self.attacker.sections[Location.RARM].basetohit = 4
        bth = calculate_bth(self.attacker, self.target, IS_MEDIUM_LASER, 3)
        self.assertEqual(bth.section_mod, 0)
        self.assertEqual(bth.total, DEFAULT_GUNNERY)

    def test_section_basetohit_added(self):
        """Test the firing section's basetohit lands in the total (mech.bth.c:101)."""
        self.attacker.sections[Location.RARM].basetohit = 4
        bth = calculate_bth(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            section=Location.RARM,
        )
        self.assertEqual(bth.section_mod, 4)
        self.assertEqual(bth.total, DEFAULT_GUNNERY + 4)

    def test_other_sections_unaffected(self):
        """Test only the firing section's penalty applies (mech.bth.c:101)."""
        self.attacker.sections[Location.RARM].basetohit = 4
        bth = calculate_bth(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            section=Location.LARM,
        )
        self.assertEqual(bth.section_mod, 0)
        self.assertEqual(bth.total, DEFAULT_GUNNERY)

    def test_shoulder_critical_raises_bth_for_that_arm_only(self):
        """
        Test a shoulder crit raises BTH for weapons in the crippled arm only.

        systems.criticals.handle_shoulder_hip_critical writes +4 to
        Section.basetohit; before A7 nothing read it back.
        """
        from systems.criticals import handle_shoulder_hip_critical

        handle_shoulder_hip_critical(self.attacker, Location.RARM)
        self.assertEqual(self.attacker.sections[Location.RARM].basetohit, 4)

        right = calculate_bth(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            section=Location.RARM,
        )
        left = calculate_bth(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            section=Location.LARM,
        )
        self.assertEqual(right.total, left.total + 4)

    def test_resolve_attack_passes_section_through(self):
        """Test resolve_attack forwards section to the BTH (mech.bth.c:42-47)."""
        self.attacker.sections[Location.RARM].basetohit = 4
        result = resolve_attack(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            to_hit_roll=7, location_roll=7, section=Location.RARM,
        )
        self.assertEqual(result.bth, DEFAULT_GUNNERY + 4)

        plain = resolve_attack(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            to_hit_roll=7, location_roll=7,
        )
        self.assertEqual(plain.bth, DEFAULT_GUNNERY)


class TestHitGroup(unittest.TestCase):
    """
    Test hit group (attack direction) determination.

    Reference: mech.hitloc.c:2833-2924 FindAreaHitGroup()

    The attack direction is the bearing from the TARGET to the ATTACKER minus
    the target's facing (mech.hitloc.c:2881-2884), i.e. ad == 0 means the
    attacker sits dead ahead of the target's nose. The pre-A3 port took the
    bearing attacker->target instead, which is ad - 180: rear shots came back
    FRONT and left/right were swapped. Every expectation below that changed
    carries the C line that proves the old one wrong.

    Mech half-widths are front 90 / aft 30 at the default btech_hit_arcs = 0
    (mech.hitloc.c:2857-2858, default confirmed at src/conf.c:93).
    """

    def setUp(self):
        self.attacker = Mech.create_test_mech()
        self.target = Mech.create_test_mech()
        self.target.set_hex_position(50, 50)
        # Attacker due north of the target: hex_bearing((50,50) -> (50,45)) is
        # exactly 0, so ad == (0 - facing) % 360 and rotating the target's
        # facing selects an exact attack direction.
        self.attacker.set_hex_position(50, 45)

    def _ad(self) -> int:
        return find_attack_direction(self.attacker, self.target)

    def test_default_arc_widths(self):
        """Test the TW rule-set half-widths (mech.hitloc.c:2855-2862)."""
        self.assertEqual(get_hit_arc_half_widths(), (90, 30, 30, 30))

    def test_front_attack(self):
        """Test attacker dead ahead of the target is FRONT (ad == 0)."""
        self.target.facing = 0
        self.assertEqual(self._ad(), 0)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.FRONT)

    def test_rear_attack(self):
        """Test attacker directly behind the target is BACK (ad == 180)."""
        self.target.facing = 180
        self.assertEqual(self._ad(), 180)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.BACK)

    def test_attacker_behind_north_facing_target_is_back(self):
        """
        Test a shot from behind a north-facing target is BACK.

        This is the A3 bug: with the bearing taken attacker->target this
        returned FRONT. mech.hitloc.c:2882-2884 measures target->attacker, so
        an attacker due south of a north-facing target is ad == 180 -> BACK
        (mech.hitloc.c:2892-2893).
        """
        self.target.facing = 0
        self.attacker.set_hex_position(50, 55)  # due south of the target
        self.assertEqual(self._ad(), 180)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.BACK)

    def test_front_arc_inclusive_at_90(self):
        """Test ad == 90 is FRONT (mech.hitloc.c:2890 - `ad <= (0 + m_fs_hw)`)."""
        self.target.facing = 270
        self.assertEqual(self._ad(), 90)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.FRONT)

    def test_front_arc_inclusive_at_270(self):
        """Test ad == 270 is FRONT (mech.hitloc.c:2890 - `ad >= (360 - m_fs_hw)`)."""
        self.target.facing = 90
        self.assertEqual(self._ad(), 270)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.FRONT)

    def test_back_arc_inclusive_at_150(self):
        """Test ad == 150 is BACK (mech.hitloc.c:2892 - `ad >= (180 - m_as_hw)`)."""
        self.target.facing = 210
        self.assertEqual(self._ad(), 150)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.BACK)

    def test_back_arc_inclusive_at_210(self):
        """Test ad == 210 is BACK (mech.hitloc.c:2892 - `ad <= (180 + m_as_hw)`)."""
        self.target.facing = 150
        self.assertEqual(self._ad(), 210)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.BACK)

    def test_right_side_attack(self):
        """Test ad == 120 is RIGHTSIDE (mech.hitloc.c:2896-2897 - ad < 180)."""
        self.target.facing = 240
        self.assertEqual(self._ad(), 120)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.RIGHTSIDE)

    def test_left_side_attack(self):
        """Test ad == 240 is LEFTSIDE (mech.hitloc.c:2894-2895 - ad >= 180)."""
        self.target.facing = 120
        self.assertEqual(self._ad(), 240)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.LEFTSIDE)

    def test_left_and_right_are_not_swapped(self):
        """
        Test the side arcs are not mirrored.

        An attacker 120 degrees clockwise of the target's nose is on the
        target's right (mech.hitloc.c:2896-2897); the pre-A3 code returned
        LEFTSIDE for that position and RIGHTSIDE for its mirror. Uses real hex
        geometry: from (50,50) the source bearing to (51,51) is 121 and to (49,51) is
        240.
        """
        self.target.facing = 0
        self.attacker.set_hex_position(51, 51)
        self.assertEqual(self._ad(), 121)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.RIGHTSIDE)

        self.attacker.set_hex_position(49, 51)
        self.assertEqual(self._ad(), 240)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.LEFTSIDE)

    def test_bearing_uses_subhex_float_positions(self):
        """
        Test the attack direction comes from MechFX/MechFY, not hex centers.

        mech.hitloc.c:2882-2883 feeds FindBearing the float cartesian positions,
        and FindBearing itself takes floats (mech.utils.c:395-418). Snapping both
        units to their hex centers reads exactly 180 here (BACK), but with real
        in-hex offsets - well inside one hex, the kind physics/movement.py
        produces every tick - the true source attack direction is 149, which is a
        RIGHTSIDE hit (mech.hitloc.c:2896-2897) because the aft arc only starts
        at 150. Snapped coordinates would pick the wrong hit table and the wrong
        rear-armor flag.
        """
        from physics.hexmath import float_to_hex, hex_bearing

        self.target.facing = 0
        self.target.set_hex_position(50, 50)
        self.attacker.set_hex_position(50, 51)   # due south: hex-center ad = 180
        self.assertEqual(hex_bearing(50, 50, 50, 51), 180)

        self.target.fx -= 100.0
        self.attacker.fx += 100.0
        # Both units are still standing in their own hexes.
        self.assertEqual(
            float_to_hex(self.attacker.fx, self.attacker.fy), (50, 51))
        self.assertEqual(float_to_hex(self.target.fx, self.target.fy), (50, 50))

        self.assertEqual(self._ad(), 149)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.RIGHTSIDE)

    def test_non_mech_target_uses_vehicle_half_widths(self):
        """
        Test a non-mech target gets the narrow fs_hw/as_hw pair.

        mech.hitloc.c:2887 switches on MechType(target): only CLASS_MECH takes
        the 90 degree front half-width (mech.hitloc.c:2857). CLASS_MW and
        CLASS_BSUIT reach the vehicle arm through the `default:` FALLTHROUGH
        (mech.hitloc.c:2901-2911), so at ad 60 they are RIGHTSIDE
        (mech.hitloc.c:2919-2920) where a mech is still FRONT.
        """
        self.target.facing = 300  # ad == 60
        self.assertEqual(self._ad(), 60)
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.FRONT)

        for unit_type in (UnitType.MW, UnitType.BSUIT, UnitType.VEH_GROUND,
                          UnitType.VTOL, UnitType.VEH_NAVAL):
            with self.subTest(unit_type=unit_type):
                self.target.unit_type = unit_type
                self.assertEqual(
                    determine_hit_group(self.attacker, self.target),
                    HitGroup.RIGHTSIDE)

    def test_non_mech_aft_arc_is_unchanged_at_default_rules(self):
        """
        Test the aft half-width is 30 for mechs and vehicles alike.

        mech.hitloc.c:2858 and :2861 - the TW rule set differs only in the front
        half-width, so ad 150 is BACK for either class.
        """
        self.target.facing = 210  # ad == 150
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.BACK)
        self.target.unit_type = UnitType.VEH_GROUND
        self.assertEqual(
            determine_hit_group(self.attacker, self.target), HitGroup.BACK)

    def test_classic_btmux_arc_rules(self):
        """
        Test btech_hit_arcs = 1 narrows the mech front arc to 45 degrees.

        mech.hitloc.c:2864-2870 - classic BTMUX rules use 45/45 for both mechs
        and vehicles.
        """
        self.target.facing = 270  # ad == 90
        with patch('systems.combat.BTECH_HIT_ARCS', 1):
            self.assertEqual(get_hit_arc_half_widths(), (45, 45, 45, 45))
            self.assertEqual(
                determine_hit_group(self.attacker, self.target),
                HitGroup.RIGHTSIDE)

    def test_bmr_arc_rules(self):
        """Test btech_hit_arcs = 2 keeps mech widths (mech.hitloc.c:2872-2878)."""
        with patch('systems.combat.BTECH_HIT_ARCS', 2):
            self.assertEqual(get_hit_arc_half_widths(), (90, 30, 90, 30))


class TestHitLocation(unittest.TestCase):
    """Test hit location determination."""

    def test_front_hit_locations(self):
        """Test front hit location table."""
        target = Mech.create_test_mech()
        for section in target.sections: section.armor_orig = 0  # Legacy TAC zero-original guard

        # Test specific rolls
        loc, crit = get_hit_location(target, HitGroup.FRONT, roll=2)
        self.assertEqual(loc, Location.CTORSO)
        self.assertTrue(crit)  # Roll of 2 is critical

        loc, crit = get_hit_location(target, HitGroup.FRONT, roll=7)
        self.assertEqual(loc, Location.CTORSO)
        self.assertFalse(crit)

        loc, crit = get_hit_location(target, HitGroup.FRONT, roll=12)
        self.assertEqual(loc, Location.HEAD)

    def test_left_side_hit_locations(self):
        """Test left side hit location table."""
        target = Mech.create_test_mech()
        for section in target.sections: section.armor_orig = 0  # Legacy TAC zero-original guard

        loc, crit = get_hit_location(target, HitGroup.LEFTSIDE, roll=2)
        self.assertEqual(loc, Location.LTORSO)
        self.assertTrue(crit)

        loc, crit = get_hit_location(target, HitGroup.LEFTSIDE, roll=7)
        self.assertEqual(loc, Location.LTORSO)

    def test_right_side_hit_locations(self):
        """Test right side hit location table."""
        target = Mech.create_test_mech()
        for section in target.sections: section.armor_orig = 0  # Legacy TAC zero-original guard

        loc, crit = get_hit_location(target, HitGroup.RIGHTSIDE, roll=2)
        self.assertEqual(loc, Location.RTORSO)
        self.assertTrue(crit)

    def test_punch_location(self):
        """Test punch hit locations (1d6)."""
        target = Mech.create_test_mech()
        for section in target.sections: section.armor_orig = 0  # Legacy TAC zero-original guard

        loc = get_punch_location(target, HitGroup.FRONT, roll=6)
        self.assertEqual(loc, Location.HEAD)

        loc = get_punch_location(target, HitGroup.FRONT, roll=3)
        self.assertEqual(loc, Location.CTORSO)

    def test_kick_location(self):
        """Test kick hit locations."""
        target = Mech.create_test_mech()
        for section in target.sections: section.armor_orig = 0  # Legacy TAC zero-original guard

        loc = get_kick_location(target, HitGroup.FRONT, roll=1)
        self.assertEqual(loc, Location.RLEG)

        loc = get_kick_location(target, HitGroup.LEFTSIDE, roll=1)
        self.assertEqual(loc, Location.LLEG)


class TestDamageApplication(unittest.TestCase):
    """Test damage application."""

    def setUp(self):
        """Create test mech with known armor values."""
        self.mech = Mech.create_test_mech()
        # CT: 16 armor, 16 internal

    def test_armor_absorbs_damage(self):
        """Test armor absorbs all damage."""
        armor_dmg, internal_dmg, overflow, crits = apply_damage_to_location(
            self.mech, Location.CTORSO, 10
        )
        self.assertEqual(armor_dmg, 10)
        self.assertEqual(internal_dmg, 0)
        self.assertEqual(overflow, 0)
        self.assertEqual(self.mech.sections[Location.CTORSO].armor, 6)

    def test_damage_penetrates_to_internal(self):
        """Test damage goes through to internal."""
        # 20 damage to CT with 16 armor = 4 internal
        armor_dmg, internal_dmg, overflow, crits = apply_damage_to_location(
            self.mech, Location.CTORSO, 20
        )
        self.assertEqual(armor_dmg, 16)
        self.assertEqual(internal_dmg, 4)
        self.assertEqual(overflow, 0)
        self.assertEqual(self.mech.sections[Location.CTORSO].armor, 0)
        self.assertEqual(self.mech.sections[Location.CTORSO].internal, 12)

    def test_section_destruction(self):
        """Test section destruction and overflow."""
        # 50 damage to CT (16 armor + 16 internal = 32 max)
        armor_dmg, internal_dmg, overflow, crits = apply_damage_to_location(
            self.mech, Location.CTORSO, 50
        )
        self.assertEqual(armor_dmg, 16)
        self.assertEqual(internal_dmg, 16)
        self.assertEqual(overflow, 18)  # 50 - 32 = 18
        self.assertTrue(self.mech.is_section_destroyed(Location.CTORSO))

    def test_rear_armor_damage(self):
        """Test rear armor takes damage correctly."""
        # CT has 5 rear armor
        armor_dmg, internal_dmg, overflow, crits = apply_damage_to_location(
            self.mech, Location.CTORSO, 3, is_rear=True
        )
        self.assertEqual(armor_dmg, 3)
        self.assertEqual(self.mech.sections[Location.CTORSO].rear, 2)

    @patch('systems.combat.roll_2d6', return_value=7)
    def test_damage_transfer(self, _roll):
        """Test damage transfer to adjacent sections."""
        # A roll of 12 blows off the limb and clears overflow in the C.
        # These transfer tests exercise the ordinary, noncritical path.
        # Destroy left arm (10 armor + 8 internal = 18)
        total = apply_damage_with_transfer(self.mech, Location.LARM, 30)
        self.assertEqual(total, 30)  # All damage dealt
        # Arm destroyed, overflow to left torso
        self.assertTrue(self.mech.is_section_destroyed(Location.LARM))

    @patch('systems.combat.roll_2d6', return_value=7)
    def test_front_transfer_stays_front(self, _roll):
        """
        Test a front arm hit overflowing into the torso eats FRONT armor.

        mech.damage.c:535-538 - DamageMech's transfer recursion passes isrear
        through unmodified (mech.damage.c:536); only non-mech targets ever have
        isrear coerced, and that is done once up front (mech.damage.c:488-506),
        not per transfer hop. The pre-A5 port forced is_rear = True on every
        hop, so front damage came out of the rear armor.
        """
        # LARM 10 armor + 8 internal = 18; 12 overflows into LTORSO's 12 front
        total = apply_damage_with_transfer(
            self.mech, Location.LARM, 30, is_rear=False
        )
        self.assertEqual(total, 30)
        ltorso = self.mech.sections[Location.LTORSO]
        self.assertEqual(ltorso.armor, 0)      # 12 front armor consumed
        self.assertEqual(ltorso.rear, 4)       # rear armor untouched
        self.assertEqual(ltorso.internal, 12)  # nothing reached internals

    @patch('systems.combat.roll_2d6', return_value=7)
    def test_rear_transfer_stays_rear(self, _roll):
        """
        Test a rear hit overflowing keeps eating rear armor.

        mech.damage.c:536 passes isrear unmodified in either direction.
        """
        total = apply_damage_with_transfer(
            self.mech, Location.LARM, 30, is_rear=True
        )
        self.assertEqual(total, 30)
        ltorso = self.mech.sections[Location.LTORSO]
        self.assertEqual(ltorso.armor, 12)     # front armor untouched
        self.assertEqual(ltorso.rear, 0)       # 4 rear armor consumed
        self.assertEqual(ltorso.internal, 4)   # remaining 8 into internals


class TestCriticalHits(unittest.TestCase):
    """Test critical hit mechanics."""

    def test_roll_critical_hits_through_armor(self):
        """Test critical roll through armor."""
        # Should return 0, 1, 2, or 3
        for _ in range(50):
            crits = roll_critical_hits(through_armor=True)
            self.assertGreaterEqual(crits, 0)
            self.assertLessEqual(crits, 3)

    def test_roll_critical_hits_direct(self):
        """Test direct critical roll."""
        for _ in range(50):
            crits = roll_critical_hits(through_armor=False)
            self.assertGreaterEqual(crits, 1)  # Minimum 1 for direct crit
            self.assertLessEqual(crits, 3)


class TestAttackResolution(unittest.TestCase):
    """Test complete attack resolution."""

    def setUp(self):
        """Create test mechs."""
        self.attacker = Mech.create_test_mech(name="Attacker")
        self.attacker.set_status(MechStatus.STARTED)
        self.attacker.set_hex_position(50, 50)
        self.attacker.facing = 0

        self.target = Mech.create_test_mech(name="Target")
        self.target.set_status(MechStatus.STARTED)
        self.target.set_hex_position(50, 53)  # 3 hexes away
        self.target.facing = 180

    def test_attack_miss(self):
        """Test attack that misses."""
        result = resolve_attack(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            to_hit_roll=3  # Will miss with BTH ~4
        )
        self.assertFalse(result.hit)
        self.assertEqual(result.damage_dealt, 0)

    def test_attack_hit(self):
        """Test attack that hits."""
        result = resolve_attack(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            to_hit_roll=10  # Will definitely hit
        )
        self.assertTrue(result.hit)
        self.assertGreater(result.damage_dealt, 0)
        self.assertIsNotNone(result.location)

    def test_attack_hit_specific_location(self):
        """Test attack hits specified location."""
        result = resolve_attack(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            to_hit_roll=12,  # Hit
            location_roll=12  # Head hit
        )
        self.assertTrue(result.hit)
        self.assertEqual(result.location, Location.HEAD)

    def test_missile_attack(self):
        """Test missile weapon attack."""
        result = resolve_attack(
            self.attacker, self.target, IS_SRM6, 3,
            to_hit_roll=10
        )
        self.assertTrue(result.hit)
        # SRM-6 does 2 damage per missile
        self.assertGreater(result.damage_dealt, 0)

    def test_target_destruction(self):
        """
        Test target destruction detection.

        The attacker sits due north of a south-facing target, so ad == 180 and
        this is a BACK shot (mech.hitloc.c:2882-2884 measures target->attacker,
        2892 classifies 180 as BACK). Rear armor therefore has to be stripped
        too - the pre-A3 code called this same geometry FRONT.
        """
        # Damage target heavily first
        self.target.sections[Location.CTORSO].armor = 1
        self.target.sections[Location.CTORSO].rear = 1
        self.target.sections[Location.CTORSO].internal = 1

        result = resolve_attack(
            self.attacker, self.target, IS_MEDIUM_LASER, 3,
            to_hit_roll=12,  # Hit
            location_roll=7  # CT hit
        )

        self.assertEqual(result.location, Location.CTORSO)
        self.assertTrue(result.is_rear)
        self.assertTrue(result.target_destroyed)


class TestCanAttack(unittest.TestCase):
    """Test attack validity checking."""

    def setUp(self):
        self.attacker = Mech.create_test_mech()
        self.attacker.set_status(MechStatus.STARTED)
        self.target = Mech.create_test_mech()
        self.target.set_status(MechStatus.STARTED)

    def test_can_attack_normal(self):
        """Test normal attack is valid."""
        can, reason = can_attack(self.attacker, self.target, IS_MEDIUM_LASER, 5)
        self.assertTrue(can)

    def test_cannot_attack_destroyed_attacker(self):
        """Test destroyed attacker cannot attack."""
        self.attacker.set_status(MechStatus.DESTROYED)
        can, reason = can_attack(self.attacker, self.target, IS_MEDIUM_LASER, 5)
        self.assertFalse(can)
        self.assertIn("destroyed", reason.lower())

    def test_cannot_attack_unstarted(self):
        """Test unstarted mech cannot attack."""
        self.attacker.clear_status(MechStatus.STARTED)
        can, reason = can_attack(self.attacker, self.target, IS_MEDIUM_LASER, 5)
        self.assertFalse(can)

    def test_cannot_attack_out_of_range(self):
        """Test cannot attack out of range target."""
        can, reason = can_attack(self.attacker, self.target, IS_MEDIUM_LASER, 50)
        self.assertFalse(can)
        self.assertIn("range", reason.lower())


class TestEstimateHitChance(unittest.TestCase):
    """Test hit probability estimation."""

    def test_hit_chance_bth_7(self):
        """Test 58% hit chance with BTH 7."""
        chance = estimate_hit_chance(7)
        self.assertAlmostEqual(chance, 58.33, places=1)

    def test_hit_chance_bth_4(self):
        """Test ~92% hit chance with BTH 4."""
        chance = estimate_hit_chance(4)
        self.assertAlmostEqual(chance, 91.67, places=1)

    def test_hit_chance_impossible(self):
        """Test 0% hit chance with BTH 13+."""
        chance = estimate_hit_chance(13)
        self.assertEqual(chance, 0.0)

    def test_hit_chance_guaranteed(self):
        """Test 100% hit chance with BTH 2."""
        chance = estimate_hit_chance(2)
        self.assertEqual(chance, 100.0)


class TestWeaponSlot(unittest.TestCase):
    """Test weapon slot tracking."""

    def test_weapon_slot_creation(self):
        """Test creating a weapon slot."""
        slot = WeaponSlot(
            weapon=IS_MEDIUM_LASER,
            section=Location.RARM,
        )
        self.assertTrue(slot.is_ready)
        self.assertTrue(slot.has_ammo)  # Energy weapon

    def test_weapon_fire_starts_recycle(self):
        """Test firing weapon starts recycle timer."""
        slot = WeaponSlot(weapon=IS_MEDIUM_LASER, section=Location.RARM)
        self.assertTrue(slot.fire())
        self.assertFalse(slot.is_ready)
        self.assertEqual(slot.recycle, IS_MEDIUM_LASER.vrt)

    def test_weapon_slot_tick(self):
        """Test recycle countdown."""
        slot = WeaponSlot(weapon=IS_MEDIUM_LASER, section=Location.RARM)
        slot.fire()
        initial_recycle = slot.recycle

        slot.tick()
        self.assertEqual(slot.recycle, initial_recycle - 1)

    def test_weapon_slot_ammo_tracking(self):
        """Test ammo tracking."""
        slot = WeaponSlot(
            weapon=IS_AC10,
            section=Location.RARM,
            ammo_count=10,
        )
        self.assertTrue(slot.has_ammo)

        slot.fire()
        self.assertEqual(slot.ammo_count, 9)

    def test_weapon_slot_no_ammo(self):
        """Test weapon with no ammo cannot fire."""
        slot = WeaponSlot(
            weapon=IS_AC10,
            section=Location.RARM,
            ammo_count=0,
        )
        self.assertFalse(slot.has_ammo)
        self.assertFalse(slot.fire())

    def test_destroyed_weapon_cannot_fire(self):
        """Test destroyed weapon cannot fire."""
        slot = WeaponSlot(
            weapon=IS_MEDIUM_LASER,
            section=Location.RARM,
            destroyed=True,
        )
        self.assertFalse(slot.is_ready)
        self.assertFalse(slot.fire())


class TestTransferLocations(unittest.TestCase):
    """Test damage transfer paths."""

    def test_arm_transfers_to_torso(self):
        """Test arm damage transfers to side torso."""
        self.assertEqual(TRANSFER_LOCATIONS[Location.LARM], Location.LTORSO)
        self.assertEqual(TRANSFER_LOCATIONS[Location.RARM], Location.RTORSO)

    def test_leg_transfers_to_torso(self):
        """Test leg damage transfers to side torso."""
        self.assertEqual(TRANSFER_LOCATIONS[Location.LLEG], Location.LTORSO)
        self.assertEqual(TRANSFER_LOCATIONS[Location.RLEG], Location.RTORSO)

    def test_side_torso_transfers_to_ct(self):
        """Test side torso transfers to center torso."""
        self.assertEqual(TRANSFER_LOCATIONS[Location.LTORSO], Location.CTORSO)
        self.assertEqual(TRANSFER_LOCATIONS[Location.RTORSO], Location.CTORSO)

    def test_ct_and_head_no_transfer(self):
        """Test CT and head have no transfer."""
        self.assertIsNone(TRANSFER_LOCATIONS[Location.CTORSO])
        self.assertIsNone(TRANSFER_LOCATIONS[Location.HEAD])


if __name__ == '__main__':
    unittest.main()
