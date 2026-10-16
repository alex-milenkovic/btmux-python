"""C terrain macro boundaries not observable through ordinary path costs."""
import unittest
from entities.map import ICE, WATER, GRASSLAND
from entities.mech import Mech, MoveType, UnitType
from physics import collision


class TestTerrainHardening(unittest.TestCase):
    def test_upper_elevation_uses_ice_surface_and_other_signed_elevations(self):
        unit = Mech.create_test_mech()
        for kind, elevation, expected in ((ICE, 3, 0), (WATER, 3, -3), (GRASSLAND, 3, 3)):
            with self.subTest(terrain=kind):
                unit.terrain, unit.elev = kind, elevation
                self.assertEqual(expected, collision.mech_upper_elevation(unit))

    def test_overwater_class_and_movement_are_independent_alternatives(self):
        unit = Mech.create_test_mech()
        for kind, move, expected in ((UnitType.MECH, MoveType.HOVER, True),
                                     (UnitType.MECH, MoveType.FOIL, True),
                                     (UnitType.MECH, MoveType.HULL, True),
                                     (UnitType.MW, MoveType.BIPED, True),
                                     (UnitType.MECH, MoveType.SUB, False),
                                     (UnitType.MECH, MoveType.BIPED, False)):
            with self.subTest(kind=kind, move=move):
                unit.unit_type, unit.move_type = kind, move
                self.assertEqual(expected, collision.overwater(unit))

    def test_bridge_water_elevation_is_the_fixed_c_sentinel(self):
        self.assertEqual(-1, collision.bridge_w_elevation(Mech.create_test_mech()))
