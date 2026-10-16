"""
Tests for mech templates (Phase 7).

Tests cover:
- ArmorLayout dataclass
- WeaponMount dataclass
- MechTemplate dataclass
- create_mech_from_template() factory
- create_weapon_slots_from_template() factory
- Pre-defined templates (TestMech, AssaultMech, LightMech)
- Template registry functions
"""

import unittest

from data.templates import (
    ArmorLayout,
    WeaponMount,
    MechTemplate,
    create_mech_from_template,
    create_weapon_slots_from_template,
    fill_default_criticals,
    find_empty_crit_run,
    MECH_TEMPLATES,
    get_template,
    list_templates,
    TEST_MECH_TEMPLATE,
    ASSAULT_MECH_TEMPLATE,
    LIGHT_MECH_TEMPLATE,
    JUMP_MECH_TEMPLATE,
)
from entities.crittypes import (
    EMPTY,
    Special,
    ammo2weapon_i,
    crits_in_loc,
    i2ammo,
    i2special,
    i2weapon,
    is_ammo,
    is_weapon,
    weapon2i,
)
from entities.mech import Location, Mech, MoveType, UnitType, Specials
from entities.pilot import Pilot
from entities.weapon import get_weapon, get_weapon_by_index
from systems.combat import WeaponSlot


class TestArmorLayout(unittest.TestCase):
    """Tests for the ArmorLayout dataclass."""

    def test_default_values(self):
        """Test ArmorLayout has sensible defaults."""
        armor = ArmorLayout()
        self.assertEqual(armor.head, 9)
        self.assertEqual(armor.ct_front, 16)
        self.assertEqual(armor.ct_rear, 5)
        self.assertEqual(armor.head_internal, 3)

    def test_custom_values(self):
        """Test ArmorLayout with custom values."""
        armor = ArmorLayout(
            head=8,
            ct_front=30,
            ct_rear=10,
            lt_front=20,
            rt_front=20,
        )
        self.assertEqual(armor.head, 8)
        self.assertEqual(armor.ct_front, 30)
        self.assertEqual(armor.ct_rear, 10)
        self.assertEqual(armor.lt_front, 20)
        self.assertEqual(armor.rt_front, 20)
        # Defaults still apply
        self.assertEqual(armor.head_internal, 3)


class TestWeaponMount(unittest.TestCase):
    """Tests for the WeaponMount dataclass."""

    def test_energy_weapon_mount(self):
        """Test mounting an energy weapon (no ammo)."""
        mount = WeaponMount("IS.MediumLaser", Location.LARM)
        self.assertEqual(mount.weapon_name, "IS.MediumLaser")
        self.assertEqual(mount.location, Location.LARM)
        self.assertEqual(mount.ammo, -1)  # Infinite
        self.assertFalse(mount.rear_mounted)

    def test_ballistic_weapon_mount(self):
        """Test mounting a ballistic weapon with ammo."""
        mount = WeaponMount("IS.AC/10", Location.RTORSO, ammo=10)
        self.assertEqual(mount.weapon_name, "IS.AC/10")
        self.assertEqual(mount.location, Location.RTORSO)
        self.assertEqual(mount.ammo, 10)

    def test_rear_mounted_weapon(self):
        """Test a rear-mounted weapon."""
        mount = WeaponMount("IS.MediumLaser", Location.CTORSO, rear_mounted=True)
        self.assertTrue(mount.rear_mounted)


class TestMechTemplate(unittest.TestCase):
    """Tests for the MechTemplate dataclass."""

    def test_default_values(self):
        """Test MechTemplate has sensible defaults."""
        template = MechTemplate(name="Test", mech_type="TST-1")
        self.assertEqual(template.name, "Test")
        self.assertEqual(template.mech_type, "TST-1")
        self.assertEqual(template.tonnage, 50)
        self.assertEqual(template.walk_mp, 4)
        self.assertEqual(template.run_mp, 6)
        self.assertEqual(template.heat_sinks, 10)
        self.assertFalse(template.double_heat_sinks)
        self.assertFalse(template.clan_tech)

    def test_calculate_max_speed(self):
        """Test max speed calculation from run MP."""
        template = MechTemplate(name="Test", mech_type="TST-1", run_mp=6)
        speed = template.calculate_max_speed()
        self.assertAlmostEqual(speed, 64.5, places=1)

        # Faster mech
        template2 = MechTemplate(name="Fast", mech_type="FST-1", run_mp=9)
        speed2 = template2.calculate_max_speed()
        self.assertAlmostEqual(speed2, 96.75, places=1)

    def test_custom_template(self):
        """Test creating a custom template."""
        template = MechTemplate(
            name="Custom",
            mech_type="CST-1A",
            tonnage=75,
            walk_mp=4,
            run_mp=6,
            heat_sinks=15,
            clan_tech=True,
            double_heat_sinks=True,
            weapons=[
                WeaponMount("CL.ERMediumLaser", Location.LARM),
                WeaponMount("CL.ERMediumLaser", Location.RARM),
            ],
        )
        self.assertEqual(template.tonnage, 75)
        self.assertTrue(template.clan_tech)
        self.assertTrue(template.double_heat_sinks)
        self.assertEqual(len(template.weapons), 2)


