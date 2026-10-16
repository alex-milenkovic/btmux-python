"""Public commands and fresh-process persistence, using real finite skill rolls."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path


class RepairEconomyCLITests(unittest.TestCase):
    def document(self,root):
        return {'pilots':{'root':root+'/chars'},'construction':{'root':root+'/templates'},'file_root':root+'/maps',
            'repair_economy':{'root':root+'/economy','objects':[{'id':1000,'ECONPARTS':'[547,0,3]'}]},
            'map':{'id':1000},'config':{'periodic_updates':False},
            'units':[{'name':'u','id':10,'character':101,'started':False,'repair':{'stall':True},
                'sections':[{'index':4,'internal':10,'internal_orig':10,'armor':7,'armor_orig':10}]}],
            'characters':[{'id':101,'name':'Tech','tech':True,'location':10,'values':{'Build':5,'Reflexes':5,'Intuition':5,'Learn':5,'Technician-Battlemech':6}}],
            'random':{'streams':{'tech_rolls':[12]}},'actions':[]}
    def run_cli(self,document):
        result=subprocess.run([sys.executable,'-m','tools.repair_economy'],input=json.dumps(document),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
    def test_command_debit_queue_and_due_state_are_public(self):
        with tempfile.TemporaryDirectory() as root:
            doc=self.document(root);doc['actions']=[{'op':'command','unit':'u','name':'fixarmor','args':'CT'},
                {'op':'advance','seconds':180}]
            result=self.run_cli(doc)
            self.assertTrue(result['results'][0]['ok'],result['results'])
            self.assertEqual(result['state']['economy']['objects']['1000']['ECONPARTS'],'')
            self.assertEqual(result['state']['repair_jobs'][0]['type'],47)
            self.assertEqual(result['state']['repair_jobs'][0]['actor'],101)
            self.assertEqual(len(result['draws']),1)
    def test_saved_queue_and_absolute_time_reload_in_new_process(self):
        with tempfile.TemporaryDirectory() as root:
            doc=self.document(root);doc['actions']=[{'op':'command','name':'fixarmor','args':'CT'},
                {'op':'repair','kind':'save','file':'jobs.jsonl'}]
            first=self.run_cli(doc);self.assertTrue(first['results'][0]['ok'],first['results'])
            doc['repair_economy']['objects']=[];doc['characters']=[]
            doc['actions']=[{'op':'repair','kind':'load','file':'jobs.jsonl'}]
            second=self.run_cli(doc)
            self.assertEqual(second['results'][0]['loaded'],1)
            self.assertEqual(second['state']['economy']['objects']['101']['TECHTIME'],first['state']['economy']['objects']['101']['TECHTIME'])
            self.assertEqual(second['draws'],[])
    def test_actor_relocation_updates_contents_and_refusals_reach_inbox(self):
        with tempfile.TemporaryDirectory() as root:
            from tools.repair_economy import RepairEconomySession
            doc=self.document(root);session=RepairEconomySession(doc)
            self.assertIn(101,session.personnel.contents(10))
            session.action({'op':'repair','kind':'actor','actor':101,'values':{'location':1000,'tech':False}})
            self.assertNotIn(101,session.personnel.contents(10))
            self.assertIn(101,session.personnel.contents(1000))
            result=session.action({'op':'command','name':'fixarmor','args':'CT'})
            self.assertFalse(result['ok']);self.assertIn('clearance',session.characters.actor(101).inbox[-1])

    def test_public_material_and_suit_fixtures_use_live_state(self):
        from entities.crittypes import i2special,Special
        with tempfile.TemporaryDirectory() as root:
            from tools.repair_economy import RepairEconomySession
            doc=self.document(root);doc['units'][0]['repair']['max_suits']=4
            session=RepairEconomySession(doc)
            self.assertEqual(session.units['u'].max_suits,4)
            self.assertEqual(session.action({'op':'repair_diagnose','kind':'proper_armor'}),547)
            self.assertEqual(session.action({'op':'repair_diagnose','kind':'alias_part','part':i2special(Special.SHOULDER_OR_HIP)}),548)

    def test_empty_attributes_are_valid_and_clear_shared_stock(self):
        with tempfile.TemporaryDirectory() as root:
            from tools.repair_economy import RepairEconomySession
            session=RepairEconomySession(self.document(root))
            result=session.action({'op':'repair','kind':'configure_object','values':{'id':1000,'ECONPARTS':''}})
            self.assertTrue(result['ok'],result);self.assertEqual(session.inventory.raw(1000),'')
            self.assertEqual(session.action({'op':'repair_diagnose','kind':'parsepart','argument':''}),[-1,0,0,0])

    def test_unknown_fixture_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            from tools.repair_economy import RepairEconomySession
            doc=self.document(root);doc['units'][0]['repair']['expected']='success'
            with self.assertRaises(ValueError):RepairEconomySession(doc)

if __name__=='__main__':unittest.main()
