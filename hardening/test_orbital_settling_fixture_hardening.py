"""Orbital fixture units and truthful settling completion assertions."""
import unittest
from unittest.mock import patch
from acceptance.movement import context, orbital, settling
from entities.mech import MechStatus as S, Location
from core.events import EventType
from physics import jump


def ready():
    w = {}
    context.fresh(w)
    return w


class TestOrbitalSettlingFixtures(unittest.TestCase):
    def test_flood_fixture_rejects_impossible_armor_and_accepts_intact_boundaries(self):
        for section,front,rear,original,message in (
                ('CTORSO','17','5','5','remaining armor exceeds original armor'),
                ('CTORSO','10','6','5','remaining armor exceeds original armor'),
                ('LARM','0','0','3','only torso sections have rear armor')):
            with self.subTest(section=section,front=front,rear=rear),self.assertRaises(ValueError) as error:
                settling.flooded_section(ready(),section,front,rear,original)
            self.assertEqual(message,str(error.exception))
        for section in ('LTORSO','RTORSO','CTORSO'):
            w=ready();loc=Location[section]
            front=w['unit'].sections[loc].armor_orig
            settling.flooded_section(w,section,str(front),'5','5')
            self.assertEqual((front,5,5),(w['unit'].sections[loc].armor,w['unit'].sections[loc].rear,w['unit'].sections[loc].rear_orig))

    def test_orbital_fixture_preserves_nominal_tons_and_fixed_point_equipment_mass(self):
        w = ready()
        orbital.orbit_setup(w, '60', '20', '2')
        self.assertEqual(60, w['unit'].tonnage)
        self.assertEqual(60 * 1024, w['unit'].measured_mass)
        self.assertEqual(2, w['roll'])
        w['unit'].set_status(S.FALLEN)
        with self.assertRaises(AssertionError):
            orbital.orbit_start(w, '0')

    def test_orbital_roll_fixture_endpoints_and_invalid_diagnostics(self):
        with self.assertRaises(ValueError) as error:
            orbital.cocoon_setup(ready(), '20', '11', '-1')
        self.assertEqual('jump capability must be nonnegative', str(error.exception))
        for action, label in ((lambda w, roll: orbital.orbit_setup(w, '50', '20', roll), 'pilot roll'), (lambda w, roll: orbital.touchdown_terrain(w, 'GRASSLAND', '11', roll), 'pilot roll'), (lambda w, roll: orbital.interception(w, '1', roll), 'interception roll')):
            w = ready()
            action(w, '2')
            action(w, '12')
            with self.assertRaises(ValueError) as error:
                action(w, '13')
            self.assertEqual(f'{label} must be from 2 through 12: 13', str(error.exception))

    def test_interception_breach_uses_the_real_fall_queue(self):
        w = ready()
        orbital.interception_setup(w, '5', '20')
        orbital.interception(w, '5', '9')
        orbital.interception_result(w, '0', '20')
        self.assertTrue(w['engine'].has_event(EventType.FALL, w['unit']))
        self.assertFalse(w['engine'].has_event(EventType.OOD, w['unit']))

    def test_fall_fixture_is_positioned_on_its_declared_terrain_floor(self):
        for terrain in ('WATER', 'GRASSLAND'):
            w = ready()
            settling.fall_setup(w, '50', terrain, '100', '350')
            u = w['unit']
            self.assertEqual(w['map'].base_elevation(u.x, u.y), u.z)

    def test_settling_invalid_tokens_and_direction_have_actionable_failures(self):
        for action, expected in ((lambda w: settling.fall(w, '1', '7'), 'fall direction die must be from 1 through 6: 7'), (lambda w: settling.flood_setup(w, 'BIPED', 'BAD_POSTURE', '1'), 'BAD_POSTURE'), (lambda w: settling.workflow_setup(w, 'BAD_WORKFLOW'), 'BAD_WORKFLOW'), (lambda w: settling.workflow_result(w, 'BAD_RESULT'), 'BAD_RESULT')):
            with self.assertRaises(ValueError) as error:
                action(ready())
            self.assertEqual(expected, str(error.exception))

    def test_standing_completion_assertions_reject_a_still_pending_event(self):
        for workflow, result in (('QUAD_STAND', 'STANDING_WITHOUT_ROLL'), ('STAND_CHECK', 'BTH_REPORTED_NO_STATE_CHANGE')):
            w = ready()
            settling.workflow_setup(w, workflow)
            settling.workflow(w)
            u = w['unit']
            w['engine'].cancel_events_of_type(EventType.STAND, u)
            u._stand_event = w['engine'].schedule_event(20, EventType.STAND, lambda e: None, data=u)
            with self.subTest(workflow=workflow), self.assertRaises(AssertionError):
                settling.workflow_result(w, result)

    def test_early_land_keeps_its_actual_command_result(self):
        w = ready()
        settling.workflow_setup(w, 'EARLY_LAND')
        settling.workflow(w)
        self.assertEqual((True, 'You are able to abort the jump.'), w['command'])

    def test_intact_jump_stops_advancing_at_its_actual_landing_tick(self):
        w = ready()
        settling.workflow_setup(w, 'INTACT_JUMP')
        landing_ticks = []
        original = jump.land_mech
        def landed(*args, **kwargs):
            landing_ticks.append(w['engine'].events.tick)
            return original(*args, **kwargs)
        with patch.object(jump, 'land_mech', side_effect=landed):
            settling.workflow(w)
        self.assertEqual([w['engine'].events.tick], landing_ticks)

    def test_named_bth_13_workflow_uses_that_pilot_threshold(self):
        w = ready()
        settling.workflow_setup(w, 'STAND_BTH_13')
        settling.workflow(w)
        self.assertEqual(13, w['unit'].pilot.piloting)

    def test_standing_result_stops_at_the_actual_completion_tick(self):
        w = ready()
        settling.workflow_setup(w, 'QUAD_STAND')
        settling.workflow(w)
        due_tick = w['unit']._stand_event.tick
        settling.workflow_result(w, 'STANDING_WITHOUT_ROLL')
        self.assertEqual(due_tick, w['engine'].events.tick)

    def test_touchdown_stops_at_its_actual_scheduled_event_tick(self):
        w = ready()
        orbital.touchdown_setup(w, '5')
        orbital.touchdown_terrain(w, 'GRASSLAND', '11', '7')
        due_tick = w['engine'].events.tick + w['engine'].event_time_remaining(EventType.OOD, w['unit'])
        orbital.touchdown(w)
        self.assertEqual(due_tick, w['engine'].events.tick)
