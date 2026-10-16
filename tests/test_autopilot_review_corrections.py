"""Focused regressions for AI-R1 through AI-R9 in port/AI/REVIEW.md."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from core.events import EventType as E
from core.game_loop import GameEngine
from core.attributes import attributes_for
from entities.autopilot import Autopilot
from entities.mech import Mech, MechStatus as S
from entities.map import LIGHT_FOREST, GRASSLAND, FIRE, SMOKE
from systems import autopilot_ai as navigation, autopilot_core as core
from systems import autopilot_commands as orders, autopilot_autogun as gun
from systems import autopilot_radio as radio, autopilot_storage as storage
from systems.autopilot import auto_com_event
from systems.communications import auto_reply_event
from tests import test_autopilot as base
unit_fixture = base.unit_fixture


def world_callback(event):
    # Exercise insertion and cancellation while restored callbacks are pending.
    if event.data2 == 'chain':
        event.data._engine.schedule_event(1,E.CUSTOM,world_callback,event.data,'child')
    if event.data2 == 'cancel':
        for other in event.data._engine.events.pending_events(E.AUTO_REPLY,event.data):
            if other.data2 == 'cancelled-reply':
                other.cancel()


class ReviewCorrections(unittest.TestCase):
    session = base.AutopilotTests.session

    def test_r1_crashed_neighbor_slots_survive_scans_and_other_controllers(self):
        for friends in (True,False):
            with self.subTest(friends=friends):
                s,a,u = self.session([unit_fixture(),
                    unit_fixture('Neighbor',11,'NE',(19,10,0),1 if friends else 2),
                    unit_fixture('Observer',12,'OB',(3,12,0),1)])
                neighbor = s.units['Neighbor']
                neighbor.speed = neighbor.desired_speed = 64.5
                neighbor.facing = neighbor.desired_facing = 90
                scan = navigation.getFriends if friends else navigation.getEnemies
                scan(u,s.map)
                navigation.ai_path_score(u,s.map,a,[(0,0)],not friends,u.fx,u.fy)
                state = navigation._neighbor_state(u,s.map,friends)
                slot = next(i for i,row in enumerate(state.slots[:state.count]) if row.mech is neighbor)
                self.assertTrue(state.slots[slot].out)
                scan(u,s.map)
                self.assertTrue(state.slots[slot].out)
                observer = s.units['Observer']
                second = core.auto_newautopilot(s.engine,201,observer)
                core.auto_engage(second,second)
                scan(observer,s.map)
                self.assertIs(navigation._neighbor_state(observer,s.map,friends),state)
                self.assertTrue(state.slots[slot].out)
                self.assertEqual(state.slots[slot].loc.x,neighbor.x)
                # Shrinking/repopulating the roster retains dormant exclusion slots.
                neighbor.set_status(S.DESTROYED)
                scan(observer,s.map)
                neighbor.clear_status(S.DESTROYED)
                scan(observer,s.map)
                self.assertTrue(state.slots[slot].out)
                self.assertEqual(scan(observer,s.map,1),0)
                self.assertFalse(any(row.out for row in state.slots[:state.count]))
                other,_,unit = self.session()
                self.assertIsNot(navigation._neighbor_state(unit,other.map,friends),state)

    def test_r2_disembark_uses_literal_hash_decimal_prefix_and_real_containment(self):
        for text,inside,accepted in (('#1010',True,True),('#1010suffix',False,True),
                ('# +1010suffix',False,True),('1010',True,False),('##1010',True,False),
                (' #1010',True,False),('#999999',True,False),('#-1',True,False)):
            with self.subTest(text=text):
                s,a,u = self.session([unit_fixture(),unit_fixture('Carrier',11,'CA')])
                carrier = s.units['Carrier'];carrier.hardcode = True
                actor = u.command_actor
                s.personnel.add(actor,u._id if inside else carrier._id)
                from systems.startup import shutdown
                shutdown(s.engine,u,caller=actor)
                s.personnel.move(u._id,carrier._id,True)
                s.map.remove_mech(u);u.mapindex = -1;u.map = None
                attributes_for(u).set(u._id,'A_PILOTNUM',text)
                result = orders.auto_command_udisembark(u)
                self.assertEqual(result['ok'],accepted)
                self.assertEqual(u.is_started,accepted and inside)
                self.assertEqual(u.location,s.map._id if accepted else carrier._id)
                self.assertIs(u.pilot,actor if accepted and inside else None)

    def test_r3_scheduled_callbacks_respect_live_hardcode_and_type(self):
        callbacks = [('speed 40',E.AUTOCOM,auto_com_event),
            ('oldgoto 3 3',E.AUTOGOTO,orders.auto_goto_event),
            ('dumbgoto 3 3',E.AUTOGOTO,orders.auto_dumbgoto_event),
            ('goto 3 3',E.AUTOGOTO,orders.auto_astar_goto_event),
            ('follow 11',E.AUTOFOLLOW,orders.auto_astar_follow_event),
            ('dumbfollow 11',E.AUTOFOLLOW,orders.auto_dumbfollow_event),
            ('leavebase 90',E.AUTOLEAVE,orders.auto_leave_event),
            ('enterbase n',E.AUTOENTERBASE,orders.auto_enter_event),
            ('roam radius 3 10 4',E.AUTO_ROAM,orders.auto_astar_roam_event),
            ('wait 1 1',E.AUTO_SENSOR,auto_com_event),
            ('wait 1 1',E.AUTO_PROFILE,auto_com_event),
            ('wait 1 1',E.AUTOGUN,auto_com_event)]
        for historical in (False,True):
            for command,kind,callback in callbacks:
                for who in ('controller','unit'):
                    for field,value in (('hardcode',False),('xcode_type','OTHER')):
                        with self.subTest(historical=historical,callback=callback.__name__,kind=kind,who=who,field=field):
                            row = unit_fixture()
                            if historical:
                                row.update({'class':'AERO','movement':'FLY','aerospace':{'landed':True}})
                                row['sections'] = row['sections'][:6]
                            s,a,u = self.session([row,unit_fixture('Target',11,'TA',(3,5,0),2)],commands=(command,))
                            core.auto_disengage(a,a)
                            core.schedule(a,1,kind,callback,1)
                            target = a if who == 'controller' else u
                            setattr(target,field,value)
                            before = (a.speed,a.flags,deepcopy(a.commands),u.target,list(u.sensor),u.desired_speed)
                            s.engine.events.muxevent_run()
                            self.assertEqual((a.speed,a.flags,a.commands,u.target,u.sensor,u.desired_speed),before)
                            self.assertIsNone(a.weaplist)
                            self.assertIsNone(a.astar_path)
                            self.assertFalse(s.engine.events.pending_events(data=a))

    def test_r3_general_good_object_guards_keep_source_stopgun_difference(self):
        for field in ('valid','valid_object'):
            for who in ('controller','unit'):
                s,a,u = self.session()
                setattr(a if who == 'controller' else u,field,False)
                a.flags = 1
                u.sensor[:] = [0,0];u.target = 88
                gun.auto_sensor_event(a)
                self.assertEqual((u.sensor,u.target,a.flags),([0,0],88,1))
                if who == 'unit':
                    gun.auto_update_profile_event(a)
                    self.assertIsNone(a.weaplist)
                    self.assertEqual(a.flags,0)

    def test_r4_walk_margin_and_desired_speed_heat_budget_use_real_firing(self):
        for desired,shots in ((43.0,1),(43.05,1),(43.1,1),(43.11,0)):
            with self.subTest(desired=desired):
                shooter = unit_fixture(weapons=[dict(name='IS.MediumLaser',section=0,critical=4)])
                s,a,u = self.session([shooter,unit_fixture('Target',11,'TA',(3,5,0),2)])
                u.speed = 20;u.desired_speed = desired
                u.weap_heat = 2;u.minus_heat = 0
                a.target = u.target = 11;a.flags |= 256
                s.map.losinfo[u._id,11] = 3  # Source seen + current primary contact.
                gun.auto_update_profile_event(a)
                gun.auto_gun_event(a)
                self.assertEqual(getattr(u,'shots_fired',0),shots)
        for actual,label in ((43.0,'Walking'),(43.05,'Walking'),(43.1,'Walking'),(43.11,'Running')):
            s,a,u = self.session()
            u.speed = actual;u.desired_speed = 64.5
            self.assertTrue(radio.auto_radio_command_report(a,u,[]).startswith(label))

    def test_r5_hide_uses_overlay_underlay_in_radio_and_shared_consumer(self):
        from physics.decorations import add_decoration
        from systems.swarm import hide
        for overlay in (SMOKE,FIRE):
            for terrain,allowed in ((LIGHT_FOREST,True),(GRASSLAND,False)):
                with self.subTest(overlay=overlay,terrain=terrain):
                    s,a,u = self.session()
                    u.specials2 |= 0x40000
                    s.map.set_terrain(u.x,u.y,terrain)
                    add_decoration(s.engine,s.map,u.x,u.y,overlay,120)
                    u.terrain = overlay
                    reply = radio.auto_radio_command_hide(a,u,[])
                    self.assertEqual(reply,'Begining to hide' if allowed else '!Invalid Terrain')
                    self.assertEqual(s.engine.has_event(E.HIDE,u),allowed)
                    s.engine.cancel_events_of_type(E.HIDE,u)
                    result = hide(u,a)
                    self.assertEqual(result['ok'],allowed)
                    self.assertEqual(s.engine.has_event(E.HIDE,u),allowed)

    def queue_fixture(self, mixed):
        engine = GameEngine()
        unit = Mech.create_test_mech();unit._id = 10
        engine.register_entity(unit)
        a = core.auto_newautopilot(engine,200,unit)
        a.mymech = unit;a.mymechnum = unit._id;unit.auto = a._id
        rows = [(1,'reply','first'),(1,'reply','second'),(1,'reply','third')]
        if mixed:
            rows = [(1,'world','chain'),(3,'reply','later'),(1,'reply','first'),
                    (1,'world','cancel'),(1,'reply','second'),(1,'world','zombie'),
                    (2,'reply','cancelled-reply'),(1,'reply','third'),(5,'world','last')]
        for delay,kind,text in rows:
            event = engine.schedule_event(delay,E.AUTO_REPLY if kind == 'reply' else E.CUSTOM,
                         auto_reply_event if kind == 'reply' else world_callback,data=unit,data2=text)
            if text == 'zombie':event.cancel()
        if mixed:
            for kind in (E.AUTO_SENSOR,E.AUTO_PROFILE,E.AUTOGUN):
                core.schedule(a,1,kind)
        return engine,a,unit

    def test_r6_reload_preserves_heap_order_with_world_callbacks_and_zombies(self):
        for mixed in (False,True):
            traces = []
            for reloads in (0,1,3):
                engine,a,u = self.queue_fixture(mixed)
                original = storage.save_snapshot(engine)
                for _ in range(reloads):
                    a = storage.load_snapshot(engine,storage.save_snapshot(engine))[200]
                    saved = storage.save_snapshot(engine)
                    self.assertEqual(saved['events'],original['events'])
                observed = []
                engine.events.observe_execution = lambda phase,event: observed.append((engine.tick,event.event_type.name,event.data2)) if phase == 'pre' else None
                for _ in range(6):engine.events.muxevent_run()
                traces.append(observed)
            self.assertEqual(traces[1],traces[0])
            self.assertEqual(traces[2],traces[0])
            if not mixed:
                self.assertEqual([row[2] for row in traces[0]],['first','second','third'])
            else:
                self.assertIn((2,'CUSTOM','child'),traces[0])
                self.assertFalse(any(row[2] in ('zombie','cancelled-reply') for row in traces[0]))

    def test_r6_missing_world_anchors_are_not_replayed_and_new_events_survive(self):
        engine,a,u = self.queue_fixture(True)
        data = storage.save_snapshot(engine)
        engine.events.cancel_by_type(E.CUSTOM)
        engine.events.purge_zombies()
        engine.schedule_event(1,E.CUSTOM,world_callback,u,'new-world-event')
        loaded = storage.load_snapshot(engine,data)[200]
        size = len(engine.events.heap_events())
        for _ in range(2):
            loaded = storage.load_snapshot(engine,data)[200]
            self.assertEqual(len(engine.events.heap_events()),size)
        self.assertEqual([event.tick for event in engine.events.pending_events(E.AUTO_REPLY)],
                         [row['remaining'] for row in data['events'] if row['kind'] == 'AUTO_REPLY'])
        observed = []
        engine.events.observe_execution = lambda phase,event: observed.append(event.data2) if phase == 'pre' else None
        for _ in range(6):engine.events.muxevent_run()
        self.assertIn('new-world-event',observed)
        self.assertFalse(any(name in observed for name in ('chain','cancel','last','zombie')))
        self.assertTrue(loaded.allocated)

    def test_r6_invalid_layout_rejects_atomically(self):
        engine,a,u = self.queue_fixture(True)
        data = storage.save_snapshot(engine)
        before = engine.events.heap_events()
        bad = deepcopy(data);bad['layout'][1]['id'] = bad['layout'][0]['id']
        with self.assertRaises(ValueError):storage.load_snapshot(engine,bad)
        self.assertEqual(engine.events.heap_events(),before)
        self.assertTrue(a.allocated)

    def test_r7_public_load_rejects_all_name_collisions_before_mutation(self):
        for names in (('Autopilot','Autopilot'),('ai','new'),('reserved','new')):
            with self.subTest(names=names):
                s,a,u = self.session([unit_fixture(),unit_fixture('Two',11,'TW'),unit_fixture('Three',12,'TH')],
                    commands=('goto 3 3',),objects=[dict(name='reserved',id=500,type='OTHER')])
                data = storage.save_snapshot(s.engine)
                template = data['controllers'][0]
                data['controllers'] = []
                data['events'] = []
                for ident,name,unit in zip((201,202),names,(11,12)):
                    row = deepcopy(template);row.update(id=ident,name=name,pilot=False)
                    row['values'].update(location=unit,mymechnum=unit)
                    data['controllers'].append(row)
                s.path('collision.json').write_text(json.dumps(data),encoding='utf-8')
                before = s.engine.events.heap_events()
                entities = s.engine.get_entities()
                result = s.action(dict(op='ai_load',file='collision.json'))
                self.assertFalse(result['ok'])
                self.assertIn('Duplicate public controller name',result['error'])
                self.assertEqual(s.engine.get_entities(),entities)
                self.assertEqual(s.engine.events.heap_events(),before)
                self.assertIs(s.autopilots['ai'],a)
                self.assertIs(s.personnel.objects[a._id],a)
                self.assertTrue(a.allocated)

    def test_r7_successful_load_keeps_every_public_controller_and_existing_handle(self):
        s,a,u = self.session([unit_fixture(),unit_fixture('Two',11,'TW')])
        data = storage.save_snapshot(s.engine)
        row = deepcopy(data['controllers'][0]);row.update(id=201,name='second',pilot=False)
        row['values'].update(location=11,mymechnum=11)
        data['controllers'].append(row)
        data['controllers'][0]['name'] = 'changed-display-name'
        s.path('valid.json').write_text(json.dumps(data),encoding='utf-8')
        self.assertTrue(s.action(dict(op='ai_load',file='valid.json'))['ok'])
        self.assertEqual({name:a._id for name,a in s.autopilots.items()},{'ai':200,'second':201})
        self.assertEqual(len(storage.save_snapshot(s.engine,list(s.autopilots.values()))['controllers']),2)

    def test_r8_both_startup_routes_and_reload_keep_nonplayer_defaults(self):
        from systems.startup import shutdown
        for via_radio in (False,True):
            for reload in (False,True):
                with self.subTest(via_radio=via_radio,reload=reload):
                    s,a,u = self.session()
                    shutdown(s.engine,u,caller=u.command_actor)
                    if via_radio:
                        radio.auto_parse_command(a,u,0,'SH startup')
                    else:
                        core.auto_addcommand(a,a,'startup');core.auto_engage(a,a)
                    s.action(dict(op='advance',seconds=5))
                    self.assertIs(u.pilot,a)
                    if reload:
                        a = storage.load_snapshot(s.engine,storage.save_snapshot(s.engine))[200]
                    s.action(dict(op='advance',seconds=30))
                    self.assertTrue(u.is_started)
                    self.assertIs(u.pilot,a)
                    self.assertFalse(a.is_player)
                    self.assertFalse(s.characters.record(a._id)['is_player'])
                    self.assertNotIn(a._id,s.characters.records)
                    self.assertEqual((u.comm,u.per),(6,6))

    def test_r8_genuine_player_startup_still_uses_character_skills(self):
        from systems.startup import shutdown, startup
        from systems.characters import skill_target
        s,a,u = self.session(characters=[dict(id=42,name='Pilot',location=10,
            values={'Intuition':3,'Learn':4,'Charisma':2,'Perception':4,'Comm-Conventional':3})])
        actor = s.characters.actor(42)
        expected = tuple(skill_target(s.characters,42,name) for name in ('Comm-Conventional','Perception'))
        shutdown(s.engine,u,caller=u.command_actor)
        self.assertTrue(startup(s.engine,u,caller=actor)[0])
        s.action(dict(op='advance',seconds=30))
        self.assertTrue(s.characters.record(42)['is_player'])
        self.assertEqual((u.comm,u.per),expected)
        self.assertNotEqual(expected,(6,6))


    def opaque_repair_event(self, engine, unit):
        from systems.repair_jobs import RepairJobs
        from core.events import SourceEventType, very_fake_func
        jobs = RepairJobs(engine,None,SimpleNamespace(objects={unit._id:unit}))
        # The exact recorded AI-R9 reproduction, through the real repair loader.
        self.assertEqual(jobs.load('[10,59,-5,0]\n[-1]\n'),
                         dict(loaded=1,skipped=0,error=None))
        event = next(e for e in engine.events.pending_events() if e.event_type.name == 'SOURCE_59')
        self.assertIsInstance(event.event_type,SourceEventType)
        self.assertIs(event.callback,very_fake_func)
        return event

    def test_r9_repair_loaded_opaque_anchors_preserve_order_and_cancellation(self):
        for cancellation in ('live','before-save','after-save'):
            traces = []
            for reloads in (0,1,3):
                with self.subTest(cancellation=cancellation,reloads=reloads):
                    engine,a,u = self.queue_fixture(True)
                    self.assertEqual(storage.save_snapshot(engine)['version'],2)
                    opaque = self.opaque_repair_event(engine,u)
                    # These coincide with the opaque repair callback and existing world work.
                    engine.schedule_event(5,E.AUTO_REPLY,auto_reply_event,u,'reply-after-repair')
                    core.schedule(a,5,E.AUTO_PROFILE)
                    if cancellation == 'before-save':opaque.cancel()
                    data = json.loads(json.dumps(storage.save_snapshot(engine)))
                    slot = next(row for row in data['layout'] if row['id'] == opaque.event_id)
                    self.assertEqual((slot['kind'],slot['remaining'],slot['zombie']),
                                     ('SOURCE_59',5,cancellation == 'before-save'))
                    self.assertNotIn(opaque.event_id,[row['id'] for row in data['events']])
                    if cancellation == 'after-save':opaque.cancel()
                    for _ in range(reloads):
                        a = storage.load_snapshot(engine,data)[200]
                        current = next(e for e in engine.events.heap_events() if e.event_id == opaque.event_id)
                        self.assertIs(current,opaque)
                        self.assertIs(current.data,u)
                        self.assertEqual((current.data2,current.tick,current.repair_fake,current.repair_callback),
                                         (0,5,True,None))
                        self.assertEqual(current.zombie,cancellation != 'live')
                        self.assertEqual(storage.save_snapshot(engine)['events'],data['events'])
                    observed = []
                    engine.events.observe_execution = lambda phase,event: observed.append(
                        (engine.tick,event.event_type.name,getattr(event.data,'_id',None),event.data2)) if phase == 'pre' else None
                    for _ in range(6):engine.events.muxevent_run()
                    self.assertEqual(sum(row[1] == 'SOURCE_59' for row in observed),int(cancellation == 'live'))
                    traces.append(observed)
            self.assertEqual(traces[1],traces[0])
            self.assertEqual(traces[2],traces[0])

    def test_r9_public_save_load_accepts_live_and_canceled_opaque_repairs(self):
        for canceled in (False,True):
            with self.subTest(canceled=canceled):
                s,a,u = self.session()
                result = s.action(dict(op='repair',kind='load',text='[10,59,-5,0]\n[-1]\n'))
                self.assertEqual(result,dict(loaded=1,skipped=0,error=None))
                opaque = next(e for e in s.engine.events.pending_events() if e.event_type.name == 'SOURCE_59')
                if canceled:opaque.cancel()
                self.assertTrue(s.action(dict(op='ai_save',file='opaque.json'))['ok'])
                self.assertTrue(s.action(dict(op='ai_load',file='opaque.json'))['ok'])
                self.assertIsNot(s.autopilots['ai'],a)
                self.assertIs(next(e for e in s.engine.events.heap_events() if e.event_id == opaque.event_id),opaque)
                self.assertIs(opaque.data,u)
                self.assertEqual(opaque.zombie,canceled)

    def test_r9_absent_opaque_anchors_remain_inert_across_reloads(self):
        from core.events import SOURCE_EVENT_IDS
        engine,a,u = self.queue_fixture(False)
        opaque = self.opaque_repair_event(engine,u)
        data = storage.save_snapshot(engine)
        opaque.cancel();engine.events.purge_zombies()
        # A foreign snapshot can name a supported opaque kind absent from this
        # process's type registry. Layout validation must not register it.
        for kind in ('SOURCE_59','SOURCE_0','SOURCE_987654321'):
            with self.subTest(kind=kind):
                document = deepcopy(data)
                next(row for row in document['layout'] if row['id'] == opaque.event_id)['kind'] = kind
                registered = dict(SOURCE_EVENT_IDS)
                for _ in range(3):
                    a = storage.load_snapshot(engine,document)[200]
                    self.assertEqual(len(engine.events.heap_events()),len(document['layout']))
                    self.assertFalse(any(e.event_type.name == kind for e in engine.events.pending_events()))
                self.assertEqual(SOURCE_EVENT_IDS,registered)
        observed = []
        engine.events.observe_execution = lambda phase,event: observed.append(event.event_type.name) if phase == 'pre' else None
        for _ in range(6):engine.events.muxevent_run()
        self.assertEqual(observed,['AUTO_REPLY']*3)

    def test_r9_opaque_layout_metadata_keeps_ai_callback_validation_strict(self):
        engine,a,u = self.queue_fixture(False)
        opaque = self.opaque_repair_event(engine,u)
        data = storage.save_snapshot(engine)
        before = engine.events.heap_events()
        invalid = []
        for kind in ('SOURCE_-1','SOURCE_+59','SOURCE_059','SOURCE_59suffix',
                     'SOURCE_','SOURCE_٥٩','UNRECOGNIZED',59,None,{}):
            bad = deepcopy(data)
            next(row for row in bad['layout'] if row['id'] == opaque.event_id)['kind'] = kind
            invalid.append(bad)
        # A valid opaque layout kind must not become an accepted AI event kind.
        bad = deepcopy(data)
        row = bad['events'][0];row['kind'] = 'SOURCE_59'
        next(slot for slot in bad['layout'] if slot['id'] == row['id'])['kind'] = row['kind']
        invalid.append(bad)
        bad = deepcopy(data);bad['events'][0]['callback'] = 'unrecognized'
        invalid.append(bad)
        # Known names also retain the callback/type pairing check.
        bad = deepcopy(data)
        row = bad['events'][0];row['kind'] = 'AUTOCOM'
        next(slot for slot in bad['layout'] if slot['id'] == row['id'])['kind'] = row['kind']
        invalid.append(bad)
        for index,bad in enumerate(invalid):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):storage.load_snapshot(engine,bad)
                self.assertEqual(engine.events.heap_events(),before)
                self.assertTrue(a.allocated)
                self.assertIn(a,engine.get_entities())
                self.assertIs(opaque.data,u)
                self.assertFalse(opaque.zombie)


if __name__ == '__main__':
    unittest.main()
