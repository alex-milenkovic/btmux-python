import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.acceptance_entrypoint_generator import generate
from tools.acceptance_runner import evaluate
from tests.test_acceptance_pipeline import feature


class TestAcceptanceGenerator(unittest.TestCase):
    def test_deterministic_entrypoint_metadata_and_supplied_ir(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ir = feature([{'depth': '1', 'expected': '1'}])
            ir['feature_path'] = 'features/Path Costs.feature'
            source = root / 'input.json'
            source.write_text(json.dumps(ir))
            entrypoint = generate(source, root / 'generated')
            original = entrypoint.read_bytes()
            generate(source, root / 'generated')
            self.assertEqual(entrypoint.read_bytes(), original)
            metadata = json.loads((root / 'generated/metadata/features-path-costs-feature.json').read_text())
            self.assertEqual(metadata['implementation_hash'], 'sha256:' + hashlib.sha256(original).hexdigest())
            job = dict(id='fixture', feature_json=str(source), generated_dir=str(root / 'generated'), timeout='5s')
            self.assertEqual(evaluate(job)['outcome'], 'test_success')
            ir['scenarios'][0]['examples'][0]['expected'] = '2'
            source.write_text(json.dumps(ir))
            self.assertEqual(evaluate(job)['outcome'], 'test_failure')
            job['feature_json'] = str(root / 'missing.json')
            self.assertEqual(evaluate(job)['outcome'], 'infrastructure_error')
