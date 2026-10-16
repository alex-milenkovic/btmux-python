"""
Tests for the critical hit effects system.

Tests cover:
- Equipment critical effects (engine, gyro, sensors, etc.)
- Ammo explosion system
- CASE technology
- Integration with combat system
"""

import unittest
from unittest.mock import patch, MagicMock

from entities.crittypes import Special, i2ammo, i2special, i2weapon
from entities.mech import (
    Mech, Location, MechStatus, CritStatus, SectionConfig,
    FireMode, Specials, MoveType, WeaponState
)
from entities.weapon import get_weapon
from systems.criticals import (
    EquipmentType,
    CriticalResult,
    AmmoExplosionResult,
    apply_ammo_critical,
    apply_critical_to_slot,
    apply_weapon_critical,
    destroy_weapon,
    find_first_weapon_crit,
    handle_engine_critical,
    handle_gyro_critical,
    handle_sensors_critical,
    handle_cockpit_critical,
    handle_life_support_critical,
    handle_shoulder_hip_critical,
    handle_actuator_critical,
    handle_heat_sink_critical,
    handle_jump_jet_critical,
    handle_targeting_computer_critical,
    handle_critical_hit,
    ammo_explosion,
    calculate_ammo_damage,
    check_and_apply_criticals,
    recalculate_mech_stats,
    get_equipment_name,
    is_arm_location,
    is_leg_location,
    ENGINE_HEAT_PER_HIT,
    ENGINE_HITS_TO_DESTROY,
    GYRO_PILOTING_MODIFIER,
    SENSORS_BTH_MODIFIER_1,
    SENSORS_BTH_MODIFIER_2,
    SHOULDER_ARM_BTH_MODIFIER,
    HIP_PILOTING_MODIFIER,
    ACTUATOR_BTH_MODIFIER,
    AMMO_EXPLOSION_PILOT_DAMAGE,
    NO_EQUIPMENT_TYPE,
)


class TestEquipmentNames(unittest.TestCase):
    """Tests for equipment name lookup."""

    def test_shoulder_in_arm(self):
        """Shoulder/hip in arm location should be 'Shoulder'."""
        name = get_equipment_name(EquipmentType.SHOULDER_OR_HIP, Location.LARM)
        self.assertEqual(name, "Shoulder")

    def test_hip_in_leg(self):
        """Shoulder/hip in leg location should be 'Hip'."""
        name = get_equipment_name(EquipmentType.SHOULDER_OR_HIP, Location.LLEG)
        self.assertEqual(name, "Hip")

    def test_hand_actuator(self):
        """Hand/foot actuator in arm should be 'Hand Actuator'."""
        name = get_equipment_name(EquipmentType.HAND_OR_FOOT_ACTUATOR, Location.RARM)
        self.assertEqual(name, "Hand Actuator")

    def test_foot_actuator(self):
        """Hand/foot actuator in leg should be 'Foot Actuator'."""
        name = get_equipment_name(EquipmentType.HAND_OR_FOOT_ACTUATOR, Location.RLEG)
        self.assertEqual(name, "Foot Actuator")


class TestLocationHelpers(unittest.TestCase):
    """Tests for location helper functions."""

    def test_is_arm_location(self):
        """Test arm location detection."""
        self.assertTrue(is_arm_location(Location.LARM))
        self.assertTrue(is_arm_location(Location.RARM))
        self.assertFalse(is_arm_location(Location.LLEG))
        self.assertFalse(is_arm_location(Location.CTORSO))

    def test_is_leg_location(self):
        """Test leg location detection."""
        self.assertTrue(is_leg_location(Location.LLEG))
        self.assertTrue(is_leg_location(Location.RLEG))
        self.assertFalse(is_leg_location(Location.LARM))
        self.assertFalse(is_leg_location(Location.CTORSO))


class TestEngineCritical(unittest.TestCase):
    """Tests for engine critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_first_engine_hit(self):
        """First engine hit adds +5 heat."""
        result = handle_engine_critical(self.mech, Location.CTORSO)

        self.assertTrue(result.effect_applied)
        self.assertFalse(result.mech_destroyed)
        self.assertEqual(self.mech.engine_hits, 1)
        self.assertEqual(self.mech.engine_heat, ENGINE_HEAT_PER_HIT)

    def test_second_engine_hit(self):
        """Second engine hit adds another +5 heat."""
        self.mech.engine_hits = 1
        self.mech.engine_heat = ENGINE_HEAT_PER_HIT

        result = handle_engine_critical(self.mech, Location.CTORSO)

        self.assertTrue(result.effect_applied)
        self.assertFalse(result.mech_destroyed)
        self.assertEqual(self.mech.engine_hits, 2)
        self.assertEqual(self.mech.engine_heat, ENGINE_HEAT_PER_HIT * 2)

    def test_third_engine_hit_destroys_mech(self):
        """Third engine hit destroys the mech."""
        self.mech.engine_hits = 2
        self.mech.engine_heat = ENGINE_HEAT_PER_HIT * 2

        result = handle_engine_critical(self.mech, Location.CTORSO)

        self.assertTrue(result.effect_applied)
        self.assertTrue(result.mech_destroyed)
        self.assertEqual(self.mech.engine_hits, ENGINE_HITS_TO_DESTROY)
        self.assertTrue(self.mech.has_status(MechStatus.DESTROYED))


class TestGyroCritical(unittest.TestCase):
    """Tests for gyro critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.pilot_skill_base = 0

    def test_first_gyro_hit(self):
        """First gyro hit adds +3 piloting and requires check."""
        result = handle_gyro_critical(self.mech, Location.CTORSO)

        self.assertTrue(result.effect_applied)
        self.assertTrue(result.piloting_check_required)
        self.assertTrue(self.mech.has_crit_status(CritStatus.GYRO_DAMAGED))
        self.assertFalse(self.mech.has_crit_status(CritStatus.GYRO_DESTROYED))
        self.assertEqual(self.mech.pilot_skill_base, GYRO_PILOTING_MODIFIER)

    def test_second_gyro_hit_destroys(self):
        """Second gyro hit destroys gyro."""
        self.mech.set_crit_status(CritStatus.GYRO_DAMAGED)

        result = handle_gyro_critical(self.mech, Location.CTORSO)

        self.assertTrue(result.effect_applied)
        self.assertTrue(self.mech.has_crit_status(CritStatus.GYRO_DESTROYED))

    def test_hit_on_destroyed_gyro(self):
        """Hit on already-destroyed gyro just reports it."""
        self.mech.set_crit_status(CritStatus.GYRO_DAMAGED)
        self.mech.set_crit_status(CritStatus.GYRO_DESTROYED)

        result = handle_gyro_critical(self.mech, Location.CTORSO)

        self.assertFalse(result.effect_applied)
        self.assertIn("already", result.message.lower())


