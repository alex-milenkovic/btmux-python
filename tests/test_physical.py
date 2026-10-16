"""
Tests for systems/physical.py - the mech.physical.c port.

Every expectation cites the C line that justifies it (mech.physical.c unless
otherwise noted). Dice are made deterministic through explicit roll kwargs or
@patch - the RNG is never seeded.
"""

import math
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.templates import get_template, create_mech_from_template
from entities.mech import (
    Location, MechStatus, CritStatus, SectionConfig, Specials, UnitType,
    MoveType, FireMode, WeaponState,
)
from entities.crittypes import Special, i2special, i2weapon
from entities.weapon import get_weapon
from entities.map import HEAVY_FOREST, LIGHT_FOREST
from systems.piloting import (
    PilotingResult, find_pilot_piloting, find_spilot_piloting,
)
from systems.combat import (
    MP1, calculate_attacker_movement_modifier,
    calculate_target_movement_modifier,
)
import systems.physical as physical
from systems.physical import (
    PhysicalAttackType, CARRYING_CLUB, PHYSICAL_RECYCLE_TIME, MP_PER_KPH,
    RESECT, all_limbs_recycled, phys_common_checks, find_obj,
    sect_has_busy_weap, have_axe, have_claw, have_saw, have_sword, have_mace,
    mech_punch, mech_club, mech_axe, mech_saw, mech_claw, mech_mace,
    mech_sword, mech_kick, mech_trip, mech_charge, charge_mech,
    mech_grabclub, physical_trip,
)

PILOTING = 5          # entities/pilot.py default piloting skill
PSR_OK = PilotingResult(success=True)
PSR_FAIL = PilotingResult(success=False)


def make_mech(name="Alpha"):
    template = get_template("TestMech")     # 50 tons (data/templates.py)
    mech = create_mech_from_template(template, name=name)
    mech.rtons=mech.tonnage*1024
    mech.set_hex_position(50, 50)
    mech.set_status(MechStatus.STARTED)
    from entities.map import GameMap
    from core.game_loop import GameEngine
    mech.map=GameMap(128,128)
    mech.map._id=100
    mech.map.add_mech(mech)
    mech._engine=GameEngine()
    mech._engine.register_entity(mech.map)
    mech._engine.register_entity(mech)
    return mech


def place(attacker, target, bearing=0.0, dist=100.0):
    """Place target at cartesian bearing/dist from attacker (0 = North)."""
    rad = math.radians(bearing)
    target.fx = attacker.fx + dist * math.sin(rad)
    target.fy = attacker.fy - dist * math.cos(rad)
    target.x, target.y = attacker.x, attacker.y
    target.z = attacker.z


def make_pair():
    """Attacker facing its target 100 cartesian units (0.31 hex) north."""
    a = make_mech("Alpha")
    t = make_mech("Target")
    a.facing = 0
    t.facing = 180          # facing the attacker: FRONT hit group
    place(a, t)
    from systems.los import MECHLOSFLAG_SEESP
    t.map=a.map
    a.map.add_mech(t)
    t._engine=a._engine
    a._engine.register_entity(t)
    a.map.losinfo={(a._id,t._id):MECHLOSFLAG_SEESP,(t._id,a._id):MECHLOSFLAG_SEESP}
    t.desired_facing=t.facing
    return a, t


def kill_crit(mech, loc, slot):
    mech.sections[loc].criticals[slot].firemode |= FireMode.DESTROYED_MODE


def add_special(mech, loc, special, count, start=4):
    for i in range(start, start + count):
        mech.sections[loc].criticals[i].type = i2special(special)


def total_armor(mech):
    return sum(s.armor + s.rear + s.internal for s in mech.sections)


class TestAllLimbsRecycled(unittest.TestCase):
    """all_limbs_recycled (mech.physical.c:59-74)."""

    def test_clean_mech_passes(self):
        ok, msg = all_limbs_recycled(make_mech())
        self.assertTrue(ok)

    def test_arm_recycle_blocks(self):
        mech = make_mech()
        mech.sections[Location.RARM].recycle = 10
        ok, msg = all_limbs_recycled(mech)
        self.assertFalse(ok)
        # mech.physical.c:63-64
        self.assertEqual(msg, "You still have arms recovering from another "
                              "attack.")

    def test_leg_recycle_blocks(self):
        mech = make_mech()
        mech.sections[Location.LLEG].recycle = 10
        ok, msg = all_limbs_recycled(mech)
        self.assertFalse(ok)
        # mech.physical.c:69-70
        self.assertEqual(msg, "Your legs are still recovering from your last "
                              "attack.")


class TestPhysCommonChecks(unittest.TestCase):
    """phys_common_checks (mech.physical.c:220-244)."""

    def test_jumping_blocks(self):
        mech = make_mech()
        mech.set_status(MechStatus.JUMPING)
        ok, msg = phys_common_checks(mech)
        self.assertFalse(ok)
        # mech.physical.c:225-227
        self.assertEqual(msg, "You can't perform physical attacks while in "
                              "the air!")

    def test_standing_up_blocks(self):
        mech = make_mech()
        from core.events import EventType
        mech._engine.events.schedule(10, EventType.STAND, lambda event: None, mech)
        ok, msg = phys_common_checks(mech)
        self.assertFalse(ok)
        # mech.physical.c:230-232
        self.assertEqual(msg, "You are still trying to stand up!")

    def test_recycle_actually_blocks_punch_command(self):
        """A recycling limb blocks the whole attack (mech.physical.c:239-241);
        the old tests never wired this gate."""
        a, t = make_pair()
        a.sections[Location.LARM].recycle = 30
        results = mech_punch(a, t, roll=12)
        self.assertFalse(results[0].success)
        self.assertIn("You still have arms recovering from another attack.",
                      results[0].messages)


