"""Physical audit regressions through source-ordered command and packet consumers."""
import unittest
from unittest.mock import patch
from core.randomness import use_source
from core.events import EventType
from entities.mech import Location as L, MechStatus as S, UnitType as U
from systems import physical as p
from systems import hit_locations as h
from systems.combat import HitGroup as H
from tests import test_combat_physical_completion as fixtures


class PhysicalAuditTests(unittest.TestCase):
    setUp = fixtures.PhysicalCommandsTest.setUp

    def test_arm_refusal_precedes_other_arm_attack_without_reply_replay(self):
        self.u.sections[L.LARM].internal = self.u.sections[L.LARM].armor = 0
        trace = []
        original = p.mech_notify
        def notice(unit, audience, text):
            trace.append(('notice', unit._id, text))
            return original(unit, audience, text)
        def damage(*args, **kwargs):
            trace.append(('damage', args[0]._id, args[2]))
            return args[2]
        with patch.object(p, 'mech_notify', side_effect=notice), patch.object(p, 'apply_damage_with_transfer', side_effect=damage):
            result = self.s.invoke(p.physical_command, self.u, 'punch')
        self.assertTrue(result['accepted'])
        self.assertIn('left arm is destroyed', trace[0][2])
        self.assertEqual(1, sum('You try to punch' in str(row[2]) for row in trace))
        self.assertEqual('damage', trace[-1][0])
        self.assertFalse(any('tries to punch you' in text for text in self.u.movement_messages))
        self.assertEqual(60, self.u.sections[L.RARM].recycle)

    def test_class_refusal_precedes_bad_target_and_reaches_caller(self):
        self.u.unit_type = U.VEH_GROUND
        with patch('core.effects.notify_actor') as personal, patch.object(p, 'mech_notify') as unit_notice:
            result = p.physical_command(self.u, 'punch', 'ZZ', caller=self.u.pilot)
        self.assertFalse(result['accepted'])
        self.assertIn('with this vehicle', result['text'])
        personal.assert_called_once()
        self.assertIs(personal.call_args.args[1], self.u.pilot)
        unit_notice.assert_not_called()

    def test_stand_queue_is_authoritative_without_handle(self):
        self.u.standing_up = True
        self.assertTrue(p.phys_common_checks(self.u)[0])
        self.u._engine.events.schedule(10, EventType.STAND, lambda event: None, self.u)
        self.assertFalse(p.phys_common_checks(self.u)[0])

    def test_dfa_reselects_after_packet_fall_and_notifies_before_damage(self):
        self.u.status |= S.JUMPING | S.DFA_ATTACK
        self.s.streams.update(dfa_rolls=[12], physical_location=[3]*20)
        normals = []
        def damage(victim, location, amount, **kwargs):
            if victim is self.v:
                self.assertIn('You land on your target legs first!', self.u.movement_messages)
                victim.status |= S.FALLEN
            return amount
        def normal(victim, group, **kwargs):
            normals.append(victim)
            return L.CTORSO, False
        with patch.object(p, 'apply_damage_with_transfer', side_effect=damage), patch.object(p, 'get_punch_location', return_value=L.CTORSO) as punch, patch.object(h, 'find_hit_location', side_effect=normal):
            result = self.s.invoke(p.dfa_attack, self.u, self.v)
        self.assertTrue(result.hit)
        self.assertEqual(1, punch.call_count)
        self.assertTrue(normals and all(unit is self.v for unit in normals))

    def test_charge_retains_critical_between_target_and_self_streams(self):
        self.u.speed = 40
        flags = []
        def location(unit, group, critical=False):
            flags.append((unit, critical))
            return L.CTORSO, True
        with patch.object(h, 'find_hit_location', side_effect=location), patch.object(p, 'apply_damage_with_transfer', return_value=5):
            result = self.s.invoke(p.charge_mech, self.u, self.v, roll=12)
        self.assertTrue(result.attacker_hit)
        self.assertFalse(flags[0][1])
        self.assertTrue(all(flag for unit, flag in flags[1:]))
        self.assertTrue(any(unit is self.u for unit, flag in flags))

    def test_negative_charge_remainder_is_signed(self):
        packets = []
        with patch.object(h, 'find_hit_location', return_value=(L.CTORSO, False)), patch.object(p, 'apply_damage_with_transfer', side_effect=lambda unit, loc, amount, **kwargs: packets.append(amount) or amount):
            self.assertEqual(-2, p._apply_charge_clusters(self.u, None, H.FRONT, -7))
        self.assertEqual([-2], packets)

    def test_hit_statistics_and_existing_critical_do_not_skip_draw(self):
        self.u.unit_type = U.VEH_GROUND
        self.u.sections[2].armor_orig = self.u.sections[2].armor = 100
        draws = []
        with use_source(lambda name, low, high, default: draws.append(name) or 1):
            self.assertTrue(h.find_hit_location(self.u, H.FRONT, 2, profile='legacy', critical=True)[1])
        self.assertEqual(['crittable_chance'], draws)
        self.assertEqual(1, self.s.engine.randomness.total_hit_rolls)
        self.u.status |= S.COMBAT_SAFE
        h.find_hit_location(self.u, H.FRONT, 7, profile='legacy')
        self.assertEqual(1, self.s.engine.randomness.total_hit_rolls)
