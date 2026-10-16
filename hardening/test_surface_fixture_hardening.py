"""Surface fixture depth, below-ice position and actual random bounds."""
import unittest
from acceptance.movement import context, surfaces


def ready():
    w = {}
    context.fresh(w)
    return w


class TestSurfaceFixtures(unittest.TestCase):
    def test_other_occupant_cannot_be_below_the_stored_ice_floor(self):
        w=ready()
        surfaces.other_occupant(w,'2','MECH','BIPED','-2','False')
        self.assertEqual(-2,w['other'].z)
        with self.assertRaises(ValueError) as error:
            surfaces.other_occupant(ready(),'2','MECH','BIPED','-3','False')
        self.assertEqual('occupant height is below the stored floor',str(error.exception))

    def test_surface_draws_respect_the_real_ice_and_bridge_ranges(self):
        for terrain, elevation, draw, maximum in (('ICE', '2', '16', 15), ('BRIDGE', '3', '41', 40)):
            w = ready()
            surfaces.surface_target(w, terrain, elevation, 'False')
            with self.assertRaises(ValueError) as error:
                surfaces.blast(w, '5', draw)
            self.assertEqual(f'surface draw must be from 1 through {maximum}: {draw}', str(error.exception))
        w = ready()
        surfaces.surface_target(w, 'GRASSLAND', '0', 'False')
        with self.assertRaises(ValueError) as error:
            surfaces.blast(w, '5', '0')
        self.assertEqual('surface draw must be positive: 0', str(error.exception))

    def test_triggering_unit_is_actually_below_the_ice_and_above_the_floor(self):
        w = ready()
        surfaces.other_occupant(w, '1', 'MECH', 'BIPED', '0', 'False')
        u = w['unit']
        self.assertLess(u.z, 0)
        self.assertGreaterEqual(u.z, w['map'].base_elevation(u.x, u.y))

    def test_ice_unit_fixture_uses_its_declared_depth_when_it_drops(self):
        w = ready()
        surfaces.ice_unit(w, 'MECH', 'BIPED', '2')
        self.assertEqual(2, w['map'].elevation(w['unit'].x, w['unit'].y))
        surfaces.chance(w, '1')
        self.assertEqual(-2, w['unit'].z)

    def test_invalid_drop_die_retains_its_diagnostic(self):
        w = ready()
        surfaces.ice_unit(w, 'MECH', 'BIPED', '2')
        with self.assertRaises(ValueError) as error:
            surfaces.chance(w, '7')
        self.assertEqual('ice drop die must be from 1 through 6: 7', str(error.exception))
