"""
Tests for systems/missile.py: MissileHitIndex, clustersize, Missile_Hit
grouping, AMS, inferno burn, and NARC pod attachment.

All dice are deterministic via explicit roll kwargs or @patch on the
module's random/roll imports - the RNG is never seeded.
"""

import unittest
from unittest.mock import patch

from core.game_loop import GameEngine
from entities.crittypes import i2ammo, i2weapon
from entities.map import HEAVY_FOREST, LIGHT_FOREST, WATER
from entities.mech import (
    AmmoMode,
    CritStatus,
    FireMode,
    Location,
    Mech,
    MechStatus,
    MoveType,
    Specials,
    SectionConfig,
    UnitType,
    WeaponState,
)
from entities.weapon import get_weapon
from systems.combat import HitGroup
from systems.ecm import (
    ANGEL_ECM_DISTURBED,
    ANGEL_ECM_PROTECTED,
    ECM_DISTURBANCE,
    ECM_PROTECTED,
    INARC_ECM_ATTACHED,
)
from systems.missile import (
    AMS_IMMUNE_AMMO_MODES,
    INARC_HAYWIRE_ATTACHED,
    INARC_HOMING_ATTACHED,
    NARC_ATTACHED,
    NARC_POD_INARC_ECM,
    NARC_POD_INARC_HAYWIRE,
    NARC_POD_INARC_HOMING,
    NARC_POD_NARC,
    NARC_POD_NONE,
    ams_defends_against,
    ams_missiles,
    apply_ams_to_salvo,
    check_all_sections,
    clustersize,
    heat_effect,
    hot_loading,
    inferno_burn,
    inferno_hit,
    locate_ams_defenses,
    missile_hit,
    missile_hit_index,
    narc_attach,
    resolve_narc_pod_type,
    water_extinguish_inferno,
)


def make_mech(name: str = "M") -> Mech:
    mech = Mech.create_test_mech(name)
    mech.set_status(MechStatus.STARTED)
    return mech


def mount_weapon(mech: Mech, weapon_name: str, section: int,
                 critical: int = 0):
    """Place a weapon crit + parallel WeaponState; returns (weapon, slot)."""
    weapon = get_weapon(weapon_name)
    slot = mech.sections[section].criticals[critical]
    slot.type = i2weapon(weapon.index)
    slot.data = 0
    slot.firemode = FireMode.NONE
    slot.ammomode = 0
    mech.weapons.append(WeaponState(
        section=int(section), critical=critical, weapon_idx=weapon.index))
    return weapon, slot


def add_ammo(mech: Mech, weapon, section: int, critical: int, rounds: int):
    slot = mech.sections[section].criticals[critical]
    slot.type = i2ammo(weapon.index)
    slot.data = rounds
    return slot