class TestCreateMechFromTemplate(unittest.TestCase):
    """Tests for the create_mech_from_template() factory."""

    def test_basic_creation(self):
        """Test creating a mech from TestMech template."""
        mech = create_mech_from_template(TEST_MECH_TEMPLATE)

        # Check identity
        self.assertEqual(mech.name, "TestMech")
        self.assertEqual(mech.mech_type, "TST-1A")

        # Check base stats
        self.assertEqual(mech.tonnage, 50)
        self.assertEqual(mech.num_sinks, 10)
        self.assertAlmostEqual(mech.max_speed, 64.5, places=1)

    def test_custom_name(self):
        """Test creating a mech with a custom name."""
        mech = create_mech_from_template(TEST_MECH_TEMPLATE, name="MyMech")
        self.assertEqual(mech.name, "MyMech")
        self.assertEqual(mech.mech_type, "TST-1A")  # Type unchanged

    def test_armor_application(self):
        """Test armor is correctly applied from template."""
        mech = create_mech_from_template(TEST_MECH_TEMPLATE)

        # Head
        self.assertEqual(mech.sections[Location.HEAD].armor, 9)
        self.assertEqual(mech.sections[Location.HEAD].armor_orig, 9)
        self.assertEqual(mech.sections[Location.HEAD].internal, 3)

        # Center Torso (TestMech has 21 front, 7 rear)
        self.assertEqual(mech.sections[Location.CTORSO].armor, 21)
        self.assertEqual(mech.sections[Location.CTORSO].rear, 7)
        self.assertEqual(mech.sections[Location.CTORSO].internal, 16)

        # Arms
        self.assertEqual(mech.sections[Location.LARM].armor, 12)
        self.assertEqual(mech.sections[Location.RARM].armor, 12)

        # Legs
        self.assertEqual(mech.sections[Location.LLEG].armor, 16)
        self.assertEqual(mech.sections[Location.RLEG].armor, 16)

    def test_specials_flags(self):
        """Test specials flags are set correctly."""
        # IS mech - no specials
        mech = create_mech_from_template(TEST_MECH_TEMPLATE)
        self.assertFalse(mech.specials & Specials.CLAN_TECH)
        self.assertFalse(mech.specials & Specials.DOUBLE_HEAT_TECH)

        # Create a Clan mech with DHS
        clan_template = MechTemplate(
            name="ClanMech",
            mech_type="CLN-1A",
            clan_tech=True,
            double_heat_sinks=True,
        )
        clan_mech = create_mech_from_template(clan_template)
        self.assertTrue(clan_mech.specials & Specials.CLAN_TECH)
        self.assertTrue(clan_mech.specials & Specials.DOUBLE_HEAT_TECH)

    def test_movement_stats(self):
        """Test movement stats are set correctly."""
        mech = create_mech_from_template(TEST_MECH_TEMPLATE)
        self.assertEqual(mech.walk_speed, 4)
        self.assertEqual(mech.run_speed, 6)
        self.assertEqual(mech.move_type, MoveType.BIPED)
        self.assertEqual(mech.unit_type, UnitType.MECH)


