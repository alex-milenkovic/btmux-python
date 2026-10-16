"""B1/B2 and R1-R5 observable weather and map behavior, independent of APS."""
import io
import unittest
from core.game_loop import GameEngine
from core.randomness import RandomState, number, use_simulation, use_source
from entities.map import GameMap
from entities.map_objects import bits_for, load_objects, save_objects
from physics import weather


def fixture(width=1,height=1):
    engine=GameEngine(); board=GameMap(width,height); board._id=10
    board.grav=100; board.temp=20; engine.register_entity(board)
    return engine,board


class CorrectedBitsTest(unittest.TestCase):
    def test_all_right_edges_roundtrip_and_short_load_is_atomic(self):
        for width in (1,2,3,4,5,7,8,9,1000):
            with self.subTest(width=width):
                _,board=fixture(width)
                bits=bits_for(board); bits.set(width-1,0,1); bits.set(width-1,0,2)
                wire=save_objects(board)
                copy=GameMap(width,1); load_objects(copy,wire)
                self.assertEqual((width-1)//4,bits.position(width-1,0)[0])
                self.assertEqual(3 << (2*((width-1)%4)),bits_for(copy).rows[0][-1])
                self.assertTrue(copy.flags&1)
                with self.assertRaises(ValueError):load_objects(copy,wire[:-3])
                self.assertEqual(bits.rows,bits_for(copy).rows)
                with self.assertRaises(ValueError):bits.set(width,0,1)


class WeatherReconstructionTest(unittest.TestCase):
    def test_equal_bounds_uninjected_preserve_exclusions_sign_and_normalization(self):
        engine,board=fixture(6,1);engine.randomness=RandomState(7)
        for x,terrain in enumerate(('/','&','~','-'),2):board.set_terrain(x,0,terrain)
        board.layers[1,0]={'snow','mud'};board.layer_data[1,0]=995
        terrain=[row[:] for row in board._terrain]
        with use_simulation(engine.randomness):
            self.assertEqual(0,number(10,10))  # Shared Number retains its source rule.
            weather.command(board,'snow.grow',dict(low=10,high=10))
            self.assertEqual({(0,0):10,(1,0):1005},board.layer_data)
            self.assertEqual({(0,0):{'snow'},(1,0):{'deep_snow'}},board.layers)
            weather.command(board,'snow.grow',dict(low=-10,high=-10))
            self.assertEqual({(0,0):0,(1,0):995},board.layer_data)
            self.assertEqual({(0,0):set(),(1,0):{'snow'}},board.layers)
            weather.command(board,'snow.grow',dict(low=10,high=-10))
            self.assertEqual({(0,0):0,(1,0):985},board.layer_data)
            weather.command(board,'snow.grow',dict(low=0,high=0))
            self.assertEqual({(0,0):0,(1,0):985},board.layer_data)
            self.assertEqual({(0,0):set(),(1,0):{'snow'}},board.layers)
        self.assertEqual(terrain,board._terrain)
        self.assertEqual(0,engine.randomness.mt.words_consumed)

    def test_equal_bounds_scheduled_growth_without_injection(self):
        from core.events import EventType
        for condition in ('precipitation','heavy_precipitation'):
            with self.subTest(condition=condition):
                engine,board=fixture(6,1);engine.randomness=RandomState(7)
                for x,terrain in enumerate(('/','&','~','-'),2):board.set_terrain(x,0,terrain)
                weather.command(board,'weather.set',dict(conditions=[condition],temperature=0,
                    cadence_ticks=3,snow_low=10,snow_high=10,heavy_snow_low=10,heavy_snow_high=10))
                first=board.weather_event
                engine.run_ticks(2)
                self.assertEqual({},board.layer_data);self.assertIs(first,board.weather_event)
                engine.run_ticks(1)
                self.assertEqual({(0,0):10,(1,0):10},board.layer_data)
                self.assertIsNot(first,board.weather_event)
                self.assertEqual(6,board.weather_event.tick)
                engine.run_ticks(3)
                self.assertEqual({(0,0):20,(1,0):20},board.layer_data)
                self.assertEqual({(0,0):{'snow'},(1,0):{'snow'}},board.layers)
                self.assertEqual(9,board.weather_event.tick)
                self.assertEqual(1,engine.events.count_type(EventType.WEATHER))
                self.assertEqual(0,engine.randomness.mt.words_consumed)

    def test_normalizer_and_growth_preserve_only_source_surviving_flags(self):
        _,board=fixture(); board.layers[0,0]={'snow','mud'}; board.layer_data[0,0]=100
        with use_source(lambda n,l,h,f:h):weather.grow(board,-200,-200)
        self.assertEqual((0,{'mud'}),(board.layer_data[0,0],board.layers[0,0]))
        board.layers[0,0]={'snow','mud'};board.layer_data[0,0]=100
        with use_source(lambda n,l,h,f:h):weather.grow(board,901,901)
        self.assertEqual((1001,{'deep_snow'}),(board.layer_data[0,0],board.layers[0,0]))

    def test_ice_under_smoke_breaks_and_expiry_cannot_restore_ice(self):
        from physics.decorations import add_smoke
        engine,board=fixture();board.set_terrain(0,0,'-');board.set_elevation(0,0,2)
        smoke=add_smoke(engine,board,0,0,10)
        draws=[]
        with use_source(lambda n,l,h,f:draws.append(n) or l):weather.melt(board,0,0,1,steam=True)
        self.assertEqual('~',board.terrain(0,0));self.assertEqual(-2,board.base_elevation(0,0))
        self.assertEqual([],draws)
        engine.run_ticks(10)
        self.assertEqual('~',board.rterrain(0,0))

    def test_clock_configuration_validation_and_rearming(self):
        engine,board=fixture()
        weather.command(board,'weather.set',{'conditions':['precipitation'],'temperature':0})
        event=board.weather_event
        engine.run_ticks(10)
        weather.command(board,'weather.set',{'conditions':['precipitation']})
        self.assertIs(event,board.weather_event)
        for bad in ({'cadence_ticks':0},{'temperature':True},{'snow_low':21},{'conditions':['unknown']}):
            with self.assertRaises(ValueError):weather.command(board,'weather.set',bad)
            self.assertIs(event,board.weather_event)
        draws=[]
        with use_source(lambda n,l,h,f:draws.append((n,l,h)) or l):engine.run_ticks(50)
        self.assertEqual(10,board.layer_data[0,0]);self.assertEqual(120,board.weather_event.tick)
        self.assertEqual([('snow_growth',10,20)],draws)
        weather.command(board,'weather.disable',{})
        self.assertIsNone(board.weather_event)
        engine.run_ticks(10);weather.command(board,'weather.enable',{})
        self.assertEqual(130,board.weather_event.tick)

    def test_generic_decoration_ice_uses_underlying_query_for_control_and_clock(self):
        from entities.map_objects import MapObject,add_object,delete_object
        for automatic in (False,True):
            with self.subTest(automatic=automatic):
                engine,board=fixture();board.set_terrain(0,0,'B');board.set_elevation(0,0,2)
                overlay=add_object(board,2,MapObject(datac=ord('-')))
                draws=[]
                with use_source(lambda n,l,h,f:draws.append(n) or l):
                    if automatic:
                        weather.command(board,'weather.set',{'temperature':50,'steam':True})
                        engine.run_ticks(60)
                    else:
                        # Source Elevation still uses raw B: depth below 400 cannot break it.
                        weather.command(board,'snow.melt',dict(x=0,y=0,depth=399))
                        self.assertEqual('B',board.terrain(0,0))
                        weather.command(board,'snow.melt',dict(x=0,y=0,depth=400,steam=True))
                self.assertEqual(('~',-2,ord('~')),
                                 (board.terrain(0,0),board.base_elevation(0,0),overlay.datac))
                self.assertEqual([],draws)
                delete_object(board,overlay,2)
                self.assertEqual('~',board.terrain(0,0))

    def test_temperature_and_wind_shared_ownership(self):
        from entities.map import map_update
        from entities.mech import Mech,MechStatus
        engine,board=fixture();unit=Mech();board.add_mech(unit)
        weather.command(board,'weather.set',{'temperature':51,'windspeed':61,'winddir':90})
        self.assertTrue(unit.has_status(MechStatus.UNDERTEMPERATURE))
        event=board.weather_event
        engine.run_ticks(25);map_update(engine,board)
        self.assertEqual((90,61),(board.winddir,board.windspeed));self.assertIs(event,board.weather_event)
        self.assertEqual(['high_winds'],weather.command(board,'weather.show',{})['effects'])


class EnvironmentPersistenceTest(unittest.TestCase):
    def test_self_spreading_fire_restores_all_callbacks_and_cancels_by_object(self):
        from copy import deepcopy
        from core.events import EventType
        from entities.map_objects import delete_object
        from physics.decorations import add_fire
        from systems.environment_storage import save_snapshot,load_snapshot
        engine,board=fixture();board.set_terrain(0,0,'`')
        board.winddir=-100;board.windspeed=1
        original=add_fire(engine,board,0,0,180)
        def spread(name,low,high,fallback):
            return {'fire_spread':12,'fire_wind':1,'fire_duration':180}[name]
        with use_source(spread):engine.run_ticks(59)
        fire=board.map_objects[0][0]
        self.assertIsNot(original,fire);self.assertEqual(121,fire.datas)
        pending=engine.events.pending_events(EventType.DECORATION,board)
        self.assertEqual(2,len(pending));self.assertTrue(all(e.data2 is fire for e in pending))
        snapshot=save_snapshot(engine,[board])
        self.assertEqual([dict(map=10,callback='spread_fire',remaining=59,group=0,index=0)]*2,
                         snapshot['events'])
        for key,value in (('group',1),('index',1),('callback','expire_smoke')):
            with self.subTest(invalid_reference=key):
                malformed=deepcopy(snapshot);malformed['events'][1][key]=value
                with self.assertRaisesRegex(ValueError,'invalid decoration event reference'):
                    load_snapshot(engine,malformed)
                self.assertIs(fire,board.map_objects[0][0])
                self.assertTrue(all(not e.zombie for e in pending))
        fresh=GameEngine();fresh.run_ticks(100)
        restored=load_snapshot(fresh,snapshot)[10];copy=restored.map_objects[0][0]
        resumed=fresh.events.pending_events(EventType.DECORATION,restored)
        self.assertEqual([159,159],[e.tick for e in resumed])
        self.assertTrue(all(e.data2 is copy for e in resumed))
        draws=[]
        for clock,target in ((engine,board),(fresh,restored)):
            trace=[]
            with use_source(lambda name,low,high,fallback:trace.append(name) or 2):
                clock.run_ticks(59)
            draws.append(trace)
            self.assertEqual(3,target.map_objects[0][0].datas)
        self.assertEqual([['fire_spread']*8]*2,draws)
        continued=save_snapshot(engine,[board])
        self.assertEqual(continued,save_snapshot(fresh,[restored]))
        self.assertEqual([('expire_fire',3),('spread_fire',59)],
                         [(e['callback'],e['remaining']) for e in continued['events']])
        saved=list(fresh.events.pending_events(EventType.DECORATION,restored))
        load_snapshot(fresh,continued)
        self.assertTrue(all(e.zombie for e in saved))
        fire=restored.map_objects[0][0]
        pending=fresh.events.pending_events(EventType.DECORATION,restored)
        self.assertEqual([(162,'expire_fire'),(218,'spread_fire')],
                         [(e.tick,e.callback.__name__) for e in pending])
        self.assertTrue(all(e.data2 is fire for e in pending))
        delete_object(restored,fire,0,1)
        self.assertTrue(all(e.zombie for e in pending))
        self.assertEqual([],fresh.events.pending_events(EventType.DECORATION,restored))
        fresh.run_ticks(59)
        self.assertEqual('`',restored.terrain(0,0));self.assertEqual([],restored.external_effects)

    def test_relative_weather_and_steam_resume_once_and_preserve_huge_depth(self):
        from systems.environment_storage import save_snapshot,load_snapshot
        engine,board=fixture(2,1)
        weather.command(board,'layer.set',dict(x=0,y=0,layers=['snow'],data=500))
        weather.command(board,'layer.set',dict(x=1,y=0,layers=['deep_snow'],data=9007199254740993))
        weather.command(board,'weather.set',dict(temperature=1))
        engine.run_ticks(65)
        snap=save_snapshot(engine,[board])
        self.assertEqual('9007199254740983',snap['maps'][0]['weather']['cells'][1]['data'])
        fresh=GameEngine();fresh.run_ticks(100)
        restored=load_snapshot(fresh,snap)[10]
        self.assertEqual(155,restored.weather_event.tick)
        self.assertEqual([105,105],[o.event.tick for o in restored.map_objects[1]])
        fresh.run_ticks(5);engine.run_ticks(5)
        self.assertEqual(board.layers,restored.layers);self.assertEqual(board.layer_data,restored.layer_data)
        self.assertEqual(board._terrain,restored._terrain)
        self.assertEqual([],restored.map_objects[1])

    def test_entire_snapshot_rejects_before_cancelling_or_replacing(self):
        from copy import deepcopy
        from systems.environment_storage import save_snapshot,load_snapshot
        engine,board=fixture();weather.command(board,'weather.set',dict(temperature=0,conditions=['precipitation']))
        snap=save_snapshot(engine,[board]);event=board.weather_event
        for change in ('version','delay','data','names','dimensions','duplicate_weather'):
            malformed=deepcopy(snap)
            if change=='version':malformed['version']=2
            elif change=='delay':malformed['events'][0]['remaining']=-1
            elif change=='data':malformed['maps'][0]['weather']['cells']=[dict(x=0,y=0,layers=['snow'],data='01')]
            elif change=='names':malformed['maps'][0]['weather']['conditions']=['unknown']
            elif change=='dimensions':malformed['maps'][0]['width']=-1
            else:malformed['events'].append(dict(malformed['events'][0]))
            with self.assertRaises(ValueError):load_snapshot(engine,malformed)
            self.assertIs(event,board.weather_event);self.assertFalse(event.zombie)
        copy=deepcopy(snap);del copy['maps'][0]['weather'];copy['events']=[]
        load_snapshot(engine,copy)
        self.assertFalse(board.weather_enabled);self.assertEqual({},board.layers)


class SharedWeatherTest(unittest.TestCase):
    def test_cli_heat_fixture_retains_unit_record_and_normal_dispatch(self):
        from tools.maps_environment import MapsSession
        session=MapsSession({'units':[{'name':'u','heat_state':{'num_sinks':10}}],
                             'config':{'periodic_updates':True},'actions':[]})
        session.action(dict(op='map_command',name='weather.set',args=dict(temperature=51,conditions=['precipitation'])))
        session.action(dict(op='advance',seconds=2))
        self.assertEqual(8,session.units['u'].minus_heat)

    def test_live_modifiers_distinguish_weapon_classes_layers_and_temperature_gate(self):
        from entities.mech import Mech,MoveType,MechStatus
        from entities.weapon import get_weapon
        from systems.combat import calculate_bth
        from systems.piloting import piloting_bth
        from systems.heat import update_from_environment
        engine,board=fixture(9,9);unit=Mech.create_test_mech();unit.x=unit.y=1
        board.add_mech(unit);engine.register_entity(unit);unit.num_sinks=10
        from entities.crittypes import i2special,Special
        from entities.mech import Location
        unit.sections[Location.LLEG].criticals[4].type=i2special(Special.HEAT_SINK)
        base=piloting_bth(unit)
        for weapon_name,expected in [('IS.AC/5',2),('IS.MediumLaser',0),('IS.LRM-10',0),('IS.StreakSRM-2',0)]:
            weapon=get_weapon(weapon_name)
            weather.command(board,'weather.set',dict(temperature=20,windspeed=61))
            result=calculate_bth(unit,None,weapon,3)
            self.assertEqual(expected,result.weather_mod)
        weather.command(board,'layer.set',dict(x=1,y=1,layers=['deep_snow','mud','rapids'],data=1001))
        self.assertEqual(base+5,piloting_bth(unit))
        unit.move_type=MoveType.HOVER;self.assertEqual(base+1,piloting_bth(unit))
        unit.z=1;self.assertEqual(base,piloting_bth(unit));unit.z=0;unit.move_type=MoveType.BIPED
        unit.set_status(MechStatus.JUMPING);self.assertEqual(base,piloting_bth(unit));unit.clear_status(MechStatus.JUMPING)
        weather.command(board,'weather.disable',{});self.assertEqual(base,piloting_bth(unit))
        for temp,expected in [(-31,11),(51,9)]:
            weather.command(board,'weather.set',dict(temperature=temp,conditions=[],enabled=False))
            update_from_environment(unit,2);self.assertEqual(expected,unit.minus_heat)
            weather.command(board,'weather.set',dict(conditions=['precipitation']))
            update_from_environment(unit,4);self.assertEqual(expected-(temp>0)-1,unit.minus_heat)  # deep snow leg sinks
        weather.command(board,'weather.disable',{});board.flags &= ~2
        update_from_environment(unit,6);self.assertEqual(10,unit.minus_heat)

    def test_ordinary_stand_roll_at_weather_boundary_has_real_failure(self):
        from tools.maps_environment import MapsSession
        for enabled,accepted in [(False,True),(True,False)]:
            session=MapsSession({'units':[dict(name='u',fallen=True)],'config':{'periodic_updates':False},'actions':[]})
            session.action(dict(op='map_command',name='weather.set',args=dict(temperature=20,conditions=['heavy_precipitation'],enabled=enabled)))
            session.streams['pilot_rolls']=[5,12]
            check=session.action(dict(op='command',name='stand',args=['check']))
            result=session.action(dict(op='command',name='stand',args=[]))
            self.assertEqual(accepted,result['accepted'])
            self.assertEqual(not accepted,session.units['u'].is_fallen)
            self.assertIn(str(5+int(enabled)),str(check))
            self.assertTrue(any(d['name']=='pilot_rolls' and d['value']==5 for d in session.draws))


class EnvironmentLifecycleTest(unittest.TestCase):
    def test_registration_resize_reset_and_text_failure_boundaries(self):
        from systems import map_management as maps
        from entities.map_objects import delete_objects
        engine,board=fixture(2,2)
        weather.command(board,'weather.set',dict(temperature=0,conditions=['precipitation']))
        weather.command(board,'layer.set',dict(x=1,y=1,layers=['mud'],data=999))
        engine.run_ticks(10);old=board.weather_event
        bits_for(board)
        with self.assertRaises(ValueError):maps.resize(board,'3 3')
        self.assertIs(old,board.weather_event)
        delete_objects(board,8);maps.resize(board,'3 3')
        self.assertEqual(70,board.weather_event.tick);self.assertEqual({(1,1):999},board.layer_data)
        maps.resize(board,'1 1');self.assertEqual({},board.layer_data)
        maps.resize(board,'0 0');self.assertIsNone(board.weather_event)
        maps.resize(board,'1 1');self.assertEqual(70,board.weather_event.tick)
        engine.unregister_entity(board);self.assertIsNone(board.weather_event)
        engine.run_ticks(10);engine.register_entity(board);self.assertEqual(80,board.weather_event.tick)
        maps.clear(board);self.assertEqual(80,board.weather_event.tick)
        self.assertEqual(-2,maps.load_text(board,'2 2\n.0.0\n','bad'))
        self.assertIsNone(board.weather_event);self.assertEqual({},board.layers)
        maps.load_text(board,'1 1\n.0\n','valid')
        self.assertFalse(board.weather_enabled);self.assertIsNone(board.weather_event)

    def test_invalid_controls_reject_without_state_draw_or_event_change(self):
        from copy import deepcopy
        engine,board=fixture()
        weather.command(board,'weather.set',dict(temperature=0,conditions=['precipitation']))
        expected=weather.command(board,'weather.show',dict(cells=[[0,0]]));event=board.weather_event
        requests=[('weather.set',{'enabled':1}),('weather.set',{'steam':0}),('weather.set',{'winddir':1.0}),
                  ('weather.set',{'snow_low':30}),('layer.set',dict(x=True,y=0,layers=['snow'],data=1)),
                  ('layer.set',dict(x=1,y=0,layers=['mud'],data=1)),('layer.set',dict(x=0,y=0,layers=['bad'],data=1)),
                  ('snow.grow',dict(low=False,high=2)),('snow.melt',dict(x=0,y=0,depth=1,steam=1))]
        for name,values in requests:
            with self.subTest(name=name,values=values):
                with use_source(lambda *args:self.fail('invalid operation consumed a draw')):
                    with self.assertRaises(ValueError):weather.command(board,name,values)
                self.assertEqual(expected,weather.command(board,'weather.show',dict(cells=[[0,0]])))
                self.assertIs(event,board.weather_event)

    def test_multi_map_snapshot_retains_roster_bits_cf_and_event_order(self):
        from systems.environment_storage import save_snapshot,load_snapshot
        from entities.map_objects import MapObject,add_object
        from entities.mech import Mech
        from systems.buildings import start_regen
        from physics.decorations import add_smoke
        engine,board=fixture(2,1);inside=GameMap(1,1,'inside');inside._id=20;inside.cf=90;inside.cfmax=100
        engine.register_entity(inside);start_regen(inside)
        unit=Mech.create_test_mech();unit._id=40;unit.x=unit.y=0;engine.register_entity(unit);board.add_mech(unit)
        board.mechflags=[3];board.slot_los=[[17]]
        add_object(board,4,MapObject(x=0,y=0,obj=20));bits_for(board).set(1,0,2)
        add_smoke(engine,board,0,0,120);weather.command(board,'weather.set',dict(temperature=0))
        engine.run_ticks(10);snapshot=save_snapshot(engine,[board,inside])
        saved=board.weather_event;self.assertEqual(60,saved.tick)
        load_snapshot(engine,snapshot)
        self.assertIs(unit.map,board);self.assertEqual([40],board.roster_ids);self.assertEqual([[17]],board.slot_los)
        self.assertEqual(8,bits_for(board).query(1,0,2));self.assertTrue(saved.zombie)
        self.assertEqual(1,len(board.map_objects[1]));self.assertEqual(120,board.map_objects[1][0].event.tick)
        engine.run_ticks(110);self.assertEqual(91,inside.cf);self.assertEqual(' ',board.terrain(0,0))

    def test_bit_load_publishes_mine_coverage_for_existing_gameplay_consumers(self):
        from entities.map_objects import MapObject,add_object
        from systems.environment_storage import save_snapshot,load_snapshot
        engine,board=fixture(4,1);add_object(board,3,MapObject(x=3,y=0,datac=1,datas=5))
        bits_for(board).set(3,0,1)
        copy=GameMap(4,1);load_objects(copy,save_objects(board))
        self.assertEqual({(3,0)},copy.mine_hexes)
        restored=load_snapshot(GameEngine(),save_snapshot(engine,[board]))[10]
        self.assertEqual({(3,0)},restored.mine_hexes)

    def test_invalid_first_bit_operation_does_not_create_storage(self):
        from tools.maps_environment import MapsSession
        session=MapsSession(dict(maps=[dict(name='outside',id=10,size=[1,1])],units=[],actions=[]))
        for x in (1,True,0.0):
            with self.assertRaises(ValueError):session.action(dict(op='map_diagnose',kind='bits',args=['set',x,0,1]))
            self.assertEqual([],session.map.map_objects[8])


class SightWeatherContractTest(unittest.TestCase):
    def test_sight_then_fire_separate_draws_same_bth_resources_and_real_cf(self):
        from tools.maps_environment import MapsSession
        session=MapsSession(dict(maps=[dict(name='outside',id=10,size=[9,9],
            hexes=[dict(at=[1,1],terrain='BUILDING',elevation=0)],
            map_objects=[dict(kind='BUILDING',x=1,y=1,obj=20)]),
            dict(name='inside',id=20,size=[1,1],cf=100,cfmax=100)],
            units=[dict(name='u',id=40,at=[1,3,0],facing=0,weapons=['IS.AC/5'],
                        ammo=[dict(weapon='IS.AC/5',rounds=20,section=2,critical=5)])],
            config=dict(periodic_updates=False,lock_tick=0),actions=[]))
        session.action(dict(op='map_command',name='weather.set',args=dict(temperature=20,windspeed=61)))
        session.action(dict(op='command',name='lock',args=[1,1,'B']))
        unit=session.units['u'];slot=unit.sections[unit.weapons[0].section].criticals[unit.weapons[0].critical]
        before=(unit.sections[2].criticals[5].data,unit.weap_heat,slot.data,session.maps['inside'].cf)
        draws=len(session.draws)
        session.action(dict(op='map_command',name='weather.show',args={}))
        self.assertEqual(draws,len(session.draws))
        session.streams['attack_rolls']=[12,12]
        sight=session.action(dict(op='command',name='sight',args=[0]))
        self.assertEqual(before,(unit.sections[2].criticals[5].data,unit.weap_heat,slot.data,session.maps['inside'].cf))
        fire=session.action(dict(op='command',name='fire',args=[0]))
        self.assertEqual(sight['attack']['bth_breakdown'],fire['attack']['bth_breakdown'])
        self.assertEqual(2,fire['attack']['bth_breakdown']['weather_mod'])
        self.assertEqual([12,12],[row['value'] for row in session.draws[draws:] if row['name']=='attack_rolls'])
        self.assertEqual(19,unit.sections[2].criticals[5].data)
        self.assertEqual(before[1]+1,unit.weap_heat);self.assertGreater(slot.data,0)
        self.assertEqual(95,session.maps['inside'].cf)


class FreshProcessContinuationTest(unittest.TestCase):
    def test_weather_and_steam_continue_with_relative_time_and_same_finite_draws(self):
        import json,subprocess,sys,os
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from systems.environment_storage import save_snapshot
        for steam in (False,True):
            with self.subTest(steam=steam),TemporaryDirectory() as directory:
                engine,board=fixture()
                if steam:weather.command(board,'layer.set',dict(x=0,y=0,layers=['snow'],data=500))
                weather.command(board,'weather.set',dict(temperature=1 if steam else 0,conditions=[] if steam else ['precipitation']))
                engine.run_ticks(65 if steam else 10)
                snapshot=save_snapshot(engine,[board])
                (Path(directory)/'snapshot.json').write_text(json.dumps(snapshot))
                after=5 if steam else 50
                actions=[dict(op='advance',seconds=100),dict(op='map_command',name='environment.load',args=dict(file='snapshot.json')),
                         dict(op='inspect'),dict(op='advance',seconds=after),dict(op='inspect')]
                document=dict(file_root=directory,maps=[dict(name='outside',id=10,size=[1,1])],units=[],
                              config=dict(periodic_updates=False),random={'streams':{} if steam else {'snow_growth':[10]}},actions=actions)
                result=subprocess.run([sys.executable,'-m','tools.maps_environment'],input=json.dumps(document),
                    capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=20)
                self.assertEqual(0,result.returncode,result.stderr);output=json.loads(result.stdout)
                before=output['results'][2]['maps']['outside'];actual=output['state']['maps']['outside']
                self.assertEqual(155 if steam else 150,before['weather']['deadline'])
                if steam:self.assertEqual(105,before['objects'][0]['deadline'])
                draws=[]
                with use_source(lambda n,l,h,f:draws.append((n,l,h)) or 10):engine.run_ticks(after)
                self.assertEqual(board.layer_data[0,0],actual['layers'][0]['data'])
                self.assertEqual(board.terrain(0,0),actual['hexes'][0]['terrain'])
                self.assertEqual([d[0] for d in draws],[d['name'] for d in output['draws']])
                if steam:self.assertEqual([],actual['objects'])