class TestSensorsCritical(unittest.TestCase):
    """Tests for sensor critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.lrs_range = 30
        self.mech.tac_range = 15
        self.mech.scan_range = 20
        self.mech.base_to_hit = 0

    def test_first_sensor_hit(self):
        """First sensor hit halves ranges and adds +2 BTH."""
        result = handle_sensors_critical(self.mech, Location.HEAD)

        self.assertTrue(result.effect_applied)
        self.assertTrue(self.mech.has_crit_status(CritStatus.SENSORS_DAMAGED))
        self.assertEqual(self.mech.lrs_range, 15)  # Halved from 30
        self.assertEqual(self.mech.tac_range, 7)   # Halved from 15
        self.assertEqual(self.mech.scan_range, 10) # Halved from 20
        self.assertEqual(self.mech.base_to_hit, SENSORS_BTH_MODIFIER_1)

    def test_second_sensor_hit_blinds(self):
        """Second sensor hit blinds pilot (+75 BTH)."""
        self.mech.set_crit_status(CritStatus.SENSORS_DAMAGED)
        self.mech.lrs_range = 15
        self.mech.base_to_hit = SENSORS_BTH_MODIFIER_1

        result = handle_sensors_critical(self.mech, Location.HEAD)

        self.assertTrue(result.effect_applied)
        self.assertEqual(self.mech.lrs_range, 0)
        self.assertEqual(self.mech.tac_range, 0)
        self.assertEqual(self.mech.scan_range, 0)
        # BTH should now be +75 instead of +2
        self.assertEqual(self.mech.base_to_hit, SENSORS_BTH_MODIFIER_2)


class TestCockpitCritical(unittest.TestCase):
    """Tests for cockpit critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_cockpit_critical_kills_pilot(self):
        """Cockpit critical instantly kills pilot and destroys mech."""
        result = handle_cockpit_critical(self.mech, Location.HEAD)

        self.assertTrue(result.effect_applied)
        self.assertTrue(result.pilot_killed)
        self.assertTrue(result.mech_destroyed)
        self.assertEqual(self.mech.pilot_hits, 0)  # cockpit death does not synthesize injuries
        self.assertIsNone(self.mech.pilot)
        self.assertTrue(self.mech.has_status(MechStatus.DESTROYED))


class TestLifeSupportCritical(unittest.TestCase):
    """Tests for life support critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_life_support_destroyed(self):
        """Life support critical sets flag."""
        result = handle_life_support_critical(self.mech, Location.HEAD)

        self.assertTrue(result.effect_applied)
        self.assertTrue(self.mech.has_crit_status(CritStatus.LIFE_SUPPORT_DESTROYED))

    def test_already_destroyed_life_support(self):
        """Every life support critical repeats the source destroyed notice."""
        self.mech.set_crit_status(CritStatus.LIFE_SUPPORT_DESTROYED)

        result = handle_life_support_critical(self.mech, Location.HEAD)

        self.assertTrue(result.effect_applied)
        self.assertEqual("Your life support has been destroyed!", result.message)
        self.assertTrue(self.mech.has_crit_status(CritStatus.LIFE_SUPPORT_DESTROYED))


class TestShoulderHipCritical(unittest.TestCase):
    """Tests for shoulder/hip critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.pilot_skill_base = 0
        self.mech.max_speed = 64.5

    def test_shoulder_critical(self):
        """Shoulder critical adds +4 BTH for arm weapons."""
        result = handle_shoulder_hip_critical(self.mech, Location.LARM)

        self.assertTrue(result.effect_applied)
        self.assertEqual(result.equipment_name, "Shoulder")
        self.assertEqual(self.mech.sections[Location.LARM].basetohit, SHOULDER_ARM_BTH_MODIFIER)

    def test_first_hip_critical(self):
        """First hip critical halves speed and adds +2 piloting."""
        result = handle_shoulder_hip_critical(self.mech, Location.LLEG)

        self.assertTrue(result.effect_applied)
        self.assertEqual(result.equipment_name, "Hip")
        self.assertTrue(result.piloting_check_required)
        self.assertTrue(self.mech.has_crit_status(CritStatus.HIP_DAMAGED))
        self.assertEqual(self.mech.max_speed, 64.5 / 2)
        self.assertEqual(self.mech.pilot_skill_base, HIP_PILOTING_MODIFIER)

    def test_second_hip_critical_biped(self):
        """Second hip critical destroys hip for bipeds."""
        self.mech.set_crit_status(CritStatus.HIP_DAMAGED)
        self.mech.move_type = MoveType.BIPED

        result = handle_shoulder_hip_critical(self.mech, Location.RLEG)

        self.assertTrue(result.effect_applied)
        self.assertTrue(self.mech.has_crit_status(CritStatus.HIP_DESTROYED))


