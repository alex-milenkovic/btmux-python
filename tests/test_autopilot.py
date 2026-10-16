"""Focused source-boundary checks for the complete AI port."""
import io
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from core.events import EventType as E
from core.game_loop import GameEngine
from entities.autopilot import Autopilot
from entities.mech import UnitType as U, MechStatus as S, CritStatus as C, Specials
from entities.weapon import get_weapon
from systems import autopilot_core as core
from systems import autopilot_ai as navigation
from systems import autopilot_commands as orders
from systems import autopilot_autogun as gun
from systems import autopilot_radio as radio
from systems import autopilot_storage as storage
from tools.autopilot import AutopilotSession


def unit_fixture(name='Sheep',ident=10,contact='SH',at=(3,10,0),team=1,**values):
    row=dict(name=name,id=ident,contact_id=contact,at=list(at),team=team,
        tonnage=50,gunnery=2,piloting=3,perception=2,
        actor=dict(id=1000+ident,location=ident,connected=True,gunnery=2,piloting=3,perception=2),
        core=dict(max_speed=64.5,desired_speed=0),
        communications=dict(radio_type=6,freq=[12345]),
        sections=[dict(index=i,armor=20,armor_orig=20,rear=0,rear_orig=0,internal=10,internal_orig=10) for i in range(8)])
    row.update(values)
    return row