class TestFillDefaultCriticals(unittest.TestCase):
    """Tests for the FillDefaultCriticals port (mech.build.c:39-103)."""

    def setUp(self):
        self.mech = Mech()
        fill_default_criticals(self.mech)

    def test_head_layout(self):
        """Life support, sensors, cockpit, gap, sensors, life support.

        Reference: mech.build.c:62-70 - slot 3 is deliberately left empty
        """
        head = self.mech.sections[Location.HEAD].criticals
        self.assertEqual(head[0].type, i2special(Special.LIFE_SUPPORT))
        self.assertEqual(head[1].type, i2special(Special.SENSORS))
        self.assertEqual(head[2].type, i2special(Special.COCKPIT))
        self.assertEqual(head[3].type, EMPTY)
        self.assertEqual(head[4].type, i2special(Special.SENSORS))
        self.assertEqual(head[5].type, i2special(Special.LIFE_SUPPORT))

    def test_center_torso_layout(self):
        """Engine 0-2, gyro 3-6, engine 7-9, two free.

        Reference: mech.build.c:72-83
        """
        ct = self.mech.sections[Location.CTORSO].criticals
        for i in (0, 1, 2, 7, 8, 9):
            self.assertEqual(ct[i].type, i2special(Special.ENGINE), f"slot {i}")
        for i in (3, 4, 5, 6):
            self.assertEqual(ct[i].type, i2special(Special.GYRO), f"slot {i}")
        self.assertEqual(ct[10].type, EMPTY)
        self.assertEqual(ct[11].type, EMPTY)

    def test_side_torsos_are_empty(self):
        """Reference: mech.build.c:85-87 - LTORSO/RTORSO break immediately."""
        for loc in (Location.LTORSO, Location.RTORSO):
            for crit in self.mech.sections[loc].criticals:
                self.assertEqual(crit.type, EMPTY)

    def test_limb_actuators(self):
        """Reference: mech.build.c:89-101 - all four limbs get the same four."""
        expected = [
            i2special(Special.SHOULDER_OR_HIP),
            i2special(Special.UPPER_ACTUATOR),
            i2special(Special.LOWER_ACTUATOR),
            i2special(Special.HAND_OR_FOOT_ACTUATOR),
        ]
        for loc in (Location.LARM, Location.RARM, Location.LLEG, Location.RLEG):
            crits = self.mech.sections[loc].criticals
            self.assertEqual([c.type for c in crits[:4]], expected)
            self.assertEqual(crits[4].type, EMPTY)

    def test_blanks_existing_slots(self):
        """Reference: mech.build.c:43-48 - every slot is cleared first."""
        self.mech.sections[Location.LTORSO].criticals[5].type = 99
        self.mech.sections[Location.LTORSO].criticals[5].data = 7
        fill_default_criticals(self.mech)
        crit = self.mech.sections[Location.LTORSO].criticals[5]
        self.assertEqual(crit.type, EMPTY)
        self.assertEqual(crit.data, 0)


class TestFindEmptyCritRun(unittest.TestCase):
    """Tests for the contiguous-run search used by weapon placement."""

    def setUp(self):
        self.mech = Mech()
        fill_default_criticals(self.mech)

    def test_finds_first_free_run(self):
        self.assertEqual(find_empty_crit_run(self.mech, Location.LARM, 2), 4)

    def test_respects_crits_in_loc(self):
        """A leg only has 6 slots, so a 3-slot weapon does not fit.

        Reference: mech.utils.c:151-166 (CritsInLoc)
        """
        self.assertEqual(crits_in_loc(self.mech, Location.LLEG), 6)
        self.assertEqual(find_empty_crit_run(self.mech, Location.LLEG, 2), 4)
        self.assertEqual(find_empty_crit_run(self.mech, Location.LLEG, 3), -1)

    def test_no_room_returns_minus_one(self):
        self.assertEqual(find_empty_crit_run(self.mech, Location.CTORSO, 3), -1)


