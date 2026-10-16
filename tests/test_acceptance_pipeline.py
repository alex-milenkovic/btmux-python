"""Runtime contract tests, kept separate from generated feature executions."""
import copy
import unittest

from acceptance.runtime import run_feature


def feature(examples):
    return {'name': 'fixture', 'background': [
        {'keyword': 'Given', 'text': 'a fresh 4 by 4 path-cost map with source at 0 0 and destination at 1 0'}],
        'scenarios': [{'name': 'water', 'examples': examples, 'steps': [
            {'keyword': 'Given', 'text': 'source terrain GRASSLAND with stored elevation 0'},
            {'keyword': 'And', 'text': 'destination terrain WATER with stored elevation <depth>'},
            {'keyword': 'When', 'text': 'the hover path cost is requested'},
            {'keyword': 'Then', 'text': 'the path cost is <expected>'}]}]}


class TestAcceptanceRuntime(unittest.TestCase):
    def test_examples_drive_independent_executions(self):
        self.assertEqual(run_feature(feature([
            {'depth': '1', 'expected': '1'}, {'depth': '2', 'expected': '0'}])), 2)

    def test_changed_expected_value_fails(self):
        with self.assertRaises(AssertionError):
            run_feature(feature([{'depth': '1', 'expected': '2'}]))

    def test_missing_and_invalid_values_fail(self):
        for row in ({'expected': '1'}, {'depth': 'oops', 'expected': '1'},
                    {'depth': '10', 'expected': '1'}, {'depth': 1, 'expected': '1'}):
            with self.subTest(row=row), self.assertRaises(AssertionError):
                run_feature(feature([row]))

    def test_unsupported_step_fails(self):
        ir = feature([{'depth': '1', 'expected': '1'}])
        ir['scenarios'][0]['steps'][0]['text'] = 'silently ignore this'
        with self.assertRaisesRegex(AssertionError, 'unsupported'):
            run_feature(ir)

    def test_scenario_without_examples_runs_once(self):
        ir = feature([])
        ir['scenarios'][0]['steps'][1]['text'] = 'destination terrain WATER with stored elevation 1'
        ir['scenarios'][0]['steps'][3]['text'] = 'the path cost is 1'
        original = copy.deepcopy(ir)
        self.assertEqual(run_feature(ir), 1)
        self.assertEqual(ir, original)

    def test_background_terrain_applies_to_all_three_modes(self):
        ir = {
            'name': 'background terrain',
            'background': [
                {'text': 'all map hexes are ROUGH with stored elevation 1'},
                {'text': 'map dimensions 4 by 4'},
            ],
            'scenarios': [{
                'name': 'shared terrain charge', 'examples': [],
                'steps': [
                    {'text': 'source coordinates 0 0 and destination coordinates 1 0'},
                    {'text': 'all three path costs are requested'},
                    {'text': 'each path cost is 2'},
                ],
            }],
        }
        self.assertEqual(run_feature(ir), 1)

    def test_feature_without_scenarios_fails(self):
        with self.assertRaisesRegex(AssertionError, 'no scenario executions'):
            run_feature({'scenarios': []})
