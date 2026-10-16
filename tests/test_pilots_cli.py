"""Public JSON character controls persist across ordinary CLI processes."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path

class PilotsCLITest(unittest.TestCase):
    def test_reload_keeps_actor_identity_and_reconciles_ordered_contents(self):
        with tempfile.TemporaryDirectory() as root:
            from tools.pilots import PilotsSession
            s=PilotsSession({'pilots':{'root':root+'/chars'},'construction':{'root':root+'/templates'},'file_root':root+'/maps',
                'config':{'periodic_updates':False},'units':[{'name':'u','id':10,'character':101}],
                'characters':[{'id':101,'name':'Alice','location':10}], 'actions':[]})
            actor=s.units['u'].pilot
            record=json.loads((Path(root)/'chars/101.json').read_text());record['location']=20
            (Path(root)/'chars/101.json').write_text(json.dumps(record))
            self.assertTrue(s.action({'op':'character','kind':'reload'}))
            self.assertIs(actor,s.units['u'].pilot)
            self.assertEqual([],s.personnel.contents(10));self.assertEqual([101],s.personnel.contents(20))

    def test_boarding_command_accepts_normal_argument_array(self):
        with tempfile.TemporaryDirectory() as root:
            from tools.pilots import PilotsSession
            s=PilotsSession({'pilots':{'root':root+'/chars'},'construction':{'root':root+'/templates'},'file_root':root+'/maps',
                'config':{'periodic_updates':False},'units':[
                    {'name':'u','id':10,'class':'MW','character':101,'in_character':True,'at':[3,3,0],'started':True},
                    {'name':'v','id':20,'contact_id':'VV','in_character':True,'at':[3,3,0]}],
                'characters':[{'id':101,'name':'Alice','location':10}], 'actions':[]})
            result=s.action({'op':'command','unit':'u','name':'embark','args':['VV']})
            self.assertTrue(result['ok'],result)
            self.assertEqual(20,s.characters.actor(101).location)

    def test_configured_public_award_persists_and_exposes_applied_request(self):
        with tempfile.TemporaryDirectory() as root:
            from tools.pilots import PilotsSession
            s=PilotsSession({'pilots':{'root':root+'/chars','xp':{'oldxpsystem':False}},
                'construction':{'root':root+'/templates'},'file_root':root+'/maps',
                'config':{'periodic_updates':False,'extended_piloting':False},'units':[{'name':'u','id':10,'character':101,'in_character':True}],
                'characters':[{'id':101,'name':'Alice','location':10}], 'actions':[]})
            result=s.action({'op':'experience','kind':'piloting','unit':'u','reason':3,'addanyway':True})
            self.assertTrue(result,result)
            from data.characters import SKILLS
            from data.character_values import code
            self.assertEqual(3,s.characters.retrieve(101,SKILLS).xp[code('Piloting-Battlemech')]%16777216)
            self.assertTrue(s.snapshot()['units']['u']['xp_requests'][-1]['applied'])

    def test_set_reload_skill_and_personal_initialization(self):
        with tempfile.TemporaryDirectory() as root:
            base={'pilots':{'root':root+'/characters'},'construction':{'root':root+'/templates'},'file_root':root+'/maps',
                  'config':{'periodic_updates':False},'units':[{'name':'u','class':'MW','id':10,'character':101}],
                  'characters':[{'id':101,'name':'Alice','wizard':True,'location':10,'values':{'Build':5,'Reflexes':4,'Running':3}}],
                  'random':{'streams':{'character_d6':[6,6]}},'actions':[{'op':'character','kind':'set','caller':101,'name':'Running','amount':4},
                  {'op':'character','kind':'skill','player':101,'name':'Running'},{'op':'personnel','kind':'initialize','unit':'u'}]}
            def run(doc):
                r=subprocess.run([sys.executable,'-m','tools.pilots'],input=json.dumps(doc),text=True,capture_output=True)
                self.assertEqual(0,r.returncode,r.stderr);return json.loads(r.stdout)
            result=run(base)
            self.assertEqual(5,result['results'][1]['target'])
            self.assertTrue(result['results'][1]['success'])
            self.assertEqual(2,len(result['draws']))
            self.assertEqual('Runni:4/',result['state']['characters']['101']['categories']['skills'])
            base['characters']=[];base['actions']=[{'op':'character','kind':'get','caller':101,'name':'Running'}]
            result=run(base)
            self.assertEqual(4,result['results'][0])

    def test_invalid_action_is_recoverable_and_permissions_are_real(self):
        with tempfile.TemporaryDirectory() as root:
            from tools.pilots import PilotsSession
            s=PilotsSession({'pilots':{'root':root+'/chars'},'construction':{'root':root+'/templates'},'file_root':root+'/maps',
                'units':[],'characters':[{'id':101,'name':'Alice'}],'actions':[]})
            self.assertIn('PERMISSION DENIED',s.action({'op':'character','kind':'get','caller':101,'name':'Build'})['error'])
            self.assertIn('attributes',s.action({'op':'character','kind':'status','caller':101}))
