"""Posture command refusal, lifecycle, cancellation and prone-fall boundaries."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from acceptance.movement.context import fresh, psr
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, MoveType, UnitType
from entities.pilot import Pilot
from core.events import EventType
from systems import movement_commands as posture
from systems import combat


def ready():
    w = {}
    fresh(w)
    w['unit'].move_type = MoveType.QUAD
    return w


class TestPostureHardening(unittest.TestCase):
    def test_hulldown_round_trip_preserves_state_feedback_and_event_owner(self):
        w = ready()
        u, engine = w['unit'], w['engine']
        u.desired_speed = 20
        u._engine = None
        self.assertEqual((True, 'You start to lower yourself to the ground.'), posture.hulldown(engine, u))
        self.assertEqual(0, u.desired_speed)
        self.assertIs(engine, u._engine)
        self.assertTrue(engine.has_event(EventType.HULLDOWN, u))
        self.assertEqual((False, 'You are busy changing your hulldown mode.'), posture.hulldown(engine, u))
        engine.run_ticks(10)
        self.assertTrue(u.has_status(S.HULLDOWN))
        self.assertIn('You finish lowering yourself to the ground.', u.movement_messages)
        self.assertEqual((False, 'You are already hulldown.'), posture.hulldown(engine, u))
        self.assertEqual((True, 'You start to lift yourself up.'), posture.hulldown(engine, u, '-'))
        engine.run_ticks(10)
        self.assertFalse(u.has_status(S.HULLDOWN))
        self.assertIn('You finish lifting yourself up.', u.movement_messages)
        self.assertEqual((False, 'You are not hulldown.'), posture.hulldown(engine, u, '-'))

    def test_hulldown_stop_cancels_only_the_requesting_unit(self):
        w = ready()
        u, engine = w['unit'], w['engine']
        self.assertEqual((False, 'You are not currently changing your hulldown mode.'), posture.hulldown(engine, u, 'stop'))
        self.assertEqual((False, "Invalid argument for 'hulldown'."), posture.hulldown(engine, u, 'bogus'))
        self.assertTrue(posture.hulldown(engine, u)[0])
        own = u._hulldown_event
        other = Mech.create_test_mech()
        other_event = engine.schedule_event(10, EventType.HULLDOWN, lambda ev: None, data=other)
        self.assertEqual((True, 'You stop changing your hulldown mode.'), posture.hulldown(engine, u, 'stop'))
        self.assertTrue(own.zombie)
        self.assertFalse(other_event.zombie)
        self.assertIsNone(u._hulldown_event)

    def test_hulldown_rejects_another_pilot_and_each_blocked_state(self):
        for condition in ('other_pilot', 'fortified', 'cocoon', 'fallen', 'jumping', 'standing', 'stabilizing'):
            w = ready()
            u = w['unit']
            caller = None
            if condition == 'other_pilot': caller = Pilot()
            if condition == 'fortified': u.set_status2(S2.FORTIFIED)
            if condition == 'cocoon': u.cocoon = 11
            if condition == 'fallen': u.set_status(S.FALLEN)
            if condition == 'jumping': u.set_status(S.JUMPING)
            if condition == 'standing': u._stand_event = SimpleNamespace(zombie=False)
            if condition == 'stabilizing': u._stabil_event = SimpleNamespace(zombie=False)
            expected = ("You're not the pilot!" if condition == 'other_pilot' else
                'Only unfortified QUADs on the ground can hulldown.' if condition in ('fortified', 'cocoon') else
                'You cannot hulldown while moving, prone, standing or stabilizing.')
            with self.subTest(condition=condition):
                self.assertEqual((False, expected), posture.hulldown(w['engine'], u, caller=caller))

    def test_prone_refuses_each_blocked_state_and_guard_failure(self):
        for condition in ('dead', 'class', 'fallen', 'jumping', 'cocoon', 'standing'):
            w = ready()
            u = w['unit']
            if condition == 'dead': u.set_status(S.DESTROYED)
            if condition == 'class': u.unit_type = UnitType.VEH_GROUND
            if condition == 'fallen': u.set_status(S.FALLEN)
            if condition == 'jumping': u.set_status(S.JUMPING)
            if condition == 'cocoon': u.cocoon = 11
            if condition == 'standing': u._stand_event = SimpleNamespace(zombie=False)
            with self.subTest(condition=condition):
                self.assertEqual((False, 'Unit is destroyed.' if condition == 'dead' else "You can't prone in this state!"), posture.prone(w['engine'], u))

    def test_prone_speed_and_stagger_control_the_required_roll_and_fall(self):
        for speed, stagger, modifier, levels in ((30, 0, 0, 1), (50, 0, 2, 2), (0, 3, 3, 1), (50, 3, 5, 2)):
            w = ready()
            u = w['unit']
            u.set_status(S.COMBAT_SAFE)
            u.speed, u.stagger_level = speed, stagger
            u.stagger_damage = 17
            u._engine = None
            with self.subTest(speed=speed, stagger=stagger), psr(w, False) as roll, patch.object(combat, 'roll_1d6', return_value=1):
                self.assertEqual((True, 'You drop to the ground prone!'), posture.prone(w['engine'], u))
                roll.assert_called_once_with(u, modifier)
                self.assertEqual(levels, u.last_fall_levels)
                self.assertEqual(0, u.stagger_damage)
                self.assertIs(w['engine'], u._engine)
                self.assertTrue(u.is_fallen)

    def test_stand_command_preserves_guards_and_event_engine(self):
        w = ready()
        u = w['unit']
        u.set_status(S.FALLEN)
        u._engine = None
        with psr(w):
            self.assertTrue(posture.stand(w['engine'], u)[0])
        self.assertIs(w['engine'], u._engine)
        self.assertTrue(w['engine'].has_event(EventType.STAND, u))
        u.set_status(S.DESTROYED)
        self.assertEqual((False, 'Unit is destroyed.'), posture.stand(w['engine'], u))
