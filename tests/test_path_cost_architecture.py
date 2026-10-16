"""Path pricing on read-only maps and adapter dispatch behavior."""
import contextlib
from dataclasses import dataclass
import io
import unittest
from unittest.mock import Mock, patch

from acceptance import steps
from physics import path_costs
from tools import path_cost, path_cost_inputs


@dataclass(frozen=True)
class ReadOnlyMap:
    """No GameMap inheritance, storage arrays, occupants, or write methods."""
    map_width: int = 2

    def valid(self, x, y):
        return 0 <= x < 2 and y == 0

    def base_elevation(self, x, y):
        return x

    def rterrain(self, x, y):
        return ' '


class TestPathCostArchitecture(unittest.TestCase):
    def test_prices_through_read_only_map_contract(self):
        view = ReadOnlyMap()
        for function in path_cost_inputs.COST_FUNCTIONS.values():
            self.assertEqual(function(view, 0, 0, 1, 0), 2)
            self.assertEqual(function(view, -1, 0, 1, 0), 0)


    def test_adapters_dispatch_each_mode_and_present_the_returned_cost(self):
        expected = {'mech': path_costs.mech_tile_cost,
                    'hover': path_costs.hover_tank_tile_cost,
                    'tracked': path_costs.tracked_tank_tile_cost}
        self.assertEqual(path_cost_inputs.COST_FUNCTIONS, expected)
        for mode in expected:
            with self.subTest(mode=mode):
                pricing = Mock(return_value=73)
                with patch.dict(path_cost_inputs.COST_FUNCTIONS, {mode: pricing}):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        status = path_cost.main([
                            '--mode', mode, '--size', '2', '1',
                            '--from', '0', '0', '--to', '1', '0',
                            '--source', 'GRASSLAND', '0',
                            '--destination', 'GRASSLAND', '0'])
                    self.assertEqual((status, output.getvalue()), (0, 'cost=73\n'))
                    pricing.assert_called_once()
                    self.assertEqual(pricing.call_args.args[1:], (0, 0, 1, 0))
                    view = ReadOnlyMap()
                    world = {'map': view, 'source': (0, 0), 'destination': (1, 0)}
                    pricing.reset_mock()
                    steps.request_cost(world, mode)
                    pricing.assert_called_once_with(view, 0, 0, 1, 0)
                    self.assertEqual(world['costs'], [73])