class TestActuatorCritical(unittest.TestCase):
    """Tests for actuator critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.pilot_skill_base = 0
        self.mech.max_speed = 64.5

    def test_arm_actuator_critical(self):
        """Arm actuator critical adds +1 BTH."""
        result = handle_actuator_critical(self.mech, Location.LARM, EquipmentType.UPPER_ACTUATOR)

        self.assertTrue(result.effect_applied)
        self.assertEqual(self.mech.sections[Location.LARM].basetohit, ACTUATOR_BTH_MODIFIER)

    def test_leg_actuator_critical(self):
        """Leg actuator critical reduces MP and adds piloting modifier."""
        original_speed = self.mech.max_speed

        result = handle_actuator_critical(self.mech, Location.LLEG, EquipmentType.LOWER_ACTUATOR)

        self.assertTrue(result.effect_applied)
        self.assertTrue(result.piloting_check_required)
        self.assertLess(self.mech.max_speed, original_speed)


class TestHeatSinkCritical(unittest.TestCase):
    """Tests for heat sink critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.num_sinks = 10

    def test_heat_sink_destroyed(self):
        """Heat sink critical removes one sink."""
        result = handle_heat_sink_critical(self.mech, Location.CTORSO)

        self.assertTrue(result.effect_applied)
        self.assertEqual(self.mech.num_sinks, 9)


class TestJumpJetCritical(unittest.TestCase):
    """Tests for jump jet critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.jump_mp = 5

    def test_jump_jet_destroyed(self):
        """Jump jet critical reduces jump MP."""
        result = handle_jump_jet_critical(self.mech, Location.LTORSO)

        self.assertTrue(result.effect_applied)
        self.assertEqual(self.mech.jump_mp, 4)

    def test_last_jump_jet_while_jumping(self):
        """Losing last jump jet while jumping causes fall."""
        self.mech.jump_mp = 1
        self.mech.set_status(MechStatus.JUMPING)

        result = handle_jump_jet_critical(self.mech, Location.LTORSO)

        self.assertTrue(result.effect_applied)
        self.assertEqual(self.mech.jump_mp, 0)
        self.assertTrue(result.fell)


class TestTargetingComputerCritical(unittest.TestCase):
    """Tests for targeting computer critical effects."""

    def setUp(self):
        self.mech = Mech.create_test_mech()

    def test_tc_destroyed(self):
        """TC critical sets destroyed flag."""
        result = handle_targeting_computer_critical(self.mech, Location.CTORSO)

        self.assertTrue(result.effect_applied)
        self.assertTrue(self.mech.has_crit_status(CritStatus.TC_DESTROYED))


class TestAmmoDamageCalculation(unittest.TestCase):
    """Tests for ammo explosion damage calculation."""

    def test_single_shot_ammo(self):
        """Single-shot weapon ammo damage."""
        damage = calculate_ammo_damage(ammo_rounds=10, weapon_damage=5, missiles_per_shot=1)
        self.assertEqual(damage, 50)

    def test_missile_ammo(self):
        """Missile weapon ammo damage includes missiles per shot."""
        # LRM-10: 10 missiles * 1 damage per missile = 10 damage per shot
        damage = calculate_ammo_damage(ammo_rounds=12, weapon_damage=1, missiles_per_shot=10)
        self.assertEqual(damage, 120)


class TestAmmoExplosion(unittest.TestCase):
    """Tests for ammo explosion effects.

    Every call passes an attacker: the C's ammo_explosion bails out right after
    destroying the bin when there is none (mech.update.c:1156-1158), and both
    real callers always have one - HandleMechCrit forwards the attacker
    (crit.c:1711) and the heat cook-off passes the mech itself
    (mech.update.c:1245).
    """

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.mech.pilot_hits = 0
        self.mech.heat = 0
        self.attacker = Mech.create_test_mech()

    def test_gauss_ammo_no_explosion(self):
        """Gauss ammo doesn't explode."""
        result = ammo_explosion(
            self.mech, Location.RTORSO,
            ammo_rounds=8, weapon_damage=15,
            is_gauss=True, attacker=self.attacker
        )

        self.assertEqual(result.damage, 0)
        self.assertIn("no explosion", result.message.lower())

    def test_normal_ammo_explosion(self):
        """Normal ammo explosion damages internals and pilot."""
        result = ammo_explosion(
            self.mech, Location.RTORSO,
            ammo_rounds=10, weapon_damage=5, attacker=self.attacker
        )

        self.assertEqual(result.damage, 50)
        self.assertEqual(result.pilot_damage, AMMO_EXPLOSION_PILOT_DAMAGE)
        self.assertEqual(self.mech.pilot_hits, AMMO_EXPLOSION_PILOT_DAMAGE)

    def test_explosion_bypasses_armor(self):
        """Ammo explosion damage is internal only, armour untouched.

        Reference: mech.update.c:1167-1170 passes damage = -1 and
        intDamage = damage to DamageMech (args 8/9 of the signature at
        mech.damage.c:334-343), so the armour branch at mech.damage.c:702 is
        never entered.
        """
        section = self.mech.sections[Location.RTORSO]
        armor_before = section.armor
        rear_before = section.rear
        internal_before = section.internal

        ammo_explosion(
            self.mech, Location.RTORSO,
            ammo_rounds=1, weapon_damage=3, attacker=self.attacker
        )

        self.assertEqual(section.armor, armor_before)
        self.assertEqual(section.rear, rear_before)
        self.assertEqual(section.internal, internal_before - 3)

    def test_explosion_needs_an_attacker_to_deal_damage(self):
        """With no attacker the C stops after destroying the bin.

        Reference: mech.update.c:1156-1158 - DestroyPart then
        `if(!attacker) return;`, ahead of the inferno heat, the DamageMech call
        and the pilot injury.
        """
        section = self.mech.sections[Location.RTORSO]
        internal_before = section.internal

        result = ammo_explosion(
            self.mech, Location.RTORSO,
            ammo_rounds=10, weapon_damage=5
        )

        self.assertEqual(section.internal, internal_before)
        self.assertEqual(result.pilot_damage, 0)
        self.assertEqual(self.mech.pilot_hits, 0)

    @patch('systems.criticals.BTECH_INFERNO_PENALTY', 1)
    def test_inferno_ammo_explosion(self):
        """Inferno ammo adds heat and deals half damage."""
        result = ammo_explosion(
            self.mech, Location.RTORSO,
            ammo_rounds=10, weapon_damage=4,
            is_inferno=True, attacker=self.attacker
        )

        self.assertTrue(result.was_inferno)
        self.assertEqual(result.heat_added, 30.0)
        self.assertEqual(result.damage, 20)  # Half of 40
        self.assertEqual(self.mech.weap_heat, 30.0)  # C adds retained weapon heat.

    def test_case_contains_explosion(self):
        """CASE technology contains explosion."""
        self.mech.sections[Location.RTORSO].config |= SectionConfig.CASE_TECH

        result = ammo_explosion(
            self.mech, Location.RTORSO,
            ammo_rounds=10, weapon_damage=5, attacker=self.attacker
        )

        self.assertTrue(result.contained_by_case)
        self.assertEqual(self.mech.sections[Location.CTORSO].internal, self.mech.sections[Location.CTORSO].internal_orig)

    def test_case_ii_does_not_replace_c_case_transfer_gate(self):
        """C internal transfer checks CASE_TECH, not CASEII_TECH (damage.c:763)."""
        self.mech.sections[Location.RTORSO].config |= SectionConfig.CASEII_TECH

        result = ammo_explosion(
            self.mech, Location.RTORSO,
            ammo_rounds=10, weapon_damage=5, attacker=self.attacker
        )

        self.assertFalse(result.contained_by_case)
        self.assertEqual(result.damage, 50)
        self.assertLess(self.mech.sections[Location.CTORSO].internal, self.mech.sections[Location.CTORSO].internal_orig)


