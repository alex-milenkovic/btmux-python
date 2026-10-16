"""Source-boundary regressions through real Communications consumers."""
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_communications import CommunicationsFixture
from core.events import EventType, SOURCE_EVENT_IDS
from core.randomness import float32, use_source
from entities.mech import MechStatus as S, CritStatus as C
from systems import communications as radio, notifications as notice, c3


class CommunicationsAuditRepairs(CommunicationsFixture):
    def radios(self):
        for unit in self.units:
            unit.radio_type=114; unit.radio_range=80
            unit.freq=[17,0]; unit.freqmodes=[1,0]; unit.chantitle=['','']

    def auto(self, unit):
        unit.autopilot=900
        self.store.create(900,'AUTO',location=unit._id)
        return self.world.add(self.store.actor(900),unit._id)

    def test_delivery_callbacks_keep_raw_text_order_flags_and_each_call(self):
        effects=self.engine.effects; trace=[]; actor=self.a.pilot
        effects.connect_client(actor,lambda text:trace.append(('client',text)),lambda text:text.replace('%ch','').replace('%cn',''))
        effects.listen(actor,lambda who,text,sender,flags:trace.append(('listener',text,sender,flags)))
        effects.forward(actor,self.b.pilot); effects.forward(self.b.pilot,actor)
        for _ in range(2):
            notice.mech_notify(self.a,notice.MECHALL,'%chHello%cn')
        self.assertEqual([('client','Hello'),('listener','%chHello%cn',-5,notice.CONTENTS_FLAGS)]*2,trace)
        self.assertEqual(['%chHello%cn']*2,actor.inbox)
        self.assertEqual(actor.inbox,self.b.pilot.inbox)
        self.assertTrue(all(r['applied'] for r in actor.notification_requests))
        count=len(effects.notifications)
        self.assertEqual([],notice.mech_notify(self.a,notice.MECHALL,'\0ignored'))
        self.assertEqual(count,len(effects.notifications))

    def test_turret_source_slots_preserve_order_and_exclude_fourth(self):
        self.engine.arc_override=1; self.a.aero_turrets=[700,701,702,703]
        people=[]
        for index,room in enumerate(self.a.aero_turrets):
            actor=SimpleNamespace(_id=400+index,inbox=[])
            self.world.add(actor,room);people.append(actor)
        self.assertEqual([110,400,401,402],notice.mech_notify(self.a,notice.MECHALL,'crew'))
        self.assertEqual([],people[3].inbox)

    def test_unused_printf_arguments_and_pair_two_stage_bounds(self):
        notice.mech_printf(self.a,2,'literal %%',900)
        notice.mech_printf(self.a,2,'%*.*s',5,2,'hello','unused')
        self.assertEqual(['literal %','   he'],self.a.pilot.inbox)
        with patch('systems.sensors.possibly_see_mech'),patch('systems.los.in_line_of_sight',return_value=1):
            notice.pair_los_broadcast(self.a,self.b,'waves 100%%')
            self.assertEqual('A [aa] waves 100%',self.c.pilot.inbox[-1])
            notice.pair_los_broadcast(self.a,self.b,'x'*17000)
            self.assertEqual(('A [aa] '+'x'*16383)[:16383],self.c.pilot.inbox[-1])

    def test_invalid_identity_does_not_enter_los_or_reset_viewer(self):
        old=self.a.mapindex;self.b.valid=False
        with patch('systems.los.in_line_of_sight_nb',side_effect=AssertionError('unexpected LOS')):
            self.assertEqual('',notice.identity(self.a,self.b))
        self.assertEqual(old,self.a.mapindex)
        self.assertEqual([],getattr(self.a.pilot,'inbox',[]))

    def test_hex_bounds_and_float_radius_before_delivery(self):
        from physics.hexmath import SCALEMAP
        for message in ('','\u00e9','x'*16384,'$H'*1100):
            with self.subTest(message=message[:12]),self.assertRaises(ValueError):
                notice.hex_broadcast(self.board,3,3,message)
        for unit in self.units:unit.fx,unit.fy,unit.fz=20*SCALEMAP,0,0
        self.a.fx=SCALEMAP
        for dimensions in (2,3):
            self.assertEqual(1,notice.limited_broadcast(self.board,0,0,0,.99999998,'edge',dimensions))
        with self.assertRaisesRegex(ValueError,'float range'):
            notice.limited_broadcast(self.board,0,0,0,1e50,'overflow')

    def test_network_commands_preserve_newline_token_and_virtual_heading(self):
        from systems.network_reports import network_data,targets
        self.a.facing=350;self.a.lateral=40
        for ordinary in (True,False):
            with self.subTest(ordinary=ordinary):
                c3.add(self.a,self.b,ordinary)
                result=c3.command(self.b,self.b.pilot,'join','-\n',ordinary)
                self.assertFalse(result['ok'])
                self.assertEqual(1,c3.network_size(self.b,ordinary))
                self.assertIn('h: 30',network_data(self.b,ordinary)[1])
                self.assertTrue(any('h: 30' in row for row in targets(self.b,ordinary)))
                self.assertTrue(c3.command(self.b,self.b.pilot,'join','-\t',ordinary)['ok'])
                self.assertEqual(0,c3.network_size(self.b,ordinary))

    def test_network_reports_address_current_actor_and_message_addresses_crews(self):
        self.radios(); c3.add(self.a,self.b,False)
        actor=SimpleNamespace(_id=500,wizard=True,inbox=[])
        self.world.add(actor,self.a._id);client=[]
        self.engine.effects.connect_client(actor,client.append)
        before=list(self.a.pilot.inbox)
        report=c3.command(self.a,actor,'network','',False)
        self.assertEqual(report['rows'],client)
        self.assertEqual(before,self.a.pilot.inbox)
        c3.command(self.a,actor,'message',' hello',False)
        self.assertEqual('%chC3i/You: hello%cn',self.a.pilot.inbox[-1])
        self.assertEqual('%chC3i/A [AA]: hello%cn',self.b.pilot.inbox[-1])

    def test_range_parameter_rounds_before_empty_or_disabled_return(self):
        from systems.combat_ranges import find_c3_range
        self.assertEqual((float32(.1),0),c3.range_with_network(self.a,None,.1,[]))
        self.a.crit_status|=C.C3I_DESTROYED
        self.assertEqual((float32(.1),77),c3.range_query(self.a,None,.1,False,77))
        self.assertEqual((float32(.1),-1),find_c3_range(self.a,None,.1,False))

    def test_frequency_confirmation_precedes_mutation_and_each_abuse_publication(self):
        self.radios(); self.a.freq[0]=0;self.b.team=2;self.b.freq=[17,17]
        trace=[]; effects=self.engine.effects
        effects.listen(self.a.pilot,lambda *args:trace.append(('confirmation',self.a.freq[0])))
        effects.subscribe('MechFreqs',self.c.pilot)
        effects.listen(self.c.pilot,lambda *args:trace.append(('channel',self.a.freq[0])))
        for _ in range(2):radio.set_frequency(self.a,'a=17',self.a.pilot)
        self.assertEqual([('confirmation',0),('channel',17),('channel',17),('confirmation',17),('channel',17),('channel',17)],trace)
        expected='ALERT: Possible abuse by #10 (Team 1) setting freq 17 matching #11 (Team 2)!'
        self.assertEqual([expected]*4,self.c.pilot.inbox)

    def test_zero_frequency_exact_channel_text_precedes_each_send(self):
        self.radios(); self.a.freq[0]=0;self.board.in_character=True
        self.b.freq=self.c.freq=[17,18]
        self.a.pilot.object_name='Database Pilot'; trace=[]
        self.engine.effects.subscribe('ZeroFrequencies',self.c.pilot)
        self.engine.effects.listen(self.c.pilot,lambda who,text,*rest:trace.append(('channel',text)))
        self.engine.effects.listen(self.a.pilot,lambda who,text,*rest:trace.append(('radio',text)))
        for _ in range(2):radio.send_channel(self.a,self.a.pilot,'a=hello')
        self.assertEqual(['channel','radio','channel','radio'],[kind for kind,text in trace])
        self.assertEqual('Player #110 (Database Pilot) in mech #10 (channel A) on map #1000 0-freqs "hello"',trace[0][1])

    def test_auto_parser_runs_before_range_uses_original_message_and_live_mutation(self):
        from systems.ecm import ECM_DISTURBANCE,ANGEL_ECM_DISTURBED
        self.radios(); obj=self.auto(self.b);self.b.freq=[99,17];self.b.radio_range=0
        received=[]
        def parser(auto,unit,channel,message):
            received.append((auto,unit,channel,message,unit.radio_range));unit.radio_range=80
        self.engine.auto_services['radio']=parser
        radio.transmit(self.a,0,'hold')
        self.assertEqual((obj,self.b,1,'hold',0),received[0])
        self.assertIn('hold',self.b.pilot.inbox[-1])
        self.assertEqual(900,self.b.auto)
        self.b.status2|=ANGEL_ECM_DISTURBED
        radio.autopilot_receive(self.b,1,'angel allowed')
        self.b.status2|=ECM_DISTURBANCE
        radio.autopilot_receive(self.b,1,'ordinary blocked')
        self.assertEqual(['hold','angel allowed'],[row[3] for row in received])
        self.world.move(900,self.a._id)
        radio.autopilot_receive(self.b,1,'wrong place')
        self.assertEqual('MechAI',self.engine.effects.channels[-1]['channel'])
        self.assertTrue(self.b.external_effects[-1]['applied'])

    def test_reply_guard_order_delay_and_channel_zero_dispatch(self):
        self.radios();self.b.autopilot=900;self.b.freq[0]=0
        with patch('core.randomness.draw',side_effect=AssertionError('guard consumed RNG')):
            self.assertIsNone(radio.auto_reply(self.b,'zero'));self.assertEqual(900,self.b.autopilot)
            self.b.freq[0]=17;self.assertIsNone(radio.auto_reply(self.b,'absent'));self.assertEqual(-1,self.b.auto)
        self.auto(self.b); draws=[]
        def draw(name,lo,hi,fallback):draws.append((name,lo,hi));return 2
        with use_source(draw):self.assertTrue(radio.directed_radio(self.a,self.a.pilot,'BB=hello')['ok'])
        event=self.engine.events.pending_events(event_type=EventType.AUTO_REPLY,data=self.b)[0]
        self.assertEqual(30,SOURCE_EVENT_IDS[event.event_type]);self.assertEqual(2,event.tick)
        self.assertEqual([('radio_reply_delay',1,2)],draws)
        self.a.freq[0]=self.b.freq[0]=23;self.b.autopilot=-1;self.b.status=S.NONE
        before=len(self.a.pilot.inbox)
        self.engine.process_tick();self.assertEqual(before,len(self.a.pilot.inbox))
        self.engine.process_tick()
        self.assertEqual(before+1,len(self.a.pilot.inbox))
        self.assertIn("A [aa] radio'ed me 'hello'",self.a.pilot.inbox[-1])

    def test_reply_event_revalidates_map_and_does_not_transmit_after_removal(self):
        self.radios();self.auto(self.b)
        with use_source(lambda *args:1):radio.auto_reply(self.b,'reply')
        self.b.mapindex=-1
        with patch('systems.communications.transmit') as send:
            self.engine.process_tick();send.assert_not_called()

    def test_comm_xp_uses_event_tick_and_preserves_distinct_successful_channel_effects(self):
        from data.characters import SKILLS
        from data.character_values import code
        from systems.characters import set_value
        self.radios();self.c.radio_type=0;self.a.in_character=False;self.b.pilot.connected=True
        for name in ('Build','Reflexes','Intuition','Learn','Charisma'):
            set_value(self.store,self.b.pilot._id,name,5)
        set_value(self.store,self.b.pilot._id,'Comm-Conventional',4)
        self.engine.effects.subscribe('MechXP',self.c.pilot)
        self.engine.sim_now=10000
        with patch('systems.communications.scramble_message',return_value=('scrambled',True)):
            for tick,expected in ((60,0),(61,1),(121,1),(122,2)):
                self.engine.sim_now=10000+tick
                self.engine.events.set_tick(tick);radio.transmit(self.a,0,'same')
                self.assertEqual(expected,self.store.retrieve(self.b.pilot._id,SKILLS).xp[code('Comm-Conventional')]%16777216)
        self.assertEqual(['B pilot gained 1 Comm-Conventional XP (in #11)']*2,self.c.pilot.inbox)
        self.assertEqual(122,self.b.comm_last)

    def test_scan_and_status_reach_original_turret_gunner_before_target_warning(self):
        from systems import turrets
        from systems.network_reports import show_flags
        self.radios();self.a.in_character=False;self.auto(self.b)
        gunner=SimpleNamespace(_id=501,valid=True,inbox=[],wizard=False)
        turret=turrets.Turret(_id=600,parent=self.a._id,gunner=501,target=self.b._id)
        self.world.add(turret,self.a._id);self.world.add(gunner,600)
        self.a.status|=S.HULLDOWN;self.b.status|=S.HULLDOWN
        trace=[]
        self.engine.effects.connect_client(gunner,lambda text:trace.append(('gunner',text)))
        self.engine.effects.connect_client(self.b.pilot,lambda text:trace.append(('target',text)))
        result=turrets.command(self.engine,turret,gunner,'scan','BB')
        self.assertTrue(result['ok'],result)
        self.assertEqual([line for line in result['lines'] if line],gunner.inbox)
        self.assertEqual('target',trace[-1][0]);self.assertIn('being scanned',trace[-1][1])
        self.assertEqual([],getattr(self.a.pilot,'inbox',[]))
        reply=self.engine.events.pending_events(event_type=EventType.AUTO_REPLY,data=self.b)[0]
        self.assertEqual('A [aa] just scanned me.',reply.data2)
        gunner.inbox.clear();trace.clear()
        result=turrets.command(self.engine,turret,gunner,'report','BB')
        self.assertEqual(result['lines'],gunner.inbox)
        self.assertTrue(all(kind=='gunner' for kind,text in trace))
        gunner.inbox.clear();trace.clear()
        result=turrets.command(self.engine,turret,gunner,'status','I')
        self.assertTrue(result['ok'],result)
        self.assertTrue(any('HULLDOWN' in line for line in gunner.inbox))
        self.assertEqual(result['lines'],gunner.inbox)
        self.assertEqual(0,self.engine.arc_override)
        gunner.inbox.clear()
        result=turrets.command(self.engine,turret,gunner,'scan',f'{self.a.x} {self.a.y} H')
        self.assertTrue(result['ok'],result)
        self.assertEqual('You see nothing else of interest in the hex, either.',gunner.inbox[-1])
        self.assertNotIn(gunner.inbox[-1],self.a.pilot.inbox)

    def test_parser_mode_mutation_changes_same_receiver_and_later_routing(self):
        self.radios();self.auto(self.b)
        self.engine.auto_services['radio']=lambda *args:self.a.freqmodes.__setitem__(0,0)
        rows=radio.transmit(self.a,0,'switch')
        self.assertTrue(rows[0]['text'].startswith('['))
        self.assertTrue(rows[1]['text'].startswith('('))
        self.assertTrue(rows[2]['text'].startswith('('))


    def test_hex_review_write_boundaries_use_only_selected_expansions(self):
        size=notice.LBUF_SIZE
        with patch('systems.notifications.sees_hex',return_value=True):
            notice.hex_broadcast(self.board,3,3,'x'*(size-1)+'$')
            self.assertEqual('x'*(size-1),self.a.pilot.inbox[-1])
            for unit in self.units:unit.x=4
            notice.hex_broadcast(self.board,3,3,'$H'*1100)
            self.assertEqual('%ch%cy3,3%cn'*1100,self.c.pilot.inbox[-1])
            notice.hex_broadcast(self.board,3,3,'x'*(size-4)+'$h$')
            self.assertEqual('x'*(size-4)+'3,3',self.a.pilot.inbox[-1])
            for message in ('x'*size,'x'*size+'$','x'*(size-3)+'$h$'):
                with self.subTest(tail=message[-6:]),self.assertRaises(ValueError):
                    notice.hex_broadcast(self.board,3,3,message)
            count=len(self.engine.effects.notifications)
            notice.hex_broadcast(self.board,3,3,'$')
            self.assertEqual(count,len(self.engine.effects.notifications))
            self.b.x=3
            for unit in self.units:unit.pilot.inbox=[]
            with self.assertRaises(ValueError):
                notice.hex_broadcast(self.board,3,3,'$H'*1100)
            # The earlier remote delivery precedes the later own-hex overflow.
            self.assertEqual(['%ch%cy3,3%cn'*1100],self.a.pilot.inbox)
            self.assertEqual([],self.b.pilot.inbox)

    def test_printf_review_integer_rules_and_empty_delivery(self):
        cases=[('%#o',(8,99),'010'),('%#.0x',(0,99),''),('%#.0X',(0,99),''),
               ('%#.0o',(0,99),'0'),('%.0d',(0,99),''),('%+.0d',(0,),'+'),
               ('%#08x',(42,),'0x00002a'),('%#08.4x',(42,),'  0x002a'),
               ('%08.4d',(12,),'    0012'),('%#.4o',(8,),'0010'),
               ('%#05o',(8,),'00010'),('%-#8x',(42,),'0x2a    '),
               ('%0*d',(-6,12),'12    '),('%0*.*d',(6,3,-12),'  -012'),
               ('%08.*d',(-1,12),'00000012'),('%hhd',(255,99),'-1'),
               ('%hu',(65537,),'1'),('%u',(-1,99),'4294967295'),
               ('%#llX',((1<<64)-1,),'0XFFFFFFFFFFFFFFFF'),
               ('%*.*d:%s',(6,4,12,'ok','unused'),'  0012:ok')]
        client=[];self.engine.effects.connect_client(self.a.pilot,client.append)
        for template,args,expected in cases:
            with self.subTest(template=template,args=args):
                self.a.pilot.inbox=[];client.clear()
                delivered=notice.mech_printf(self.a,notice.MECHALL,template,*args)
                self.assertEqual([expected] if expected else [],client)
                self.assertEqual(client,self.a.pilot.inbox)
                self.assertEqual([self.a.pilot._id] if expected else [],delivered)
        notice.mech_printf(self.a,notice.MECHALL,'%#.16384o',8,99)
        self.assertEqual(('0'*16382+'10')[:16383],client[-1])

    def test_c3_message_identity_survives_recipient_listener_mutation(self):
        for ordinary in (True,False):
            with self.subTest(ordinary=ordinary):
                self.a.name='A';self.a.contact_id='AA'
                c3.write(self.a,[self.b._id,self.c._id],ordinary)
                self.engine.effects.notification_listeners.clear()
                trace=[]
                for unit in self.units:
                    self.engine.effects.connect_client(unit.pilot,lambda text,ident=unit._id:trace.append((ident,text)))
                def rename(*args):self.a.name='Renamed';self.a.contact_id='ZX'
                self.engine.effects.listen(self.b.pilot,rename)
                result=c3.command(self.a,self.a.pilot,'message','hello',ordinary)
                kind='C3' if ordinary else 'C3i'
                peer=f'%ch{kind}/A [AA]: hello%cn'
                self.assertTrue(result['ok'],result)
                self.assertEqual([(11,peer),(12,peer),(10,f'%ch{kind}/You: hello%cn')],trace)
                self.assertEqual('Renamed',self.a.name)

    def test_c3_message_skips_peers_invalidated_during_previous_delivery(self):
        for ordinary in (True,False):
            for state in ('unregistered','invalid','invalid_object','destroyed'):
                with self.subTest(ordinary=ordinary,state=state):
                    self.engine.effects.notification_listeners.clear()
                    self.engine.register_entity(self.c)
                    self.c.valid=self.c.valid_object=True;self.c.status=S.STARTED
                    for unit in self.units:unit.pilot.inbox=[]
                    c3.write(self.a,[self.b._id,self.c._id],ordinary)
                    trace=[]
                    for unit in self.units:
                        self.engine.effects.connect_client(unit.pilot,lambda text,ident=unit._id:trace.append(ident))
                    def invalidate(*args):
                        if state=='unregistered':self.engine.unregister_entity(self.c)
                        elif state=='invalid':self.c.valid=False
                        elif state=='invalid_object':self.c.valid_object=False
                        else:self.c.status|=S.DESTROYED
                    self.engine.effects.listen(self.b.pilot,invalidate)
                    self.assertTrue(c3.command(self.a,self.a.pilot,'message','hello',ordinary)['ok'])
                    self.assertEqual([11,10],trace)
                    self.assertEqual([],self.c.pilot.inbox)

    def test_reply_rechecks_current_hardcode_and_explicit_type(self):
        self.radios();self.auto(self.b)
        for field,value in (('hardcode',False),('xcode_type','AUTO'),('xcode_type','')):
            with self.subTest(field=field,value=value):
                self.b.hardcode=True;self.b.xcode_type='MECH'
                with use_source(lambda *args:1):radio.auto_reply(self.b,'suppressed reply')
                setattr(self.b,field,value)
                self.a.pilot.inbox=[]
                self.engine.events.muxevent_run()
                self.assertEqual([],self.a.pilot.inbox)
                self.assertEqual([],self.engine.events.pending_events(event_type=EventType.AUTO_REPLY))
        self.b.hardcode=True;self.b.xcode_type='MECH'
        with use_source(lambda *args:1):radio.auto_reply(self.b,'current zero channel')
        self.b.status=S.NONE;self.b.auto=-1
        self.a.freq[0]=self.b.freq[0]=0
        self.engine.events.muxevent_run()
        self.assertIn('current zero channel',self.a.pilot.inbox[-1])

    def check_radio_entry_map_after_callback(self,parser):
        from entities.map import GameMap
        from physics.hexmath import SCALEMAP
        self.radios()
        for unit,distance in zip(self.units,(0,5,10)):
            unit.fx=distance*SCALEMAP;unit.fy=unit.fz=0;unit.radio_range=6
        self.b.freqmodes[0]=radio.FREQ_DIGITAL|radio.FREQ_RELAY
        self.c.freqmodes[0]=radio.FREQ_DIGITAL|radio.FREQ_INFO
        destination=GameMap(30,30);destination._id=1001
        self.engine.register_entity(destination)
        moved=[]
        def move_sender(*args):
            moved.append(True)
            self.board.remove_mech(self.a)
            if not parser:destination.add_mech(self.a)
            for unit in self.units:unit.freq[0]=23
        if parser:
            self.auto(self.b);self.engine.auto_services['radio']=move_sender
            rows=radio.transmit(self.a,0,'entry map relay')
            self.assertIsNone(self.a.map)
            self.assertTrue(self.b.external_effects[-1]['applied'])
        else:
            self.engine.effects.listen(self.b.pilot,move_sender)
            result=radio.send_channel(self.a,self.a.pilot,'a=entry map relay')
            self.assertTrue(result['ok'],result);rows=result['deliveries']
            self.assertIs(self.a.map,destination)
        self.assertEqual([True],moved)
        self.assertIn(self.c._id,[row['unit'] for row in rows])
        self.assertIn('{R-path:[BB]',self.c.pilot.inbox[-1])
        self.assertIn('entry map relay',self.c.pilot.inbox[-1])

    def test_radio_relay_keeps_entry_map_after_parser_detaches_sender(self):
        self.check_radio_entry_map_after_callback(True)

    def test_radio_relay_keeps_entry_map_after_recipient_moves_sender(self):
        self.check_radio_entry_map_after_callback(False)

    def test_turret_scan_rechecks_observer_state_after_requester_output(self):
        from systems import turrets
        self.radios();self.a.in_character=False;self.auto(self.b)
        gunner=SimpleNamespace(_id=501,valid=True,inbox=[],wizard=False)
        turret=turrets.Turret(_id=600,parent=self.a._id,gunner=501,target=self.b._id)
        self.world.add(turret,self.a._id);self.world.add(gunner,600)
        for initially_observer in (False,True):
            with self.subTest(initially_observer=initially_observer):
                self.engine.effects.notification_listeners.clear()
                self.a.crit_status=(self.a.crit_status|C.OBSERVATORIC if initially_observer else self.a.crit_status&~C.OBSERVATORIC)
                def change_observer(*args):
                    self.a.crit_status=(self.a.crit_status&~C.OBSERVATORIC if initially_observer else self.a.crit_status|C.OBSERVATORIC)
                self.engine.effects.listen(gunner,change_observer)
                trace=[]
                self.engine.effects.connect_client(gunner,lambda text:trace.append('gunner'))
                self.engine.effects.connect_client(self.b.pilot,lambda text:trace.append('target'))
                result=turrets.command(self.engine,turret,gunner,'scan','BB')
                self.assertTrue(result['ok'],result)
                self.assertEqual(int(initially_observer),trace.count('target'))
                self.assertEqual(int(initially_observer),len(self.engine.events.pending_events(event_type=EventType.AUTO_REPLY)))
                if initially_observer:self.assertEqual('target',trace[-1])

    def test_scan_reply_identity_is_evaluated_after_warning_before_guards(self):
        from systems.observation import scan_effects
        self.radios();self.auto(self.b)
        for route in ('default','engine','target','guarded'):
            with self.subTest(route=route):
                self.engine.events.cancel_by_type(EventType.AUTO_REPLY)
                self.engine.effects.notification_listeners.clear()
                self.a.name='A';self.a.contact_id='AA';self.a.team=1;self.b.freq[0]=17
                calls=[]
                self.engine.auto_reply=(lambda unit,text:calls.append(('engine',unit,text))) if route in ('engine','target') else None
                self.b.autonomous_scan_reply=(lambda viewer:calls.append(('target',viewer))) if route=='target' else None
                def rename(*args):
                    self.a.name='Renamed';self.a.contact_id='ZX';self.a.team=2
                    if route=='guarded':self.b.freq[0]=0
                self.engine.effects.listen(self.b.pilot,rename)
                with patch('systems.notifications.identity',wraps=notice.identity) as identify:
                    self.assertEqual([],scan_effects(self.a,self.b))
                    self.assertEqual(2,identify.call_count)
                self.assertEqual('You are being scanned by A [aa]',self.b.pilot.inbox[-1])
                events=self.engine.events.pending_events(event_type=EventType.AUTO_REPLY)
                if route=='default':
                    self.assertEqual('Renamed [ZX] just scanned me.',events[0].data2)
                else:
                    self.assertEqual([],events)
                    expected=[('engine',self.b,'Renamed [ZX] just scanned me.')] if route=='engine' else [('target',self.a)] if route=='target' else []
                    self.assertEqual(expected,calls)