class TestMissileHitIndex(unittest.TestCase):
    """MissileHitIndex matrix (mech.combat.missile.c:119-189)."""

    def setUp(self):
        self.attacker = make_mech("Attacker")
        self.target = make_mech("Target")
        self.lrm, self.lrm_slot = mount_weapon(
            self.attacker, "IS.LRM-20", Location.LTORSO, 0)

    def _index(self, **kwargs):
        kwargs.setdefault('fresh_roll', 7)
        return missile_hit_index(
            self.attacker, self.lrm, Location.LTORSO, 0, self.target,
            **kwargs)

    def test_base_roll_no_bonus(self):
        """No bonuses: 2d6 - 2."""
        self.assertEqual(self._index(fresh_roll=7), 5)

    def test_artemis_bonus(self):
        """ARTEMIS_MODE on the firing crit: +2 on the table."""
        self.lrm_slot.ammomode = int(AmmoMode.ARTEMIS_MODE)
        self.assertEqual(self._index(fresh_roll=7), 7)

    def test_narc_bonus_via_narc_pod(self):
        """NARC_MODE + NARC pod on the target: +2."""
        self.lrm_slot.ammomode = int(AmmoMode.NARC_MODE)
        self.target.sections[Location.CTORSO].specials |= NARC_ATTACHED
        self.assertEqual(self._index(fresh_roll=7), 7)

    def test_narc_bonus_via_inarc_homing_pod(self):
        """NARC_MODE + iNARC homing pod also grants the +2."""
        self.lrm_slot.ammomode = int(AmmoMode.NARC_MODE)
        self.target.sections[Location.LARM].specials |= \
            INARC_HOMING_ATTACHED
        self.assertEqual(self._index(fresh_roll=7), 7)

    def test_narc_mode_without_pod_no_bonus(self):
        """NARC_MODE alone (no pod on target) grants nothing."""
        self.lrm_slot.ammomode = int(AmmoMode.NARC_MODE)
        self.assertEqual(self._index(fresh_roll=7), 5)

    def test_narc_pod_on_destroyed_section_ignored(self):
        """The pod scan skips destroyed sections (mech.utils.c:2447)."""
        self.lrm_slot.ammomode = int(AmmoMode.NARC_MODE)
        section = self.target.sections[Location.LARM]
        section.specials |= NARC_ATTACHED
        section.armor=section.internal=0
        self.assertEqual(self._index(fresh_roll=7), 5)

    def test_bonuses_do_not_stack(self):
        """Artemis + NARC = one +2, not +4 (:152-153)."""
        self.lrm_slot.ammomode = int(AmmoMode.ARTEMIS_MODE |
                                     AmmoMode.NARC_MODE)
        self.target.sections[Location.CTORSO].specials |= NARC_ATTACHED
        self.assertEqual(self._index(fresh_roll=7), 7)

    def test_target_ecm_negates_bonuses(self):
        """ECM-protected target loses the attacker both bonuses."""
        self.lrm_slot.ammomode = int(AmmoMode.ARTEMIS_MODE)
        self.target.status2 = ECM_PROTECTED
        self.assertEqual(self._index(fresh_roll=7), 5)

    def test_target_angel_ecm_negates_bonuses(self):
        self.lrm_slot.ammomode = int(AmmoMode.NARC_MODE)
        self.target.sections[Location.CTORSO].specials |= NARC_ATTACHED
        self.target.status2 = ANGEL_ECM_PROTECTED
        self.assertEqual(self._index(fresh_roll=7), 5)

    def test_attacker_disturbed_negates_bonuses(self):
        """ECM-disturbed attacker loses both bonuses (:144-147)."""
        self.lrm_slot.ammomode = int(AmmoMode.ARTEMIS_MODE)
        self.attacker.status2 = ECM_DISTURBANCE
        self.assertEqual(self._index(fresh_roll=7), 5)

    def test_hotload_uses_two_lowest_dice(self):
        """Hotloading: two lowest of 3d6, minus 2 (:155-163)."""
        self.lrm_slot.firemode = FireMode.HOTLOAD_MODE
        self.assertTrue(hot_loading(self.lrm, self.lrm_slot.firemode))
        # sorted (6, 2, 5) -> 2 + 5 - 2 = 5
        self.assertEqual(self._index(dice=(6, 2, 5), fresh_roll=12), 5)

    def test_non_hotload_uses_fresh_2d6_not_the_triple(self):
        """Without hotload the fresh 2d6 is used, not the 3d6 (:165-167)."""
        self.assertEqual(self._index(dice=(1, 1, 1), fresh_roll=10), 8)

    def test_streak_returns_10(self):
        """Streak vs unprotected target: row 10 outright (:169-172)."""
        streak, _ = mount_weapon(
            self.attacker, "IS.StreakSRM-6", Location.RTORSO, 0)
        idx = missile_hit_index(self.attacker, streak, Location.RTORSO, 0,
                                self.target, fresh_roll=2)
        self.assertEqual(idx, 10)

    def test_streak_vs_angel_protected_rolls_normally(self):
        streak, _ = mount_weapon(
            self.attacker, "IS.StreakSRM-6", Location.RTORSO, 0)
        self.target.status2 = ANGEL_ECM_PROTECTED
        idx = missile_hit_index(self.attacker, streak, Location.RTORSO, 0,
                                self.target, fresh_roll=7)
        self.assertEqual(idx, 5)

    def test_streak_attacker_angel_disturbed_rolls_normally(self):
        streak, _ = mount_weapon(
            self.attacker, "IS.StreakSRM-6", Location.RTORSO, 0)
        self.attacker.status2 = ANGEL_ECM_DISTURBED
        idx = missile_hit_index(self.attacker, streak, Location.RTORSO, 0,
                                self.target, fresh_roll=7)
        self.assertEqual(idx, 5)

    def test_glance_minus_four(self):
        """Glancing: -4 off the table (:174-179)."""
        self.assertEqual(self._index(fresh_roll=7, glance=True), 1)

    def test_glance_below_zero_returns_minus_one(self):
        """Glancing below 0 means exactly one missile (:181-183)."""
        self.assertEqual(self._index(fresh_roll=3, glance=True), -1)

    def test_glance_stacks_with_artemis(self):
        """Glance -4 and artemis +2 combine into one roll_inc."""
        self.lrm_slot.ammomode = int(AmmoMode.ARTEMIS_MODE)
        self.assertEqual(self._index(fresh_roll=7, glance=True), 3)

    def test_clamp_high(self):
        self.lrm_slot.ammomode = int(AmmoMode.ARTEMIS_MODE)
        self.assertEqual(self._index(fresh_roll=12), 10)

    def test_clamp_low(self):
        self.assertEqual(self._index(fresh_roll=2), 0)


