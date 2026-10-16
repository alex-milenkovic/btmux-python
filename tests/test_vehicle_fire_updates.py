"""Scheduled vehicle burns, extinguishing and water smoke lifecycle."""
from tests.movement_fixture import MovementTestCase
from entities.mech import UnitType,MoveType,MechStatus as S,CritStatus as C
from entities.map import WATER,SMOKE
from core.randomness import use_source
from systems import vehicle_fire


class VehicleFireUpdates(MovementTestCase):
    def setUp(self):
        super().setUp()
        self.unit.unit_type=UnitType.VEH_GROUND
        self.unit.move_type=MoveType.TRACK
        for section in self.unit.sections:
            section.internal=0
        self.side=self.unit.sections[0]
        self.side.internal=self.side.armor=100

    def test_start_damages_once_and_one_die_still_schedules(self):
        with use_source(lambda name,lo,hi,fallback:max(lo,1)):
            vehicle_fire.start_burn(self.engine,self.unit)
            vehicle_fire.start_burn(self.engine,self.unit)
        self.assertEqual(self.side.armor,99)
        self.assertEqual(len(vehicle_fire.burning_sides(self.unit)),1)
        with use_source(lambda name,lo,hi,fallback:max(lo,1)):
            self.engine.run_ticks(60)
        self.assertEqual(self.side.armor,98)
        self.assertFalse(vehicle_fire.burning_sides(self.unit))

    def test_extinguish_survives_restart_and_cancels_all_burns(self):
        with use_source(lambda name,lo,hi,fallback:3):
            vehicle_fire.start_burn(self.engine,self.unit)
            self.unit.clear_status(S.STARTED)
            self.assertTrue(vehicle_fire.extinguish(self.engine,self.unit)[0])
            self.assertFalse(vehicle_fire.extinguish(self.engine,self.unit)[0])
            self.unit.set_status(S.STARTED)
            self.engine.run_ticks(120)
        self.assertFalse(vehicle_fire.burning_sides(self.unit))
        self.assertIsNone(self.unit._extinguish_event)

    def test_water_cancels_inferno_and_smoke_restores_underlay(self):
        from systems.missile import inferno_burn,water_extinguish_inferno
        self.unit.unit_type=UnitType.MECH
        self.board.set_terrain(10,10,WATER)
        self.board.set_elevation(10,10,2)
        self.unit.elev=2
        self.unit.z=-2
        inferno_burn(self.engine,self.unit,180)
        self.assertTrue(water_extinguish_inferno(self.engine,self.unit).extinguished)
        self.assertFalse(self.unit.has_crit_status(C.JELLIED))
        self.assertIsNone(self.unit._burn_event)
        self.assertEqual(self.board.terrain(10,10),SMOKE)
        self.assertEqual(self.board.rterrain(10,10),WATER)
        self.engine.run_ticks(120)
        self.assertEqual(self.board.terrain(10,10),WATER)

    def test_real_motive_chart_changes_pilot_control_before_speed(self):
        from systems.vehicle_combat import motive_system_hit
        self.unit.pilot_skill_base=0
        before=self.unit.max_speed
        with use_source(lambda name,lo,hi,fallback:8):
            motive_system_hit(self.unit)
        self.assertEqual(self.unit.pilot_skill_base,1)
        self.assertEqual(self.unit.max_speed,before)

    def test_registering_detached_inferno_binds_expiry_to_event_clock(self):
        from systems.missile import inferno_burn
        from entities.mech import Mech
        unit=Mech.create_test_mech()
        inferno_burn(None,unit,6)
        self.engine.register_entity(unit)
        self.engine.run_ticks(5)
        self.assertTrue(unit.has_crit_status(C.JELLIED))
        self.engine.run_ticks(1)
        self.assertFalse(unit.has_crit_status(C.JELLIED))
