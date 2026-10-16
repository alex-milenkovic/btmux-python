"""Unit-level command contract checks; no independent QA suite execution."""
import contextlib
import io
import unittest

from tools.path_cost import main


class TestPathCostCommand(unittest.TestCase):
    def invoke(self, **changes):
        options = dict(mode=['hover'], size=['4', '4'],
                       source=['GRASSLAND', '0'], destination=['WATER', '1'],
                       **{'from': ['0', '0'], 'to': ['1', '0']})
        options.update(changes)
        args = [part for key, values in options.items() if values is not None
                for part in ['--' + key, *values]]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                status = main(args)
            except SystemExit as error:
                status = error.code
        return status, out.getvalue(), err.getvalue()

    def test_water_costs_for_each_mode(self):
        for mode, expected in [('hover', 1), ('mech', 0), ('tracked', 0)]:
            self.assertEqual(self.invoke(mode=[mode]), (0, f'cost={expected}\n', ''))

    def test_out_of_map_endpoints_are_safe(self):
        for endpoint in ('from', 'to'):
            self.assertEqual(self.invoke(**{endpoint: ['-1', '0']}), (0, 'cost=0\n', ''))
            self.assertEqual(self.invoke(**{endpoint: ['4', '0']}), (0, 'cost=0\n', ''))

    def test_same_hex_requires_matching_values(self):
        self.assertEqual(self.invoke(to=['0', '0'], destination=['GRASSLAND', '0']),
                         (0, 'cost=1\n', ''))
        status, out, err = self.invoke(to=['0', '0'])
        self.assertNotEqual(status, 0)
        self.assertEqual(out, '')
        self.assertIn('same', err)

    def test_invalid_inputs_fail_without_result(self):
        for change in (dict(mode=['flying']), dict(size=['0', '4']),
                       dict(size=['4', '-1']), dict(size=['x', '4']),
                       dict(source=['BOGUS', '0']), dict(destination=['WATER', '10']),
                       dict(source=['ICE', '-1']), dict(source=['ICE', '1.5']),
                       dict(mode=None)):
            with self.subTest(change=change):
                status, out, err = self.invoke(**change)
                self.assertNotEqual(status, 0)
                self.assertEqual(out, '')
                self.assertTrue(err)

    def test_help_explains_fidelity_limits(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as result:
            main(['--help'])
        self.assertEqual(result.exception.code, 0)
        for phrase in ('signed', 'destination row', 'decorat', 'width', 'height'):
            self.assertIn(phrase, ' '.join(out.getvalue().lower().split()))
