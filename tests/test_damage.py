"""
Tests for systems/damage.py - the DestroySection / DestroyParts port.

Covers:
- Section destruction kills the weapons mounted there and dumps ammo bins
- Side-torso loss cascades to the arm (mech.damage.c:1030-1034)
- Leg loss forces a fall (map.conditions.c:323-330)
- CTORSO / HEAD loss destroys the mech (mech.damage.c:1035-1062)
- Heat-sink crits in the lost section reduce the sink count
  (map.conditions.c:216-222)
- Double-destroy is a no-op (mech.damage.c:934-948)
"""

import unittest

from data.templates import create_mech_from_template, get_template
from entities.crittypes import Special, crits_in_loc, i2special, is_ammo
from entities.mech import (
    FireMode,
    Location,
    MechStatus,
    SectionConfig,
)
from systems.damage import destroy_parts, destroy_section


def _make_mech(template_name: str = "AssaultMech", name: str = "Wounded"):
    """Build a fully-configured mech from a template."""
    return create_mech_from_template(get_template(template_name), name=name)


class TestSectionWeaponsAndAmmo(unittest.TestCase):
    """Destroying a section kills its weapons and dumps its ammo."""

    def test_rtorso_kills_lrm_and_zeroes_ammo(self):
        # AssaultMech RTORSO: LRM-10 plus its 12-round ammo bin
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        rtorso = wounded.sections[Location.RTORSO]
        ammo_slots = [c for c in rtorso.criticals if is_ammo(c.type)]
        self.assertEqual(len(ammo_slots), 1)
        self.assertEqual(ammo_slots[0].data, 12)

        lrm_states = [ws for ws in wounded.weapons
                      if ws.section == Location.RTORSO]
        self.assertEqual(len(lrm_states), 1)
        self.assertFalse(lrm_states[0].destroyed)

        destroy_section(wounded, attacker, Location.RTORSO)

        # The weapon is dead, both on the parallel state...
        self.assertTrue(lrm_states[0].destroyed)
        # ...and on the crit slots themselves (the C's real mechanism)
        for i in range(crits_in_loc(wounded, Location.RTORSO)):
            self.assertTrue(
                rtorso.criticals[i].firemode & FireMode.DESTROYED_MODE)
        # Ammo bin dumped (map.conditions.c:193-195)
        self.assertEqual(ammo_slots[0].data, 0)

    def test_testmech_rtorso_kills_ac10_and_ammo(self):
        # TestMech RTORSO: AC/10 (7 crits) with a 10-round bin
        wounded = _make_mech("TestMech")
        attacker = _make_mech("TestMech", name="Attacker")

        rtorso = wounded.sections[Location.RTORSO]
        ammo_slots = [c for c in rtorso.criticals if is_ammo(c.type)]
        self.assertEqual(len(ammo_slots), 1)
        self.assertEqual(ammo_slots[0].data, 10)

        ac10 = [ws for ws in wounded.weapons
                if ws.section == Location.RTORSO][0]

        destroy_section(wounded, attacker, Location.RTORSO)

        self.assertTrue(ac10.destroyed)
        self.assertEqual(ammo_slots[0].data, 0)

    def test_section_state_zeroed(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        rtorso = wounded.sections[Location.RTORSO]
        rtorso.recycle = 30  # mid-physical, mech.damage.c:958 uncycles it

        destroy_section(wounded, attacker, Location.RTORSO)

        self.assertEqual(rtorso.armor, 0)
        self.assertEqual(rtorso.internal, 0)
        self.assertEqual(rtorso.rear, 0)
        self.assertEqual(rtorso.specials, 0)
        self.assertEqual(rtorso.recycle, 0)
        self.assertTrue(rtorso.config & SectionConfig.SECTION_DESTROYED)


class TestTorsoCascade(unittest.TestCase):
    """Side-torso loss takes the arm with it (mech.damage.c:1030-1034)."""

    def test_ltorso_cascades_to_larm(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_section(wounded, attacker, Location.LTORSO)

        larm = wounded.sections[Location.LARM]
        self.assertTrue(larm.config & SectionConfig.SECTION_DESTROYED)
        self.assertEqual(larm.armor, 0)
        self.assertEqual(larm.internal, 0)

    def test_rtorso_cascades_to_rarm(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_section(wounded, attacker, Location.RTORSO)

        rarm = wounded.sections[Location.RARM]
        self.assertTrue(rarm.config & SectionConfig.SECTION_DESTROYED)
        # The AssaultMech's PPC lives in the RARM and dies in the cascade
        ppc = [ws for ws in wounded.weapons
               if ws.section == Location.RARM][0]
        self.assertTrue(ppc.destroyed)

    def test_arm_loss_does_not_cascade(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_section(wounded, attacker, Location.LARM)

        ltorso = wounded.sections[Location.LTORSO]
        self.assertFalse(ltorso.config & SectionConfig.SECTION_DESTROYED)
        self.assertFalse(wounded.has_status(MechStatus.DESTROYED))


class TestLegDestructionFall(unittest.TestCase):
    """Leg loss forces a fall (map.conditions.c:318-329)."""

    def test_leg_destruction_forces_fall(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")
        self.assertFalse(wounded.has_status(MechStatus.FALLEN))

        destroy_section(wounded, attacker, Location.LLEG)

        self.assertTrue(wounded.has_status(MechStatus.FALLEN))

    def test_no_attacker_no_fall(self):
        # The C's auto-fall is gated on a non-NULL attacker
        # (map.conditions.c:322-323)
        wounded = _make_mech()

        destroy_section(wounded, None, Location.RLEG)

        self.assertFalse(wounded.has_status(MechStatus.FALLEN))
        self.assertTrue(wounded.sections[Location.RLEG].config &
                        SectionConfig.SECTION_DESTROYED)

    def test_arm_loss_no_fall(self):
        # Biped arm loss returns before the fall block
        # (map.conditions.c:315-317)
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_section(wounded, attacker, Location.RARM)

        self.assertFalse(wounded.has_status(MechStatus.FALLEN))


class TestMechKillingSections(unittest.TestCase):
    """CTORSO / HEAD loss kills the mech (mech.damage.c:1035-1062)."""

    def test_ctorso_destroys_mech(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_section(wounded, attacker, Location.CTORSO)

        self.assertTrue(wounded.has_status(MechStatus.DESTROYED))

    def test_head_destroys_mech(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_section(wounded, attacker, Location.HEAD)

        self.assertTrue(wounded.has_status(MechStatus.DESTROYED))
        # Only the head (and nothing else) was blown off
        self.assertTrue(wounded.sections[Location.HEAD].config &
                        SectionConfig.SECTION_DESTROYED)
        self.assertFalse(wounded.sections[Location.CTORSO].config &
                         SectionConfig.SECTION_DESTROYED)


class TestHeatSinkLoss(unittest.TestCase):
    """Heat-sink crits in the lost section decrement num_sinks
    (map.conditions.c:216-222)."""

    def test_ltorso_heat_sinks_reduce_count(self):
        # AssaultMech carries 15 sinks; the 5 non-integral ones are placed
        # in the LTORSO after its two medium lasers.
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        hs_type = i2special(Special.HEAT_SINK)
        n_sinks_in_loc = sum(
            1 for c in wounded.sections[Location.LTORSO].criticals
            if c.type == hs_type)
        self.assertEqual(n_sinks_in_loc, 5)
        self.assertEqual(wounded.num_sinks, 15)

        destroy_section(wounded, attacker, Location.LTORSO)

        self.assertEqual(wounded.num_sinks, 15 - n_sinks_in_loc)


class TestDoubleDestroy(unittest.TestCase):
    """Double-destroy is a no-op (mech.damage.c:934-948)."""

    def test_double_destroy_is_noop(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_section(wounded, attacker, Location.LTORSO)
        sinks_after_first = wounded.num_sinks

        destroy_section(wounded, attacker, Location.LTORSO)

        # No second round of heat-sink decrements or other side effects
        self.assertEqual(wounded.num_sinks, sinks_after_first)

    def test_cascaded_arm_redestroy_is_noop(self):
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_section(wounded, attacker, Location.LTORSO)
        larm = wounded.sections[Location.LARM]
        self.assertTrue(larm.config & SectionConfig.SECTION_DESTROYED)

        # Hitting the already-cascaded arm again does nothing
        destroy_section(wounded, attacker, Location.LARM)
        self.assertTrue(larm.config & SectionConfig.SECTION_DESTROYED)

    def test_destroy_parts_skips_destroyed_slots(self):
        # Slots already flagged DESTROYED are skipped
        # (map.conditions.c:183), so their side effects never re-fire.
        wounded = _make_mech()
        attacker = _make_mech(name="Attacker")

        destroy_parts(attacker, wounded, Location.LTORSO)
        self.assertEqual(wounded.num_sinks, 10)

        destroy_parts(attacker, wounded, Location.LTORSO)
        self.assertEqual(wounded.num_sinks, 10)


if __name__ == "__main__":
    unittest.main()
