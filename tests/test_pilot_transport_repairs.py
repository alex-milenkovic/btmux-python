"""Source boundaries needing real callbacks, partial writes and ordered effects."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from core.attributes import AttributeStore
from core.events import EventType as E
from core.randomness import use_source
from entities.mech import UnitType as U, MoveType as M, MechStatus as S, MechStatus2 as S2
from systems import occupants
from tests import test_transport as transport_fixture, test_ejection as ejection_fixture


class TransportRepairTests(unittest.TestCase):
    setUp=transport_fixture.TransportTest.setUp
    make=transport_fixture.TransportTest.make

    def carry(self):
        self.board.remove_mech(self.own)
        self.world.move(self.own._id,self.carrier._id)

    def test_loud_transport_delivers_attributes_and_actions_in_source_order(self):
        self.engine.attributes=AttributeStore()
        for ident,name,text in ((10,'A_LEAVE','Leaving'),(101,'A_TPORT','Teleporting'),(20,'A_ENTER','Entering')):
            self.engine.attributes.set(ident,name,text)
        calls=[]
        for ident,operation in ((10,'ALEAVE'),(101,'ATPORT'),(101,'AMOVE'),(20,'AENTER')):
            self.engine.effects.hooks[ident,operation]=lambda actor,target,op=operation:calls.append((op,actor._id,target._id,actor.location))
        self.assertEqual(1,occupants.tele_contents(self.engine,10,20,4))
        self.assertEqual([('ALEAVE',101,10,10),('ATPORT',101,101,20),('AMOVE',101,101,20),('AENTER',101,20,20)],calls)
        self.assertEqual(['Leaving','Teleporting','Entering'],self.actor.inbox)
        self.assertTrue(all(c['applied'] for c in self.engine.effects.hook_calls))

    def test_lock_failure_uses_actor_target_and_one_personal_notice(self):
        self.engine.attributes=AttributeStore()
        self.carrier.enter_lock='configured';self.carrier.lock_result=False
        self.carrier.fail_message='Legacy text must not replace the source default.'
        default="That unit's bay doors are locked."
        calls=[]
        self.engine.effects.hooks[20,'AFAIL']=lambda actor,target:calls.append(
            (actor._id,target._id,self.engine.action_requests[-1]['default']))
        for kind in (U.MECH,U.MW):
            for attribute in ('The hatch is sealed.',''):
                with self.subTest(kind=kind,attribute=attribute):
                    self.own.unit_type=kind;self.actor.inbox=[];calls.clear()
                    self.engine.attributes.set(20,'A_FAIL',attribute)
                    result=occupants.embark(self.own,self.actor,self.carrier)
                    self.assertFalse(result['ok'])
                    self.assertEqual(attribute or default,result['error'])
                    self.assertEqual([(101,20,default)],calls)
                    self.assertEqual([attribute or default],self.actor.inbox)
                    request=self.engine.action_requests[-1]
                    self.assertEqual(('A_FAIL','A_AFAIL',[],default),
                                     (request['what'],request['awhat'],request['args'],request['default']))
                    self.assertEqual(1000,self.own.location)

    def test_disposal_hooks_run_before_cleanup_and_cancel_owned_events(self):
        auto=SimpleNamespace(_id=77,_engine=self.engine,flags=0x17,mymechnum=10,
                             commands=[1],astar_path=[2],profile=[[3],None],weaplist=[4])
        self.engine.register_entity(auto);self.world.add(auto,10);self.own.auto=77
        self.engine.schedule_event(12,E.AUTOCOM,lambda event:None,data=auto)
        unrelated=self.engine.schedule_event(12,E.CUSTOM,lambda event:None,data=auto)
        self.engine.schedule_event(12,E.CUSTOM,lambda event:None,data=self.own)
        occupants.discard_mw(self.own);occupants.discard_mw(self.own)
        observed=[]
        self.engine.effects.hooks[1000,'ALEAVE']=lambda actor,target:observed.append(
            (actor.hardcode,actor in self.engine.get_entities(),target is self.board,actor.location))
        occupants.discard_event(SimpleNamespace(data=self.own))
        self.assertEqual([(True,True,True,1000)],observed)
        self.assertFalse(self.engine.events.pending_events(data=self.own))
        self.assertEqual([unrelated],self.engine.events.pending_events(data=auto))
        self.assertEqual((0x10,-1,-1),(auto.flags,auto.mymechnum,self.own.auto))
        self.assertEqual((None,None,[None,None],None),(auto.commands,auto.astar_path,auto.profile,auto.weaplist))
        self.assertEqual(901,self.own.location)

    def test_live_multitick_repair_blocks_exit_even_without_fixture_flag(self):
        from systems.repair_jobs import RepairJobs
        self.carry();self.own.repair_remaining=0
        jobs=RepairJobs(self.engine,None,None)
        jobs.schedule(47,self.own,101*65536+3*16,1)
        self.assertEqual(361,jobs.latest(self.own))
        result=occupants.unit_disembark(self.own,self.actor)
        self.assertFalse(result['ok']);self.assertIn('under repairs',result['error'])
        self.assertEqual((20,-1),(self.own.location,self.own.mapindex))

    def test_invalid_carrier_map_preserves_xy_but_copies_explicit_z(self):
        from physics.hexmath import ZSCALE
        self.carry();self.carrier.mapindex=999;self.carrier.x=8;self.carrier.y=9;self.carrier.z=7
        before=(self.own.x,self.own.y,self.own.last_x,self.own.last_y)
        result=occupants.unit_disembark(self.own,self.actor)
        self.assertFalse(result['ok']);self.assertIn('Major map error',result['error'])
        self.assertEqual(before,(self.own.x,self.own.y,self.own.last_x,self.own.last_y))
        self.assertEqual((-1,7,7*ZSCALE,20),(self.own.mapindex,self.own.z,self.own.fz,self.own.location))

    def test_refused_drop_still_finishes_recycle_health_and_carrier_speed(self):
        from systems.characters import set_value
        self.carry();self.carrier.z=5;self.own.set_status(S.FALLEN)
        self.engine.events._tick=30;self.own.last_weapon_recycle=0
        set_value(self.store,101,'Build',5);set_value(self.store,101,'Bruise',10)
        with patch('systems.vehicle_combat.correct_speed') as correct:
            result=occupants.unit_disembark(self.own,self.actor)
        self.assertTrue(result['ok'],result)
        self.assertEqual("You'll have to get up first.",result['ood_error'])
        self.assertEqual(1,self.actor.inbox.count(result['ood_error']))
        self.assertEqual([60]*8,[s.recycle for s in self.own.sections])
        self.assertEqual(30,self.own.last_weapon_recycle)
        self.assertEqual(1,self.own.pilot_hits)
        correct.assert_called_once_with(self.carrier)
        self.assertFalse(self.engine.has_event(E.OOD,self.own))

    def test_positive_stale_map_cache_notifies_then_resets_and_shuts_down(self):
        self.own.mapindex=999
        result=occupants.eject(self.own,self.actor)
        self.assertFalse(result['ok']);self.assertEqual(-1,self.own.mapindex)
        self.assertFalse(self.own.is_started)
        self.assertEqual(1,self.actor.inbox.count('You are on an invalid map! Map index reset!'))

    def test_ood_parsing_flying_type_and_notice_before_mode_change(self):
        from physics.orbital import initiate_ood
        from core.effects import notify_actor
        self.own.unit_type=U.VEH_GROUND;self.own.move_type=M.VTOL;self.own.desired_angle=37
        self.own.status2|=S2.EVADING|S2.SPRINTING
        observed=[]
        def notice(unit,actor,text):
            if text=='OOD initiated.':observed.append((unit.status2,unit.has_status(S.LANDED),self.engine.has_event(E.MOVE,unit)))
            return notify_actor(unit,actor,text)
        with patch('core.effects.notify_actor',side_effect=notice):
            self.assertTrue(initiate_ood(self.engine,self.own,'4tail 5 7 ignored',actor=self.actor)[0])
        self.assertEqual([(S2.EVADING|S2.SPRINTING,True,False)],observed)
        self.assertEqual(37,self.own.desired_angle)
        self.assertFalse(self.engine.has_event(E.OOD,self.own))
        self.own.unit_type=U.AERO;self.own.move_type=M.BIPED;self.own.status2|=S2.EVADING
        self.assertTrue(initiate_ood(self.engine,self.own,'4 5 8',actor=self.actor)[0])
        self.assertTrue(self.own.status2&S2.EVADING);self.assertEqual(0,self.own.desired_angle)


class EjectionRepairTests(unittest.TestCase):
    setUp=ejection_fixture.EjectionTest.setUp

    def test_contact_collisions_and_radio_follow_transfer_and_initialization(self):
        from entities.mech import CritStatus,Location
        from systems.notifications import personal_notify
        from systems.enhanced_crits import part_temp_nuke
        self.unit.contact_id='AA';self.unit.team=2
        slot=self.unit.sections[Location.HEAD].criticals[2];slot.brand=0x73
        draws=iter((0,0,1,1));trace=[]
        def source(name,low,high,fallback):
            self.assertEqual('map_contact_id',name)
            trace.append('contact');return next(draws)
        def broadcast(shell,text):
            trace.append(('los',shell.in_character,self.actor.location==shell._id,slot.brand,text))
        def radio():
            shell=self.world.objects[self.actor.location]
            self.assertTrue(shell.has_crit_status(CritStatus.PC_INITIALIZED))
            self.assertIs(self.actor,shell.pilot);self.assertTrue(shell.in_character)
            trace.append('radio');return 123456
        def notice(actor,text):
            if text=='You eject from the unit!':trace.append(('notice',slot.brand))
            personal_notify(actor,text)
        self.world.radio_source=radio
        with use_source(source),patch('systems.sensors.los_broadcast',side_effect=broadcast),patch('systems.occupants.personal_notify',side_effect=notice):
            result=occupants.eject(self.unit,self.actor)
        self.assertTrue(result['ok'],result)
        shell=self.world.objects[result['unit']]
        self.assertEqual('BB',shell.contact_id)
        self.assertEqual((3,3,3,3),(shell.x,shell.y,shell.last_x,shell.last_y))
        self.assertEqual('MechWarrior - Alice',shell.object_name)
        self.assertEqual(['contact']*4,trace[:4])
        self.assertEqual((False,True,0x73),trace[4][1:4])
        self.assertIn('[AA]',trace[4][4])
        self.assertEqual(['radio',('notice',0x73)],trace[5:7])
        self.assertEqual((0,3),(part_temp_nuke(slot),slot.brand))
