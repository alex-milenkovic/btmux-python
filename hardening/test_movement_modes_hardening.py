"""Mode command feedback, transition boundaries and interruption scheduling."""
import unittest
from types import SimpleNamespace
from acceptance.movement.context import fresh, set_hex
from entities.mech import MechStatus as S, MechStatus2 as S2, UnitType, Location, FireMode, SectionConfig
from core.events import EventType
from systems import movement_commands as modes


def ready():
    w = {}
    fresh(w)
    return w


class TestMovementModesHardening(unittest.TestCase):
    def test_mode_rejections_explain_the_specific_condition(self):
        cases = [('cocoon', 'sprint', 'While falling out of the sky?'),
            ('pending', 'sprint', 'You are already changing movement modes!'),
            ('other_mode', 'evade', 'You cannot perform multiple movement modes!'),
            ('no_advantage', 'dodge', 'You need the Dodge Maneuver advantage.'),
            ('absent_advantage', 'dodge', 'You need the Dodge Maneuver advantage.'),
            ('charge', 'sprint', 'You cannot change modes while charging!'),
            ('recycle', 'sprint', 'You have weapons or limbs recycling!'),
            ('jump', 'sprint', 'You cannot do this while jumping, towing, or mounted.'),
            ('tow', 'sprint', 'You cannot do this while jumping, towing, or mounted.'),
            ('mounted', 'sprint', 'You cannot do this while jumping, towing, or mounted.'),
            ('limping', 'sprint', "That's kind of hard while limping."),
            ('water', 'sprint', 'You cannot start sprinting while in water!'),
            ('hip', 'evade', 'You need both hips functional to evade.')]
        for condition, mode, expected in cases:
            w = ready()
            u = w['unit']
            if condition == 'cocoon': u.cocoon = 11
            if condition == 'pending': modes.schedule_mode(w['engine'], u, S2.SPRINTING, True)
            if condition == 'other_mode': u.set_status2(S2.SPRINTING)
            if condition == 'no_advantage': u.pilot.dodge_maneuver = False
            if condition == 'absent_advantage': del u.pilot.dodge_maneuver
            if condition == 'charge': u.charge_target = 1
            if condition == 'recycle': u.sections[Location.LARM].recycle = 10
            if condition == 'jump': u.set_status(S.JUMPING)
            if condition == 'tow': u.carrying = 1
            if condition == 'mounted': u.swarm_target = object()
            if condition == 'limping': u.sections[Location.LLEG].config |= SectionConfig.SECTION_DESTROYED
            if condition == 'water':
                set_hex(w, 'WATER', 2)
                u.z = -2
            if condition == 'hip': u.sections[Location.LLEG].criticals[0].firemode |= FireMode.DISABLED_MODE
            with self.subTest(condition=condition):
                self.assertEqual((False, expected), modes.set_mode(w['engine'], u, mode))

    def test_zero_carrying_and_charge_ids_do_not_block_modes(self):
        w = ready()
        w['unit'].carrying = w['unit'].charge_target = 0
        self.assertEqual((True, 'You begin changing sprint mode.'), modes.set_mode(w['engine'], w['unit'], 'sprint'))

    def test_callback_feedback_and_exact_speed_boundaries(self):
        cases = [('sprint', S2.SPRINTING, 0, 20, 20), ('sprint', S2.SPRINTING, .5, 20, 20),
                 ('evade', S2.EVADING, -1, 20, 20), ('evade', S2.EVADING, 70, 20, 64.5),
                 ('evade', S2.EVADING, 64.5, 20, 20), ('evade', S2.EVADING, 20, 70, 64.5)]
        for name, flag, speed, desired, expected in cases:
            w = ready()
            u = w['unit']
            u.speed, u.desired_speed = speed, desired
            modes.schedule_mode(w['engine'], u, flag, True)
            w['engine'].run_ticks(30)
            with self.subTest(mode=name, speed=speed, desired=desired):
                self.assertTrue(u.has_status2(flag))
                self.assertEqual(expected, u.desired_speed)
                self.assertIn('Movement mode '+flag.name+' enabled.', u.movement_messages)
                self.assertTrue(modes.set_mode(w['engine'], u, name)[0])
                w['engine'].run_ticks(30)
                self.assertFalse(u.has_status2(flag))
                self.assertIn('Movement mode '+flag.name+' disabled.', u.movement_messages)

    def test_dodge_callback_explains_limb_use_since_request(self):
        w = ready()
        u = w['unit']
        self.assertTrue(modes.set_mode(w['engine'], u, 'dodge')[0])
        u.sections[Location.LARM].recycle = 20
        w['engine'].run_ticks(1)
        self.assertFalse(u.has_status2(S2.DODGING))
        self.assertIn('You cannot enter DODGE mode due to physical useage.', u.movement_messages)

    def test_damage_interrupt_preserves_existing_exit_and_fixed_thirty_second_delay(self):
        for existing in (False, True):
            w = ready()
            u, engine = w['unit'], w['engine']
            u.unit_type = UnitType.MW
            u.set_status2(S2.SPRINTING)
            previous = None
            if existing:
                modes.schedule_mode(engine, u, S2.SPRINTING, False, 30)
                previous = u._mode_event
            modes.damage_interrupt(u)
            with self.subTest(existing=existing):
                self.assertFalse(u.has_status2(S2.SPRINTING))
                self.assertEqual(30, engine.event_time_remaining(EventType.MOVEMODE, u))
                if existing: self.assertIs(previous, u._mode_event)
                self.assertIn('You lose your sprinting momentum as you take damage!', u.movement_messages)
                engine.run_ticks(30)
                self.assertFalse(u.has_status2(S2.SPRINTING))
                self.assertIsNone(u._mode_event)
                self.assertIn('Movement mode SPRINTING disabled.', u.movement_messages)

    def test_damage_interrupt_cancels_entry_and_supports_missing_engine(self):
        w = ready()
        u = w['unit']
        modes.schedule_mode(w['engine'], u, S2.SPRINTING, True)
        pending = u._mode_event
        modes.damage_interrupt(u)
        self.assertTrue(pending.zombie)
        self.assertIsNone(u._mode_event)
        self.assertIn('Your movement mode changes are cancelled as you take damage!', u.movement_messages)
        u._engine = None
        u.set_status2(S2.SPRINTING)
        modes.damage_interrupt(u)
        self.assertFalse(u.has_status2(S2.SPRINTING))
        self.assertIsNone(u._mode_event)