class AutopilotTests(unittest.TestCase):
    def session(self,units=None,commands=(),engage=True,**document):
        directory=TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        units=units or [unit_fixture()]
        document.update(hud_display={'root':directory.name},units=units,
                        autopilots=[dict(name='ai',id=200,unit=units[0]['name'],commands=list(commands),engage=engage)],actions=[])
        document.setdefault('map',dict(size=[20,20]))
        document.setdefault('random',dict(seed=3))
        s=AutopilotSession(document)
        return s,s.autopilots['ai'],s.units[units[0]['name']]

    def test_defaults_are_installed_and_explicit_overrides_survive(self):
        engine=GameEngine()
        override=lambda a:None
        engine.auto_services['gun']=override
        a=core.auto_newautopilot(engine,20)
        self.assertIs(engine.auto_services['gun'],override)
        self.assertEqual(set(engine.auto_services),{'command','gun','sensor','profile','radio'})
        self.assertIsNone(a.mymech)
        self.assertEqual(a.speed,100)

    def test_command_records_roundtrip_and_atomic_rejection(self):
        s,a,u=self.session(commands=('goto 8 9','autogun target 14','roam radius 5 5 3'),engage=False)
        data=core.auto_save_commands(a)
        self.assertEqual(data[:5],b'\x33\x03\0\0\0')
        b=Autopilot(201)
        core.auto_load_commands(b,data)
        self.assertEqual([n.args for n in a.commands],[n.args for n in b.commands])
        with self.assertRaises(ValueError):core.auto_load_commands(b,data[:-1])
        self.assertEqual(len(b.commands),3)
        self.assertEqual(core.auto_valid_progline(a,1),0)
        self.assertIn('disabled',core.auto_jump(a,a)['message'])

    def test_queue_completion_cancellation_and_disabled_wait(self):
        s,a,u=self.session(commands=('speed 45','wait 1 2','speed 80'))
        s.action(dict(op='advance',seconds=4))
        self.assertEqual(a.speed,45)
        self.assertEqual(a.commands[0].args[0],'wait')
        self.assertFalse(s.engine.events.pending_events(data=a))
        core.schedule(a,4,E.AUTOGOTO,orders.auto_dumbgoto_event)
        self.assertTrue(core.auto_pilot_on(a))
        core.auto_disengage(a,a)
        self.assertFalse(s.engine.events.pending_events(data=a))
        core.auto_delcommand(a,a,'1')
        core.auto_engage(a,a)
        s.action(dict(op='advance',seconds=2))
        self.assertEqual(a.speed,80)
        self.assertEqual(a.commands,[])

    def test_single_separator_numeric_and_radio_matching_boundaries(self):
        s,a,u=self.session()
        self.assertEqual(core.explode_arguments('SH  go 4 5',2),['SH',' go 4 5'])
        for text in ('00','-0','0x',' 0'):
            with self.assertRaises(ValueError):core.readnum(text)
        self.assertEqual(core.readnum('12suffix'),12)
        self.assertIsNone(radio.auto_parse_command(a,u,0,'ALL speed 45'))
        self.assertFalse(radio.auto_parse_command(a,u,0,'SH Speed 45')['matched'])
        self.assertFalse(radio.auto_parse_command(a,u,0,'SH  speed 45')['matched'])
        self.assertEqual(radio.auto_parse_command(a,u,0,'sh sp 45')['command'],'speed')
        self.assertEqual(a.speed,45)
        self.assertEqual(radio.auto_parse_command(a,u,0,'SH st o')['command'],'startup')
        self.assertEqual(radio.auto_parse_command(a,u,0,'SH he 90')['reply'],'Ok.')

    def test_radio_silent_error_and_reset(self):
        s,a,u=self.session()
        result=radio.auto_parse_command(a,u,0,'SH autogun threshold 101')
        self.assertTrue(result['reply'].startswith('ERROR:'))
        count=len(s.engine.events.pending_events(event_type=E.AUTO_REPLY))
        self.assertTrue(radio.auto_parse_command(a,u,0,'SH sw 4 5')['silent'])
        self.assertEqual(len(s.engine.events.pending_events(event_type=E.AUTO_REPLY)),count)
        self.assertEqual((a.auto_goweight,a.auto_fweight),(4,5))
        radio.auto_parse_command(a,u,0,'SH reset')
        self.assertEqual((a.speed,a.target,a.flags),(100,-2,0))

    def test_weapon_range_minimum_and_profile_collision_order(self):
        weapons=[dict(name='IS.MediumLaser',section=0,critical=4),
                 dict(name='IS.MediumLaser',section=1,critical=4)]
        s,a,u=self.session([unit_fixture(weapons=weapons)])
        index=get_weapon('IS.MediumLaser').index
        self.assertEqual([gun.auto_calc_weapon_score(index,d) for d in (0,3,6,9)],[925,815,640,0])
        gun.auto_update_profile_event(a)
        self.assertEqual(a.mech_max_range,9)
        self.assertEqual([(k,n.weapon_number) for k,n in a.profile[0].items()],[(925,0),(926,1)])
        self.assertIsNone(a.profile[9])
        ppc=get_weapon('IS.PPC')
        self.assertEqual(gun.auto_calc_weapon_score(ppc.index,1),gun.auto_calc_weapon_score(ppc.index,3)-100)
        lrm=get_weapon('IS.LRM-10')
        self.assertEqual(gun.auto_calc_weapon_score(lrm.index,6),gun.auto_calc_weapon_score(lrm.index,7)+110)

    def test_target_score_fraction_signed_speed_and_seen_bonus(self):
        other=unit_fixture('Target',11,'TA',(3,5,0),2)
        s,a,u=self.session([unit_fixture(),other])
        t=s.units['Target'];board=s.map
        board.losinfo[u._id,t._id]=0
        expected=1045  # range 5 =>250; speed0=>300; full damage fraction=>495.
        self.assertEqual(gun.auto_calc_target_score(a,u,t,board),expected)
        t.speed=-10
        self.assertEqual(gun.auto_calc_target_score(a,u,t,board),expected+20)
        board.losinfo[u._id,t._id]=1
        self.assertEqual(gun.auto_calc_target_score(a,u,t,board),expected+2020)
        t.set_status(S.COMBAT_SAFE)
        self.assertEqual(gun.auto_calc_target_score(a,u,t,board),0)

    def test_sensor_priority_direct_general_and_locked_manual(self):
        s,a,u=self.session([unit_fixture(),unit_fixture('Target',11,'TA',(3,8,0),2,tonnage=65)])
        u.target=11;u.specials|=Specials.BEAGLE_PROBE_TECH
        gun.auto_sensor_event(a)
        self.assertEqual(u.sensor,[3,2])  # Heavy branch precedes active probe.
        self.assertEqual(u.target,-1)
        u.target=11;u.sensor[:]=[0,0];a.flags|=16
        gun.auto_sensor_event(a)
        self.assertEqual(u.sensor,[0,0])
        self.assertEqual(u.target,11)

    def test_astar_avoids_blocked_elevation_and_costs_ties(self):
        wall=[dict(at=[x,8],terrain='MOUNTAINS',elevation=4) for x in range(7)]
        s,a,u=self.session(map=dict(size=[20,20],hexes=wall))
        self.assertEqual(navigation.auto_astar_generate_path(a,u,3,3),1)
        path=[(n.x,n.y) for n in a.astar_path]
        self.assertEqual(path[-1],(3,3))
        self.assertTrue(any(x>=7 for x,y in path))
        self.assertTrue(all(not (x<7 and y==8) for x,y in path))
        before=list(path)
        navigation.astar_smooth_path(a)
        self.assertEqual([(n.x,n.y) for n in a.astar_path],before)

    def test_controller_reload_keeps_queue_deadline_and_rebuilds_path(self):
        s,a,u=self.session(commands=('goto 3 3',))
        s.action(dict(op='advance',seconds=12))
        self.assertTrue(a.astar_path)
        data=storage.save_snapshot(s.engine)
        self.assertNotIn('astar_path',data['controllers'][0]['values'])
        remaining=data['events'][0]['remaining']
        loaded=storage.load_snapshot(s.engine,data)[200]
        self.assertIsNone(loaded.astar_path)
        self.assertIsNone(loaded.weaplist)
        self.assertFalse(a.allocated)
        self.assertIs(s.personnel.objects[200],loaded)
        self.assertEqual(s.engine.events.pending_events(data=loaded)[0].tick,s.engine.tick+remaining)
        s.action(dict(op='advance',seconds=remaining))
        self.assertTrue(loaded.astar_path)
        self.assertEqual(loaded.commands[0].args,['goto','3','3'])

    def test_snapshot_invalid_input_cannot_cancel_running_ai(self):
        s,a,u=self.session(commands=('goto 3 3',))
        data=storage.save_snapshot(s.engine)
        before=s.engine.events.pending_events(data=a)
        bad=deepcopy(data);bad['events'][0]['callback']='unknown'
        with self.assertRaises(ValueError):storage.load_snapshot(s.engine,bad)
        self.assertEqual(s.engine.events.pending_events(data=a),before)
        self.assertTrue(a.allocated)

    def test_real_firing_heat_ammo_and_sensor_change(self):
        shooter=unit_fixture(weapons=[dict(name='IS.AC/5',section=0,critical=4),dict(name='IS.MediumLaser',section=1,critical=4)],
                             ammo=[dict(weapon='IS.AC/5',rounds=40)])
        s,a,u=self.session([shooter,unit_fixture('Target',11,'TA',(3,5,0),2,tonnage=65)])
        s.action(dict(op='advance',seconds=60))
        from entities.crittypes import is_ammo
        rounds=sum(c.data for sec in u.sections for c in sec.criticals if is_ammo(c.type))
        self.assertLess(rounds,40)
        self.assertGreater(u.shots_fired,2)
        self.assertGreater(s.units['Target'].damage_taken,0)
        self.assertEqual(u.sensor,[3,2])
        self.assertTrue(any('fire' in m for m in u.movement_messages))

    def test_assigned_target_loss_unassigns_and_reselects(self):
        s,a,u=self.session([unit_fixture(),unit_fixture('One',11,'ON',(3,5,0),2),unit_fixture('Two',12,'TW',(4,5,0),2)])
        radio.auto_parse_command(a,u,0,'SH target ON')
        gun.auto_update_profile_event(a)
        s.units['One'].set_status(S.DESTROYED)
        s.map.losinfo[u._id,12]=1
        gun.auto_gun_event(a)
        self.assertFalse(a.flags&256)
        self.assertEqual(a.target,12)

    def test_aerospace_cadence_sensor_delay_and_stop(self):
        fighter=unit_fixture(**{'class':'AERO','movement':'FLY','aerospace':{'landed':True}})
        fighter['sections']=fighter['sections'][:6]
        fighter['weapons']=[dict(name='IS.MediumLaser',section=0,critical=4)]
        s,a,u=self.session([fighter,unit_fixture('Target',11,'TA',(3,5,0),2,tonnage=65)],commands=('autogun on',))
        s.action(dict(op='advance',seconds=3))
        pending={e.event_type:e.tick for e in s.engine.events.pending_events(data=a)}
        self.assertEqual(pending[E.AUTO_PROFILE],182)
        self.assertEqual(pending[E.AUTO_SENSOR],32)
        self.assertIn(E.AUTOGUN,pending)
        from systems.damage_commands import section_names
        self.assertEqual(len(section_names(u)),6)
        self.assertTrue(all(n.section < 6 for n in a.weaplist))
        radio.auto_parse_command(a,u,0,'SH autogun off')
        shots=getattr(u,'shots_fired',0)
        s.action(dict(op='advance',seconds=45))
        self.assertEqual(getattr(u,'shots_fired',0),shots)
        self.assertFalse(any(e.event_type in (E.AUTOGUN,E.AUTO_SENSOR,E.AUTO_PROFILE) for e in s.engine.events.pending_events(data=a)))

    def test_shutdown_and_public_startup_resume_general_gunnery(self):
        s,a,u=self.session([unit_fixture(),unit_fixture('Target',11,'TA',(3,5,0),2)])
        radio.auto_parse_command(a,u,0,'SH shutdown')
        s.action(dict(op='advance',seconds=2))
        self.assertFalse(u.is_started)
        radio.auto_parse_command(a,u,0,'SH startup')
        s.action(dict(op='advance',seconds=33))
        self.assertTrue(u.is_started)
        self.assertIs(u.pilot,a)
        self.assertEqual(a.target,11)

    def test_free_detaches_and_cancels_without_touching_another_controller(self):
        s,a,u=self.session(commands=('goto 3 3',))
        core.auto_newautopilot(s.engine,a._id,selector=0,autopilot=a)
        self.assertEqual(u.autopilot,-1)
        self.assertFalse(s.engine.events.pending_events(data=a))
        self.assertNotIn(a,s.engine.get_entities())
        self.assertNotIn(a._id,s.personnel.objects)
        self.assertNotIn(a._id,s.personnel.contents(u._id))

    def test_core_command_enum_is_independent_of_display_token(self):
        s,a,u=self.session(commands=('speed=label 42',))
        s.action(dict(op='advance',seconds=1))
        self.assertEqual(a.speed,42)
        self.assertEqual(a.commands,[])

    def test_legacy_adapter_and_explicit_service_override_keep_their_contract(self):
        from systems.autopilot import auto_com_event
        engine=GameEngine()
        core.auto_newautopilot(engine,200)
        legacy=SimpleNamespace(_engine=engine,mymech=SimpleNamespace(unit_type=U.MECH),external_effects=[])
        engine.auto_heartbeat(legacy)
        self.assertEqual(len(legacy.external_effects),3)
        called=[]
        engine.auto_services['sensor']=lambda a:called.append(a)
        auto_com_event(SimpleNamespace(data=legacy,event_type=E.AUTO_SENSOR,data2=1))
        self.assertEqual(called,[legacy])

    def test_one_shot_historical_sensor_does_not_rearm(self):
        from systems.autopilot import auto_com_event
        fighter=unit_fixture(**{'class':'AERO','movement':'FLY','aerospace':{'landed':True}})
        s,a,u=self.session([fighter])
        auto_com_event(SimpleNamespace(data=a,event_type=E.AUTO_SENSOR,data2=1))
        self.assertFalse(s.engine.events.pending_events(event_type=E.AUTO_SENSOR,data=a))
        auto_com_event(SimpleNamespace(data=a,event_type=E.AUTO_SENSOR,data2=0))
        self.assertEqual(s.engine.events.pending_events(event_type=E.AUTO_SENSOR,data=a)[0].tick,30)

    def test_reload_replaces_containment_without_stale_membership(self):
        s,a,u=self.session([unit_fixture(),unit_fixture('Other',11,'OT')])
        document=storage.save_snapshot(s.engine)
        document['controllers'][0]['values']['location']=11
        loaded=storage.load_snapshot(s.engine,document)[200]
        self.assertNotIn(200,s.personnel.contents(10))
        self.assertEqual(s.personnel.contents(11).count(200),1)
        self.assertIs(s.personnel.objects[200],loaded)
        self.assertEqual(loaded.location,11)

    def test_old_dumb_and_roam_orders_drive_real_movement(self):
        for command in ('oldgoto 3 3','dumbgoto 3 3','dumbfollow 11','roam radius 3 10 4'):
            with self.subTest(command=command):
                s,a,u=self.session([unit_fixture(),unit_fixture('Leader',11,'LE',(3,5,0))],commands=(command,))
                s.action(dict(op='advance',seconds=60))
                self.assertNotEqual((u.x,u.y),(3,10))
                self.assertTrue(s.engine.events.pending_events(data=a))
                if command.startswith('roam'):
                    self.assertTrue(any(d['name']=='ai_roam_bearing' for d in s.draws))

    def test_historical_and_general_navigation_use_source_deadlines(self):
        for historical,expected in ((False,5),(True,4)):
            row=unit_fixture()
            if historical:row.update({'class':'AERO','movement':'FLY','aerospace':{'landed':True}})
            s,a,u=self.session([row],commands=('goto 3 3',))
            s.action(dict(op='advance',seconds=1))
            self.assertEqual(s.engine.events.pending_events(event_type=E.AUTOGOTO,data=a)[0].tick,expected)

    def test_physical_ai_uses_real_kick_damage_and_limb_recycle(self):
        s,a,u=self.session([unit_fixture(facing=180),unit_fixture('Target',11,'TA',(3,10,0),2)])
        s.action(dict(op='advance',seconds=1))
        self.assertEqual(s.units['Target'].damage_taken,10)
        self.assertTrue(any(sec.recycle for sec in u.sections))
        self.assertTrue(any('try to kick' in m for m in u.movement_messages))
        s.action(dict(op='advance',seconds=10))
        self.assertEqual(s.units['Target'].damage_taken,10)

    def test_pickup_and_dropoff_use_shared_towing_relationship(self):
        s,a,u=self.session([unit_fixture(),unit_fixture('Load',11,'LO',(3,10,0))],commands=('pickup 11','wait 1 1','dropoff'))
        load=s.units['Load'];load.in_character=True  # Starting transport fixture.
        s.action(dict(op='advance',seconds=2))
        self.assertEqual(u.carrying,11)
        self.assertIs(u.towed_unit,load)
        self.assertTrue(load.status&S.TOWED)
        self.assertFalse(load.is_started)
        core.auto_delcommand(a,a,'1');core.auto_engage(a,a)
        s.action(dict(op='advance',seconds=2))
        self.assertEqual(u.carrying,-1)
        self.assertFalse(load.status&S.TOWED)

    def test_enterbase_completes_real_map_transfer_and_next_command(self):
        directory=TemporaryDirectory();self.addCleanup(directory.cleanup)
        document=dict(hud_display={'root':directory.name},random={'seed':3},
            maps=[dict(name='outside',id=100,size=[20,20],map_objects=[dict(kind='BUILDING',x=3,y=10,obj=101)]),
                  dict(name='inside',id=101,size=[12,12],onmap=100,cf=100,cfmax=100,map_objects=[dict(kind='ENTRA',x=5,y=2,datac=110)])],
            units=[unit_fixture(map='outside')],autopilots=[dict(name='ai',id=200,unit='Sheep',commands=['enterbase n','speed 35'])],actions=[])
        s=AutopilotSession(document);u=s.units['Sheep'];a=s.autopilots['ai']
        s.action(dict(op='advance',seconds=19))
        self.assertEqual(u.mapindex,100)
        s.action(dict(op='advance',seconds=3))
        self.assertEqual((u.mapindex,u.x,u.y),(101,5,2))
        self.assertEqual(a.mapindex,101)
        self.assertEqual(a.speed,35)
        self.assertEqual(a.commands,[])


    def test_predictive_navigation_uses_raw_elevation_like_the_source(self):
        from physics.hexmath import hex_to_float
        s,a,u=self.session(map=dict(size=[20,20],hexes=[dict(at=[3,9],terrain='WATER',elevation=1)]))
        u.sections[6].armor=0  # Exposed limb in the starting fixture.
        location=navigation.LOCInit(u)
        location.fx,location.fy=hex_to_float(3,9)
        self.assertEqual(navigation.ai_crash(s.map,u,location),0)
        self.assertEqual(location.e,1)  # Elevation(), not the signed water surface.



if __name__=='__main__':
    unittest.main()

