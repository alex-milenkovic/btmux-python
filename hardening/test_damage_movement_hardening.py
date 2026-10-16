"""Breach/disable state and orbital fall exclusion at the damage boundary."""
import unittest
from unittest.mock import patch
from acceptance.movement.context import fresh
from entities.mech import Location, FireMode, WeaponState, MechStatus as S
from entities.crittypes import Special, i2special, i2weapon
from systems import damage


def ready():
    w={};fresh(w);return w


class TestDamageMovementHardening(unittest.TestCase):
    def test_disabling_preserves_mode_bits_and_marks_only_location_weapons(self):
        w=ready();u=w['unit'];section=u.sections[Location.LARM]
        section.criticals[0].type=i2weapon(0)
        u.sections[Location.RARM].criticals[0].type=i2weapon(0)
        section.criticals[0].firemode=FireMode.REAR_MOUNT
        own=WeaponState(section=Location.LARM);other=WeaponState(section=Location.RARM)
        u.weapons=[own,other]
        damage.destroy_parts(u,u,Location.LARM,disable=True)
        self.assertEqual(FireMode.REAR_MOUNT|FireMode.DISABLED_MODE,section.criticals[0].firemode)
        self.assertTrue(own.disabled)
        self.assertFalse(own.destroyed)
        self.assertFalse(getattr(other,'disabled',False))
        self.assertFalse(other.destroyed)
        self.assertFalse(u.is_destroyed)

    def test_previously_disabled_part_only_reapplies_side_effects_in_disable_mode(self):
        for disable in (False,True):
            w=ready();u=w['unit'];slot=u.sections[Location.LARM].criticals[0]
            slot.type=i2special(Special.HEAT_SINK);slot.firemode=FireMode.DISABLED_MODE
            sinks=u.num_sinks
            damage.destroy_parts(u,u,Location.LARM,disable=disable)
            self.assertEqual(sinks-int(disable),u.num_sinks)
            self.assertEqual(not disable,bool(slot.firemode & FireMode.DESTROYED_MODE))

    def test_head_breach_requires_explicit_breach_and_uses_flood_death_without_blast(self):
        for breach,location,dead in ((False,Location.HEAD,False),(True,Location.HEAD,True),(True,Location.LARM,False)):
            w=ready();u=w['unit'];messages=[]
            with patch.object(damage,'NOTIFY_HOOK',side_effect=lambda who,text:messages.append(text)):
                if breach:damage.destroy_parts(u,u,location,breach=True,disable=True)
                else:damage.destroy_parts(u,u,location)
            self.assertEqual(dead,u.is_destroyed)
            if dead:
                self.assertEqual('FLOOD',u.kill_reason)
                self.assertEqual(['You have been destroyed!'],messages)

    def test_leg_loss_does_not_start_a_ground_fall_during_orbital_drop(self):
        for cocoon,fallen in ((0,True),(1,False),(-1,False)):
            w=ready();u=w['unit'];u.cocoon=cocoon;u.set_status(S.COMBAT_SAFE)
            damage.destroy_parts(u,u,Location.RLEG)
            self.assertEqual(fallen,u.is_fallen)

    def test_head_flood_removes_the_pilot_and_preserves_an_existing_death_record(self):
        from acceptance.movement.context import set_hex
        from physics.flooding import flood_location
        for prior,expected,already_destroyed in ((0,6,False),(8,8,False),(8,8,True)):
            w=ready();u=w['unit'];u.pilot_hits=prior
            if prior==8:u.pilot=None
            set_hex(w,'WATER',2);u.z=-2;u.sections[Location.HEAD].armor=0
            if already_destroyed:
                damage.destroy_mech(u,u,showboom=False,engine=w['engine'])
            self.assertTrue(flood_location(u,Location.HEAD,-2))
            self.assertTrue(u.is_destroyed)
            self.assertIsNone(u.pilot)
            self.assertEqual(expected,u.pilot_hits)