class TestTemplateCritPlacement(unittest.TestCase):
    """Tests for A4.5 crit-slot population in create_mech_from_template."""

    def setUp(self):
        self.mech = create_mech_from_template(TEST_MECH_TEMPLATE)

    def test_fixed_internals_present(self):
        """Templates get the default internals under their loadout."""
        self.assertEqual(self.mech.sections[Location.HEAD].criticals[2].type,
                         i2special(Special.COCKPIT))
        self.assertEqual(self.mech.sections[Location.CTORSO].criticals[3].type,
                         i2special(Special.GYRO))

    def test_weapons_occupy_contiguous_slots(self):
        """AC/10 fills 7 consecutive RT slots with one type byte."""
        ac10 = get_weapon("IS.AC/10")
        rt = self.mech.sections[Location.RTORSO].criticals
        for i in range(ac10.crits):
            self.assertEqual(rt[i].type, i2weapon(ac10.index))

    def test_weapon_states_registered(self):
        """mech.weapons carries one WeaponState per mount, in template order."""
        self.assertEqual(len(self.mech.weapons), len(TEST_MECH_TEMPLATE.weapons))
        for ws, mount in zip(self.mech.weapons, TEST_MECH_TEMPLATE.weapons):
            self.assertEqual(ws.section, mount.location)
            self.assertEqual(get_weapon_by_index(ws.weapon_idx).name,
                             mount.weapon_name)
            # The WeaponState points at the first crit of the run
            crit = self.mech.sections[ws.section].criticals[ws.critical]
            self.assertEqual(weapon2i(crit.type), ws.weapon_idx)

    def test_ammo_bin_placed_with_rounds(self):
        """The AC/10's 10 rounds live in a bin's data byte (btmacros.h:311)."""
        ac10 = get_weapon("IS.AC/10")
        bins = [
            (loc, i, c.data)
            for loc in Location
            for i, c in enumerate(self.mech.sections[loc].criticals)
            if is_ammo(c.type) and ammo2weapon_i(c.type) == ac10.index
        ]
        self.assertEqual(len(bins), 1)
        self.assertEqual(bins[0][2], 10)

    def test_energy_weapons_get_no_bin(self):
        """Medium lasers do not use ammo, so no bin is placed for them."""
        ml = get_weapon("IS.MediumLaser")
        for loc in Location:
            for crit in self.mech.sections[loc].criticals:
                if is_ammo(crit.type):
                    self.assertNotEqual(ammo2weapon_i(crit.type), ml.index)

    def test_no_extra_heat_sink_crits_at_ten_sinks(self):
        """Ten sinks are engine-integral and occupy no slots."""
        self.assertEqual(TEST_MECH_TEMPLATE.heat_sinks, 10)
        self.assertEqual(self._count(self.mech, Special.HEAT_SINK), 0)

    def test_extra_heat_sinks_get_crits(self):
        """AssaultMech's 15 sinks mean 5 placed crits."""
        mech = create_mech_from_template(ASSAULT_MECH_TEMPLATE)
        self.assertEqual(self._count(mech, Special.HEAT_SINK),
                         ASSAULT_MECH_TEMPLATE.heat_sinks - 10)

    def test_jump_jets_match_jump_mp(self):
        """One JUMP_JET crit per jump MP (map.conditions.c:223-226)."""
        mech = create_mech_from_template(JUMP_MECH_TEMPLATE)
        self.assertEqual(self._count(mech, Special.JUMP_JET),
                         JUMP_MECH_TEMPLATE.jump_mp)
        self.assertEqual(mech.jump_mp, JUMP_MECH_TEMPLATE.jump_mp)

    def test_all_templates_fit(self):
        """Every registered template places without overflowing a section."""
        for name in MECH_TEMPLATES:
            mech = create_mech_from_template(MECH_TEMPLATES[name])
            self.assertEqual(len(mech.weapons),
                             len(MECH_TEMPLATES[name].weapons), name)

    def test_rear_mounted_sets_firemode(self):
        """rear_mounted stamps REAR_MOUNT on the weapon's slots (mech.h:616)."""
        from entities.mech import FireMode

        template = MechTemplate(
            name="RearGun",
            mech_type="RG-1",
            weapons=[WeaponMount("IS.MediumLaser", Location.CTORSO,
                                 rear_mounted=True)],
        )
        mech = create_mech_from_template(template)
        ws = mech.weapons[0]
        crit = mech.sections[ws.section].criticals[ws.critical]
        self.assertTrue(crit.firemode & FireMode.REAR_MOUNT)

    def test_weapon_that_does_not_fit_raises(self):
        """A weapon with no room raises rather than silently vanishing."""
        template = MechTemplate(
            name="Overstuffed",
            mech_type="OVR-1",
            # Legs have 6 slots, 4 of them actuators: a 7-crit AC/10 cannot fit
            weapons=[WeaponMount("IS.AC/10", Location.LLEG)],
        )
        with self.assertRaises(ValueError):
            create_mech_from_template(template)

    def test_default_pilot_attached(self):
        """create_mech_from_template seats a Pilot by default (A9)."""
        self.assertIsInstance(self.mech.pilot, Pilot)
        self.assertEqual(self.mech.pilot.gunnery, 4)
        self.assertEqual(self.mech.pilot.piloting, 5)

    def test_explicit_pilot_honoured(self):
        ace = Pilot(name="Natasha", gunnery=1, piloting=2)
        mech = create_mech_from_template(TEST_MECH_TEMPLATE, pilot=ace)
        self.assertIs(mech.pilot, ace)

    def test_create_test_mech_stays_slot_empty(self):
        """Mech.create_test_mech is the bare fixture; it fills no crits."""
        mech = Mech.create_test_mech()
        for loc in Location:
            for crit in mech.sections[loc].criticals:
                self.assertEqual(crit.type, EMPTY)

    @staticmethod
    def _count(mech, sub_index):
        want = i2special(sub_index)
        return sum(
            1
            for loc in Location
            for i in range(crits_in_loc(mech, loc))
            if mech.sections[loc].criticals[i].type == want
        )


