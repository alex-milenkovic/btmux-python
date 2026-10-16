"""Shared local guards, C numeric prefixes and notification delivery."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from acceptance.movement.context import fresh, set_hex
from entities.mech import MechStatus as S, MechStatus2 as S2, MoveType
from systems import movement_commands as common
from physics import movement


def ready():
    w = {}
    fresh(w)
    return w


class TestMovementCommonHardening(unittest.TestCase):
    def test_notification_initialization_history_return_and_delivery(self):
        # The helper supports any unit carrying the notification contract.
        unit = SimpleNamespace()
        messages = []
        with patch.object(movement, 'NOTIFY_HOOK', side_effect=lambda who, text: messages.append((who, text))):
            self.assertEqual('first', common.notify(unit, 'first'))
            self.assertEqual('second', common.notify(unit, 'second'))
        self.assertEqual(['first', 'second'], unit.movement_messages)
        self.assertEqual([(unit, 'first'), (unit, 'second')], messages)

    def test_guard_reports_individual_conditions(self):
        for condition, expected in (('dead', 'Unit is destroyed.'), ('mapless', 'Invalid map!'),
            ('offmap', 'Invalid map!'), ('unconscious', 'You are unconscious or blinded.'),
            ('blinded', 'You are unconscious or blinded.'), ('pilot', 'You have no pilot!'),
            ('off', 'Reactor is not started.')):
            w = ready()
            u = w['unit']
            if condition == 'dead': u.set_status(S.DESTROYED)
            if condition == 'mapless': u.map = None
            if condition == 'offmap': u.x = -1
            if condition == 'unconscious': u.set_status(S.UNCONSCIOUS)
            if condition == 'blinded': u.set_status(S.BLINDED)
            if condition == 'pilot': u.pilot = None
            if condition == 'off': u.clear_status(S.STARTED)
            with self.subTest(condition=condition):
                self.assertEqual(expected, common.guard(u))

    def test_pilot_only_policy_distinguishes_other_callers_from_default(self):
        w = ready()
        u = w['unit']
        other = object()
        self.assertIsNone(common.guard(u, other))
        self.assertIsNone(common.guard(u, u.pilot, True))
        self.assertIsNone(common.guard(u, None, True))
        self.assertEqual("You're not the pilot!", common.guard(u, other, True))

    def test_movement_guard_reports_each_condition_and_allows_floating_naval_unit(self):
        for condition, expected in (('fortified', 'Your fortified state prevents you from moving.'),
            ('stationary', 'This piece of equipment is stationary!'),
            ('standing', 'You are currently standing up and cannot move.'),
            ('prone', 'You are currently prone and cannot move.'),
            ('beached', 'You are regrettably unable to move at this time.'), ('afloat', None)):
            w = ready()
            u = w['unit']
            if condition == 'fortified': u.set_status2(S2.FORTIFIED)
            if condition == 'stationary': u.move_type = MoveType.NONE
            if condition == 'standing': u._stand_event = SimpleNamespace(zombie=False)
            if condition == 'prone': u.set_status(S.FALLEN)
            if condition in ('beached', 'afloat'): u.move_type = MoveType.HULL
            if condition == 'afloat':
                set_hex(w, 'WATER', 2)
                u.z = -1
            with self.subTest(condition=condition):
                self.assertEqual(expected, common.moving_guard(u))

    def test_c_numeric_prefixes_accept_both_exponent_cases(self):
        for value, expected in (('1E2suffix', 100), ('1e2suffix', 100), (' -.25e+2xx', -25), ('3E-1', .3)):
            with self.subTest(value=value):
                self.assertEqual(expected, common.c_number(value))
        self.assertEqual(1, common.c_number('1E2', True))

    def test_maybe_move_records_engine_even_during_orbital_descent(self):
        w = ready()
        u = w['unit']
        u._engine = None
        u.cocoon = 11
        common.maybe_move(w['engine'], u)
        self.assertIs(w['engine'], u._engine)