class TestClustersize(unittest.TestCase):
    """Clustersize (mech.combat.h:17)."""

    def test_lrm_clusters_in_fives(self):
        """IDF + damage 1: salvo size 5."""
        self.assertEqual(clustersize(get_weapon("IS.LRM-20")), 5)

    def test_mrm_clusters_in_fives(self):
        """MRM + damage 1: salvo size 5."""
        self.assertEqual(clustersize(get_weapon("IS.MRM-30")), 5)

    def test_srm_per_missile(self):
        """SRMs (damage 2) roll a location per missile."""
        self.assertEqual(clustersize(get_weapon("IS.SRM-6")), 1)

    def test_lbx_per_pellet(self):
        """LBX pellets have no missile flags: one per pellet."""
        self.assertEqual(clustersize(get_weapon("IS.LB10-XAC")), 1)


@patch('systems.missile.determine_hit_group',
       return_value=HitGroup.FRONT)
class TestMissileHit(unittest.TestCase):
    """Missile_Hit grouping and woods absorption (:31-118)."""

    def setUp(self):
        self.attacker = make_mech("Attacker")
        self.target = make_mech("Target")
        self.lrm = get_weapon("IS.LRM-20")
        self.srm = get_weapon("IS.SRM-6")

    def test_lrm_groups_of_five(self, _mock_group):
        """10 LRMs at salvo 5 = two 5-damage groups."""
        result = missile_hit(self.attacker, self.target, self.lrm,
                             missiles_hit=10, damage_each=1, salvo_size=5,
                             location_rolls=[7, 7])
        self.assertEqual(len(result.groups), 2)
        self.assertEqual(result.groups[0],
                         (Location.CTORSO, 5, False))
        self.assertEqual(result.total_damage, 10)
        # 16 CT armor - 10
        self.assertEqual(self.target.sections[Location.CTORSO].armor, 6)

    def test_partial_last_group(self, _mock_group):
        """7 missiles at salvo 5 = groups of 5 and 2."""
        result = missile_hit(self.attacker, self.target, self.lrm,
                             missiles_hit=7, damage_each=1, salvo_size=5,
                             location_rolls=[7, 7])
        self.assertEqual([d for (_, d, _) in result.groups], [5, 2])
        self.assertEqual(result.missiles_applied, 7)

    def test_srm_rolls_location_per_missile(self, _mock_group):
        """4 SRMs at salvo 1 = four 2-damage groups, each own location."""
        result = missile_hit(self.attacker, self.target, self.srm,
                             missiles_hit=4, damage_each=2, salvo_size=1,
                             location_rolls=[7, 5, 9, 7])
        self.assertEqual(len(result.groups), 4)
        self.assertEqual([d for (_, d, _) in result.groups],
                         [2, 2, 2, 2])
        # Rolls 5 and 9 land off-CT
        locations = [loc for (loc, _, _) in result.groups]
        self.assertEqual(locations.count(Location.CTORSO), 2)

    def test_woods_light_forest_absorbs_two(self, _mock_group):
        """Light forest: -2 total damage before grouping (:61-63)."""
        self.target.terrain = LIGHT_FOREST
        self.target.z = 0
        self.target.elev = 0
        result = missile_hit(self.attacker, self.target, self.lrm,
                             missiles_hit=10, damage_each=1, salvo_size=5,
                             mod_damage_with_woods=True,
                             location_rolls=[7, 7])
        self.assertEqual(result.missiles_absorbed, 2)
        self.assertEqual(result.missiles_applied, 8)
        self.assertEqual([d for (_, d, _) in result.groups], [5, 3])
        self.assertIn("Some of the missiles are absorbed by the trees!",
                      result.messages.attacker)
        self.assertIn("The trees absorb some of the missiles",
                      result.messages.target)

    def test_woods_heavy_forest_absorbs_all(self, _mock_group):
        """Heavy forest eats a 3-missile salvo entirely (:64-72)."""
        self.target.terrain = HEAVY_FOREST
        self.target.z = 0
        self.target.elev = 0
        result = missile_hit(self.attacker, self.target, self.lrm,
                             missiles_hit=3, damage_each=1, salvo_size=5,
                             mod_damage_with_woods=True)
        self.assertEqual(result.missiles_applied, 0)
        self.assertEqual(result.total_damage, 0)
        self.assertIn("All of the missiles are absorbed by the trees!",
                      result.messages.attacker)
        self.assertEqual(self.target.sections[Location.CTORSO].armor, 16)

    def test_woods_single_missile_wording(self, _mock_group):
        self.target.terrain = HEAVY_FOREST
        self.target.z = 0
        self.target.elev = 0
        result = missile_hit(self.attacker, self.target, self.lrm,
                             missiles_hit=1, damage_each=1, salvo_size=5,
                             mod_damage_with_woods=True)
        self.assertIn("The missile is absorbed by the trees!",
                      result.messages.attacker)

    def test_woods_gate_off_by_default(self, _mock_group):
        """mudconf.btech_moddamagewithwoods off: trees absorb nothing."""
        self.target.terrain = HEAVY_FOREST
        self.target.z = 0
        self.target.elev = 0
        result = missile_hit(self.attacker, self.target, self.lrm,
                             missiles_hit=10, damage_each=1, salvo_size=5,
                             location_rolls=[7, 7])
        self.assertEqual(result.missiles_absorbed, 0)
        self.assertEqual(result.total_damage, 10)