class TestHandleCriticalHit(unittest.TestCase):
    """Tests for main critical hit handler."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_handle_engine_critical(self):
        """Main handler routes engine critical correctly."""
        result = handle_critical_hit(
            self.mech, Location.CTORSO, EquipmentType.ENGINE
        )

        self.assertTrue(result.effect_applied)
        self.assertEqual(result.equipment_type, EquipmentType.ENGINE)

    @patch('systems.piloting.make_piloting_roll')
    def test_handle_gyro_with_piloting_check(self, mock_roll):
        """An attacker triggers the first gyro hit's piloting check."""
        mock_roll.return_value = MagicMock(success=True)
        result = handle_critical_hit(self.mech, Location.CTORSO, EquipmentType.GYRO,
                                     attacker=self.mech)
        self.assertTrue(result.piloting_check_required)
        mock_roll.assert_called_once()


class TestCheckAndApplyCriticals(unittest.TestCase):
    """Tests for batch critical application."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        # The real C center-torso layout: engine 0-2, gyro 3-6, engine 7-9,
        # two free slots (mech.build.c:72-83). Crit slots hold
        # I2Special(sub-index), not the bare sub-index (mech.h:158).
        for i, crit in enumerate(self.mech.sections[Location.CTORSO].criticals):
            if i < 3:
                crit.type = i2special(Special.ENGINE)
            elif i < 7:
                crit.type = i2special(Special.GYRO)
            elif i < 10:
                crit.type = i2special(Special.ENGINE)
            else:
                crit.type = 0  # Empty

    @patch('systems.criticals.random.choice')
    def test_apply_single_critical(self, mock_choice):
        """Apply single critical to random slot."""
        mock_choice.return_value = 0  # First slot (engine)

        results = check_and_apply_criticals(self.mech, Location.CTORSO, 1)

        self.assertEqual(len(results), 1)
        # Should have hit the engine
        self.assertTrue(
            self.mech.sections[Location.CTORSO].criticals[0].firemode
            & FireMode.DESTROYED_MODE
        )

    @patch('systems.piloting.check_for_fall')
    @patch('systems.criticals.random.choice')
    def test_apply_multiple_criticals(self, mock_choice, mock_check_fall):
        """Apply multiple criticals to random slots."""
        # Engine, engine, gyro under the C layout (gyro starts at slot 3,
        # mech.build.c:76)
        mock_choice.side_effect = [0, 1, 3]
        # Prevent piloting check from cascading into mech_falls
        mock_check_fall.return_value = MagicMock(fell=False)

        results = check_and_apply_criticals(self.mech, Location.CTORSO, 3)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[2].equipment_type, EquipmentType.GYRO)

    def test_all_twelve_slots_are_candidates_when_explicitly_populated(self):
        """HandleCritical scans NUM_CRITICALS, including synthetic head slots."""
        head = self.mech.sections[Location.HEAD]
        for slot in head.criticals:
            slot.type = i2special(Special.LIFE_SUPPORT)
        results = check_and_apply_criticals(self.mech, Location.HEAD, 12)
        self.assertEqual(len(results), 12)
        self.assertTrue(all(slot.firemode & FireMode.DESTROYED_MODE for slot in head.criticals))

    @patch('systems.criticals.random.choice')
    def test_candidate_list_is_rebuilt_for_every_crit(self, mock_choice):
        """A crit can never be handed a slot an earlier crit in the batch killed.

        Reference: crit.c:2395-2429 - the critList scan (2397-2415) is nested
        inside `while (num > 0)` (2395), so the list is rebuilt from scratch
        before every roll and DESTROYED slots are gone from it.  HandleMechCrit
        always returns 1, so all `num` crits land on live slots.
        """
        ac10 = get_weapon("IS.AC/10")
        rt = self.mech.sections[Location.RTORSO]
        for i in range(ac10.crits):
            rt.criticals[i].type = i2weapon(ac10.index)

        seen = []

        def pick(candidates):
            seen.append(list(candidates))
            return candidates[0]

        mock_choice.side_effect = pick

        results = check_and_apply_criticals(self.mech, Location.RTORSO, 3)

        # Slot 0 is destroyed by the first crit, so it must be absent from the
        # lists offered to crits 2 and 3
        self.assertEqual(seen[0][0], 0)
        self.assertNotIn(0, seen[1])
        self.assertNotIn(0, seen[2])
        # ...and no critical is silently discarded
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertNotEqual(result.message, "Hit already-destroyed equipment")

    def test_uncrittable_specials_are_skipped(self):
        """Armour/structure fillers are never crit candidates.

        Reference: crit.c:2402-2410 - CASE, ferro, endo steel, TSM,
        supercharger and MASC are excluded from critList
        """
        lt = self.mech.sections[Location.LTORSO]
        lt.criticals[0].type = i2special(Special.CASE)
        lt.criticals[1].type = i2special(Special.FERRO_FIBROUS)
        lt.criticals[2].type = i2special(Special.MASC)

        results = check_and_apply_criticals(self.mech, Location.LTORSO, 3)

        self.assertEqual(results, [])
        for i in range(3):
            self.assertFalse(lt.criticals[i].firemode & FireMode.DESTROYED_MODE)


class TestRecalculateMechStats(unittest.TestCase):
    """Tests for stat recalculation after damage."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_recalc_with_gyro_damage(self):
        """Recalc applies gyro damage modifier."""
        self.mech.set_crit_status(CritStatus.GYRO_DAMAGED)

        recalculate_mech_stats(self.mech)

        self.assertEqual(self.mech.pilot_skill_base, GYRO_PILOTING_MODIFIER)

    def test_recalc_with_gyro_destroyed(self):
        """Recalc preserves the destroyed flag; ordinary gyro damage contributes +3."""
        self.mech.set_crit_status(CritStatus.GYRO_DESTROYED | CritStatus.GYRO_DAMAGED)

        recalculate_mech_stats(self.mech)

        self.assertEqual(self.mech.pilot_skill_base, 3)

    def test_recalc_with_leg_destroyed(self):
        """Recalc adds +5 per destroyed leg."""
        self.mech.sections[Location.LLEG].armor = self.mech.sections[Location.LLEG].internal = 0

        recalculate_mech_stats(self.mech)

        self.assertEqual(self.mech.pilot_skill_base, 5)

    def test_recalc_with_sensor_damage(self):
        """Actuator recalc preserves independently established sensor BTH."""
        self.mech.set_crit_status(CritStatus.SENSORS_DAMAGED)
        self.mech.lrs_range = 15  # Not blind
        self.mech.base_to_hit = SENSORS_BTH_MODIFIER_1

        recalculate_mech_stats(self.mech)

        self.assertEqual(self.mech.base_to_hit, SENSORS_BTH_MODIFIER_1)

    def test_recalc_with_sensor_destroyed_blind(self):
        """Actuator recalc preserves blindness BTH."""
        self.mech.set_crit_status(CritStatus.SENSORS_DAMAGED)
        self.mech.lrs_range = 0
        self.mech.tac_range = 0
        self.mech.base_to_hit = SENSORS_BTH_MODIFIER_2

        recalculate_mech_stats(self.mech)

        self.assertEqual(self.mech.base_to_hit, SENSORS_BTH_MODIFIER_2)


