"""Terrain and movement queries work on read-only unit state."""
from dataclasses import dataclass
import unittest

from entities.map import ICE, WATER
from entities.mech import MoveType, UnitType
from physics import collision
from systems import movement_commands


@dataclass(frozen=True)
class TerrainView:
    """No engine, concrete map, mutation methods or Mech inheritance."""
    terrain: str = ICE
    elev: int = 3
    z: int = -1
    move_type: MoveType = MoveType.BIPED
    unit_type: UnitType = UnitType.MECH


class MovementArchitectureTests(unittest.TestCase):
    def test_domain_queries_need_only_read_only_unit_state(self):
        unit = TerrainView()
        self.assertEqual(-3, collision.mech_elevation(unit))
        self.assertEqual(0, collision.mech_upper_elevation(unit))
        self.assertTrue(movement_commands.in_water(unit))
        self.assertFalse(collision.overwater(unit))
        self.assertFalse(movement_commands.water_beast(unit))
        self.assertEqual(-3, collision.mech_upper_elevation(TerrainView(terrain=WATER)))
