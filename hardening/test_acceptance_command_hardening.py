"""Acceptance command discovers both groups and keeps same-stem IRs separate."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import run_acceptance
from tests.test_acceptance_pipeline import feature


class TestAcceptanceCommandHardening(unittest.TestCase):
    def test_both_groups_are_parsed_then_executed_without_same_stem_collision(self):
        original=Path.cwd()
        with tempfile.TemporaryDirectory(dir=original/'tmp') as directory:
            root=Path(directory).resolve();calls=[]
            (root/'tmp/acceptance').mkdir(parents=True)
            for group in ('movement','path_costs'):
                folder=root/'features'/group;folder.mkdir(parents=True)
                (folder/'shared.feature').write_text('Feature: '+group+'\n')
            def run(command,*,check,env):
                self.assertTrue(check)
                self.assertEqual(str(root/'tmp'),env['TMPDIR'])
                self.assertEqual(str(root),env['PYTHONPATH'])
                self.assertEqual('1',env['PYTHONDONTWRITEBYTECODE'])
                self.assertEqual('preserved',env['MOVEMENT_ACCEPTANCE_SENTINEL'])
                calls.append(command)
                if command[0]=='gherkin-parser':
                    self.assertEqual(3,len(command))
                    self.assertIn(command[1], ('features/movement/shared.feature', 'features/path_costs/shared.feature'))
                    self.assertTrue(command[2].startswith('./tmp/'))
                    self.assertTrue(command[2].endswith('.json'))
                    ir=feature([{'depth':'1','expected':'1'}])
                    Path(command[2]).write_text(json.dumps(ir))
                else:
                    self.assertEqual(run_acceptance.sys.executable,command[0])
                    self.assertEqual(2,len(command))
                    self.assertTrue(Path(command[1]).is_file())
                    self.assertEqual((root/'tmp/acceptance/generated').resolve(),Path(command[1]).resolve().parent)
            try:
                with patch.dict(os.environ, {'MOVEMENT_ACCEPTANCE_SENTINEL':'preserved'}),patch.object(run_acceptance,'__file__',str(root/'tools/run_acceptance.py')),patch.object(run_acceptance.subprocess,'run',side_effect=run):
                    os.environ.pop('PYTHONDONTWRITEBYTECODE', None)
                    run_acceptance.main()
                self.assertEqual(4,len(calls))
                self.assertEqual(['gherkin-parser','gherkin-parser'],[c[0] for c in calls[:2]])
                self.assertNotEqual(calls[2][1],calls[3][1])
                for group in ('movement','path_costs'):
                    data=json.loads((root/'tmp/acceptance'/f'{group}-shared.json').read_text())
                    self.assertEqual(f'features/{group}/shared.feature',data['feature_path'])
            finally:
                os.chdir(original)

    def test_empty_discovery_fails_instead_of_claiming_an_acceptance_pass(self):
        original=Path.cwd()
        with tempfile.TemporaryDirectory(dir=original/'tmp') as directory:
            root=Path(directory).resolve()
            try:
                with patch.object(run_acceptance,'__file__',str(root/'tools/run_acceptance.py')),self.assertRaises(RuntimeError) as error:
                    run_acceptance.main()
                self.assertEqual('no acceptance features found',str(error.exception))
            finally:
                os.chdir(original)
