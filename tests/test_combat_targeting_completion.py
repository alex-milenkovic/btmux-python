"""Lock command grammar and delayed sixth-sense notifications."""
import unittest
from unittest.mock import patch
from core.game_loop import GameEngine
from core.randomness import use_source
from entities.mech import Mech,MechStatus as S,Specials,CritStatus as C
from entities.map import GameMap
from entities.pilot import Pilot
from systems import targeting
from tests.test_damage_failures import Draws


class TargetingCompletionTest(unittest.TestCase):
    def setUp(self):
        self.e=GameEngine()
        self.board=GameMap(40,40)
        self.board._id=1000
        self.e.register_entity(self.board)
        self.u,self.v=Mech.create_test_mech(),Mech.create_test_mech()
        for u in (self.u,self.v):
            u.pilot=Pilot()
            u.map=self.board
            u.set_status(S.STARTED)
            u.rtons=50*1024
            self.e.register_entity(u)
            u.mapindex=self.board._id
            u.pilot._id=u._id+100
            u.pilot.location=u._id
        self.board.mechs_on_map=[self.u,self.v]
        self.v.contact_id='AB'
        self.v.specials |= Specials.SS_ABILITY

    def test_lock_atoi_prefix_and_signed_floor_and_atomic_mode_failure(self):
        from entities.map import WATER
        self.board.set_terrain(3,4,WATER)
        self.board.set_elevation(3,4,2)
        ok,_=targeting.lock_command(self.e,self.u,'3junk 4')
        self.assertTrue(ok)
        self.assertEqual((3,4,-2),(self.u.targ_x,self.u.targ_y,self.u.targ_z))
        self.assertFalse(targeting.lock_command(self.e,self.u,'4 5 wrong')[0])
        self.assertEqual((3,4),(self.u.targ_x,self.u.targ_y))

    def test_sixth_sense_boundaries_and_delayed_delivery(self):
        for delta,distance,index in ((-20,8,0),(-19,8,1),(20,8,2),(-20,9,3),(0,19.9,4),(20,20,8)):
            self.u.rtons=(50+delta)*1024
            self.v.movement_messages=[]
            self.e.events.set_tick(0)
            with patch('systems.targeting.fa_mech_range',return_value=distance),use_source(Draws(8,2)):
                targeting.sixth_sense_check(self.u,self.v)
            self.e.events.set_tick(1)
            self.e.events.run_events()
            self.assertEqual([],self.v.movement_messages)
            self.e.events.set_tick(2)
            self.e.events.run_events()
            self.assertEqual([targeting.SIXTH_SENSE_MESSAGES[index]],self.v.movement_messages)

    def test_observer_guard_and_callback_pilot_gates(self):
        self.u.crit_status |= C.OBSERVATORIC
        with use_source(Draws()):targeting.sixth_sense_check(self.u,self.v)
        self.assertEqual(0,self.e.events.count_type(targeting.EventType.SIXTH_SENSE))
        from types import SimpleNamespace
        self.v.pilot=None
        targeting.sixth_sense_event(SimpleNamespace(data=self.v,data2=99))
        self.assertEqual([],self.v.movement_messages)
        self.v.pilot=Pilot()
        self.v.pilot._id=100
        self.v.pilot.location=self.v._id
        self.v.set_status(S.UNCONSCIOUS)
        targeting.sixth_sense_event(SimpleNamespace(data=self.v,data2=99))
        self.assertEqual([],self.v.movement_messages)
        self.v.clear_status(S.UNCONSCIOUS)
        targeting.sixth_sense_event(SimpleNamespace(data=self.v,data2=99))
        self.assertEqual([targeting.SIXTH_SENSE_MESSAGES[8]],self.v.movement_messages)

    def test_aim_accepts_section_name_and_dash_and_guard_precedes_dash(self):
        self.u.target=self.v._id
        self.assertTrue(targeting.aim_command(self.e,self.u,'CT')[0])
        self.assertEqual(4,self.u.aim)
        self.u.clear_status(S.STARTED)
        self.assertFalse(targeting.aim_command(self.e,self.u,'-')[0])
        self.assertEqual(4,self.u.aim)

class SourceSectionNamesTest(unittest.TestCase):
    def test_target_class_names_include_suits_quads_and_dropships(self):
        from systems.damage_commands import armor_section_from_string
        from entities.mech import Mech,UnitType as U,MoveType as M
        u=Mech.create_test_mech()
        for kind,movement,text,expected in ((U.BSUIT,M.BIPED,'S3',2),(U.MECH,M.QUAD,'FL',0),
            (U.SPHEROID_DS,M.FLY,'FR',0),(U.DS,M.FLY,'A',4),(U.VEH_GROUND,M.TRACK,'FS',2)):
            u.unit_type=kind;u.move_type=movement
            self.assertEqual(expected,armor_section_from_string(u,text))
