"""Source flight boundaries and real event integration."""
from unittest.mock import patch
from tests.movement_fixture import MovementTestCase
from entities.mech import UnitType as U, MoveType as M, MechStatus as S, CritStatus
from core.events import EventType
from core.game_loop import mech_update
from physics import aerospace as a


class FlightTests(MovementTestCase):
    def setUp(self):
        super().setUp()
        self.board._id = self.unit.mapindex = 100
        self.unit.unit_type, self.unit.move_type = U.AERO, M.FLY
        self.unit.max_speed = 60
        self.unit.fuel = 1000
        self.unit.desired_angle = 0

    def test_takeoff_callback_is_count_plus_one_and_rechecks_speed(self):
        u = self.unit
        u.set_status(S.LANDED)
        u.speed = 32.25
        self.assertTrue(a.takeoff(self.engine, u)[0])
        self.engine.run_ticks(10)
        self.assertTrue(u.has_status(S.LANDED))
        u.speed = 32.24
        self.engine.run_ticks(1)
        self.assertTrue(u.has_status(S.LANDED))
        self.assertFalse(self.engine.has_event(EventType.TAKEOFF, u))

    def test_launch_aborts_without_later_effects_and_can_restart(self):
        u = self.unit
        u.unit_type = U.DS
        u.set_status(S.LANDED)
        a.takeoff(self.engine, u)
        self.assertTrue(a.land(self.engine, u)[0])
        self.engine.run_ticks(301)
        self.assertTrue(u.has_status(S.LANDED))
        self.assertFalse(self.engine.has_event(EventType.MOVE, u))
        u.pilot.wizard = True
        a.takeoff(self.engine, u, '-2')
        self.engine.run_ticks(1)
        self.assertFalse(u.has_status(S.LANDED))
        self.assertEqual((u.z, u.desired_angle, u.desired_speed), (1, 90, 40))
        self.assertTrue(self.engine.has_event(EventType.MOVE, u))

    def test_landing_integer_horizontal_and_truncated_vertical_bounds(self):
        u = self.unit
        u.z = 1
        u.speed = u.desired_speed = 32
        self.assertTrue(a.land(self.engine, u)[0])
        u.clear_status(S.LANDED)
        u.unit_type, u.move_type = U.VTOL, M.VTOL
        u.speed = 0
        u.desired_speed = u.vertical_speed = 10.9
        self.assertTrue(a.land(self.engine, u)[0])
        u.clear_status(S.LANDED)
        u.desired_speed = u.vertical_speed = 11
        self.assertFalse(a.land(self.engine, u)[0])

    def test_thrust_rounds_input_before_minimum_comparison(self):
        self.assertFalse(a.thrust(self.engine, self.unit, '6.45')[0])
        self.assertTrue(a.thrust(self.engine, self.unit, '6.450001')[0])

    def test_landing_script_is_only_in_general_vtol_profile(self):
        u=self.unit
        for kind,movement in ((U.VTOL,M.VTOL),(U.SPHEROID_DS,M.FLY)):
            u.unit_type,u.move_type=kind,movement
            u.clear_status(S.LANDED);u.z=1;u.fuel=1000
            trace=[]
            def mine(unit,reason):
                self.assertTrue(unit.has_status(S.LANDED))
                trace.append('mine')
            with patch('systems.damage.external_effect',side_effect=lambda unit,service,text:trace.append('script') if text=='A_AAEROLAND' else None),patch('systems.mines.possible_mine_poof',side_effect=mine):
                self.assertTrue(a.land(self.engine,u)[0])
            self.assertEqual(trace,['script','mine'] if kind==U.VTOL else ['mine'])

    def test_landed_aerofighter_can_build_takeoff_speed_with_speed_command(self):
        from systems.movement_commands import speed
        self.unit.set_status(S.LANDED)
        self.assertTrue(speed(self.engine,self.unit,'40')[0])
        self.engine.run_ticks(20)
        self.assertGreaterEqual(self.unit.speed,32.25)
        self.assertTrue(a.takeoff(self.engine,self.unit)[0])

    def test_acceleration_cap_and_backup_target(self):
        u = self.unit
        u.z, u.desired_speed, u.desired_angle = 99, 60, 90
        a.update_speed(u)
        self.assertAlmostEqual(u.start_fz, 12.5)
        u.unit_type, u.z, u.fuel, u.desired_speed = U.DS, 100, -1, 1
        u.start_fx = u.start_fy = u.start_fz = 0
        a.update_speed(u)
        self.assertAlmostEqual(u.start_fz, 1)

    def test_zero_vector_delta_keeps_scalar_and_spheroid_keeps_heading(self):
        u = self.unit
        u.speed = 9
        a.update_speed(u)
        self.assertEqual(u.speed, 9)
        u.unit_type, u.z, u.desired_speed, u.desired_facing = U.SPHEROID_DS, 100, 60, 90
        a.update_speed(u)
        self.assertGreater(u.start_fx, 0)
        self.assertEqual(u.facing, 0)

    def test_airborne_event_moves_vectors_and_spends_fuel(self):
        u = self.unit
        u.z, u.fz = 100, 6450
        before = (u.fx, u.fy, u.fz)
        a.thrust(self.engine, u, '20')
        a.vheading(u, '30', 1)
        self.engine.run_ticks(2)
        self.assertNotEqual((u.fx, u.fy, u.fz), before)
        self.assertLess(u.fuel, 1000)
        self.assertEqual(sum(e.event_type == EventType.MOVE and not e.zombie for e in self.engine.events.pending_events(data=u)), 1)

    def test_periodic_window_and_spin_modifier_use_simulation_time(self):
        u = self.unit
        u.set_crit_status(CritStatus.SPINNING)
        u.start_spin = 0
        self.engine.sim_now = 15
        with patch('systems.stability.update_pilot_skill_rolls') as pilot, patch('systems.heat.update_from_environment') as heat, patch('systems.piloting.make_piloting_roll') as psr:
            psr.return_value.success = True
            mech_update(self.engine, u)
        pilot.assert_called_once()
        heat.assert_called_once()
        psr.assert_called_once_with(u, 7)
        self.assertFalse(u.has_crit_status(CritStatus.SPINNING))

    def test_template_reset_clears_flight_runtime_but_preserves_persistent_bays(self):
        from data.template_files import clear_mech
        self.unit.desired_angle=75;self.unit.start_spin=123
        self.unit.aero_bays=[101,-1,-1,-1]
        clear_mech(self.unit,True)
        self.assertEqual((self.unit.desired_angle,self.unit.start_spin),(0,0))
        self.assertEqual(self.unit.aero_bays,[101,-1,-1,-1])