class TestWeaponPresence(unittest.TestCase):
    """have_* thresholds (mech.physical.c:174-215) with FUNCTIONAL-only
    counting (FindObj, mech.utils.c:2508-2517)."""

    def test_have_axe_threshold(self):
        mech = make_mech()      # 50 tons -> needs 50/15 = 3 axe crits
        self.assertFalse(have_axe(mech, Location.RARM))
        add_special(mech, Location.RARM, Special.AXE, 3)
        self.assertTrue(have_axe(mech, Location.RARM))

    def test_destroyed_crits_do_not_count(self):
        """FindObj counts !PartIsNonfunctional only (mech.utils.c:2508-2517)."""
        mech = make_mech()
        add_special(mech, Location.RARM, Special.AXE, 3)
        kill_crit(mech, Location.RARM, 4)
        self.assertEqual(find_obj(mech, Location.RARM,
                                  i2special(Special.AXE)), 2)
        self.assertFalse(have_axe(mech, Location.RARM))

    def test_have_claw_threshold(self):
        mech = make_mech()      # 50/15 = 3 (mech.physical.c:188-191)
        add_special(mech, Location.LARM, Special.CLAW, 3)
        self.assertTrue(have_claw(mech, Location.LARM))
        self.assertFalse(have_claw(mech, Location.RARM))

    def test_have_saw_threshold(self):
        mech = make_mech()      # flat 7 crits (mech.physical.c:196-199)
        add_special(mech, Location.RARM, Special.DUAL_SAW, 6)
        self.assertFalse(have_saw(mech, Location.RARM))
        add_special(mech, Location.RARM, Special.DUAL_SAW, 7)
        self.assertTrue(have_saw(mech, Location.RARM))

    def test_have_sword_threshold(self):
        mech = make_mech()      # (50+15)/20 = 3 (mech.physical.c:204-208)
        add_special(mech, Location.RARM, Special.SWORD, 2)
        self.assertFalse(have_sword(mech, Location.RARM))
        add_special(mech, Location.RARM, Special.SWORD, 3)
        self.assertTrue(have_sword(mech, Location.RARM))

    def test_have_mace_threshold(self):
        mech = make_mech()      # 50/10 = 5 (mech.physical.c:213-216)
        add_special(mech, Location.RARM, Special.MACE, 4)
        self.assertFalse(have_mace(mech, Location.RARM))
        add_special(mech, Location.RARM, Special.MACE, 5)
        self.assertTrue(have_mace(mech, Location.RARM))

    def test_sect_has_busy_weap(self):
        """SectHasBusyWeap (mech.utils.c:168-180)."""
        mech = make_mech()
        mech.weapons.append(WeaponState(section=Location.RARM, critical=4, recycle=5))
        mech.sections[Location.RARM].criticals[4].type=i2weapon(get_weapon('IS.SmallLaser').index)
        mech.sections[Location.RARM].criticals[4].data=5
        self.assertTrue(sect_has_busy_weap(mech, Location.RARM))
        self.assertFalse(sect_has_busy_weap(mech, Location.LARM))


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestBaseBTH(unittest.TestCase):
    """btech_phys_use_pskill switch: pskill=1 (DEFAULT) uses piloting-derived
    bases, pskill=0 uses the flat constants (mech.physical.c:359-361, 441-444,
    509-511, 563-565, 614-616, 691-693, 764-766, 861-863). The old tests only
    knew the flat PUNCH 4 / KICK 3 constants."""

    def test_punch_base_is_piloting(self, _psr):
        a, t = make_pair()
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        # mech.physical.c:359-361: base = FindPilotPiloting under pskill
        self.assertEqual(result.bth, PILOTING)

    def test_punch_flat_base_when_pskill_off(self, _psr):
        a, t = make_pair()
        with patch('systems.physical.BTECH_PHYS_USE_PSKILL', 0):
            result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        self.assertEqual(result.bth, 4)     # mech.physical.c:349 default

    def test_kick_base_is_piloting_minus_2(self, _psr):
        a, t = make_pair()
        result = mech_kick(a, t, roll=12, location_roll=3)
        # mech.physical.c:861-863
        self.assertEqual(result.bth, PILOTING - 2)

    def test_kick_flat_base_when_pskill_off(self, _psr):
        a, t = make_pair()
        with patch('systems.physical.BTECH_PHYS_USE_PSKILL', 0):
            result = mech_kick(a, t, roll=12, location_roll=3)
        self.assertEqual(result.bth, 3)     # mech.physical.c:862

    def test_club_base_is_piloting_minus_1(self, _psr):
        a, t = make_pair()
        a.sections[Location.RARM].specials |= CARRYING_CLUB
        result = mech_club(a, t, roll=12, location_roll=7)
        # mech.physical.c:441-444
        self.assertEqual(result.bth, PILOTING - 1)

    def test_axe_base_is_piloting_minus_1(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.AXE, 3)
        result = mech_axe(a, t, arm='R', roll=12, location_roll=7)[0]
        # mech.physical.c:509-511
        self.assertEqual(result.bth, PILOTING - 1)

    def test_saw_base_plus_one(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.DUAL_SAW, 7)
        result = mech_saw(a, t, arm='R', roll=12, location_roll=7)[0]
        # base piloting-1 (mech.physical.c:563-565) + saw +1 (:1348-1350)
        self.assertEqual(result.bth, PILOTING - 1 + 1)

    def test_mace_base_plus_two(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.MACE, 5)
        result = mech_mace(a, t, arm='R', roll=12, location_roll=7)[0]
        # base piloting-1 (mech.physical.c:691-693) + mace +2 (:1352-1354)
        self.assertEqual(result.bth, PILOTING - 1 + 2)

    def test_claw_base_plus_one(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.CLAW, 3)
        result = mech_claw(a, t, arm='R', roll=12, location_roll=3)[0]
        # base piloting (mech.physical.c:614-616) + claw +1 (:1356-1358)
        self.assertEqual(result.bth, PILOTING + 1)

    def test_sword_base_is_piloting_minus_2(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.SWORD, 3)
        result = mech_sword(a, t, arm='R', roll=12, location_roll=7)[0]
        # mech.physical.c:764-766
        self.assertEqual(result.bth, PILOTING - 2)

    def test_sword_flat_base_when_pskill_off(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.SWORD, 3)
        with patch('systems.physical.BTECH_PHYS_USE_PSKILL', 0):
            result = mech_sword(a, t, arm='R', roll=12, location_roll=7)[0]
        self.assertEqual(result.bth, 3)     # mech.physical.c:754


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestPunch(unittest.TestCase):

    def test_damage_is_tons_over_10(self, _psr):
        a, t = make_pair()
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        self.assertTrue(result.hit)
        # floor(50/10) = 5 (mech.physical.c:1545, weight 10 from :382)
        self.assertEqual(result.damage_dealt, 5)

    def test_destroyed_arm_refused(self, _psr):
        a, t = make_pair()
        a.sections[Location.RARM].config |= SectionConfig.SECTION_DESTROYED
        a.sections[Location.RARM].armor=a.sections[Location.RARM].internal=0
        result = mech_punch(a, t, arm='R', roll=12)[0]
        self.assertFalse(result.success)
        # mech.physical.c:317-321
        self.assertEqual(result.message, "Your right arm is destroyed, you "
                                         "can't punch with it.")

    def test_destroyed_shoulder_refused(self, _psr):
        a, t = make_pair()
        kill_crit(a, Location.RARM, 0)
        result = mech_punch(a, t, arm='R', roll=12)[0]
        # mech.physical.c:322-326
        self.assertEqual(result.message, "Your right shoulder is destroyed, "
                                         "you can't punch with that arm.")

    def test_carrying_club_refused(self, _psr):
        a, t = make_pair()
        a.sections[Location.LARM].specials |= CARRYING_CLUB
        result = mech_punch(a, t, arm='L', roll=12)[0]
        # mech.physical.c:327-331
        self.assertEqual(result.message, "You're carrying a club in your "
                                         "left arm and can't punch with it.")

    def test_upper_actuator_bth_and_halving(self, _psr):
        a, t = make_pair()
        kill_crit(a, Location.RARM, 1)      # upper actuator
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        # +2 BTH (mech.physical.c:1037-1040), damage halved (:1569-1571)
        self.assertEqual(result.bth, PILOTING + 2)
        self.assertEqual(result.damage_dealt, 5 // 2)

    def test_hand_actuator_plus_one(self, _psr):
        a, t = make_pair()
        kill_crit(a, Location.RARM, 3)      # hand actuator
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        # +1 BTH, punch/kick only (mech.physical.c:1047-1053); no halving
        self.assertEqual(result.bth, PILOTING + 1)
        self.assertEqual(result.damage_dealt, 5)

    def test_both_actuators_double_halving(self, _psr):
        a, t = make_pair()
        kill_crit(a, Location.RARM, 1)
        kill_crit(a, Location.RARM, 2)
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        # mech.physical.c:1566-1572: two successive halvings
        self.assertEqual(result.damage_dealt, 5 // 2 // 2)

    def test_recycle_set_on_miss_and_axed_cleared(self, _psr):
        a, t = make_pair()
        a.sections[Location.RARM].config |= SectionConfig.AXED
        result = mech_punch(a, t, arm='R', roll=2)[0]
        self.assertFalse(result.hit)
        # Recycle is set HIT OR MISS (mech.physical.c:1401)
        self.assertEqual(a.sections[Location.RARM].recycle,
                         PHYSICAL_RECYCLE_TIME)
        # Punch clears AXED (mech.physical.c:1408-1409)
        self.assertFalse(a.sections[Location.RARM].config & SectionConfig.AXED)

    def test_no_target_message(self, _psr):
        a, _ = make_pair()
        result = mech_punch(a, roll=12)[0]
        # mech.physical.c:1091
        self.assertEqual(result.message, "You do not have a target set!")


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestClub(unittest.TestCase):

    def test_no_trees_no_club(self, _psr):
        a, t = make_pair()
        result = mech_club(a, t, roll=12)
        # mech.physical.c:412-415
        self.assertEqual(result.message, "You can not seem to find any trees "
                                         "around to club with.")

    def test_club_always_shatters_on_hit(self, _psr):
        """The C club ALWAYS shatters on a successful hit
        (mech.physical.c:1430-1445). The old 1-in-6 break was invented."""
        a, t = make_pair()
        a.sections[Location.LARM].specials |= CARRYING_CLUB
        result = mech_club(a, t, roll=12, location_roll=7)
        self.assertTrue(result.hit)
        self.assertIn("Your club shatters on contact.", result.messages)
        self.assertFalse(a.sections[Location.LARM].specials & CARRYING_CLUB)

    def test_club_survives_a_miss(self, _psr):
        a, t = make_pair()
        a.sections[Location.RARM].specials |= CARRYING_CLUB
        result = mech_club(a, t, roll=2)
        self.assertFalse(result.hit)
        # Shatter only happens inside the hit branch (mech.physical.c:1430)
        self.assertTrue(a.sections[Location.RARM].specials & CARRYING_CLUB)

    def test_damage_is_tons_over_5(self, _psr):
        a, t = make_pair()
        a.terrain = HEAVY_FOREST        # improvised club (mech.physical.c:412-417)
        result = mech_club(a, t, roll=12, location_roll=7)
        # floor(50/5) = 10 (weight 5, mech.physical.c:441)
        self.assertEqual(result.damage_dealt, 10)

    def test_club_recycles_both_arms(self, _psr):
        a, t = make_pair()
        a.sections[Location.RARM].specials |= CARRYING_CLUB
        mech_club(a, t, roll=2)
        # mech.physical.c:1401 + 1413-1415
        self.assertEqual(a.sections[Location.RARM].recycle,
                         PHYSICAL_RECYCLE_TIME)
        self.assertEqual(a.sections[Location.LARM].recycle,
                         PHYSICAL_RECYCLE_TIME)

    def test_busy_weapons_on_either_arm_block(self, _psr):
        """SectHasBusyWeap on both arms is checked at the command layer
        (mech.physical.c:436-438, SectHasBusyWeap per mech.utils.c:168-180)."""
        a, t = make_pair()
        a.sections[Location.RARM].specials |= CARRYING_CLUB
        a.weapons.append(WeaponState(section=Location.LARM, critical=4, recycle=5))
        a.sections[Location.LARM].criticals[4].data=5
        result = mech_club(a, t, roll=12)
        self.assertEqual(result.message,
                         "You have weapons recycling on your arms.")

    def test_hand_gates(self, _psr):
        a, t = make_pair()
        a.sections[Location.RARM].specials |= CARRYING_CLUB
        kill_crit(a, Location.LARM, 3)
        result = mech_club(a, t, roll=12)
        # mech.physical.c:432-433
        self.assertEqual(result.message, "You can't club anyone with a "
                                         "destroyed or missing left hand.")

    def test_club_actuator_quirk_type_checked_on_rarm(self, _psr):
        """C QUIRK (mech.physical.c:1067-1070): the LARM actuator checks read
        GetPartType from `sect` (RARM), so blanking LARM's upper actuator TYPE
        (without making it nonfunctional) adds no +2."""
        a, t = make_pair()
        a.sections[Location.RARM].specials |= CARRYING_CLUB
        a.sections[Location.LARM].criticals[1].type = 0     # EMPTY, functional
        result = mech_club(a, t, roll=12, location_roll=7)
        self.assertEqual(result.bth, PILOTING - 1)

    def test_club_larm_nonfunctional_adds_two(self, _psr):
        a, t = make_pair()
        a.sections[Location.RARM].specials |= CARRYING_CLUB
        kill_crit(a, Location.LARM, 1)      # nonfunctional half does fire
        result = mech_club(a, t, roll=12, location_roll=7)
        # mech.physical.c:1067-1070
        self.assertEqual(result.bth, PILOTING - 1 + 2)


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestAxe(unittest.TestCase):

    def test_no_axe_message(self, _psr):
        a, t = make_pair()
        results = mech_axe(a, t, roll=12)
        # mech.physical.c:519-521
        self.assertEqual(results[-1].message,
                         "You may lack the axe, but not the will! Try "
                         "punch/club until you find one.")

    def test_damage_is_tons_over_5_and_axed_flag(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.AXE, 3)
        result = mech_axe(a, t, arm='R', roll=12, location_roll=7)[0]
        self.assertEqual(result.damage_dealt, 10)   # weight 5 (:513)
        # AXED set for axe/sword/saw/mace (mech.physical.c:1403-1406)
        self.assertTrue(a.sections[Location.RARM].config & SectionConfig.AXED)

    def test_hand_message_left_hand_quirk(self, _psr):
        """C QUIRK (mech.physical.c:466-469): the hand refusal has no %s, so
        it always says 'left hand', even for the right arm."""
        a, t = make_pair()
        add_special(a, Location.RARM, Special.AXE, 3)
        kill_crit(a, Location.RARM, 3)
        result = mech_axe(a, t, arm='R', roll=12)[0]
        self.assertEqual(result.message, "Your left hand is destroyed, you "
                                         "can't axe with that arm.")


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestSaw(unittest.TestCase):

    def test_flat_7_damage(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.DUAL_SAW, 7)
        result = mech_saw(a, t, arm='R', roll=12, location_roll=7)[0]
        # mech.physical.c:1533-1537
        self.assertEqual(result.damage_dealt, 7)

    def test_saw_is_tsm_immune(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.DUAL_SAW, 7)
        a.specials |= Specials.TRIPLE_MYOMER_TECH
        a.heat = 9
        result = mech_saw(a, t, arm='R', roll=12, location_roll=7)[0]
        # TSM branch excludes PA_SAW (mech.physical.c:1533-1551)
        self.assertEqual(result.damage_dealt, 7)

    def test_no_saw_message(self, _psr):
        a, t = make_pair()
        results = mech_saw(a, t, roll=12)
        self.assertEqual(results[-1].message, "You don't have a dual saw!")


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestClaw(unittest.TestCase):

    def test_damage_is_tons_over_7(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.CLAW, 3)
        result = mech_claw(a, t, arm='R', roll=12, location_roll=3)[0]
        # floor(50/7) = 7 (weight 7, mech.physical.c:626-633)
        self.assertEqual(result.damage_dealt, 7)

    def test_no_per_arm_check_quirk(self, _psr):
        """C QUIRK (mech.physical.c:625-634): mech_claw has NO checkArm call,
        so a destroyed arm is not refused at the command layer."""
        a, t = make_pair()
        add_special(a, Location.RARM, Special.CLAW, 3)
        a.sections[Location.RARM].config |= SectionConfig.SECTION_DESTROYED
        a.sections[Location.RARM].armor=a.sections[Location.RARM].internal=0
        result = mech_claw(a, t, arm='R', roll=12, location_roll=3)[0]
        self.assertTrue(result.success)

    def test_no_claw_message(self, _psr):
        a, t = make_pair()
        results = mech_claw(a, t, roll=12)
        self.assertEqual(results[-1].message,
                         "You do not have any claws! Try punching/clubbing "
                         "instead!")


class TestMace(unittest.TestCase):

    @patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
    def test_damage_is_tons_over_4(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.MACE, 5)
        result = mech_mace(a, t, arm='R', roll=12, location_roll=7)[0]
        # floor(50/4) = 12 (weight 4, mech.physical.c:708)
        self.assertEqual(result.damage_dealt, 12)

    @patch('systems.physical.mech_falls')
    @patch('systems.physical.make_piloting_roll', return_value=PSR_FAIL)
    def test_miss_forces_psr_plus_2(self, psr, falls):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.MACE, 5)
        result = mech_mace(a, t, arm='R', roll=2)[0]
        self.assertFalse(result.hit)
        # mech.physical.c:1466-1480: mace failRoll = 2
        self.assertIn("You miss and try to remain standing!", result.messages)
        self.assertEqual(psr.call_args.kwargs['modifier'], 2)
        self.assertIn("You lose your balance and fall down!", result.messages)
        falls.assert_called_once()


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestSword(unittest.TestCase):

    def test_damage_formula(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.SWORD, 3)
        result = mech_sword(a, t, arm='R', roll=12, location_roll=7)[0]
        # (50+5)/10 + 1 = 6 (mech.physical.c:1541-1542, weight 10 from :777)
        self.assertEqual(result.damage_dealt, 6)

    def test_no_sword_message(self, _psr):
        a, t = make_pair()
        results = mech_sword(a, t, roll=12)
        self.assertEqual(results[-1].message,
                         "You have no sword to chop people with!")


class TestKickAndTrip(unittest.TestCase):

    @patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
    def test_kick_damage_is_tons_over_5(self, _psr):
        a, t = make_pair()
        result = mech_kick(a, t, roll=12, location_roll=3)
        # floor(50/5) = 10 (weight 5, mech.physical.c:861)
        self.assertEqual(result.damage_dealt, 10)
        self.assertEqual(a.sections[Location.RLEG].recycle,
                         PHYSICAL_RECYCLE_TIME)

    @patch('systems.physical.mech_falls')
    @patch('systems.physical.make_piloting_roll', return_value=PSR_FAIL)
    def test_kick_hit_forces_target_psr(self, psr, falls):
        a, t = make_pair()
        result = mech_kick(a, t, roll=12, location_roll=3)
        # mech.physical.c:1687-1694: PSR+0, fall on failure
        self.assertTrue(result.target_fell)
        self.assertIn("The kick knocks you to the ground!", result.messages)
        self.assertEqual(psr.call_args.kwargs['modifier'], 0)
        falls.assert_called_with(t, levels=1, notify_fall=False)

    @patch('systems.physical.mech_falls')
    @patch('systems.physical.make_piloting_roll', return_value=PSR_FAIL)
    def test_kick_miss_forces_psr_plus_0(self, psr, falls):
        a, t = make_pair()
        result = mech_kick(a, t, roll=2)
        self.assertFalse(result.hit)
        # mech.physical.c:1466-1480: kick failRoll = 0
        self.assertIn("You miss and try to remain standing!", result.messages)
        self.assertEqual(psr.call_args.kwargs['modifier'], 0)
        self.assertTrue(result.attacker_fell)

    @patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
    def test_quad_front_leg_remap(self, _psr):
        a, t = make_pair()
        a.move_type = MoveType.QUAD
        result = mech_kick(a, t, roll=2)
        self.assertTrue(result.success)
        # Quads kick with the arm slots (mech.physical.c:820-823)
        self.assertEqual(a.sections[Location.RARM].recycle,
                         PHYSICAL_RECYCLE_TIME)

    def test_both_legs_levitate_message(self):
        a, t = make_pair()
        result = mech_kick(a, t, arm='B', roll=12)
        # mech.physical.c:842-846
        self.assertEqual(result.message,
                         "What, yer gonna LEVITATE? I Don't Think So.")

    def test_dead_leg_generic_check(self):
        a, t = make_pair()
        a.sections[Location.LLEG].config |= SectionConfig.SECTION_DESTROYED
        a.sections[Location.LLEG].armor=a.sections[Location.LLEG].internal=0
        result = mech_kick(a, t, roll=12)
        # GENERIC_CHECK expansion text (mech.physical.c:900-903)
        self.assertEqual(result.message, "With one leg? Are you kidding?")

    def test_hip_damaged_gate(self):
        a, t = make_pair()
        a.set_crit_status(CritStatus.HIP_DAMAGED)
        result = mech_kick(a, t, roll=12)
        # mech.physical.c:848-854
        self.assertEqual(result.message,
                         "You can't kick with a destroyed hip.")

    @patch('systems.physical.mech_falls')
    @patch('systems.physical.make_piloting_roll', return_value=PSR_FAIL)
    def test_trip_never_does_damage(self, psr, falls):
        a, t = make_pair()
        before = total_armor(t)
        result = mech_trip(a, t, roll=12)
        self.assertTrue(result.hit)
        # PhysicalTrip (mech.physical.c:1499-1520): PSR+0, no damage ever
        self.assertEqual(total_armor(t), before)
        self.assertEqual(result.damage_dealt, 0)
        self.assertIn("You are tripped and fall to the ground!",
                      result.messages)
        self.assertEqual(psr.call_args.kwargs['modifier'], 0)
        falls.assert_called_with(t, levels=1, notify_fall=False)

    @patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
    def test_trip_target_stays_upright(self, _psr):
        a, t = make_pair()
        result = mech_trip(a, t, roll=12)
        # mech.physical.c:1517-1518
        self.assertIn("manages to stay upright!", result.messages)
        self.assertFalse(result.target_fell)

    def test_trip_only_mechs(self):
        a, t = make_pair()
        t.unit_type = UnitType.VEH_GROUND
        result = mech_trip(a, t, roll=12)
        # mech.physical.c:1188-1189
        self.assertEqual(result.message, "You can only trip mechs!")

    def test_trip_fallen_target(self):
        a, t = make_pair()
        t.set_status(MechStatus.FALLEN)
        result = mech_trip(a, t, roll=12)
        # mech.physical.c:1192-1194
        self.assertEqual(result.message, "Your target is already down!")


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestTSMAndMeleeSpecialist(unittest.TestCase):

    def test_tsm_doubles_punch_at_heat_9(self, _psr):
        a, t = make_pair()
        a.specials |= Specials.TRIPLE_MYOMER_TECH
        a.heat = 9
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        # mech.physical.c:1548-1551: heat >= 9 + TSM tech -> x2
        self.assertEqual(result.damage_dealt, 10)

    def test_tsm_needs_heat_9(self, _psr):
        a, t = make_pair()
        a.specials |= Specials.TRIPLE_MYOMER_TECH
        a.heat = 8
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        self.assertEqual(result.damage_dealt, 5)

    def test_melee_specialist_damage_and_bth(self, _psr):
        a, t = make_pair()
        a.pilot.melee_specialist = True
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        # +1 damage (mech.physical.c:1559-1561)
        self.assertEqual(result.damage_dealt, 6)
        # BTH: MIN(0, AttackMovementMods - 1) = -1 when stationary
        # (mech.physical.c:1329-1331)
        self.assertEqual(result.bth, PILOTING - 1)


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestGlancingBlows(unittest.TestCase):
    """btech_glancing_blows = 1 by default (src/conf.c:91-143);
    mech.physical.c:1417-1428 + 1673-1675."""

    def test_roll_equal_bth_is_glancing(self, _psr):
        a, t = make_pair()
        result = mech_punch(a, t, arm='R', roll=PILOTING, location_roll=3)[0]
        self.assertTrue(result.hit)
        self.assertTrue(result.glancing)
        self.assertIn("You are nicked by a glancing blow!", result.messages)
        # glance damage = (5+1)/2 (mech.physical.c:1673-1675)
        self.assertEqual(result.damage_dealt, 3)

    def test_roll_above_bth_full_damage(self, _psr):
        a, t = make_pair()
        result = mech_punch(a, t, arm='R', roll=PILOTING + 1,
                            location_roll=3)[0]
        self.assertFalse(result.glancing)
        self.assertEqual(result.damage_dealt, 5)

    def test_roll_below_bth_misses(self, _psr):
        a, t = make_pair()
        result = mech_punch(a, t, arm='R', roll=PILOTING - 1)[0]
        self.assertFalse(result.hit)

    def test_glancing_disabled(self, _psr):
        a, t = make_pair()
        with patch('systems.physical.BTECH_GLANCING_BLOWS', 0):
            result = mech_punch(a, t, arm='R', roll=PILOTING,
                                location_roll=3)[0]
        self.assertTrue(result.hit)
        self.assertFalse(result.glancing)
        self.assertEqual(result.damage_dealt, 5)


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestPhysicalAttackGates(unittest.TestCase):

    def test_fallen_kick_refused(self, _psr):
        a, t = make_pair()
        a.set_status(MechStatus.FALLEN)
        result = mech_kick(a, t, roll=12)
        # mech.physical.c:1119-1123
        self.assertEqual(result.message,
                         "You can't kick from a prone position.")

    def test_fallen_punch_vs_mech_refused(self, _psr):
        a, t = make_pair()
        a.set_status(MechStatus.FALLEN)
        result = mech_punch(a, t, arm='R', roll=12)[0]
        # mech.physical.c:1126-1133
        self.assertEqual(result.message,
                         "You can't punch from a prone position.")

    def test_fallen_punch_vs_bsuit_not_swarming(self, _psr):
        a, t = make_pair()
        a.set_status(MechStatus.FALLEN)
        t.unit_type = UnitType.BSUIT
        result = mech_punch(a, t, arm='R', roll=12)[0]
        # mech.physical.c:1134-1138
        self.assertEqual(result.message,
                         "You may only physical suits that are swarming you "
                         "while prone.")

    def test_punch_vehicle_needs_prone(self, _psr):
        a, t = make_pair()
        t.unit_type = UnitType.VEH_GROUND
        result = mech_punch(a, t, arm='R', roll=12)[0]
        # mech.physical.c:1181-1185
        self.assertEqual(result.message,
                         "You can't punch vehicles unless you are prone!")

    def test_out_of_range(self, _psr):
        a, t = make_pair()
        place(a, t, dist=400)      # 1.24 hexes >= maxRange 1
        result = mech_punch(a, t, arm='R', roll=12)[0]
        # mech.physical.c:1158
        self.assertEqual(result.message, "Target out of range!")

    def test_bsuit_half_hex_range(self, _psr):
        a, t = make_pair()
        t.unit_type = UnitType.BSUIT
        place(a, t, dist=200)      # 0.62 hexes >= 0.5 (mech.physical.c:1155-1158)
        result = mech_punch(a, t, arm='R', roll=12)[0]
        self.assertEqual(result.message, "Target out of range!")

    def test_airborne_target_refused(self, _psr):
        a, t = make_pair()
        t.set_status(MechStatus.JUMPING)
        result = mech_punch(a, t, arm='R', roll=12)[0]
        # mech.physical.c:1160-1161
        self.assertEqual(result.message,
                         "You can't perform physical attacks on airborne "
                         "mechs!")

    def test_bsuit_bth_terms(self, _psr):
        a, t = make_pair()
        t.unit_type = UnitType.BSUIT
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        # BSuit +1 (mech.physical.c:1337-1338)
        self.assertEqual(result.bth, PILOTING + 1)
        a2, t2 = make_pair()
        t2.unit_type = UnitType.BSUIT
        result = mech_kick(a2, t2, roll=12, location_roll=3)
        # kick vs BSuit is +1 then +3 more (mech.physical.c:1340-1341)
        self.assertEqual(result.bth, PILOTING - 2 + 1 + 3)

    def test_kick_swarmed_suit_refused(self, _psr):
        a, t = make_pair()
        t.unit_type = UnitType.BSUIT
        t.swarm_target = a._id
        # Kicks skip the direct-physical swarm gate (it lives in the
        # non-kick elevation branch, mech.physical.c:1206-1234), so equal
        # elevation reaches the kick-vs-swarmed-suit refusal.
        result = mech_kick(a, t, roll=12)
        # mech.physical.c:1366-1370
        self.assertEqual(result.message,
                         "You can't hit a swarmed suit with that, try a "
                         "hand-held weapon!")

    def test_terrain_bth_mods(self, _psr):
        # Smoke/heavy forest +2, light forest +1 (mech.physical.c:1373-1381)
        a, t = make_pair()
        t.terrain = HEAVY_FOREST
        result = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        self.assertEqual(result.bth, PILOTING + 2)
        a2, t2 = make_pair()
        t2.terrain = LIGHT_FOREST
        result = mech_punch(a2, t2, arm='R', roll=12, location_roll=3)[0]
        self.assertEqual(result.bth, PILOTING + 1)


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestElevationMatrix(unittest.TestCase):
    """mech.physical.c:1198-1273."""

    def test_punch_target_too_low(self, _psr):
        a, t = make_pair()
        a.z = 1
        result = mech_punch(a, t, arm='R', roll=12)[0]
        # mech.physical.c:1207-1211 + 1236-1240
        self.assertEqual(result.message,
                         "The target is too low in elevation for you to "
                         "punch.")

    def test_kick_target_too_high(self, _psr):
        a, t = make_pair()
        t.z = 1
        result = mech_kick(a, t, roll=12)
        # mech.physical.c:1243-1245
        self.assertEqual(result.message,
                         "The target is too high in elevation for you to "
                         "kick at.")

    def test_elevation_difference_too_large(self, _psr):
        a, t = make_pair()
        add_special(a, Location.RARM, Special.AXE, 3)
        a.z = 2
        result = mech_axe(a, t, arm='R', roll=12)[0]
        # mech.physical.c:1246-1248
        self.assertEqual(result.message,
                         "You can't attack, the elevation difference is too "
                         "large.")

    def test_vtol_fall_through_quirk(self, _psr):
        """C QUIRK (mech.physical.c:1251-1255): the VTOL 'too far away'
        branch does NOT return; the elevation-difference check still fires."""
        a, t = make_pair()
        t.move_type = MoveType.VTOL
        t.z = 5
        result = mech_punch(a, t, arm='R', roll=12)[0]
        self.assertIn("The target is too far away for you to punch.",
                      result.messages)
        self.assertIn("You can't attack, the elevation difference is too "
                      "large.", result.messages)
        self.assertFalse(result.success)


@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestWeaponArcs(unittest.TestCase):
    """mech.physical.c:1286-1322."""

    def test_right_arm_side_arc_ok_left_arm_refused(self, _psr):
        a, t = make_pair()
        place(a, t, bearing=90)    # due east of the attacker
        results = mech_punch(a, t, roll=12, location_roll=3)
        by_msg = {r.message for r in results if not r.success}
        # LARM: forward or left only (mech.physical.c:1315-1318)
        self.assertIn("Target is not in your forward or left side arc!",
                      by_msg)
        # RARM: forward or right passes (mech.physical.c:1308-1312)
        self.assertTrue(any(r.success for r in results))

    def test_kick_uses_real_forward_arc_twist_stripped(self, _psr):
        a, t = make_pair()
        place(a, t, bearing=90)
        a.status |= MechStatus.TORSO_RIGHT      # twist toward the target
        result = mech_kick(a, t, roll=12)
        # Twist is stripped for kicks (mech.physical.c:1288-1295)
        self.assertEqual(result.message,
                         "Target is not in your 'real' forward arc!")

    def test_club_is_frontal_only(self, _psr):
        a, t = make_pair()
        a.sections[Location.RARM].specials |= CARRYING_CLUB
        place(a, t, bearing=90)
        result = mech_club(a, t, roll=12)
        # mech.physical.c:1303-1306
        self.assertEqual(result.message, "Target is not in your forward arc!")

    def test_left_arm_swarming_quirk(self, _psr):
        """C QUIRK (mech.physical.c:1315-1318): `|| swarmingUs` sits outside
        the negation, so a suit swarming us always FAILS the left-arm arc."""
        a, t = make_pair()
        t.unit_type = UnitType.BSUIT
        t.swarm_target = a
        t.z = a.z + 1              # dodge the direct-physical swarm gate
        left = mech_punch(a, t, arm='L', roll=12, location_roll=3)[0]
        self.assertEqual(left.message,
                         "Target is not in your forward or left side arc!")
        right = mech_punch(a, t, arm='R', roll=12, location_roll=3)[0]
        self.assertTrue(right.success)


class TestChargeCommand(unittest.TestCase):
    """mech_charge (mech.physical.c:867-993)."""

    def test_sets_pending_target(self):
        a, t = make_pair()
        result = mech_charge(a, t)
        self.assertTrue(result.success)
        self.assertEqual(a.charge_target, t._id)
        # mech.physical.c:983-985 ("Charge" for mechs, "Ram" for vehicles)
        self.assertEqual(result.message, "Charge target set to Target [].")

    def test_cancel_clears_fields(self):
        a, t = make_pair()
        a.charge_target = t
        a.charge_timer = 30
        a.charge_distance = 2.5
        result = mech_charge(a, cancel=True)
        # mech.physical.c:951-957
        self.assertEqual(a.charge_target, -1)
        self.assertEqual(a.charge_timer, 0)
        self.assertEqual(a.charge_distance, 0)
        self.assertEqual(result.message, "You are no longer charging.")

    def test_mechwarrior_target_refused(self):
        a, t = make_pair()
        t.unit_type = UnitType.MW
        result = mech_charge(a, t)
        # mech.physical.c:934-938
        self.assertEqual(result.message,
                         "You can't charge THAT sack of bones and squishy "
                         "bits!")

    def test_bsuit_attacker_refused(self):
        a, t = make_pair()
        a.unit_type = UnitType.BSUIT
        result = mech_charge(a, t)
        # mech.physical.c:884-886
        self.assertEqual(result.message, "You cannot charge without a 'mech!")

    def test_dead_leg_gate(self):
        a, t = make_pair()
        a.sections[Location.RLEG].config |= SectionConfig.SECTION_DESTROYED
        a.sections[Location.RLEG].armor=a.sections[Location.RLEG].internal=0
        result = mech_charge(a, t)
        # mech.physical.c:900-901
        self.assertEqual(result.message, "With one leg? Are you kidding?")


@patch('systems.combat.random.randint', return_value=3)
@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestChargeMechOneSided(unittest.TestCase):
    """ChargeMech one-sided branch (mech.physical.c:2416-2660)."""

    def setUp(self):
        self.a, self.t = make_pair()
        self.a.speed = 3 * MP1
        self.a.desired_speed = self.a.speed
        self.a.charge_target = self.t
        self.t.charge_target = -1

    def _expected_bth(self):
        # 5 + piloting - FindSPilotPiloting(target) + movement mods
        # (mech.physical.c:2490-2502)
        return (5 + find_pilot_piloting(self.a) -
                find_spilot_piloting(self.t) +
                calculate_attacker_movement_modifier(self.a) +
                calculate_target_movement_modifier(self.t, 0.0))

    def test_speed_gate(self, _psr, _rng):
        self.a.speed = 5.0
        result = charge_mech(self.a, self.t)
        # mech.physical.c:2427-2428 (MP1 gate)
        self.assertIn("You aren't moving fast enough to charge.",
                      result.messages)
        self.assertFalse(result.attacker_charging)

    def test_bth_formula(self, _psr, _rng):
        # Compute before the charge: a hit zeroes the attacker's speed and
        # would change the movement modifier.
        expected = self._expected_bth()
        result = charge_mech(self.a, self.t, roll=12)
        self.assertEqual(result.attacker_bth, expected)

    def test_bth_over_12_refusal_no_recycle(self, _psr, _rng):
        self.a.pilot.piloting = 20
        result = charge_mech(self.a, self.t, roll=12)
        # mech.physical.c:2505-2507: DOCHECKMA returns BEFORE any recycle
        self.assertIn(f"Charge: BTH {result.attacker_bth}\tYou choose not "
                      "to charge.", result.messages)
        self.assertEqual(self.a.sections[Location.LLEG].recycle, 0)

    def test_hit_damage_recycle_and_speed(self, _psr, _rng):
        bth = self._expected_bth()
        t_before = total_armor(self.t)
        a_before = total_armor(self.a)
        # Classic velocity damage +1, one-sided branch only
        # (mech.physical.c:2473-2481); compute before the hit zeroes speed.
        expected = int((self.a.speed * MP_PER_KPH) * (self.a.tonnage + 5)
                       / 10 + 1)
        result = charge_mech(self.a, self.t, roll=12)
        self.assertTrue(result.attacker_hit)
        self.assertEqual(result.damage_to_target, expected)
        self.assertEqual(t_before - total_armor(self.t), expected)
        # Attacker self-damage (target_tons+5)/10 (mech.physical.c:2556-2557)
        self.assertEqual(result.damage_to_attacker,
                         (self.t.tonnage + 5) // 10)
        self.assertEqual(a_before - total_armor(self.a),
                         (self.t.tonnage + 5) // 10)
        # Attacker speed zeroed (mech.physical.c:2593-2594)
        self.assertEqual(self.a.speed, 0.0)
        # All six resect sections recycled (mech.physical.c:2650-2658)
        for loc in RESECT:
            self.assertEqual(self.a.sections[loc].recycle,
                             PHYSICAL_RECYCLE_TIME)
        self.assertGreaterEqual(result.attacker_roll, bth)

    def test_miss_still_recycles(self, _psr, _rng):
        t_before = total_armor(self.t)
        result = charge_mech(self.a, self.t, roll=2)
        self.assertFalse(result.attacker_hit)
        self.assertEqual(total_armor(self.t), t_before)
        # Recycle happens WHETHER OR NOT the roll hit (mech.physical.c:2650-2658)
        for loc in RESECT:
            self.assertEqual(self.a.sections[loc].recycle,
                             PHYSICAL_RECYCLE_TIME)
        # A miss does not stop the attacker (speed zeroed only in the hit
        # block, mech.physical.c:2593-2594)
        self.assertEqual(self.a.speed, 3 * MP1)

    def test_hit_forces_both_psr_plus_2(self, psr, _rng):
        charge_mech(self.a, self.t, roll=12)
        # mech.physical.c:2578-2590
        mods = [c.kwargs['modifier'] for c in psr.call_args_list]
        self.assertEqual(mods, [2, 2])

    def test_no_damage_pull_away(self, _psr, _rng):
        # Target running away faster in the same direction -> damage <= 0
        self.t.facing = 0
        self.t.speed = 6 * MP1
        result = charge_mech(self.a, self.t)
        # mech.physical.c:2485-2487
        self.assertIn("Your target pulls away from you and you are unable "
                      "to charge it.", result.messages)
        self.assertFalse(result.attacker_charging)

    def test_busy_weap_raw_section_quirk(self, _psr, _rng):
        """C QUIRK (mech.physical.c:2417-2424): the one-sided busy-weapon
        loop indexes raw sections 0..5, which includes the CENTER TORSO."""
        self.a.weapons.append(WeaponState(section=Location.CTORSO, critical=4, recycle=9))
        self.a.sections[Location.CTORSO].criticals[4].type=i2weapon(get_weapon('IS.SmallLaser').index)
        self.a.sections[Location.CTORSO].criticals[4].data=9
        result = charge_mech(self.a, self.t, roll=12)
        self.assertIn("You have weapons recycling on your Center Torso.",
                      result.messages)
        self.assertFalse(result.attacker_charging)

    def test_jumping_target(self, _psr, _rng):
        self.t.set_status(MechStatus.JUMPING)
        result = charge_mech(self.a, self.t)
        # mech.physical.c:2444-2445
        self.assertIn("Your target is jumping, you charge underneath it.",
                      result.messages)


@patch('systems.combat.random.randint', return_value=3)
@patch('systems.physical.make_piloting_roll', return_value=PSR_OK)
class TestChargeMechMutual(unittest.TestCase):
    """ChargeMech mutual branch (mech.physical.c:1934-2413)."""

    def setUp(self):
        self.a, self.t = make_pair()
        self.a.speed = 3 * MP1
        self.t.speed = 3 * MP1
        self.a.charge_target = self.t
        self.t.charge_target = self.a

    def test_mutual_detected_and_resolved(self, _psr, _rng):
        t_before = total_armor(self.t)
        # Mutual damage has NO +1 (mech.physical.c:2153-2168): head-on,
        # cos(0-180) = -1 doubles closing speed. Compute before the hit
        # zeroes the attacker's speed.
        closing = self.a.speed - self.t.speed * math.cos(math.radians(180))
        expected = int(closing * MP_PER_KPH * (self.a.tonnage + 5) / 10)
        result = charge_mech(self.a, self.t, roll=12, target_roll=2)
        self.assertTrue(result.mutual)
        self.assertTrue(result.attacker_hit)
        self.assertFalse(result.target_hit)
        self.assertEqual(result.damage_to_target, expected)
        # At least `expected` came off (33 points into one torso destroys the
        # section and blows off the attached arm, so the sum drops further).
        self.assertGreaterEqual(t_before - total_armor(self.t), expected)
        # Both units recycle all six sections (mech.physical.c:2497-2513)
        for loc in RESECT:
            self.assertEqual(self.a.sections[loc].recycle,
                             PHYSICAL_RECYCLE_TIME)
            self.assertEqual(self.t.sections[loc].recycle,
                             PHYSICAL_RECYCLE_TIME)
        # Target's pending fields cleared (mech.physical.c:2519-2523)
        self.assertEqual(self.t.charge_target, -1)

    def test_neither_can_charge_bails_before_rolls(self, _psr, _rng):
        self.a.speed = 0.0
        self.t.speed = 0.0
        result = charge_mech(self.a, self.t)
        # mech.physical.c:2319-2326
        self.assertFalse(result.attacker_charging)
        self.assertFalse(result.target_charging)
        self.assertEqual(result.attacker_roll, 0)
        self.assertEqual(self.t.charge_target, -1)
        self.assertEqual(self.a.sections[Location.LLEG].recycle, 0)


class TestGrabClub(unittest.TestCase):
    """mech_grabclub (mech.physical.c:2700-2786) and DropClub (btmacros.h:858,
    message text as in mech.physical.c:1430-1445)."""

    def setUp(self):
        self.mech = make_mech()
        self.mech.terrain = HEAVY_FOREST

    def test_grab_default_left_arm(self):
        ok, msgs = mech_grabclub(self.mech)
        self.assertTrue(ok)
        # LARM is checked first (mech.physical.c:2740-2744)
        self.assertTrue(self.mech.sections[Location.LARM].specials &
                        CARRYING_CLUB)
        # Grabbing recycles the arm (mech.physical.c:2784)
        self.assertEqual(self.mech.sections[Location.LARM].recycle,
                         PHYSICAL_RECYCLE_TIME)

    def test_grab_specific_arm(self):
        ok, msgs = mech_grabclub(self.mech, arm='R')
        self.assertTrue(ok)
        self.assertTrue(self.mech.sections[Location.RARM].specials &
                        CARRYING_CLUB)
        self.assertIn("You reach down and yank a tree out of the ground "
                      "with your Right Arm.", msgs)

    def test_invalid_arm_option(self):
        ok, msgs = mech_grabclub(self.mech, arm='X')
        # mech.physical.c:2760-2762
        self.assertEqual(msgs, ["Invalid option for 'grabclub'"])

    def test_no_trees(self):
        self.mech.terrain = ''
        ok, msgs = mech_grabclub(self.mech)
        # mech.physical.c:2770-2772
        self.assertEqual(msgs, ["There don't appear to be any trees within "
                                "grabbing distance."])

    def test_already_carrying(self):
        mech_grabclub(self.mech)
        self.mech.sections[Location.LARM].recycle = 0
        ok, msgs = mech_grabclub(self.mech)
        # mech.physical.c:2769
        self.assertEqual(msgs, ["You're already carrying a club."])

    def test_quad_refused(self):
        self.mech.move_type = MoveType.QUAD
        ok, msgs = mech_grabclub(self.mech)
        # mech.physical.c:2724
        self.assertEqual(msgs, ["Quads can't carry a club."])

    def test_fallen_refused(self):
        self.mech.set_status(MechStatus.FALLEN)
        ok, msgs = mech_grabclub(self.mech)
        # mech.physical.c:2725-2726
        self.assertEqual(msgs, ["You can't grab a club while lying flat on "
                                "your face."])

    def test_jumping_refused(self):
        self.mech.set_status(MechStatus.JUMPING)
        ok, msgs = mech_grabclub(self.mech)
        # mech.physical.c:2727
        self.assertEqual(msgs, ["You can't grab a club while jumping!"])

    def test_axe_exclusion(self):
        add_special(self.mech, Location.RARM, Special.AXE, 3)
        ok, msgs = mech_grabclub(self.mech)
        # mech.physical.c:2732-2733
        self.assertEqual(msgs, ["You can not grab a club if you carry an "
                                "axe."])

    def test_mace_exclusion_verbatim_typo(self):
        add_special(self.mech, Location.RARM, Special.MACE, 5)
        ok, msgs = mech_grabclub(self.mech)
        # "an mace" is the C's typo, ported verbatim (mech.physical.c:2736-2737)
        self.assertEqual(msgs, ["You can not grab a club if you carry an "
                                "mace."])

    def test_hand_actuator_gate_with_emit(self):
        kill_crit(self.mech, Location.LARM, 3)
        ok, msgs = mech_grabclub(self.mech, arm='L')
        # checkGrabClubLocation (mech.physical.c:2676-2679)
        self.assertEqual(msgs, ["Your Left Arm's hand actuator is destroyed "
                                "or missing."])

    def test_no_free_arm(self):
        kill_crit(self.mech, Location.LARM, 3)
        kill_crit(self.mech, Location.RARM, 3)
        ok, msgs = mech_grabclub(self.mech)
        # mech.physical.c:2745-2748
        self.assertEqual(msgs, ["You don't have a free arm with a working "
                                "hand actuator!"])

    def test_drop_club(self):
        mech_grabclub(self.mech)
        ok, msgs = mech_grabclub(self.mech, drop=True)
        self.assertTrue(ok)
        self.assertFalse(self.mech.sections[Location.LARM].specials &
                         CARRYING_CLUB)
        # DropClub shatter text (btmacros.h:858; mech.physical.c:1436-1440)
        self.assertIn("Your club falls to the ground and shatters.", msgs)

    def test_drop_without_club(self):
        ok, msgs = mech_grabclub(self.mech, drop=True)
        # mech.physical.c:2718-2720
        self.assertEqual(msgs, ["You aren't currently carrying a club."])


if __name__ == '__main__':
    unittest.main()