class TestAMS(unittest.TestCase):
    """LocateAMSDefenses / AMSMissiles (:474-558)."""

    def setUp(self):
        self.attacker = make_mech("Attacker")
        self.target = make_mech("Target")
        self.target.specials |= Specials.IS_ANTI_MISSILE_TECH
        self.target.set_status(MechStatus.AMS_ENABLED)
        self.ams, self.ams_slot = mount_weapon(
            self.target, "IS.Anti-MissileSystem", Location.RTORSO, 0)
        self.ammo = add_ammo(self.target, self.ams,
                             Location.RTORSO, 1, 12)

    def test_locate_finds_and_charges_ams(self):
        defense = locate_ams_defenses(self.target)
        self.assertIsNotNone(defense)
        self.assertEqual(defense.section, Location.RTORSO)
        self.assertEqual(defense.critical, 0)
        self.assertEqual(defense.ammo_section, Location.RTORSO)
        self.assertEqual(defense.ammo_critical, 1)

    def test_locate_sets_bare_vrt_recycle(self):
        """The C uses BARE vrt (:551), not WEAPON_TICK * vrt."""
        locate_ams_defenses(self.target)
        self.assertEqual(self.ams_slot.data, self.ams.vrt)     # 10, not 20
        self.assertEqual(self.target.weapons[0].recycle, self.ams.vrt)

    def test_locate_adds_heat_immediately(self):
        """Heat charged on locate (:552), before the to-hit is consulted."""
        locate_ams_defenses(self.target)
        self.assertEqual(self.target.weap_heat, float(self.ams.heat))

    def test_locate_gate_no_tech(self):
        self.target.specials &= ~Specials.IS_ANTI_MISSILE_TECH
        self.assertIsNone(locate_ams_defenses(self.target))

    def test_locate_gate_not_started(self):
        self.target.clear_status(MechStatus.STARTED)
        self.assertIsNone(locate_ams_defenses(self.target))

    def test_locate_gate_ams_disabled(self):
        self.target.clear_status(MechStatus.AMS_ENABLED)
        self.assertIsNone(locate_ams_defenses(self.target))

    def test_locate_skips_recycling_ams(self):
        self.ams_slot.data = 5
        self.assertIsNone(locate_ams_defenses(self.target))

    def test_locate_skips_nonfunctional_ams_first_match_wins(self):
        """Scan takes the FIRST functional AMS, skipping dead ones."""
        # A destroyed AMS earlier in the scan order (LARM = section 0)
        _, dead_slot = mount_weapon(
            self.target, "IS.Anti-MissileSystem", Location.LARM, 0)
        dead_slot.firemode |= FireMode.DESTROYED_MODE
        defense = locate_ams_defenses(self.target)
        self.assertIsNotNone(defense)
        self.assertEqual(defense.section, Location.RTORSO)

    def test_locate_no_arc_check(self):
        """AMS defends regardless of direction: locate takes no attacker
        or bearing at all (mech.combat.missile.c:525-535)."""
        defense = locate_ams_defenses(self.target)
        self.assertIsNotNone(defense)

    def test_locate_no_ammo_returns_none_without_charging(self):
        self.ammo.data = 0
        self.assertIsNone(locate_ams_defenses(self.target))
        self.assertEqual(self.ams_slot.data, 0)
        self.assertEqual(self.target.weap_heat, 0.0)

    def test_ams_missiles_is_1d6(self):
        """IS AMS shoots down 1d6 (:493-496)."""
        with patch('systems.missile.roll_1d6', return_value=4):
            result = ams_missiles(
                self.attacker, self.target, 10, self.ams,
                Location.RTORSO, 1, los=1, missiles_did_hit=True)
        self.assertEqual(result.shot_down, 4)
        self.assertEqual(self.ammo.data, 8)

    def test_ams_missiles_clan_is_2d6(self):
        """Clan AMS shoots down 2d6 (:493-494)."""
        clan_ams = get_weapon("CL.Anti-MissileSystem")
        with patch('systems.missile.roll_2d6', return_value=9):
            result = ams_missiles(
                self.attacker, self.target, 20, clan_ams,
                Location.RTORSO, 1, los=1, missiles_did_hit=True)
        self.assertEqual(result.shot_down, 9)

    def test_ams_missiles_capped_at_incoming(self):
        result = ams_missiles(
            self.attacker, self.target, 2, self.ams,
            Location.RTORSO, 1, los=1, missiles_did_hit=True,
            shots_roll=5)
        self.assertEqual(result.shot_down, 2)
        self.assertEqual(self.ammo.data, 10)

    def test_ams_ammo_floors_at_zero_return_not_recapped(self):
        """Ammo floors at 0 but the return is NOT re-capped (:501-504)."""
        self.ammo.data = 3
        result = ams_missiles(
            self.attacker, self.target, 8, self.ams,
            Location.RTORSO, 1, los=1, missiles_did_hit=True,
            shots_roll=5)
        self.assertEqual(self.ammo.data, 0)
        self.assertEqual(result.shot_down, 5)

    def test_ams_fires_even_when_salvo_misses(self):
        """Miss: ammo still spent, flavor message, 0 returned (:506-510)."""
        result = ams_missiles(
            self.attacker, self.target, 10, self.ams,
            Location.RTORSO, 1, los=1, missiles_did_hit=False,
            shots_roll=4)
        self.assertEqual(result.shot_down, 0)
        self.assertEqual(self.ammo.data, 8)
        self.assertIn(
            "Your Anti-Missile System activates and shoots at the "
            "incoming missiles!", result.messages.target)

    def test_ams_skips_swarm_swarm1_mine(self):
        """AMS never engages SWARM/SWARM1/MINE salvos (:232-234)."""
        self.assertFalse(ams_defends_against(int(AmmoMode.SWARM_MODE)))
        self.assertFalse(ams_defends_against(int(AmmoMode.SWARM1_MODE)))
        self.assertFalse(ams_defends_against(int(AmmoMode.MINE_MODE)))
        self.assertTrue(ams_defends_against(0))
        self.assertTrue(ams_defends_against(int(AmmoMode.ARTEMIS_MODE)))

    def test_apply_ams_partial(self):
        """Partial shoot-down: pair of %d messages, hit reduced (:337-349)."""
        hit, messages = apply_ams_to_salvo(12, 3, los=1)
        self.assertEqual(hit, 9)
        self.assertIn("The target shoots down 3 of your missiles!",
                      messages.attacker)
        self.assertIn("Your Anti-Missile System activates and shoots "
                      "down 3 incoming missiles!", messages.target)

    def test_apply_ams_all_shot_down(self):
        hit, messages = apply_ams_to_salvo(4, 6, los=1)
        self.assertEqual(hit, 0)
        self.assertIn("All of your missiles are shot down by the target!",
                      messages.attacker)
        self.assertIn("Your Anti-Missile System activates and shoots all "
                      "the incoming missiles!", messages.target)

    def test_apply_ams_all_message_los_gated(self):
        """Only the all-shot-down attacker message is LOS-gated."""
        hit, messages = apply_ams_to_salvo(4, 6, los=0)
        self.assertEqual(hit, 0)
        self.assertEqual(messages.attacker, [])
        self.assertEqual(len(messages.target), 1)

    def test_apply_ams_nothing_shot_down(self):
        hit, messages = apply_ams_to_salvo(8, 0, los=1)
        self.assertEqual(hit, 8)
        self.assertEqual(messages.attacker, [])
        self.assertEqual(messages.target, [])