class TestCreateWeaponSlots(unittest.TestCase):
    """Tests for create_weapon_slots_from_template()."""

    def test_testmech_weapons(self):
        """Test weapon slots created from TestMech template."""
        slots = create_weapon_slots_from_template(TEST_MECH_TEMPLATE)

        self.assertEqual(len(slots), 3)

        # First two are Medium Lasers in left arm
        self.assertEqual(slots[0].weapon.name, "IS.MediumLaser")
        self.assertEqual(slots[0].section, Location.LARM)
        self.assertEqual(slots[0].ammo_count, -1)  # Infinite

        self.assertEqual(slots[1].weapon.name, "IS.MediumLaser")
        self.assertEqual(slots[1].section, Location.LARM)

        # Third is AC/10 with ammo
        self.assertEqual(slots[2].weapon.name, "IS.AC/10")
        self.assertEqual(slots[2].section, Location.RTORSO)
        self.assertEqual(slots[2].ammo_count, 10)

    def test_weapon_slots_ready(self):
        """Test created weapon slots are ready to fire."""
        slots = create_weapon_slots_from_template(TEST_MECH_TEMPLATE)
        for slot in slots:
            self.assertTrue(slot.is_ready)
            self.assertFalse(slot.destroyed)

    def test_unknown_weapon_raises(self):
        """Test that an unknown weapon raises ValueError."""
        bad_template = MechTemplate(
            name="Bad",
            mech_type="BAD-1",
            weapons=[WeaponMount("INVALID.Weapon", Location.LARM)],
        )
        with self.assertRaises(ValueError) as ctx:
            create_weapon_slots_from_template(bad_template)
        self.assertIn("Unknown weapon", str(ctx.exception))


class TestTestMechTemplate(unittest.TestCase):
    """Tests specific to the TestMech template."""

    def test_template_exists(self):
        """Test TestMech template is defined."""
        self.assertIsNotNone(TEST_MECH_TEMPLATE)
        self.assertEqual(TEST_MECH_TEMPLATE.name, "TestMech")

    def test_template_stats(self):
        """Test TestMech has expected stats."""
        t = TEST_MECH_TEMPLATE
        self.assertEqual(t.tonnage, 50)
        self.assertEqual(t.walk_mp, 4)
        self.assertEqual(t.run_mp, 6)
        self.assertEqual(t.heat_sinks, 10)
        self.assertFalse(t.clan_tech)

    def test_template_weapons(self):
        """Test TestMech has expected weapons."""
        weapons = TEST_MECH_TEMPLATE.weapons
        self.assertEqual(len(weapons), 3)

        # Count weapon types
        ml_count = sum(1 for w in weapons if w.weapon_name == "IS.MediumLaser")
        ac_count = sum(1 for w in weapons if w.weapon_name == "IS.AC/10")
        self.assertEqual(ml_count, 2)
        self.assertEqual(ac_count, 1)

    def test_total_armor(self):
        """Test TestMech total armor calculation."""
        mech = create_mech_from_template(TEST_MECH_TEMPLATE)
        total = mech.total_armor()

        # Calculate expected total
        armor = TEST_MECH_TEMPLATE.armor
        expected = (
            armor.head + armor.head_internal +
            armor.ct_front + armor.ct_rear + armor.ct_internal +
            armor.lt_front + armor.lt_rear + armor.lt_internal +
            armor.rt_front + armor.rt_rear + armor.rt_internal +
            armor.la_armor + armor.la_internal +
            armor.ra_armor + armor.ra_internal +
            armor.ll_armor + armor.ll_internal +
            armor.rl_armor + armor.rl_internal
        )
        self.assertEqual(total, expected)


