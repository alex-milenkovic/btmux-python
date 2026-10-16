import json
import subprocess
import sys
import tempfile
import unittest


class ConstructionCLITest(unittest.TestCase):
    def test_diagnostic_errors_leave_session_usable_and_artillery_dump_uses_gun_range(self):
        from tools.construction_templates import ConstructionSession
        with tempfile.TemporaryDirectory() as root:
            session=ConstructionSession({'construction':{'root':root},'config':{'periodic_updates':False},'actions':[]})
            for action in ({'op':'construction_diagnose','kind':'engine_weight','args':[7]},
                {'op':'construction_diagnose','kind':'ammo_mod','args':[8,0]}):
                self.assertFalse(session.action(action)['ok'])
            session.action({'op':'editor','name':'settarget','args':'u'})
            session.action({'op':'editor','name':'reload','args':'IS.AC/5 LT 1 +'})
            self.assertEqual(1,session.action({'op':'construction_diagnose','kind':'ammo_mod','args':[2,0]}))
            rows=session.action({'op':'catalog','kind':'weapons'})['rows']
            self.assertEqual(280,next(row['gun_range'] for row in rows if row['name']=='IS.Thumper'))

    def test_fresh_process_ordinary_edits_save_load_and_inspectable_errors(self):
        with tempfile.TemporaryDirectory() as root:
            document={'construction':{'root':root},'config':{'periodic_updates':False},
              'editors':[{'name':'e','id':50}], 'units':[{'name':'u','at':[3,3,0]},{'name':'v','at':[4,3,0]}],
              'actions':[{'op':'editor','editor':'e','name':'settarget','args':'u'},
                {'op':'editor','editor':'e','name':'resetcrits'},
                {'op':'editor','editor':'e','name':'addweap','args':'IS.MediumLaser LT 1'},
                {'op':'editor','editor':'e','name':'savetemp2','args':'CUSTOM','clock':'fixed'},
                {'op':'template','kind':'load','unit':'v','reference':'CUSTOM'},
                {'op':'template','kind':'load','unit':'missing','reference':'CUSTOM'},
                {'op':'construction_readout','unit':'v'}]}
            run=subprocess.run([sys.executable,'-m','tools.construction_templates'],input=json.dumps(document),capture_output=True,text=True)
            self.assertEqual(0,run.returncode,run.stderr)
            result=json.loads(run.stdout)
            self.assertTrue(result['results'][1]['ok'])
            self.assertTrue(result['results'][3]['ok']);self.assertTrue(result['results'][4]['ok'])
            self.assertFalse(result['results'][5]['ok'])
            self.assertEqual(1,len(result['state']['units']['v']['weapons']))
            self.assertEqual(79,result['results'][6]['slots'][2][0]['source_part_id'])
            self.assertIn('Saved by: local(#0) at fixed',result['state']['construction']['files']['CUSTOM'])
            self.assertEqual('u',result['state']['construction']['editors']['e']['target'])
