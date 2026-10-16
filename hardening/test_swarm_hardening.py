"""Swarm identity, detachment cleanup and local damage/event boundaries."""
import unittest
from unittest.mock import patch
from acceptance.movement.context import fresh
from entities.mech import Mech, MechStatus2 as S2, UnitType, Location
from core.events import EventType
from systems import swarm, combat
from systems.piloting import PilotingResult


def mounted():
    w = {}
    fresh(w)
    host = w['unit']
    host._id = 101
    suit = Mech.create_test_mech()
    suit._id = 102
    suit.unit_type = UnitType.BSUIT
    suit.set_hex_position(host.x, host.y)
    w['map'].add_mech(suit)
    w['engine'].register_entity(suit)
    suit._engine = w['engine']
    suit.swarm_target = host
    host.swarmer = suit
    suit.set_status2(S2.UNIT_MOUNTING)
    host.set_status2(S2.UNIT_MOUNTED)
    return w, suit


class TestSwarmHardening(unittest.TestCase):
    def test_swarmers_accept_object_and_id_but_ignore_unrelated_occupants(self):
        w, suit = mounted()
        other = Mech.create_test_mech()
        other._id = 103
        w['map'].add_mech(other)
        for target in (w['unit'], w['unit']._id):
            suit.swarm_target = target
            self.assertEqual([suit], swarm.swarmers(w['unit']))
        self.assertEqual([], swarm.swarmers(other))

    def test_intentional_detach_resolves_id_and_recycles_only_surviving_members(self):
        w, suit = mounted()
        host = w['unit']
        suit.swarm_target = host._id
        suit.speed = 12
        suit.sections[2].internal = 0
        with patch('systems.piloting.make_piloting_roll') as roll:
            swarm.detach(suit, intentional=True)
        roll.assert_not_called()
        self.assertIsNone(suit.swarm_target)
        self.assertIsNone(host.swarmer)
        self.assertFalse(suit.has_status2(S2.UNIT_MOUNTING))
        self.assertFalse(host.has_status2(S2.UNIT_MOUNTED))
        self.assertEqual([20, 20, 0, 20, 20, 20, 0, 0], [s.recycle for s in suit.sections])
        self.assertEqual(0, suit.speed)
        self.assertTrue(w['engine'].has_event(EventType.MOVE, suit))
        self.assertIn("You drop from the 'mech!", suit.movement_messages)

    def test_failed_detach_roll_preserves_local_damage_context_and_longer_recycle(self):
        w, suit = mounted()
        before = suit.sections[Location.CTORSO].armor
        with patch('systems.piloting.make_piloting_roll', return_value=PilotingResult(success=False)) as roll, patch.object(swarm.random, 'randint', return_value=int(Location.CTORSO)) as draw, patch.object(combat, 'apply_damage_with_transfer', wraps=combat.apply_damage_with_transfer) as applied:
            swarm.detach(suit)
        roll.assert_called_once_with(suit, 4)
        draw.assert_called_once_with(0, 5)
        applied.assert_called_once_with(suit, int(Location.CTORSO), 11, attacker=suit)
        self.assertEqual(before - 11, suit.sections[Location.CTORSO].armor)
        self.assertEqual([45] * 6 + [0, 0], [s.recycle for s in suit.sections])

    def test_missing_host_id_or_map_is_a_no_change_detach(self):
        for has_map in (False, True):
            w, suit = mounted()
            suit.swarm_target = -99999
            if not has_map: suit.map = None
            with self.subTest(has_map=has_map):
                swarm.detach(suit)
                self.assertEqual(-99999, suit.swarm_target)
                self.assertTrue(suit.has_status2(S2.UNIT_MOUNTING))