class TestInferno(unittest.TestCase):
    """Inferno_Hit / heat_effect / inferno_burn (misc.c:160-206,
    fire.c:20-42, 146-170)."""

    def setUp(self):
        self.engine = GameEngine()
        self.attacker = make_mech("Attacker")
        self.target = make_mech("Target")

    def test_hmod_and_burn_duration(self):
        """5 missiles: hmod 3, burn 3 * 180 = 540 s."""
        result = inferno_hit(self.engine, self.attacker, self.target,
                             missiles=5, los=1)
        self.assertEqual(result.burn_time, 540)
        self.assertTrue(self.target.has_crit_status(CritStatus.JELLIED))
        self.assertEqual(self.target._burn_event.tick,
                         self.engine.tick + 540)

    def test_single_missile_burns_180(self):
        result = inferno_hit(self.engine, self.attacker, self.target,
                             missiles=1, los=1)
        self.assertEqual(result.burn_time, 180)

    def test_first_hit_messages(self):
        result = inferno_hit(self.engine, self.attacker, self.target,
                             missiles=2, los=1)
        self.assertIn("%ch%crYou are sprayed with burning jelly!%cn",
                      result.messages.target)
        self.assertIn("suddenly bursts into flames!",
                      result.messages.broadcast)

    def test_rejelly_messages_and_added_time(self):
        """Re-jelly ADDS the new time to the REMAINING burn (fire.c:39-41)."""
        inferno_hit(self.engine, self.attacker, self.target,
                    missiles=1, los=1)                       # 180 s
        self.engine.run_ticks(30)                            # 150 left
        result = inferno_hit(self.engine, self.attacker, self.target,
                             missiles=1, los=1)              # +180
        self.assertIn("%ch%crMore burning jelly joins the flames!%cn",
                      result.messages.target)
        self.assertIn("burns a bit more brightly.",
                      result.messages.broadcast)
        self.assertEqual(self.target._burn_event.tick,
                         self.engine.tick + 150 + 180)

    def test_no_normal_damage(self):
        """An inferno hit deals NO armor/internal damage (:362-371)."""
        before = self.target.total_armor()
        inferno_hit(self.engine, self.attacker, self.target,
                    missiles=6, los=1)
        self.assertEqual(self.target.total_armor(), before)

    def test_burn_ends_and_clears_jellied(self):
        inferno_burn(self.engine, self.target, 5)
        self.assertTrue(self.target.has_crit_status(CritStatus.JELLIED))
        self.engine.run_ticks(6)
        self.assertFalse(self.target.has_crit_status(CritStatus.JELLIED))
        self.assertIsNone(self.target._burn_event)

    def test_water_extinguishes(self):
        """Deep water puts the fire out (fire.c:146-170)."""
        inferno_burn(self.engine, self.target, 600)
        self.target.terrain = WATER
        self.target.z = -2
        result = water_extinguish_inferno(self.engine, self.target)
        self.assertTrue(result.extinguished)
        self.assertFalse(self.target.has_crit_status(CritStatus.JELLIED))
        self.assertIn("The flames extinguish in a roar of steam!",
                      result.messages.target)
        # The canceled burn event never clears the flag again
        self.engine.run_ticks(601)
        self.assertFalse(self.target.has_crit_status(CritStatus.JELLIED))

    def test_depth_one_standing_keeps_burning(self):
        """elev -1 while standing: shooter just wastes missiles."""
        inferno_burn(self.engine, self.target, 600)
        self.target.terrain = WATER
        self.target.z = -1
        self.target.elev = 1  # Water predicate uses signed terrain elevation.
        result = water_extinguish_inferno(self.engine, self.target)
        self.assertFalse(result.extinguished)
        self.assertTrue(self.target.has_crit_status(CritStatus.JELLIED))

    def test_depth_one_fallen_extinguishes(self):
        inferno_burn(self.engine, self.target, 600)
        self.target.terrain = WATER
        self.target.z = -1
        self.target.elev = 1  # Water predicate uses signed terrain elevation.
        self.target.set_status(MechStatus.FALLEN)
        result = water_extinguish_inferno(self.engine, self.target)
        self.assertTrue(result.extinguished)

    def test_water_hit_extinguishes_immediately(self):
        """Inferno_Hit calls water_extinguish_inferno itself (:205)."""
        self.target.terrain = WATER
        self.target.z = -2
        result = inferno_hit(self.engine, self.attacker, self.target,
                             missiles=4, los=1)
        self.assertTrue(result.extinguished)
        self.assertFalse(self.target.has_crit_status(CritStatus.JELLIED))

    def test_vehicle_explodes_on_roll_over_8(self):
        """Vehicle arm: 2d6 > 8 destroys the unit (misc.c:174-181)."""
        vehicle = make_mech("Tank")
        vehicle.unit_type = UnitType.VEH_GROUND
        vehicle.move_type = MoveType.TRACK
        result = heat_effect(self.engine, self.attacker, vehicle,
                             heatdam=30, from_inferno=True,
                             explosion_roll=9)
        self.assertTrue(result.exploded)
        self.assertTrue(vehicle.has_status(MechStatus.DESTROYED))
        self.assertIn("The heat's too much for your vehicle! It blows up!",
                      result.messages.target)
        self.assertIn("explodes!", result.messages.broadcast)

    def test_vehicle_survives_roll_of_8(self):
        vehicle = make_mech("Tank")
        vehicle.unit_type = UnitType.VEH_GROUND
        vehicle.move_type = MoveType.TRACK
        result = heat_effect(self.engine, self.attacker, vehicle,
                             heatdam=30, from_inferno=True,
                             explosion_roll=8)
        self.assertFalse(result.exploded)
        self.assertFalse(vehicle.has_status(MechStatus.DESTROYED))
        self.assertFalse(vehicle.has_crit_status(CritStatus.JELLIED))

    def test_immobile_vehicle_burns_instead(self):
        """MOVE_NONE units take the burn arm, not the explosion arm."""
        turret = make_mech("Turret")
        turret.unit_type = UnitType.VEH_GROUND
        turret.move_type = MoveType.NONE
        result = heat_effect(self.engine, self.attacker, turret,
                             heatdam=30, from_inferno=True)
        self.assertFalse(result.exploded)
        self.assertEqual(result.burn_time, 180)
        self.assertTrue(turret.has_crit_status(CritStatus.JELLIED))


