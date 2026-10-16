"""C heat-update regressions: capacity, clocks and applied effects."""
import unittest
from unittest.mock import patch
from tests.movement_fixture import MovementTestCase
from entities.mech import MechStatus as S, MechStatus2 as S2, CritStatus as C, Specials, Location
from entities.crittypes import Special, i2special
from systems import heat


class HeatUpdates(MovementTestCase):
    def test_cutoff_adjusts_capacity_and_current_dissipation(self):
        u = self.unit
        u.disabled_sinks = 4
        u.weap_heat = 16
        u.set_crit_status(C.HEATCUTOFF)
        heat.update_heat(u)
        self.assertEqual((u.disabled_sinks, u.minus_heat, u.heat), (3, 7, 9))

    def test_double_capacity_recovery_is_four_per_update(self):
        u = self.unit
        u.specials |= Specials.DOUBLE_HEAT_TECH
        u.disabled_sinks = 9
        heat.update_heat(u)
        self.assertEqual((u.disabled_sinks, u.minus_heat), (5, 15))

    def test_water_bonus_uses_functional_physical_slots_then_switches(self):
        u = self.unit
        u.disabled_sinks = 8
        for loc in (Location.LLEG, Location.RLEG):
            for slot in u.sections[loc].criticals[:2]:
                slot.type = i2special(Special.HEAT_SINK)
        u.weap_heat = 14
        u.set_crit_status(C.HEATCUTOFF)
        heat.update_heat(u, True, -1)
        self.assertEqual((u.disabled_sinks, u.minus_heat, u.heat), (7, 5, 9))

    def test_temperature_applies_after_inferno_without_final_clamp(self):
        u = self.unit
        u.num_sinks = 4
        u.weap_heat = 20
        u.set_crit_status(C.JELLIED)
        heat.update_heat(u, map_temperature=51)
        self.assertEqual((u.minus_heat, u.heat), (-1, 21))

    def test_heat_assignment_ignores_old_heat_and_cools_stopped_unit(self):
        u = self.unit
        u.heat, u.weap_heat = 100, 20
        u.clear_status(S.STARTED)
        heat.full_heat_update(u, 2)
        self.assertEqual(u.heat, 10)
        self.assertEqual(u.weap_heat, __import__('core.randomness', fromlist=['float32']).float32(20 - 10 / 30))

    def test_jumping_adds_movement_heat(self):
        u = self.unit
        u.speed, u.desired_speed, u.jump_speed = 10, 10, 43
        u.set_status(S.JUMPING)
        self.assertAlmostEqual(heat.calculate_movement_heat(u), 5, places=5)
        u.set_status2(S2.SPRINTING)
        self.assertAlmostEqual(heat.calculate_movement_heat(u), 7, places=5)

    def test_environment_reads_live_flags_and_fire(self):
        u = self.unit
        from entities.map import FIRE
        u.terrain = FIRE
        u.set_status2(S2.STH_ARMOR_ON | S2.NULLSIGSYS_ON)
        self.assertEqual(heat.calculate_environment_heat(u, 100), 25)

    def test_due_low_band_overheat_keeps_running(self):
        u = self.unit
        u.heat = 10
        heat.check_overheat(u, 29)
        self.assertTrue(u.is_started)
        heat.check_overheat(u, 30)
        self.assertTrue(u.is_started)
        self.assertEqual(u._last_overheat_tick, 30)

    def test_normal_ticks_reach_shutdown_threshold_after_elapsed_interval(self):
        from core.game_loop import register_special_objects
        from core.randomness import use_source
        for current_heat, started, shutdown_draws in ((13.9, True, []), (14, False, ['shutdown_rolls'])):
            with self.subTest(heat=current_heat):
                self.setUp()
                self.unit.num_sinks = 0
                self.unit.weap_heat = current_heat
                register_special_objects(self.engine)
                draws = []
                def source(name, low, high, fallback):
                    if name == 'shutdown_rolls':
                        draws.append(name)
                        return 3
                    return high
                with use_source(source):
                    self.engine.run_ticks(29)
                    self.assertTrue(self.unit.is_started)
                    self.assertEqual(0, getattr(self.unit, '_last_overheat_tick', 0))
                    self.engine.run_ticks(1)
                self.assertAlmostEqual(current_heat, self.unit.heat, places=5)
                self.assertEqual(30, self.unit._last_overheat_tick)
                self.assertEqual(started, self.unit.is_started)
                self.assertEqual(shutdown_draws, draws)

    def test_injury_is_applied_on_turn_even_when_overheat_not_due(self):
        u = self.unit
        u.set_crit_status(C.LIFE_SUPPORT_DESTROYED)
        u.weap_heat = 36
        u._last_overheat_tick = 29
        with patch('systems.piloting.handle_mw_conc', return_value=True):
            heat.full_heat_update(u, 30)
        self.assertEqual(u.pilot_hits, 2)

    def test_cutoff_command_captures_request_and_uses_four_second_event(self):
        from systems.heat_control import heat_cutoff
        u = self.unit
        self.assertTrue(heat_cutoff(self.engine, u, u.pilot)[0])
        self.assertFalse(heat_cutoff(self.engine, u, u.pilot)[0])
        self.engine.run_ticks(3)
        self.assertFalse(u.has_crit_status(C.HEATCUTOFF))
        u.clear_status(S.STARTED)
        self.engine.run_ticks(1)
        self.assertTrue(u.has_crit_status(C.HEATCUTOFF))
        self.assertIsNone(u._cutoff_event)

    def test_cutoff_does_not_require_map_started_or_assigned_pilot(self):
        from systems.heat_control import heat_cutoff
        u = self.unit
        u.map, u.pilot = None, None
        u.clear_status(S.STARTED)
        self.assertTrue(heat_cutoff(self.engine, u)[0])

    def test_double_sink_section_loss_removes_capacity_once(self):
        from systems.damage import destroy_parts
        from entities.mech import FireMode
        u=self.unit
        u.specials|=Specials.DOUBLE_HEAT_TECH
        section=u.sections[Location.LTORSO]
        for slot in section.criticals:
            slot.type=0
        for slot in section.criticals[:3]:
            slot.type=i2special(Special.HEAT_SINK)
        destroy_parts(u,u,Location.LTORSO,engine=self.engine)
        self.assertEqual(u.effective_heat_sinks,18)

    def test_special_map_temperature_uses_actual_map_flag(self):
        from core.game_loop import mech_update
        u=self.unit
        u.set_status(S.UNDERSPECIAL)
        u.weap_heat=20
        self.board.temp=51
        self.board.flags=2
        mech_update(self.engine,u)
        self.assertEqual(u.minus_heat,9)
