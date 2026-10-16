"""Naval/VTOL tail checks through production height and landing rules."""
from tests.movement_fixture import MovementTestCase
from entities.mech import UnitType,MoveType,MechStatus as S
from entities.map import WATER,MOUNTAINS,GRASSLAND
from physics import heights


class HeightUpdates(MovementTestCase):
    def test_dropship_notices_are_per_unit_and_allow_clock_rollback(self):
        self.assertFalse(heights.dropship_notice(self.unit,9))
        self.assertTrue(heights.dropship_notice(self.unit,10))
        self.assertFalse(heights.dropship_notice(self.unit,19))
        self.assertTrue(heights.dropship_notice(self.unit,20))
        self.assertTrue(heights.dropship_notice(self.unit,3))
        self.assertEqual(self.unit.last_dropship_notice,3)

    def test_fire_tail_kills_mechwarrior_but_exempts_flight(self):
        from entities.map import FIRE
        self.unit.unit_type=UnitType.MW
        self.unit.terrain=FIRE
        self.unit.move_type=MoveType.VTOL
        heights.fiery_death(self.unit)
        self.assertFalse(self.unit.is_destroyed)
        self.unit.move_type=MoveType.BIPED
        heights.fiery_death(self.unit)
        self.assertTrue(self.unit.is_destroyed)

    def test_submarine_bottom_retains_fixed_point_offset(self):
        u=self.unit
        u.unit_type,u.move_type=UnitType.VEH_NAVAL,MoveType.SUB
        u.terrain,u.elev,u.z,u.fz,u.vertical_speed=WATER,3,-3,-193.5,-10.75
        heights.check_naval_height(u,-2)
        self.assertEqual((u.z,u.vertical_speed),(-2,0))
        self.assertEqual(u.fz, __import__('core.randomness', fromlist=['float32']).float32(-180.6))

    def test_vtol_surface_is_not_in_water_and_orbit_clamps(self):
        u=self.unit
        u.unit_type,u.move_type=UnitType.VTOL,MoveType.VTOL
        u.terrain,u.elev,u.z,u.fz,u.vertical_speed=WATER,2,0,0,-10.75
        heights.check_vtol_height(u)
        self.assertFalse(u.is_destroyed)
        self.assertEqual(u.vertical_speed,-10.75)
        u.z=300
        heights.check_vtol_height(u)
        self.assertEqual((u.z,u.fz,u.vertical_speed),(299,299*64.5,0))

    def test_rejected_landing_uses_real_fall(self):
        u=self.unit
        u.unit_type,u.move_type=UnitType.VTOL,MoveType.VTOL
        u.fuel=100
        u.terrain,u.elev,u.z,u.vertical_speed=MOUNTAINS,3,2,-21.5
        u.desired_speed=21.5
        u.set_status(S.COMBAT_SAFE)
        heights.check_vtol_height(u)
        self.assertEqual(u.last_fall_levels,3)
        self.assertTrue(u.has_status(S.LANDED))
        self.assertEqual(u.z,3)