class TestCriticalIntegration(unittest.TestCase):
    """Integration tests for critical effects with combat system."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)

    def test_combat_check_for_critical_returns_tuple(self):
        """Combat system check_for_critical returns (count, results)."""
        from systems.combat import check_for_critical

        # Set up a critical slot (I2Special(ENGINE), mech.h:158)
        self.mech.sections[Location.CTORSO].criticals[0].type = i2special(Special.ENGINE)

        count, results = check_for_critical(self.mech, Location.CTORSO, 1)

        self.assertIsInstance(count, int)
        self.assertIsInstance(results, list)


class TestCritSlotDispatch(unittest.TestCase):
    """Tests for apply_critical_to_slot's namespace decode."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.mech.set_status(MechStatus.STARTED)
        self.attacker = Mech.create_test_mech()

    def test_empty_slot_is_a_no_op(self):
        """An EMPTY slot produces no effect and is not marked destroyed."""
        result = apply_critical_to_slot(self.mech, Location.CTORSO, 0)

        self.assertFalse(result.effect_applied)
        self.assertEqual(result.message, "")
        self.assertIn("%ch%cyCRITICAL HIT!!%c", self.mech.movement_messages)
        self.assertFalse(
            self.mech.sections[Location.CTORSO].criticals[0].firemode
            & FireMode.DESTROYED_MODE
        )

    def test_non_special_results_carry_no_equipment_type(self):
        """Only a Special crit sets equipment_type; 0 is a real sub-index.

        Reference: mech.h:164 SHOULDER_OR_HIP 0 vs mech.h:107 EMPTY 0 - the two
        live in different namespaces, and the C only ever computes
        Special2I(critType) after IsSpecial(critType) passes (crit.c:1859-1861),
        so it never needs to tell "sub-index 0" from "nothing".
        """
        ac10 = get_weapon("IS.AC/10")
        rt = self.mech.sections[Location.RTORSO]
        for i in range(ac10.crits):
            rt.criticals[i].type = i2weapon(ac10.index)
        rt.criticals[ac10.crits].type = i2ammo(ac10.index)
        rt.criticals[ac10.crits].data = 1

        empty = apply_critical_to_slot(self.mech, Location.CTORSO, 0)
        weapon = apply_critical_to_slot(self.mech, Location.RTORSO, 0)
        ammo = apply_critical_to_slot(self.mech, Location.RTORSO, ac10.crits)

        for result in (empty, weapon, ammo):
            self.assertEqual(result.equipment_type, NO_EQUIPMENT_TYPE)
            self.assertNotEqual(result.equipment_type,
                                EquipmentType.SHOULDER_OR_HIP)

        # ...and a real shoulder crit still reports sub-index 0
        larm = self.mech.sections[Location.LARM]
        larm.criticals[0].type = i2special(Special.SHOULDER_OR_HIP)
        shoulder = apply_critical_to_slot(self.mech, Location.LARM, 0)
        self.assertEqual(shoulder.equipment_type, EquipmentType.SHOULDER_OR_HIP)

    def test_special_slot_routes_to_handler(self):
        """A Special crit type routes through Special2I to the handler table.

        Reference: crit.c:1859-1861 - if(IsSpecial(critType)) switch
        (Special2I(critType))
        """
        self.mech.sections[Location.CTORSO].criticals[0].type = i2special(Special.ENGINE)

        result = apply_critical_to_slot(self.mech, Location.CTORSO, 0)

        self.assertEqual(result.equipment_type, EquipmentType.ENGINE)
        self.assertTrue(result.effect_applied)
        self.assertEqual(self.mech.engine_hits, 1)

    def test_weapon_slot_destroys_the_whole_run(self):
        """One crit on a multi-slot weapon takes the whole weapon out.

        Reference: mech.damage.c:809-847 (DestroyWeapon walks every slot of
        the type - first one DESTROYED, the rest BROKEN)
        """
        roller = patch('random.randint', return_value=6)
        roller.start()
        self.addCleanup(roller.stop)
        ac10 = get_weapon("IS.AC/10")
        section = self.mech.sections[Location.RTORSO]
        for i in range(ac10.crits):
            section.criticals[i].type = i2weapon(ac10.index)
        self.mech.weapons.append(WeaponState(
            section=Location.RTORSO, critical=0, weapon_idx=ac10.index))

        # Hit the fourth slot of the run
        result = apply_critical_to_slot(self.mech, Location.RTORSO, 3)

        self.assertTrue(result.effect_applied)
        self.assertEqual(result.equipment_name, "IS.AC/10")
        nonfunctional = FireMode.DESTROYED_MODE | FireMode.BROKEN_MODE
        for i in range(ac10.crits):
            self.assertTrue(section.criticals[i].firemode & nonfunctional)
        # The parallel WeaponState mirror is kept in step
        self.assertTrue(self.mech.weapons[0].destroyed)

    def test_ammo_slot_explodes_for_rounds_times_damage(self):
        """Ammo crit damage is rounds x weapon damage.

        Reference: crit.c:1699 - damage = critData * MechWeapons[weapindx].damage
        """
        roller = patch('systems.combat.roll_2d6', return_value=7)
        roller.start()
        self.addCleanup(roller.stop)
        ac10 = get_weapon("IS.AC/10")
        section = self.mech.sections[Location.RTORSO]
        crit = section.criticals[0]
        crit.type = i2ammo(ac10.index)
        crit.data = 2
        armor_before = section.armor

        result = apply_critical_to_slot(self.mech, Location.RTORSO, 0,
                                       attacker=self.attacker)

        self.assertTrue(result.effect_applied)
        self.assertEqual(crit.data, 2)  # DestroyPart preserves ammunition data
        self.assertTrue(crit.firemode & FireMode.DESTROYED_MODE)
        # 2 rounds x 10 damage, taken out of the RT's internals only
        # (mech.update.c:1167-1170 passes it as intDamage)
        self.assertIn("20", result.messages[0])
        self.assertEqual(section.armor, 0)  # DestroySection clears exhausted location armor
        self.assertEqual(section.internal, 0)

    def test_missile_ammo_multiplies_by_salvo(self):
        """Missile ammo explodes for rounds x damage x rack size.

        Reference: crit.c:1700-1704 - damage *= num_missiles[10]
        """
        srm6 = get_weapon("IS.SRM-6")
        crit = self.mech.sections[Location.LTORSO].criticals[0]
        crit.type = i2ammo(srm6.index)
        crit.data = 1

        result = apply_ammo_critical(self.mech, Location.LTORSO, 0)

        # 1 round x 2 damage x 6 missiles
        self.assertIn("12", result.messages[0])

    def test_gauss_ammo_does_not_explode(self):
        """Gauss ammo feeds are destroyed, not detonated.

        Reference: crit.c:1705-1709 - GAUSS|NOBOOM -> DestroyPart only
        """
        gauss = get_weapon("IS.GaussRifle")
        crit = self.mech.sections[Location.RTORSO].criticals[0]
        crit.type = i2ammo(gauss.index)
        crit.data = 8
        armor_before = self.mech.sections[Location.RTORSO].armor

        result = apply_ammo_critical(self.mech, Location.RTORSO, 0)

        self.assertTrue(crit.firemode & FireMode.DESTROYED_MODE)
        self.assertEqual(self.mech.sections[Location.RTORSO].armor, armor_before)
        self.assertIn("Gauss", result.message)
        self.assertEqual(crit.data, 8)  # DestroyPart preserves inert ammunition data.

    def test_empty_ammo_bin_is_lucky(self):
        """A bin with no rounds left just dies.

        Reference: crit.c:1712-1716
        """
        ac10 = get_weapon("IS.AC/10")
        crit = self.mech.sections[Location.RTORSO].criticals[0]
        crit.type = i2ammo(ac10.index)
        crit.data = 0

        result = apply_ammo_critical(self.mech, Location.RTORSO, 0)

        self.assertTrue(crit.firemode & FireMode.DESTROYED_MODE)
        self.assertIn("lucky you", result.message)

    def test_gauss_weapon_crit_explodes_internally(self):
        """A critted Gauss rifle explodes for explosiondamage, bypassing armour.

        Reference: crit.c:383-385 - DamageMech(wounded, attacker, 0, -1, hitloc,
        0, 0, 0, explosiondamage, ...): damage 0, intDamage explosiondamage,
        isrear 0 (args 6/8/9 of mech.damage.c:334-343), so armour is never
        touched and the overflow transfers internals-only.
        """
        roller = patch('systems.combat.roll_2d6', return_value=7)
        roller.start()
        self.addCleanup(roller.stop)
        gauss = get_weapon("IS.GaussRifle")
        section = self.mech.sections[Location.RTORSO]
        for i in range(gauss.crits):
            section.criticals[i].type = i2weapon(gauss.index)
        armor_before = section.armor
        rear_before = section.rear
        ct_internal_before = self.mech.sections[Location.CTORSO].internal
        overflow = gauss.explosive_damage - section.internal
        self.assertGreater(overflow, 0)  # 20 > RT internal on the test mech

        result = apply_weapon_critical(self.mech, Location.RTORSO, 0,
                                       attacker=self.attacker)

        self.assertTrue(result.effect_applied)
        self.assertEqual(section.armor, 0)  # DestroySection clears exhausted location armor
        self.assertEqual(section.rear, 0)
        self.assertEqual(section.internal, 0)
        self.assertTrue(section.config & SectionConfig.SECTION_DESTROYED)
        # ...and the remainder transfers inwards, still internals-only
        self.assertEqual(self.mech.sections[Location.CTORSO].internal,
                         ct_internal_before - overflow)
        self.assertEqual(result.pilot_damage, AMMO_EXPLOSION_PILOT_DAMAGE)

    def test_gauss_weapon_crit_needs_attacker_for_damage(self):
        """No attacker: the weapon dies and the pilot is hurt, but nothing else.

        Reference: crit.c:382 wraps only the DamageMech call in `if(attacker)`;
        the pilot injury at crit.c:388-399 sits outside that guard.
        """
        gauss = get_weapon("IS.GaussRifle")
        section = self.mech.sections[Location.RTORSO]
        for i in range(gauss.crits):
            section.criticals[i].type = i2weapon(gauss.index)
        armor_before = section.armor
        internal_before = section.internal

        result = apply_weapon_critical(self.mech, Location.RTORSO, 0)

        self.assertTrue(result.effect_applied)
        self.assertEqual(section.armor, armor_before)
        self.assertEqual(section.internal, internal_before)
        self.assertEqual(result.pilot_damage, AMMO_EXPLOSION_PILOT_DAMAGE)
        self.assertTrue(section.criticals[0].firemode & FireMode.DESTROYED_MODE)


