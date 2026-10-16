"""Focused corrections from the Core/Aerospace/HUD independent review."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from tests.test_core_startup import fixture
from entities.mech import Mech,UnitType as U,MechStatus as S,MechStatus2 as S2,CritStatus as C


def mounted_suit(engine,host):
    suit=Mech.create_test_mech('suit');suit.unit_type=U.BSUIT
    suit.swarm_target=host._id;suit.team=host.team
    suit.set_status2(S2.UNIT_MOUNTING);host.set_status2(S2.UNIT_MOUNTED)
    host.map.add_mech(suit);engine.register_entity(suit)
    return suit


class CoreReviewCorrections(unittest.TestCase):
    def test_destroy_profile_preserves_historical_lights_and_mounted_bits(self):
        from systems.damage import destroy_state
        from systems.startup import shutdown
        for historical in (False,True):
            with self.subTest(historical=historical):
                engine,unit,actor=fixture(U.AERO if historical else U.MECH)
                unit.pilot=actor;unit.set_status(S.STARTED)
                unit.set_status2(S2.SLITE_ON);unit.set_crit_status(C.SLITE_LIT)
                suit=mounted_suit(engine,unit)
                destroy_state(unit,engine,historical=historical)
                self.assertEqual(historical,bool(unit.status2&S2.SLITE_ON))
                self.assertEqual(historical,bool(unit.crit_status&C.SLITE_LIT))
                self.assertEqual(historical,bool(unit.status2&S2.UNIT_MOUNTED))
                self.assertEqual(historical,bool(suit.status2&S2.UNIT_MOUNTING))
                self.assertEqual(-1,suit.swarm_target)
        engine,unit,actor=fixture(U.AERO)
        unit.pilot=actor;unit.set_status(S.STARTED)
        unit.set_status2(S2.SLITE_ON);unit.set_crit_status(C.SLITE_LIT)
        self.assertTrue(shutdown(engine,unit)[0])
        self.assertFalse(unit.status2&S2.SLITE_ON);self.assertFalse(unit.crit_status&C.SLITE_LIT)

    def test_fall_uses_host_profile_for_real_detachment(self):
        from physics.jump import mech_falls
        for kind in (U.AERO,U.MECH):
            engine,unit,actor=fixture(kind);unit.pilot=actor
            suit=mounted_suit(engine,unit)
            with patch('systems.piloting.make_piloting_roll',return_value=SimpleNamespace(success=True)):
                mech_falls(unit,0)
            self.assertEqual(-1,suit.swarm_target)
            self.assertEqual(kind==U.AERO,bool(unit.status2&S2.UNIT_MOUNTED))
            self.assertEqual(kind==U.AERO,bool(suit.status2&S2.UNIT_MOUNTING))

def turret_fixture():
    from tests.test_aerospace_turrets import TurretTests
    f=TurretTests('runTest');f.setUp()
    return f


def arm(unit,name='IS.MediumLaser',section=4):
    from entities.mech import WeaponState
    from entities.weapon import get_weapon
    from entities.crittypes import i2weapon
    for sec in unit.sections:
        for slot in sec.criticals:slot.type=0
    weapon=get_weapon(name)
    unit.weapons=[WeaponState(weapon_idx=weapon.index,section=section,critical=0)]
    unit.sections[section].criticals[0].type=i2weapon(weapon.index)
    return weapon


class AerospaceFiringReviewCorrections(unittest.TestCase):
    def test_historical_mounts_use_live_swarmers_not_stale_bits(self):
        from systems.combat_firing import mount_guard
        f=turret_fixture();u=f.unit;arm(u,section=4)
        u.set_status2(S2.UNIT_MOUNTED)
        self.assertIsNone(mount_guard(u,0,True,True))
        suit=mounted_suit(f.engine,u);u.clear_status2(S2.UNIT_MOUNTED)
        self.assertEqual('You can not fire torso mounted weapons while you have battlesuits on you!',mount_guard(u,0,True,True))
        self.assertIsNone(mount_guard(u,0,True,False))

    def test_historical_spotter_fallthrough_and_stored_hex(self):
        from systems import turrets
        from systems.combat import AttackResult
        f=turret_fixture();u=f.unit;arm(u,'IS.LRM-5')
        u.spotter=123;f.turret.target=-1
        with patch('systems.spot.fire_spot',return_value=AttackResult(handled=False)) as spot:
            result=turrets.command(f.engine,f.turret,f.actor,'sight','0')
            self.assertIn('You do not have a default target set!',result['message'])
            spot.assert_called_once()
            f.turret.targ_x=f.turret.targ_y=5
            with patch('systems.combat.is_in_weapon_arc',return_value=True), patch('systems.los.in_line_of_sight_nb',return_value=1), patch('systems.combat.fire_weapon',return_value=AttackResult()) as fire:
                turrets.command(f.engine,f.turret,f.actor,'sight','0')
                fire.assert_called_once()
            self.assertEqual(1,spot.call_count)
        arm(u)
        with patch('systems.combat.is_in_weapon_arc',return_value=True), patch('systems.los.in_line_of_sight_nb',return_value=1), patch('systems.combat.fire_weapon',return_value=AttackResult()) as fire:
            turrets.command(f.engine,f.turret,f.actor,'sight','0')
            fire.assert_called_once()

    def test_turret_lock_checks_original_actor_before_parsing(self):
        from systems import turrets
        f=turret_fixture();u=f.unit;u.in_character=True
        result=turrets.command(f.engine,f.turret,f.actor,'settarget','')
        self.assertFalse(result['ok']);self.assertIn('only the pilot',result['message'])
        self.assertEqual(88,f.turret.target)
        self.assertEqual(0,f.engine.pilot_override)
        self.assertEqual(99,u.target)
        f.actor.wizard=True
        u.mapindex=-1
        result=turrets.command(f.engine,f.turret,f.actor,'settarget','-')
        self.assertFalse(result['ok']);self.assertEqual(88,f.turret.target)
        with patch('systems.communications.common_checks',return_value=''):
            result=turrets.command(f.engine,f.turret,f.actor,'settarget','-')
        self.assertFalse(result['ok']);self.assertEqual(88,f.turret.target)

    def test_empty_water_hex_uses_signed_elevation_in_sight_and_fire(self):
        from systems.combat_firing import fire_number
        from systems.combat import AttackResult
        from entities.map import WATER
        from physics.hexmath import ZSCALE
        for historical in (False,True):
            for sight in (False,True):
                f=turret_fixture();u=f.unit;arm(u);u.target=-1
                f.board.set_terrain(5,5,WATER);f.board.set_elevation(5,5,4)
                with patch('systems.combat.is_in_weapon_arc',return_value=True), patch('systems.los.in_line_of_sight_nb',return_value=1), patch('systems.combat.fire_weapon',return_value=AttackResult()), patch('systems.targeting.find_range',return_value=1) as distance:
                    fire_number(f.engine,u,0,(5,5),_guarded=True,historical=historical,sight=sight)
                self.assertEqual(-4,u.targ_z)
                self.assertEqual(-4*ZSCALE,distance.call_args.args[-1])

class DisplayReviewCorrections(unittest.TestCase):
    def test_map_diagnostics_precede_live_preferences_and_deliver_once(self):
        from systems import turrets
        from systems.notifications import personal_notify
        for command,args in [('lrsmap','m'),('tacmap',''),('navigate','')]:
            f=turret_fixture();actor=f.actor
            actor.ansimap=False;actor.lrsheight='1';actor.tacsize='bad';actor.mapcolor='?'
            delivered=[]
            def callback(recipient,text):
                self.assertIs(recipient,actor);delivered.append(text)
                if text.startswith('Illegal'):
                    actor.mapcolor='g'
                    actor.ansimap=True
                if 'MAPCOLOR' in text:actor.ansimap=True
                personal_notify(recipient,text)
            with patch('systems.notifications.personal_notify',side_effect=callback):
                result=turrets.command(f.engine,f.turret,actor,command,args)
            self.assertTrue(result['ok']);self.assertEqual(result['lines'],delivered)
            if command=='lrsmap':
                self.assertEqual(1,len(result['warnings']))
                self.assertFalse(any('%c' in row for row in result['rows']))
            else:self.assertTrue(any('%c' in row for row in result['rows']))

    def test_status_generic_delivery_precedes_armor_expression_and_heat_lookup(self):
        from systems import turrets
        from systems.notifications import personal_notify
        from core.attributes import attributes_for
        f=turret_fixture();u=f.unit;actor=f.actor
        attributes_for(u).set(u._id,'A_MECHSTATUS','initial')
        trace=[]
        def callback(recipient,text):
            trace.append(text)
            if text.startswith('Mech Name'):
                attributes_for(u).set(u._id,'A_MECHSTATUS','updated')
                actor.heatchars='[abcdefgh]'
            personal_notify(recipient,text)
        f.engine.expression_evaluator=lambda text,**kw:'7 '+text
        with patch('systems.notifications.personal_notify',side_effect=callback):
            result=turrets.command(f.engine,f.turret,actor,'status','AH')
        self.assertIn(' updated',result['lines'])
        self.assertEqual(result['lines'],trace)
        self.assertIn('a',result['heat_scale']['text'])

    def test_scan_report_delivery_precedes_armor_and_preserves_reply_boundary(self):
        from systems import turrets
        from systems.notifications import personal_notify
        from core.attributes import attributes_for
        f=turret_fixture();u=f.unit
        target=Mech.create_test_mech('target');target.set_hex_position(11,10)
        f.board.add_mech(target);f.engine.register_entity(target)
        f.turret.target=target._id
        attributes_for(target).set(target._id,'A_MECHSTATUS','initial')
        f.engine.expression_evaluator=lambda text,**kw:'7 '+text
        trace=[]
        def callback(recipient,text):
            trace.append(text)
            if text.startswith('['):
                attributes_for(target).set(target._id,'A_MECHSTATUS','updated')
                u.set_crit_status(C.OBSERVATORIC)
            personal_notify(recipient,text)
        with patch('systems.observation.in_line_of_sight',return_value=1), patch('systems.observation.in_line_of_sight_nb',return_value=1), patch('systems.notifications.personal_notify',side_effect=callback), patch('systems.observation.scan_effects') as reply:
            result=turrets.command(f.engine,f.turret,f.actor,'scan','A')
            reply.assert_not_called()
        self.assertTrue(result['ok']);self.assertIn(' updated',result['armor_display']['plain'])
        self.assertEqual(result['lines'],trace)

    def test_compact_historical_heat_overwrites_shared_buffer_only(self):
        from systems import turrets,status_display
        f=turret_fixture()
        result=turrets.command(f.engine,f.turret,f.actor,'status','NH')
        self.assertEqual(2,len(result['lines']));self.assertEqual(*result['lines'])
        general=status_display.status(f.unit,'NH',caller=f.actor,historical=False)
        self.assertNotEqual(*general['lines'])
        arm(f.unit)
        result=turrets.command(f.engine,f.turret,f.actor,'status','NHW')
        self.assertTrue(result['lines'][-1].startswith(result['lines'][0]))
        self.assertIn('MediumLaser|',result['lines'][-1])

    def test_historical_armor_tokens_padding_and_dead_sections(self):
        from systems.armor_display import armor_display,render_historical_template,plain
        f=turret_fixture();u=f.unit;u.sections[0].armor=3
        text='7 &+0 &(+0 &)+0\nZliteral\n0stop\n7 ignored'
        self.assertEqual(' 03 3   3\r\nliteral',plain(render_historical_template(u,text,True,flags=16)))
        u.sections[0].internal=0
        self.assertEqual('   ',plain(render_historical_template(u,'7 &+0',True,flags=16)))
        u.unit_type=U.AERO;u.status_template='7 &+0\n0stop\n7 ignored'
        result=armor_display(u,True)
        self.assertEqual('   ',result['plain'])
        del u.status_template
        u.sections[0].internal=1
        self.assertIn('Nose 03',armor_display(u,True)['plain'])
        self.assertNotIn('SI',armor_display(u,True)['plain'])
        u.status_template='expression';u.status_expression=True
        f.engine.expression_evaluator=lambda *args,**kwargs:''
        self.assertEqual([],armor_display(u,True)['lines'])

    def test_turret_critical_display_uses_historical_positional_names(self):
        from systems import turrets,status_display
        from entities.crittypes import Special,i2special
        from entities.mech import Specials
        f=turret_fixture();u=f.unit
        u.sections[0].criticals[0].type=i2special(Special.HEAT_SINK)
        u.specials|=Specials.DOUBLE_HEAT_TECH
        result=turrets.command(f.engine,f.turret,f.actor,'critstatus','LA')
        self.assertTrue(result['ok'])
        self.assertEqual('HeatSink',result['slots'][0]['name'])
        self.assertEqual('Double Heatsink',status_display.part_name(u,0,0,historical=False))

    def test_stale_view_notice_precedes_reset_even_if_listener_changes_target(self):
        from systems.observation import view
        f=turret_fixture();u=f.unit;u.target=900
        seen=[]
        def callback(unit,text,**kwargs):
            seen.append(unit.target);unit.target=901
        with patch('systems.observation.notify',side_effect=callback):
            result=view(u,caller=f.actor)
        self.assertEqual([900],seen);self.assertEqual(-1,u.target);self.assertTrue(result['notified'])

class HudContinuationReviewCorrections(unittest.TestCase):
    def test_public_display_configure_updates_discovery_and_persistence(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from tools.hud_status import DisplaySession
        from core.object_services import ObjectRegistry
        Path('tmp').mkdir(exist_ok=True)
        with TemporaryDirectory() as directory:
            session=DisplaySession({'hud_display':{'root':directory},'sessions':[{'name':'hud','unit':'u'}],
                'units':[{'name':'u'}],'config':{'periodic_updates':False},'actions':[]})
            session.action({'op':'hudinfo','session':'hud','text':'key=x'})
            for values,eligible in [({'zombie':True},False),({'zombie':False},True),({'hardcode':False},False),({'hardcode':True},True)]:
                self.assertTrue(session.action({'op':'display_configure','unit':'u','values':values})['ok'])
                wire=session.action({'op':'hudinfo','session':'hud','text':'gs'})['wire']
                self.assertEqual(eligible,'GS:R#' in wire)
                old=session.engine.object_registry
                session.engine.object_registry=ObjectRegistry(Path(directory)/'objects.json',resolve=old.resolve_live)
                wire=session.action({'op':'hudinfo','session':'hud','text':'gs'})['wire']
                self.assertEqual(eligible,'GS:R#' in wire)

    def test_hangar_callbacks_refresh_names_and_capture_coordinates_before_transfer(self):
        from tests.hud_status.test_hangar import HangarTests
        from systems.hangar import enter_base
        from systems.swarm import detach_all
        from systems.dropships import move_object
        from systems.ecm import mark_for_los_update
        for historical in (False,True):
            f=HangarTests('runTest');f.setUp();u=f.u;board=f.inside;trace=[]
            if historical:u.unit_type=U.AERO;u.set_status(S.LANDED)
            suit=mounted_suit(f.s.engine,u)
            def detach(who,**kwargs):
                detach_all(who,**kwargs)
                who.set_hex_position(1,2);board.object_name='First'
            def notice(who,text,**kwargs):
                trace.append(('notice',who._id,text))
                if who is u:
                    who.set_hex_position(2,3);board.object_name='Second'
            def broadcast(who,text):
                trace.append(('los',who._id,text))
                if who is u and who.map is f.s.maps['outside']:
                    who.set_hex_position(3,4);board.object_name='Third'
                elif who is u:board.object_name='Fifth'
            marked=False
            def mark(who):
                nonlocal marked
                mark_for_los_update(who)
                if who is u and not marked:
                    marked=True;who.set_hex_position(4,5);board.object_name='Fourth'
            def move(who,destination):
                trace.append(('move',who._id,destination));move_object(who,destination)
            self.assertTrue(enter_base(u)['ok'])
            with patch('systems.swarm.detach_all',side_effect=detach),patch('systems.hangar.notify',side_effect=notice),patch('systems.sensors.los_broadcast',side_effect=broadcast),patch('systems.ecm.mark_for_los_update',side_effect=mark),patch('systems.hangar.move_object',side_effect=move):
                f.s.engine.run_ticks(18)
            self.assertIn(('notice',u._id,'You enter the First.'),trace)
            self.assertIn(('los',u._id,'has entered the Second at 2,3.'),trace)
            arrival=('los',u._id,'has entered the Fourth at '+('4,4.' if historical else '4,5.'))
            self.assertIn(arrival,trace)
            if historical:
                self.assertFalse(any(row[0]=='los' and row[1]==f.tow._id for row in trace))
            else:
                carry=('los',f.tow._id,'has entered the Fifth at 4,5.')
                self.assertIn(carry,trace);self.assertLess(trace.index(carry),trace.index(('move',u._id,board._id)))
            self.assertLess(trace.index(arrival),trace.index(('move',u._id,board._id)))
            self.assertLess(trace.index(('move',u._id,board._id)),trace.index(('move',f.tow._id,board._id)))
            self.assertIs(u.map,board);self.assertIs(f.tow.map,board)
            self.assertEqual(historical,bool(u.status2&S2.UNIT_MOUNTED))
            self.assertEqual(historical,bool(suit.status2&S2.UNIT_MOUNTING))

    def test_hud_contact_wire_uses_source_signed_full_turn(self):
        from systems.hud import HudSession
        f=turret_fixture();u=f.unit
        other=Mech.create_test_mech('contact');other.facing=-360
        other.set_hex_position(11,10);f.board.add_mech(other);f.engine.register_entity(other)
        row=dict(mech=other,identified=True,arc=1,sees_primary=True,sees_secondary=True,range=1,bearing=60)
        session=HudSession(lambda:u);session.request('key=x')
        with patch('systems.hud.list_contacts',return_value=[row]):
            result=session.request('c')
        self.assertEqual('360',result['records'][0]['payload'].split(',')[12])

class HistoricalLockReReviewCorrections(unittest.TestCase):
    def test_turret_tokenizer_and_profile_timing_with_non_aircraft_parent(self):
        from systems import turrets
        from core.events import EventType
        from systems.los import MECHLOSFLAG_SEESP,MECHLOSFLAG_SEESS
        for kind in ('hex','unit'):
            for setting,arcs,due in [(None,0,8),(0,0,None),(3,0,3),(None,1,None)]:
                with self.subTest(kind=kind,setting=setting,arcs=arcs):
                    f=turret_fixture();u=f.unit;f.turret.arcs=arcs
                    self.assertFalse(hasattr(f.engine,'lock_tick'))
                    if setting is not None:f.engine.lock_tick=setting
                    target=Mech.create_test_mech('target');target.contact_id='ZZ';target.set_hex_position(11,10)
                    f.board.add_mech(target);f.engine.register_entity(target)
                    f.board.losinfo[u._id,target._id]=MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS
                    result=turrets.command(f.engine,f.turret,f.actor,'settarget','1\n2 3 h' if kind=='hex' else 'ZZ')
                    self.assertTrue(result['ok'],result)
                    if kind=='hex':self.assertEqual((1,3),(f.turret.targ_x,f.turret.targ_y))
                    else:self.assertEqual(target._id,f.turret.target)
                    events=f.engine.events.pending_events(EventType.LOCK,u)
                    self.assertEqual([] if due is None else [f.engine.tick+due],[event.tick for event in events])
                    self.assertEqual((99,0,0),(u.target,f.engine.arc_override,f.engine.pilot_override))

    def test_battlesuit_swarm_text_is_historical_for_both_lock_forms(self):
        from systems import turrets,targeting
        from systems.notifications import MECHALL
        f=turret_fixture();u=f.unit;u.unit_type=U.BSUIT;u.swarm_target=12345
        target=Mech.create_test_mech('target');target.contact_id='ZZ';target.set_hex_position(11,10)
        f.board.add_mech(target);f.engine.register_entity(target)
        with patch('systems.targeting.in_line_of_sight',return_value=1),patch('systems.notifications.deliver') as notice:
            for args in ('ZZ','1 3','1 3 h'):
                result=turrets.command(f.engine,f.turret,f.actor,'settarget',args)
                self.assertFalse(result['ok']);self.assertIn('a bit to busy',result['message'])
                self.assertEqual(MECHALL,notice.call_args.args[1])
                self.assertEqual(88,f.turret.target)
            result=targeting.set_target_hex(f.engine,u,1,3,historical=False)
            self.assertIn('a bit too busy',result[1])

    def test_indexed_map_replaces_missing_or_stale_cache_before_lock(self):
        from systems import turrets
        from entities.map import GameMap,WATER
        from systems.los import MECHLOSFLAG_SEESP,MECHLOSFLAG_SEESS
        for kind in ('hex','unit'):
            for missing in (False,True):
                f=turret_fixture();u=f.unit
                target=Mech.create_test_mech('target');target.contact_id='ZZ';target.set_hex_position(11,10)
                f.board.add_mech(target);f.engine.register_entity(target)
                f.board.losinfo[u._id,target._id]=MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS
                f.board.set_terrain(1,3,WATER);f.board.set_elevation(1,3,4)
                stale=GameMap(1,1);stale._id=f.board._id
                u.map=None if missing else stale
                result=turrets.command(f.engine,f.turret,f.actor,'settarget','1 3 h' if kind=='hex' else 'ZZ')
                self.assertTrue(result['ok'],result);self.assertIs(u.map,f.board);self.assertTrue(u.is_started)
                if kind=='hex':self.assertEqual(-4,f.turret.targ_z)
                else:self.assertEqual(target._id,f.turret.target)

    def test_unregistered_cached_map_notifies_then_shuts_down_then_resets(self):
        from systems import turrets
        from entities.map import GameMap
        f=turret_fixture();u=f.unit;u.map=GameMap(20,20);u.map._id=u.mapindex=9999
        calls=[]
        def notice(actor,text):
            if text:calls.append(('notice',u.mapindex,text))
        def shutdown(engine,unit,**kwargs):
            calls.append(('shutdown',unit.mapindex,kwargs['caller']))
            unit.mapindex=4321
            return True,''
        with patch('systems.notifications.personal_notify',side_effect=notice),patch('systems.startup.shutdown',side_effect=shutdown):
            result=turrets.command(f.engine,f.turret,f.actor,'settarget','1 3 h')
        self.assertFalse(result['ok']);self.assertEqual(-1,u.mapindex)
        self.assertEqual(('notice',9999,'You are on an invalid map! Map index reset!'),calls[0])
        self.assertEqual(('shutdown',9999,f.actor),calls[1])
        self.assertEqual(2,len(calls));self.assertEqual(88,f.turret.target)

class HistoricalArmorReReviewCorrections(unittest.TestCase):
    def test_combined_modifiers_through_historical_turret_status_and_scan(self):
        from systems import turrets
        f=turret_fixture();u=f.unit
        target=Mech.create_test_mech('target');target.set_hex_position(11,10)
        f.board.add_mech(target);f.engine.register_entity(target)
        f.turret.target=target._id;u.set_crit_status(C.OBSERVATORIC)
        for unit in (u,target):
            unit.sections[0].armor=3
            unit.status_template='7 &()+0 &+0 &(+0 &)+0\n0stop\n7 ignored'
        for name in ('status','scan'):
            with patch('systems.observation.in_line_of_sight',return_value=1),patch('systems.observation.in_line_of_sight_nb',return_value=1):
                result=turrets.command(f.engine,f.turret,f.actor,name,'A')
            self.assertTrue(result['ok'])
            armor=result['armor'] if name=='status' else result['armor_display']
            self.assertEqual(' 3  3 3   3',armor['plain'])
            self.assertEqual(1,len(armor['lines']))
            self.assertEqual(99,u.target)
