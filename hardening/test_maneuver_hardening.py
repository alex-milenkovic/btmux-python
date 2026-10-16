"""New maneuver command guards, feedback, LOS invalidation and event ownership."""
import unittest
from acceptance.movement.context import fresh, advance
from tests.test_maneuver import make_turreted_vehicle
from entities.mech import MechStatus as S, VehicleLocation
from entities.pilot import Pilot
from core.events import EventType
from systems import maneuver
from systems.los import MECHMAPFLAG_MOVED


def ready():
    w={};fresh(w);return w


class TestManeuverHardening(unittest.TestCase):
    def test_command_guards_reject_another_pilot_and_destroyed_units(self):
        for name,arg in (('rotate_torso','left'),('set_lateral','FL'),('set_turret',90)):
            for state,expected in (('caller',"You're not the pilot!"),('dead','Unit is destroyed.')):
                w=ready();u=make_turreted_vehicle() if name=='set_turret' else w['unit']
                caller=Pilot() if state=='caller' else u.pilot
                if state=='dead':u.set_status(S.DESTROYED)
                self.assertEqual((False,expected),getattr(maneuver,name)(w['engine'],u,arg,caller=caller))

    def test_opposite_torso_command_centers_with_directional_feedback(self):
        for prior,arg,message in ((S.TORSO_RIGHT,'Left','You rotate your torso left.'),(S.TORSO_LEFT,'Right','You rotate your torso right.')):
            w=ready();u=w['unit'];u.set_status(prior);u.mapflag=0
            self.assertEqual((True,message),maneuver.rotate_torso(w['engine'],u,arg,caller=u.pilot))
            self.assertFalse(u.has_status(S.TORSO_LEFT|S.TORSO_RIGHT))
            self.assertTrue(u.mapflag & MECHMAPFLAG_MOVED)

    def test_invalid_torso_input_reports_the_error_and_marks_los(self):
        for arg in ('invalid',None):
            w=ready();u=w['unit'];u.mapflag=0
            self.assertEqual((False,'Rotate must have LEFT RIGHT or CENTER.'),maneuver.rotate_torso(w['engine'],u,arg))
            self.assertTrue(u.mapflag & MECHMAPFLAG_MOVED)

    def test_turret_current_internal_boundary_and_report_los(self):
        for internal,expected in ((0,False),(1,True)):
            w=ready();u=make_turreted_vehicle();u.sections[VehicleLocation.TURRET].internal=internal;u.mapflag=0
            result=maneuver.set_turret(w['engine'],u,None,caller=u.pilot)
            self.assertEqual(expected,result[0])
            if expected:self.assertTrue(u.mapflag & MECHMAPFLAG_MOVED)
            else:self.assertEqual("You don't have a turret.",result[1])

    def test_lateral_replacement_and_cancel_preserve_another_units_event(self):
        w=ready();u=w['unit'];other=ready()['unit']
        self.assertTrue(maneuver.set_lateral(w['engine'],other,'FL')[0])
        other_event=other._lateral_event
        self.assertTrue(maneuver.set_lateral(w['engine'],u,'FL')[0])
        own=u._lateral_event
        self.assertTrue(maneuver.set_lateral(w['engine'],u,'FR')[0])
        self.assertTrue(own.zombie);self.assertFalse(other_event.zombie)
        self.assertEqual((True,'Lateral mode change aborted.'),maneuver.set_lateral(w['engine'],u,'-'))
        self.assertFalse(other_event.zombie)
        self.assertFalse(w['engine'].has_event(EventType.LATERAL,u))
        self.assertEqual((False,'Invalid mode!'),maneuver.set_lateral(w['engine'],u,'badmode'))

    def test_turnmode_requires_the_actual_pilot_but_allows_that_pilot(self):
        for absent in (False,True):
            w=ready();u=w['unit'];caller=Pilot()
            if absent:u.pilot=None;caller=None
            self.assertEqual((False,"You're not the pilot!"),maneuver.set_turnmode(w['engine'],u,'tight',caller))
        w=ready();u=w['unit']
        self.assertEqual((True,'You brace for tighter turns.'),maneuver.set_turnmode(w['engine'],u,'tight',u.pilot))


    def test_lateral_display_spellings_resolve_to_the_same_scheduled_heading(self):
        for arg in ('Front/Left','Front Left','Rear/Right','Rear Right'):
            w=ready();u=w['unit']
            self.assertTrue(maneuver.set_lateral(w['engine'],u,arg)[0])
            advance(w,30)
            self.assertEqual(300 if arg.startswith('Front') else 120,u.lateral)
