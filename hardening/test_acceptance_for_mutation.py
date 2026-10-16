"""Run generated APS IR in-process so source mutation can trace real bindings.

Prepare with python3 -m tools.run_acceptance. This separate hardening bridge
reuses the actual acceptance runtime and assertions; it supplies no outcomes.
"""
import json
from pathlib import Path
import unittest

from acceptance.runtime import run_feature

ROOT = Path(__file__).resolve().parents[1]
FEATURES = {'movement-cargo': 13, 'movement-controls': 28, 'movement-hulldown': 12,
            'movement-ice': 26, 'movement-maneuvers': 17, 'movement-modes': 47,
            'movement-orbital': 25, 'movement-settling': 22, 'movement-surfaces': 17,
            'path_costs-coordinates': 19, 'path_costs-hover': 34,
            'path_costs-mech': 32, 'path_costs-tracked': 30}


class TestAcceptanceForMutation(unittest.TestCase):
    pass


def feature_test(name, expected_count):
    def verify(self):
        path = ROOT / 'tmp/acceptance' / (name + '.json')
        self.assertTrue(path.is_file(), 'Generate APS acceptance IR before hardening: ' + str(path))
        self.assertEqual(run_feature(json.loads(path.read_text())), expected_count)
    return verify


for name, count in FEATURES.items():
    setattr(TestAcceptanceForMutation, 'test_' + name.replace('-', '_'), feature_test(name, count))
