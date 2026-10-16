"""Fall cleanup, result contract, C rounding and damage routing boundaries."""
import unittest
from unittest.mock import patch, call
from acceptance.movement.context import fresh, set_hex, psr
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, UnitType, MoveType, Location
from core.events import EventType
from physics import jump
from physics import movement
from systems import combat


def ready():
    world = {}
    fresh(world)
    return world


class TestFallingHardening(unittest.TestCase):
    def test_default_fall_result_feedback_and_los_invalidation(self):
        w = ready()
        u = w['unit']
        u.set_status(S.COMBAT_SAFE)
        u.facing = 350
        u.stagger_damage = 19
        u.stagger_damage_list = [{'amount': 19}]
        before = getattr(w['map'], 'moves', 0)
        with patch.object(combat, 'roll_1d6', return_value=2):
            result = jump.mech_falls(u)
        self.assertEqual((1, 0, 50, 'Mech fell 1 level(s), taking 0 damage'),
                         (result.levels_fallen, result.damage_taken, result.direction, result.message))
        self.assertIn(result.message, u.movement_messages)
        self.assertEqual((0, []), (u.stagger_damage, u.stagger_damage_list))
        self.assertGreater(w['map'].moves, before)

    def test_injury_roll_uses_the_actual_number_of_levels(self):
        w = ready()
        with psr(w) as roll, patch.object(combat, 'roll_1d6', return_value=1):
            jump.mech_falls(w['unit'], 3, notify_fall=False)
        roll.assert_called_once_with(w['unit'], 3)
        self.assertNotIn('Mech fell 3 level(s)', '\n'.join(getattr(w['unit'], 'movement_messages', [])))

    def test_fall_settling_checks_ice_break_probability(self):
        w = ready()
        u = w['unit']
        u.set_status(S.COMBAT_SAFE)
        set_hex(w, 'ICE', 2)
        with patch('physics.movement.random.randint', return_value=1), patch.object(combat, 'roll_1d6', return_value=1):
            jump.mech_falls(u, 0)
        self.assertEqual('~', w['map'].terrain(u.x, u.y))
        self.assertEqual(-2, u.z)

    def test_fall_cancels_only_its_own_jump_and_mode_events(self):
        w = ready()
        u, engine = w['unit'], w['engine']
        other = Mech.create_test_mech()
        engine.register_entity(other)
        u.set_status(S.COMBAT_SAFE | S.JUMPING)
        own = [engine.schedule_event(30, event, lambda ev: None, data=u) for event in (EventType.JUMP, EventType.MOVEMODE)]
        others = [engine.schedule_event(30, event, lambda ev: None, data=other) for event in (EventType.JUMP, EventType.MOVEMODE)]
        u._mode_event = own[1]
        with patch.object(combat, 'roll_1d6', return_value=1):
            jump.mech_falls(u, 0)
        self.assertTrue(all(event.zombie for event in own))
        self.assertTrue(all(not event.zombie for event in others))
        self.assertEqual(12, engine.event_time_remaining(EventType.JUMPSTABIL, u))
        self.assertFalse(u.is_jumping)

    def test_aircraft_falls_clear_vertical_and_launch_state(self):
        for move in (MoveType.VTOL, MoveType.FLY):
            for safe in (False, True):
                w = ready()
                u = w['unit']
                u.unit_type, u.move_type = UnitType.VTOL, move
                u.vertical_speed = 4
                u.start_fx, u.start_fy, u.start_fz = 10, 20, 30
                if safe: u.set_status(S.COMBAT_SAFE)
                with self.subTest(move=move, safe=safe), psr(w), patch.object(combat, 'roll_1d6', return_value=1):
                    jump.mech_falls(u, 0)
                    self.assertEqual((0, 0, 0, 0), (u.vertical_speed, u.start_fx, u.start_fy, u.start_fz))
                    self.assertTrue(u.has_status(S.LANDED))
                    self.assertEqual(not safe, u.is_fallen)

    def test_c_fall_damage_rounding_water_gravity_and_mechwarrior_scaling(self):
        for tons, terrain, levels, gravity, kind, expected in (
            (55, 'WATER', 1, 100, UnitType.MECH, 3),
            (54, 'GRASSLAND', 1, 100, UnitType.MECH, 5),
            (50, 'GRASSLAND', 20, 150, UnitType.MECH, 110),
            (1, 'GRASSLAND', 4, 100, UnitType.MW, 80)):
            w = ready()
            u = w['unit']
            u.tonnage, u.unit_type = tons, kind
            u.set_status(S.UNDERSPECIAL)
            w['map'].grav = gravity
            set_hex(w, terrain, 2 if terrain == 'WATER' else 0)
            u.z = -2 if terrain == 'WATER' else 0
            with self.subTest(tons=tons, terrain=terrain, levels=levels):
                self.assertEqual(expected, jump._fall_damage(u, levels))

    def test_directional_clusters_keep_attacker_engine_and_critical_context(self):
        w = ready()
        u, engine = w['unit'], w['engine']
        attacker = Mech.create_test_mech()
        u.sections[Location.CTORSO].rear = 30
        u.sections[Location.CTORSO].rear_orig = 30
        with psr(w), patch.object(combat, 'roll_1d6', return_value=4), patch.object(combat, 'roll_2d6', return_value=7), patch.object(combat, 'get_hit_location', side_effect=[(Location.CTORSO, True)] * 3) as hit, patch.object(combat, 'apply_damage_with_transfer', wraps=combat.apply_damage_with_transfer) as applied:
            result = jump.mech_falls(u, 2, attacker)
        self.assertEqual(11, result.damage_taken)
        self.assertEqual(19, u.sections[Location.CTORSO].rear)
        self.assertEqual([call(u, combat.HitGroup.BACK)] * 3, hit.call_args_list)
        self.assertEqual([5, 5, 1], [c.args[2] for c in applied.call_args_list])
        for c in applied.call_args_list:
            self.assertTrue(c.args[3])
            self.assertIs(c.kwargs['attacker'], attacker)
            self.assertIs(c.kwargs['engine'], engine)
            self.assertTrue(c.kwargs['is_critical'])