class TestAssaultMechTemplate(unittest.TestCase):
    """Tests for the AssaultMech template."""

    def test_template_exists(self):
        """Test AssaultMech template is defined."""
        self.assertIsNotNone(ASSAULT_MECH_TEMPLATE)
        self.assertEqual(ASSAULT_MECH_TEMPLATE.name, "AssaultMech")

    def test_template_stats(self):
        """Test AssaultMech has expected stats."""
        t = ASSAULT_MECH_TEMPLATE
        self.assertEqual(t.tonnage, 80)
        self.assertEqual(t.walk_mp, 3)
        self.assertEqual(t.run_mp, 5)
        self.assertEqual(t.heat_sinks, 15)

    def test_template_weapons(self):
        """Test AssaultMech weapons."""
        weapons = ASSAULT_MECH_TEMPLATE.weapons
        self.assertEqual(len(weapons), 4)

        weapon_names = [w.weapon_name for w in weapons]
        self.assertIn("IS.PPC", weapon_names)
        self.assertIn("IS.LRM-10", weapon_names)


class TestLightMechTemplate(unittest.TestCase):
    """Tests for the LightMech template."""

    def test_template_exists(self):
        """Test LightMech template is defined."""
        self.assertIsNotNone(LIGHT_MECH_TEMPLATE)
        self.assertEqual(LIGHT_MECH_TEMPLATE.name, "LightMech")

    def test_template_stats(self):
        """Test LightMech has expected stats."""
        t = LIGHT_MECH_TEMPLATE
        self.assertEqual(t.tonnage, 35)
        self.assertEqual(t.walk_mp, 6)
        self.assertEqual(t.run_mp, 9)

    def test_faster_speed(self):
        """Test LightMech is faster than TestMech."""
        light = create_mech_from_template(LIGHT_MECH_TEMPLATE)
        test = create_mech_from_template(TEST_MECH_TEMPLATE)
        self.assertGreater(light.max_speed, test.max_speed)


class TestTemplateRegistry(unittest.TestCase):
    """Tests for the template registry functions."""

    def test_mech_templates_dict(self):
        """Test MECH_TEMPLATES dictionary contains expected templates."""
        self.assertIn("TestMech", MECH_TEMPLATES)
        self.assertIn("AssaultMech", MECH_TEMPLATES)
        self.assertIn("LightMech", MECH_TEMPLATES)

    def test_get_template_found(self):
        """Test get_template() returns correct template."""
        template = get_template("TestMech")
        self.assertIsNotNone(template)
        self.assertEqual(template.name, "TestMech")

    def test_get_template_not_found(self):
        """Test get_template() returns None for unknown template."""
        template = get_template("NonexistentMech")
        self.assertIsNone(template)

    def test_list_templates(self):
        """Test list_templates() returns all template names."""
        names = list_templates()
        self.assertIn("TestMech", names)
        self.assertIn("AssaultMech", names)
        self.assertIn("LightMech", names)
        self.assertIn("JumpMech", names)
        self.assertEqual(len(names), 4)


class TestIntegrationWithCombat(unittest.TestCase):
    """Integration tests with combat system."""

    def test_mech_and_weapons_together(self):
        """Test creating a mech and its weapons from template."""
        mech = create_mech_from_template(TEST_MECH_TEMPLATE)
        weapon_slots = create_weapon_slots_from_template(TEST_MECH_TEMPLATE)

        # Mech should be valid
        self.assertEqual(mech.name, "TestMech")
        self.assertEqual(mech.tonnage, 50)

        # Weapons should be ready
        self.assertEqual(len(weapon_slots), 3)
        for slot in weapon_slots:
            self.assertTrue(slot.is_ready)

    def test_weapon_heat_vs_sinks(self):
        """Test that weapon heat can be managed by heat sinks."""
        weapon_slots = create_weapon_slots_from_template(TEST_MECH_TEMPLATE)

        # Calculate alpha strike heat
        alpha_heat = sum(slot.weapon.heat for slot in weapon_slots)

        # TestMech: 2x ML (3 heat each) + AC/10 (3 heat) = 9 heat
        self.assertEqual(alpha_heat, 9)

        # TestMech has 10 heat sinks, so can handle alpha strike
        mech = create_mech_from_template(TEST_MECH_TEMPLATE)
        self.assertGreaterEqual(mech.num_sinks, alpha_heat)


if __name__ == "__main__":
    unittest.main()
