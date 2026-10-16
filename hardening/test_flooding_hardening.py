"""Flood refusal, casualty cleanup and inferno extinction boundaries."""
import unittest
from unittest.mock import patch
from core.events import EventType
from acceptance.movement.context import fresh, set_hex
from entities.mech import MechStatus as S, UnitType, Location, SectionConfig, CritStatus
from physics import flooding
from systems import damage


def submerged():
    world = {}
    fresh(world)
    set_hex(world, 'WATER', 2)
    world['unit'].z = -2
    return world


class TestFloodingHardening(unittest.TestCase):
    def test_individual_breach_refusals_preserve_the_section(self):
        for condition in ('safe', 'destroyed', 'dry', 'zero_level', 'other_class', 'shallow_torso'):
            w = submerged()
            u = w['unit']
            location, level = Location.CTORSO, -2
            section = u.sections[location]
            section.armor = 0
            if condition == 'safe': u.set_status(S.COMBAT_SAFE)
            if condition == 'destroyed': section.internal = 0
            if condition == 'dry': set_hex(w, 'GRASSLAND')
            if condition == 'zero_level': level = 0
            if condition == 'other_class': u.unit_type = UnitType.BSUIT
            if condition == 'shallow_torso': level = -1
            with self.subTest(condition=condition):
                self.assertFalse(flooding.flood_location(u, location, level))
                self.assertFalse(section.config & SectionConfig.SECTION_FLOODED)

    def test_breach_preserves_other_flags_and_reports_the_section(self):
        w = submerged()
        u = w['unit']
        section = u.sections[Location.LARM]
        section.armor = 0
        section.config = SectionConfig.CASE_TECH
        self.assertTrue(flooding.flood_location(u, Location.LARM, -2))
        self.assertEqual(SectionConfig.CASE_TECH | SectionConfig.SECTION_FLOODED, section.config)
        self.assertIn('Water floods into your LARM disabling everything that was there!', u.movement_messages)

    def test_head_breach_cancels_live_events_and_reports_death(self):
        w = submerged()
        u, engine = w['unit'], w['engine']
        u.sections[Location.HEAD].armor = 0
        engine.schedule_event(30, EventType.MOVE, lambda event: None, data=u)
        messages = []
        with patch.object(damage, 'NOTIFY_HOOK', side_effect=lambda who, text: messages.append((who, text))):
            self.assertTrue(flooding.flood_location(u, Location.HEAD, -2))
        self.assertTrue(u.is_destroyed)
        self.assertFalse(engine.has_event(EventType.MOVE, u))
        self.assertIn((u, 'You have been destroyed!'), messages)

    def test_battlesuit_flood_death_exempts_swarmers_and_waterproof_suits(self):
        for protection in ('none', 'other_bit', 'swarming', 'waterproof', 'dry'):
            w = submerged()
            u = w['unit']
            u.unit_type = UnitType.BSUIT
            if protection == 'other_bit': u.specials2 = 1
            if protection == 'swarming': u.swarm_target = object()
            if protection == 'waterproof': u.specials2 = 0x100000
            if protection == 'dry': set_hex(w, 'GRASSLAND')
            messages = []
            with self.subTest(protection=protection), patch.object(damage, 'NOTIFY_HOOK', side_effect=lambda who, text: messages.append((who, text))):
                flooding.flood_unit(u)
                dead = protection in ('none', 'other_bit')
                self.assertEqual(dead, u.is_destroyed)
                if dead:
                    self.assertEqual('FLOOD', u.kill_reason)
                    self.assertEqual([(u, 'You have been killed!')], messages)
                else:
                    self.assertEqual([], messages)

    def test_extinguishing_requires_jelly_a_mech_and_sufficient_submersion(self):
        for condition in ('deep', 'shallow', 'fallen', 'dry', 'not_jellied', 'other_class'):
            w = submerged()
            u = w['unit']
            u.set_crit_status(CritStatus.JELLIED)
            if condition in ('shallow', 'fallen'): set_hex(w, 'WATER', 1)
            if condition == 'fallen': u.set_status(S.FALLEN)
            if condition == 'dry': set_hex(w, 'GRASSLAND')
            if condition == 'not_jellied': u.clear_crit_status(CritStatus.JELLIED)
            if condition == 'other_class': u.unit_type = UnitType.BSUIT
            expected = condition in ('deep', 'fallen')
            with self.subTest(condition=condition):
                self.assertEqual(expected, flooding.extinguish_in_water(u))
                self.assertEqual(not expected and condition != 'not_jellied', u.has_crit_status(CritStatus.JELLIED))
                self.assertEqual(['The flames extinguish in a roar of steam!'] if expected else [], getattr(u, 'movement_messages', []))
