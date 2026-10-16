"""Movement-card orbital stacking exclusions and C landing notification flag."""
import unittest
from unittest.mock import patch
from acceptance.movement.context import fresh
from entities.mech import Mech, MechStatus as S, UnitType
from physics import collision
from physics.movement import MP1
from systems.piloting import PilotingResult


def setup():
    w = {}
    fresh(w)
    u = w['unit']
    u.speed = 6 * MP1
    other = Mech.create_test_mech()
    other.set_hex_position(u.x, u.y)
    other.set_status(S.STARTED)
    other.team = u.team
    w['map'].add_mech(other)
    return w, other


class TestCollisionMovementIntegration(unittest.TestCase):
    def test_orbital_and_jumping_occupants_are_skipped_without_ending_the_scan(self):
        for excluded in ('cocoon', 'jumping', 'vehicle'):
            w, other = setup()
            if excluded == 'cocoon':
                other.cocoon = 2
            elif excluded == 'jumping':
                other.set_status(S.JUMPING)
            else:
                other.unit_type = UnitType.VEH_GROUND
            last = Mech.create_test_mech()
            last.set_hex_position(w['unit'].x, w['unit'].y)
            last.set_status(S.STARTED)
            last.team = w['unit'].team
            w['map'].add_mech(last)
            self.assertEqual(2, collision.mechs_in_hex(w['map'], 3, 3, -1, 0))
            with patch.object(collision.random, 'randint', return_value=0), patch.object(collision, 'cause_damage') as damage:
                result = collision.domino_space_in_hex(w['map'], w['unit'], 3, 3, -1, 0, 2)
            self.assertEqual(1, result)
            self.assertIs(last, damage.call_args_list[0].args[1])

    def test_failed_landing_uses_integer_half_jump_mp_for_fall_notification(self):
        # mech.move.c:2123-2124; test both sides of integer half-MP boundary
        # and gravity scaling, using real falling damage/state and notification.
        for jump_mp, gravity, expected_mp in ((1, 100, 1), (2, 100, 2), (4, 200, 2), (1, 50, 2), (2, 101, 1)):
            w, other = setup()
            u = w['unit']
            u.jump_speed = jump_mp * MP1
            u.set_status(S.UNDERGRAVITY)
            w['map'].grav = gravity
            with patch.object(collision, 'BTECH_STACKING', 1), patch.object(collision.random, 'randint', return_value=0), patch('systems.piloting.make_piloting_roll', return_value=PilotingResult(success=False)) as psr, patch('systems.combat.roll_1d6', return_value=1), patch('systems.combat.roll_2d6', return_value=7):
                result = collision.domino_space_in_hex(w['map'], u, 3, 3, -1, 2, 2)
            self.assertEqual(1, result)
            self.assertEqual((u, 2 + expected_mp // 2), psr.call_args_list[0].args)
            self.assertTrue(u.is_fallen)
            self.assertEqual(1, u.last_fall_levels)
            fall_messages = [m for m in u.movement_messages if m.startswith('Mech fell')]
            self.assertEqual(1 if expected_mp >= 2 else 0, len(fall_messages))
