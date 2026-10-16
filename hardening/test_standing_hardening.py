"""Standing eligibility, pilot-facing responses and event completion."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from acceptance.movement.context import fresh, set_hex, psr
from entities.mech import MechStatus as S, CritStatus, Location, SectionConfig, MoveType, UnitType
from core.events import EventType
from physics import jump
from systems import combat


def fallen():
    w = {}
    fresh(w)
    w['unit'].set_status(S.FALLEN)
    return w


class TestStandingHardening(unittest.TestCase):
    def test_eligibility_reports_each_local_failure_and_success(self):
        cases = [('upright', 'Mech is not fallen'), ('off', 'Mech is not started'),
                 ('destroyed', 'Mech is destroyed'), ('gyro', 'Gyro is destroyed - cannot stand'),
                 ('legs', 'Both legs destroyed - cannot stand'), ('ready', '')]
        for state, message in cases:
            w = fallen()
            u = w['unit']
            if state == 'upright': u.clear_status(S.FALLEN)
            if state == 'off': u.clear_status(S.STARTED)
            if state == 'destroyed': u.set_status(S.DESTROYED)
            if state == 'gyro': u.set_crit_status(CritStatus.GYRO_DESTROYED)
            if state == 'legs':
                for loc in (Location.LLEG, Location.RLEG):
                    u.sections[loc].config |= SectionConfig.SECTION_DESTROYED
            with self.subTest(state=state):
                self.assertEqual((state == 'ready', message), jump.can_stand(u))

    def test_one_intact_leg_remains_eligible(self):
        for destroyed in (Location.LLEG, Location.RLEG):
            w = fallen()
            w['unit'].sections[destroyed].config |= SectionConfig.SECTION_DESTROYED
            self.assertEqual((True, ''), jump.can_stand(w['unit']))

    def test_stand_rejects_class_jump_and_cocoon_individually(self):
        for condition in ('class', 'jump', 'cocoon'):
            w = fallen()
            u = w['unit']
            if condition == 'class': u.unit_type = UnitType.VEH_GROUND
            if condition == 'jump': u.set_status(S.JUMPING)
            if condition == 'cocoon': u.cocoon = 11
            with self.subTest(condition=condition):
                self.assertEqual((False, 'This unit cannot stand at this time.'), jump.stand_up(u, w['engine'].events))

    def test_leg_count_boundary_differs_between_bipeds_and_quads(self):
        for move, count, accepted in ((MoveType.BIPED, 1, True), (MoveType.BIPED, 2, False),
                                     (MoveType.QUAD, 2, True), (MoveType.QUAD, 3, False)):
            w = fallen()
            u = w['unit']
            u.move_type = move
            for loc in (Location.LLEG, Location.RLEG, Location.LARM)[:count]:
                u.sections[loc].config |= SectionConfig.SECTION_DESTROYED
            with self.subTest(move=move, count=count), psr(w):
                result = jump.stand_up(u, w['engine'].events, 'anyway')
                self.assertEqual(accepted, result[0])
                if not accepted: self.assertEqual('You have no legs to stand on!', result[1])

    def test_stand_preserves_can_stand_and_posture_rejections(self):
        for condition, message in (('off', 'Mech is not started'), ('hull', 'You can not move while hulldown'),
                                   ('recover', "You're still recovering from your last attempt!")):
            w = fallen()
            u = w['unit']
            if condition == 'off': u.clear_status(S.STARTED)
            if condition == 'hull': u.set_status(S.HULLDOWN)
            if condition == 'recover': u._standfail_event = SimpleNamespace(zombie=False)
            with self.subTest(condition=condition):
                self.assertEqual((False, message), jump.stand_up(u, w['engine'].events))

    def test_check_adds_damage_modifier_and_invalid_argument_has_no_effect(self):
        w = fallen()
        u = w['unit']
        u.pilot.piloting = 5
        u.set_crit_status(CritStatus.GYRO_DAMAGED)
        self.assertEqual((True, 'Your BTH to stand would be: 8'), jump.stand_up(u, w['engine'].events, 'check'))
        self.assertTrue(u.is_fallen)
        self.assertEqual((False, "Unknown argument! use 'stand check', 'stand careful' or 'stand anyway'"), jump.stand_up(u, w['engine'].events, 'bogus'))
        self.assertFalse(w['engine'].has_event(EventType.STAND, u))

    def test_twelve_is_allowed_and_anyway_overrides_impossible_target(self):
        for target, argument, accepted in ((12, '', True), (13, '', False), (13, 'anyway', True)):
            w = fallen()
            w['unit'].pilot.piloting = target
            with self.subTest(target=target, argument=argument), psr(w):
                result = jump.stand_up(w['unit'], w['engine'].events, argument)
                self.assertEqual(accepted, result[0])
                if not accepted:
                    self.assertEqual("You would fail; use 'stand anyway' if you really want to stand.", result[1])

    def test_success_and_recovery_callbacks_deliver_feedback(self):
        for success in (False, True):
            w = fallen()
            u, engine = w['unit'], w['engine']
            with self.subTest(success=success), psr(w, success) as roll, patch.object(combat, 'roll_1d6', return_value=1), patch.object(combat, 'roll_2d6', return_value=12):
                result = jump.stand_up(u, engine.events)
                self.assertEqual(0, roll.call_args_list[0].args[1])
                if success:
                    self.assertEqual((True, 'You begin to stand up.'), result)
                    engine.run_ticks(10)
                    self.assertIsNone(u._stand_event)
                    self.assertIn('You finish standing up.', u.movement_messages)
                else:
                    self.assertEqual((False, 'You fail your attempt to stand and fall back on the ground'), result)
                    self.assertEqual(1, u.last_fall_levels)
                    engine.run_ticks(10)
                    self.assertIsNone(u._standfail_event)
                    self.assertIn('You have finally recovered from your attempt to stand.', u.movement_messages)

    def test_mechwarrior_stands_in_four_seconds_without_a_roll(self):
        w = fallen()
        u, engine = w['unit'], w['engine']
        u.unit_type = UnitType.MW
        with psr(w) as roll:
            self.assertTrue(jump.stand_up(u, engine.events)[0])
        roll.assert_not_called()
        self.assertEqual(4, engine.event_time_remaining(EventType.STAND, u))

    def test_only_shallow_submerged_ice_breaks_during_standing(self):
        for terrain, height, expected in (('ICE', -1, '~'), ('ICE', 0, '-'), ('ICE', -2, '-'), ('WATER', -1, '~')):
            w = fallen()
            u = w['unit']
            set_hex(w, terrain, 2)
            u.z = height
            with self.subTest(terrain=terrain, height=height), psr(w):
                self.assertTrue(jump.stand_up(u, w['engine'].events)[0])
                self.assertEqual(expected, w['map'].terrain(u.x, u.y))