class TestDestroyWeapon(unittest.TestCase):
    """Tests for the DestroyWeapon slot walk."""

    def setUp(self):
        self.mech = Mech.create_test_mech()
        self.ppc = get_weapon("IS.PPC")
        self.section = self.mech.sections[Location.RTORSO]
        for i in range(self.ppc.crits):
            self.section.criticals[i].type = i2weapon(self.ppc.index)

    def test_find_first_weapon_crit(self):
        """The run's first slot is found by type match.

        Reference: mech.utils.c:2401-2424
        """
        slot = find_first_weapon_crit(
            self.mech, Location.RTORSO, -1, 0, i2weapon(self.ppc.index),
            self.ppc.crits)
        self.assertEqual(slot, 0)

    def test_find_first_weapon_crit_absent(self):
        """A type that isn't there returns -1."""
        slot = find_first_weapon_crit(
            self.mech, Location.LARM, -1, 0, i2weapon(self.ppc.index),
            self.ppc.crits)
        self.assertEqual(slot, -1)

    def test_find_first_weapon_crit_second_copy(self):
        """Two copies of one weapon in a section resolve to separate runs.

        Reference: mech.utils.c:2431-2442 - wCritsInLoc > wMaxCrits recurses
        past the first run
        """
        ml = get_weapon("IS.MediumLaser")
        larm = self.mech.sections[Location.LARM]
        larm.criticals[4].type = i2weapon(ml.index)
        larm.criticals[5].type = i2weapon(ml.index)

        first = find_first_weapon_crit(
            self.mech, Location.LARM, 4, 0, i2weapon(ml.index), ml.crits)
        second = find_first_weapon_crit(
            self.mech, Location.LARM, 5, 0, i2weapon(ml.index), ml.crits)

        self.assertEqual(first, 4)
        self.assertEqual(second, 5)

    def test_broken_single_slot_weapon_hit_dies(self):
        """A second hit on a 1-slot broken weapon finishes that slot off.

        Reference: crit.c:1720-1731 - PartIsBroken (DESTROYED|BROKEN,
        btmacros.h:331) and not DISABLED walks back to the front of the run;
        with a 1-slot weapon the walk terminates at once and DestroyPart lands on
        the slot that was hit.
        """
        larm = self.mech.sections[Location.LARM]
        ml = get_weapon("IS.MediumLaser")
        larm.criticals[4].type = i2weapon(ml.index)
        larm.criticals[4].firemode |= FireMode.BROKEN_MODE

        result = apply_weapon_critical(self.mech, Location.LARM, 4)

        self.assertFalse(result.effect_applied)
        self.assertIn("damaged some more", result.message)
        self.assertTrue(larm.criticals[4].firemode & FireMode.DESTROYED_MODE)

    def test_disabled_slot_hit_just_dies(self):
        """A DISABLED weapon slot falls through to the nonfunctional branch.

        Reference: crit.c:1732, 1835-1841 - PartIsNonfunctional
        (btmacros.h:324) with the 1720 branch excluded by !PartIsDisabled; only
        the slot that was hit is destroyed.
        """
        larm = self.mech.sections[Location.LARM]
        ml = get_weapon("IS.MediumLaser")
        larm.criticals[4].type = i2weapon(ml.index)
        larm.criticals[4].firemode |= FireMode.DISABLED_MODE

        result = apply_weapon_critical(self.mech, Location.LARM, 4)

        self.assertFalse(result.effect_applied)
        self.assertIn("non-working", result.message)
        self.assertTrue(larm.criticals[4].firemode & FireMode.DESTROYED_MODE)

    def test_broken_run_is_destroyed_front_to_back(self):
        """Repeated crits on a broken weapon convert its slots front-to-back.

        Reference: crit.c:1720-1731 - the backward walk stops at the first
        DESTROYED slot (or the front of the run) and destroys `critHit + 1`, so
        the hit slot itself is NOT the one that dies.
        """
        roller = patch('random.randint', return_value=6)
        roller.start()
        self.addCleanup(roller.stop)
        # A 7-slot AC/10 in the left torso, so there is a run to walk back along
        ac10 = get_weapon("IS.AC/10")
        lt = self.mech.sections[Location.LTORSO]
        for i in range(ac10.crits):
            lt.criticals[i].type = i2weapon(ac10.index)

        # First crit: slot 0 DESTROYED, 1..6 BROKEN
        apply_weapon_critical(self.mech, Location.LTORSO, 0)
        self.assertTrue(lt.criticals[0].firemode & FireMode.DESTROYED_MODE)

        # Second crit lands on slot 5 -> the C destroys slot 1, not slot 5
        result = apply_weapon_critical(self.mech, Location.LTORSO, 5)

        self.assertIn("damaged some more", result.message)
        self.assertTrue(lt.criticals[1].firemode & FireMode.DESTROYED_MODE)
        for i in range(2, ac10.crits):
            self.assertFalse(
                lt.criticals[i].firemode & FireMode.DESTROYED_MODE)
            self.assertTrue(lt.criticals[i].firemode & FireMode.BROKEN_MODE)

    def test_second_copy_crit_leaves_first_alone(self):
        """Critting the second of two lasers must not kill the first."""
        ml = get_weapon("IS.MediumLaser")
        larm = self.mech.sections[Location.LARM]
        larm.criticals[4].type = i2weapon(ml.index)
        larm.criticals[5].type = i2weapon(ml.index)

        apply_critical_to_slot(self.mech, Location.LARM, 5)

        nonfunctional = FireMode.DESTROYED_MODE | FireMode.BROKEN_MODE
        self.assertTrue(larm.criticals[5].firemode & nonfunctional)
        self.assertFalse(larm.criticals[4].firemode & nonfunctional)

    def test_one_destroyed_rest_broken(self):
        """numcrits=1 destroys one slot and breaks the others.

        Reference: mech.damage.c:820-841 - the first `destroyed` undamaged
        slots get DestroyPart, the remainder BreakPart
        """
        destroy_weapon(self.mech, Location.RTORSO, i2weapon(self.ppc.index),
                       0, 1, self.ppc.crits)

        self.assertTrue(self.section.criticals[0].firemode & FireMode.DESTROYED_MODE)
        for i in range(1, self.ppc.crits):
            self.assertTrue(self.section.criticals[i].firemode & FireMode.BROKEN_MODE)
            self.assertFalse(
                self.section.criticals[i].firemode & FireMode.DESTROYED_MODE)

    def test_stops_after_totalcrits(self):
        """The walk stops once totalcrits slots have been seen."""
        # A second PPC-typed slot beyond the first run must survive
        self.section.criticals[self.ppc.crits].type = i2weapon(self.ppc.index)

        touched = destroy_weapon(self.mech, Location.RTORSO,
                                 i2weapon(self.ppc.index), 0, 1, self.ppc.crits)

        self.assertEqual(touched, self.ppc.crits)
        self.assertEqual(self.section.criticals[self.ppc.crits].firemode,
                         FireMode.NONE)


if __name__ == '__main__':
    unittest.main()
