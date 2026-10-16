import unittest
from tempfile import TemporaryDirectory
from tools.maps_environment import MapsSession


class MapsCLITest(unittest.TestCase):
    def test_incomplete_environment_commands_preserve_live_timer_and_continue(self):
        session=MapsSession({'map':{'size':[1,1]},'units':[],
                             'config':{'periodic_updates':False},'actions':[]})
        session.action({'op':'map_command','name':'weather.set',
                        'args':{'temperature':0,'conditions':['precipitation']}})
        event=session.map.weather_event
        for name,values in (('layer.set',{'x':0,'y':0,'layers':['snow']}),
                            ('snow.grow',{'low':10}),('snow.melt',{'x':0,'y':0})):
            with self.subTest(name=name):
                response=session.action({'op':'map_attempt','action':{
                    'op':'map_command','name':name,'args':values}})
                self.assertEqual('invalid environment fields',response['error'])
                self.assertIs(event,session.map.weather_event)
                self.assertFalse(event.zombie)
                self.assertEqual({},session.map.layers)
        session.action({'op':'map_command','name':'layer.set',
                        'args':{'x':0,'y':0,'layers':['snow'],'data':1001}})
        self.assertEqual({'deep_snow'},session.map.layers[0,0])

    def test_heat_fixture_smoke_uses_shared_object_and_expires(self):
        from tools.heat_updates import Session
        session=Session({'map':{'default':['SMOKE',0],
            'underlying':[{'at':[2,2],'terrain':'GRASSLAND','remaining':2}]},
            'config':{'periodic_updates':False},'actions':[{'op':'advance','seconds':2}]})
        self.assertEqual(1,len(session.board.map_objects[1]))
        session.run()
        self.assertEqual(' ',session.board.terrain(2,2))
        self.assertEqual([],session.board.map_objects[1])

    def test_diagnostics_use_registered_map_objects(self):
        session=MapsSession({'units':[{'name':'u','id':40}],'actions':[]})
        state=session.action({'op':'map_diagnose','kind':'weather_mapping'})
        self.assertTrue(state['applied'])
        session.units['u'].mapindex=-1
        session.action({'op':'map_diagnose','kind':'debug_fix','args':[{}]})
        self.assertEqual([-1],session.map.roster_ids)
        self.assertIsNone(session.map.mechs_on_map[0])
        self.assertIn("Error: #40 isn't really here! Removing..",session.map.map_messages)
        self.assertEqual('Done.',session.map.map_messages[-1])

    def test_admin_conditions_fire_ticks_and_file_bytes_share_live_state(self):
        with TemporaryDirectory() as directory:
            session=MapsSession({'file_root':directory,'maps':[{'name':'outside','id':10,'size':[9,9]}],
                'units':[{'name':'u','id':40,'at':[1,1,0]}],'config':{'periodic_updates':False},
                'random':{'streams':{}},'actions':[]})
            session.action({'op':'map_command','name':'addhex','args':'1 1 ~ 3'})
            session.action({'op':'map_command','name':'conditions','args':'120 -40 1 1'})
            session.action({'op':'map_command','name':'addsmoke','args':'1 1 2'})
            session.action({'op':'map_command','name':'save','args':'sample'})
            before=session.snapshot()
            self.assertEqual('~',before['maps']['outside']['hexes'][10]['underlying'])
            self.assertEqual([40],before['maps']['outside']['roster_ids'])
            self.assertTrue(before['files']['sample']['text'].endswith('22: 120 -40\n'))
            session.action({'op':'advance','seconds':2})
            self.assertEqual('~',session.map.terrain(1,1))
            self.assertEqual([],session.snapshot()['maps']['outside']['objects'])

    def test_building_cf_ordinary_command_and_object_dynamic_roundtrip(self):
        with TemporaryDirectory() as directory:
            session=MapsSession({'file_root':directory,'maps':[{'name':'outside','id':10,'size':[9,9],
                'map_objects':[{'kind':'BUILDING','x':1,'y':1,'obj':20}]},
                {'name':'inside','id':20,'size':[9,9],'cf':100,'cfmax':100}],
                'units':[{'name':'u','id':40}],'config':{'periodic_updates':False},'actions':[]})
            session.action({'op':'map_diagnose','kind':'hit_building','unit':'u','args':[1,1,-1,10]})
            self.assertEqual(90,session.maps['inside'].cf)
            session.action({'op':'map_file','kind':'save_objects','file':'objects'})
            session.action({'op':'map_command','name':'delobj','args':'BUILDING'})
            session.action({'op':'map_file','kind':'load_objects','file':'objects'})
            self.assertEqual(20,session.map.map_objects[4][0].obj)
            session.action({'op':'map_file','kind':'save_dynamic','file':'dynamic'})
            session.action({'op':'map_file','kind':'load_dynamic','file':'dynamic','count':1})
            self.assertEqual([40],session.map.roster_ids)

    def test_failed_direct_load_remains_inspectable_and_grid_access_is_rejected(self):
        with TemporaryDirectory() as directory:
            session=MapsSession({'file_root':directory,'map':{'size':[9,9]},'units':[],
                'files':{'short':{'text':'2 2\n.0~1\n'}},'actions':[]})
            self.assertEqual(-2,session.action({'op':'map_file','kind':'load_direct','file':'short'}))
            state=session.snapshot()['maps']['main']
            self.assertEqual([9,9],state['size'])
            self.assertTrue(state['partial_grid'])
            self.assertEqual(2,len(state['hexes']))
            with self.assertRaisesRegex(ValueError,'failed load'): session.map.terrain(0,0)

    def test_permanent_overlay_and_free_are_inspectable(self):
        with TemporaryDirectory() as directory:
            session=MapsSession({'file_root':directory,'units':[],'actions':[]})
            session.action({'op':'map_command','name':'addsmoke','args':'1 1 0'})
            self.assertIsNone(session.snapshot()['maps']['main']['objects'][0]['deadline'])
            session.action({'op':'map_command','name':'free'})
            self.assertFalse(session.snapshot()['maps']['main']['grid_allocated'])
