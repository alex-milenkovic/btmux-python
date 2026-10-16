"""Strict UI input and a real delayed command exercised in a subprocess."""
import json,os,subprocess,sys,unittest

class TestSensorCLI(unittest.TestCase):
    def run_document(self,document):
        return subprocess.run([sys.executable,'-m','tools.sensors_los'],input=json.dumps(document),text=True,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=os.path.abspath('tmp')))
    def test_sensor_command_runs_on_event_clock(self):
        result=self.run_document({'actions':[{'op':'command','unit':'u','name':'sensor','args':['I','E']},{'op':'advance','seconds':10}]})
        self.assertEqual(result.returncode,0,result.stderr)
        state=json.loads(result.stdout)['state']
        self.assertEqual(state['units']['u']['sensors'],'IE')
        self.assertEqual(state['time'],10)
    def test_unknown_field_rejected(self):
        result=self.run_document({'units':[{'name':'u','fake_seen':True}],'actions':[]})
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,'')
    def test_real_weight_initializes_existing_cache(self):
        result=self.run_document({'units':[{'name':'u','tonnage':80,'real_mass':20.5}],'actions':[]})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['state']['units']['u']['real_mass'],20.5)
    def test_contacts_have_distinct_persistent_ids(self):
        result=self.run_document({'units':[{'name':str(i)} for i in range(12)],'actions':[]})
        self.assertEqual(result.returncode,0,result.stderr)
        ids=[u['id'] for u in json.loads(result.stdout)['state']['units'].values()]
        self.assertEqual(len(set(ids)),12)
    def test_global_actions_do_not_require_a_unit_named_u(self):
        result=self.run_document({'units':[{'name':'scout'}],'actions':[{'op':'advance','seconds':2},{'op':'inspect'}]})
        self.assertEqual(result.returncode,0,result.stderr)
    def test_action_fields_are_specific_to_operation(self):
        result=self.run_document({'actions':[{'op':'advance','seconds':1,'equipment':'TAG'}]})
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(result.stdout,'')
    def test_light_overlay_expires_on_real_event_clock(self):
        doc={'config':{'periodic_updates':False},'map':{'hexes':[{'at':[2,3],'terrain':'HEAVY_FOREST','elevation':0,'overlay':'FIRE','duration':2}]},
             'actions':[{'op':'map','unit':'u','origin':[2,3],'size':[1,1]},{'op':'advance','seconds':61},{'op':'map','unit':'u','origin':[2,3],'size':[1,1]}]}
        result=self.run_document(doc)
        self.assertEqual(result.returncode,0,result.stderr)
        outputs=json.loads(result.stdout)['results']
        self.assertTrue(outputs[0]['flags'][0]&8)
        self.assertFalse(outputs[2]['flags'][0]&8)
    def test_sight_reports_semiguided_mode_from_real_weapon_slot(self):
        doc={'config':{'periodic_updates':False},'units':[
            {'name':'u','at':[2,1,0],'facing':180,'team':1,'weapons':[{'name':'IS.LRM-10','ammo_mode':0x02000000}]},
            {'name':'t','contact_id':'TT','at':[2,2,0],'speed':75.25,'team':2,'tagged_by':999999}],
             'diagnostic_cache':[{'viewer':'u','target':'t','flags':15}],
             'actions':[{'op':'command','unit':'u','name':'target','args':['TT']},{'op':'command','unit':'u','name':'sight','args':[0]}]}
        from entities.mech import AmmoMode
        doc['units'][0]['weapons'][0]['ammo_mode']=int(AmmoMode.SGUIDED_MODE)
        result=self.run_document(doc)
        self.assertEqual(result.returncode,0,result.stderr)
        attack=json.loads(result.stdout)['results'][1]['attack']
        self.assertEqual(attack['bth_breakdown']['target_move'],0)
    def test_sight_preserves_loaded_ammunition(self):
        doc={'config':{'periodic_updates':False},'units':[
            {'name':'u','at':[2,1,0],'facing':180,'weapons':['IS.LRM-10'],
             'ammo':[{'weapon':'IS.LRM-10','rounds':8}]},
            {'name':'t','contact_id':'TT','at':[2,2,0],'team':2}],
             'diagnostic_cache':[{'viewer':'u','target':'t','flags':15}],
             'actions':[{'op':'command','unit':'u','name':'target','args':['TT']},{'op':'command','unit':'u','name':'sight','args':[0]}]}
        result=self.run_document(doc)
        self.assertEqual(result.returncode,0,result.stderr)
        state=json.loads(result.stdout)['state']['units']['u']
        self.assertEqual(state['ammo'][0]['rounds'],8)
        self.assertEqual(state['weapons'][0]['recycle'],0)