@patch('systems.combat.determine_hit_group',
       return_value=HitGroup.FRONT)
class TestNarcPods(unittest.TestCase):
    """NARC pod resolution and attachment (:212-300)."""

    def setUp(self):
        self.attacker = make_mech("Attacker")
        self.target = make_mech("Target")
        self.narc = get_weapon("IS.NarcBeacon")
        self.inarc = get_weapon("IS.iNarcBeacon")

    def test_pod_type_resolution(self, _mock_group):
        self.assertEqual(resolve_narc_pod_type(self.narc, 0),
                         NARC_POD_NARC)
        # NARC_MODE = explosive rounds, not a pod
        self.assertEqual(
            resolve_narc_pod_type(self.narc, int(AmmoMode.NARC_MODE)),
            NARC_POD_NONE)
        self.assertEqual(resolve_narc_pod_type(self.inarc, 0),
                         NARC_POD_INARC_HOMING)
        self.assertEqual(
            resolve_narc_pod_type(self.inarc,
                                  int(AmmoMode.INARC_HAYWIRE_MODE)),
            NARC_POD_INARC_HAYWIRE)
        self.assertEqual(
            resolve_narc_pod_type(self.inarc,
                                  int(AmmoMode.INARC_ECM_MODE)),
            NARC_POD_INARC_ECM)
        self.assertEqual(
            resolve_narc_pod_type(self.inarc,
                                  int(AmmoMode.INARC_EXPLO_MODE)),
            NARC_POD_NONE)
        # Non-missile weapons never fire pods
        self.assertEqual(
            resolve_narc_pod_type(get_weapon("IS.MediumLaser"), 0),
            NARC_POD_NONE)

    def test_narc_attach_sets_section_bit(self, _mock_group):
        result = narc_attach(self.attacker, self.target, NARC_POD_NARC,
                             did_hit=True, los=1, location_roll=7)
        self.assertTrue(result.attached)
        self.assertEqual(result.location, Location.CTORSO)
        self.assertTrue(self.target.sections[Location.CTORSO].specials &
                        NARC_ATTACHED)
        self.assertIn(
            "A NARC Beacon has been attached to your Center Torso!",
            result.messages.target)
        self.assertIn(
            "Your NARC Beacon attaches to the target's Center Torso!",
            result.messages.attacker)
        self.assertTrue(check_all_sections(self.target, NARC_ATTACHED))

    def test_inarc_homing_attach(self, _mock_group):
        result = narc_attach(self.attacker, self.target,
                             NARC_POD_INARC_HOMING,
                             did_hit=True, los=1, location_roll=7)
        self.assertTrue(self.target.sections[Location.CTORSO].specials &
                        INARC_HOMING_ATTACHED)
        self.assertTrue(result.attached)

    def test_inarc_haywire_attach(self, _mock_group):
        result = narc_attach(self.attacker, self.target,
                             NARC_POD_INARC_HAYWIRE,
                             did_hit=True, los=1, location_roll=7)
        self.assertTrue(self.target.sections[Location.CTORSO].specials &
                        INARC_HAYWIRE_ATTACHED)
        self.assertIn("Your targetting system goes a bit haywire!",
                      result.messages.target)

    def test_inarc_ecm_attach_runs_check_ecm(self, _mock_group):
        with patch('systems.missile.check_ecm') as mock_check:
            result = narc_attach(self.attacker, self.target,
                                 NARC_POD_INARC_ECM,
                                 did_hit=True, los=1, location_roll=7)
        self.assertTrue(self.target.sections[Location.CTORSO].specials &
                        INARC_ECM_ATTACHED)
        mock_check.assert_called_once_with(self.target)
        self.assertTrue(result.attached)

    def test_miss_message(self, _mock_group):
        result = narc_attach(self.attacker, self.target, NARC_POD_NARC,
                             did_hit=False, los=1)
        self.assertFalse(result.attached)
        self.assertIn("Your NARC Beacon flies off into the distance.",
                      result.messages.attacker)
        self.assertFalse(check_all_sections(self.target, NARC_ATTACHED))

    def test_pod_shot_down_by_ams(self, _mock_group):
        """A pod counts as incoming=1; any shoot-down stops it (:243-253)."""
        result = narc_attach(self.attacker, self.target, NARC_POD_NARC,
                             did_hit=True, los=1, ams_shot_down=1)
        self.assertFalse(result.attached)
        self.assertTrue(result.shot_down)
        self.assertIn("The pod is shot down by the target!",
                      result.messages.attacker)
        self.assertIn("Your Anti-Missile System activates and shoots "
                      "down the incoming pod!", result.messages.target)
        self.assertFalse(check_all_sections(self.target, NARC_ATTACHED))


if __name__ == '__main__':
    unittest.main()
