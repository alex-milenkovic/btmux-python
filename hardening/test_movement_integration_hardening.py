"""Current movement integrations: modes, vertical travel, ice and events."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from acceptance.movement.context import fresh, advance, set_hex
from entities.mech import MechStatus as S, MechStatus2 as S2, MoveType, UnitType
from entities.map import WATER, ROAD, BRIDGE
from core.events import EventType
from physics import movement, jump
from systems.piloting import PilotingResult
from systems.movement_commands import schedule_mode
from systems.los import MECHMAPFLAG_MOVED


def ready():
    w={};fresh(w);return w


def immersed():
    w=ready();u=w['unit']
    set_hex(w,'WATER',2)
    w['map'].set_terrain(3,2,WATER);w['map'].set_elevation(3,2,2)
    u.last_x,u.last_y=3,2;u.z=-2;u.fz=-129
    return w


class TestMovementIntegrationHardening(unittest.TestCase):
    def test_modes_scale_turning_with_speed_demon_and_maneuvering_ace(self):
        for mode in (S2.SPRINTING,S2.EVADING):
            for ace,demon,expected in ((False,False,4.5),(False,True,6),(True,False,9),(True,True,9)):
                w=ready();u=w['unit'];u.set_status2(mode)
                u.pilot.maneuvering_ace=ace;u.pilot.speed_demon=demon
                self.assertAlmostEqual(expected,movement.calculate_turn_rate(u,64.5),delta=1e-5)
        w=ready();u=w['unit']
        self.assertAlmostEqual(9,movement.calculate_turn_rate(u,64.5),delta=1e-5)
        u.set_status2(S2.SPRINTING);u.pilot=None
        self.assertAlmostEqual(4.5,movement.calculate_turn_rate(u,64.5),delta=1e-5)

    def test_sprint_removes_pavement_bonus_for_tracks_and_wheels(self):
        for move in (MoveType.TRACK,MoveType.WHEEL):
            for terrain in (ROAD,BRIDGE):
                w=ready();u=w['unit'];u.move_type=move
                self.assertEqual(53.75,movement.terrain_speed(u,43,43,terrain,0))
                u.set_status2(S2.SPRINTING)
                self.assertEqual(43,movement.terrain_speed(u,43,43,terrain,0))

    def test_vertical_motion_updates_height_and_los_but_landed_vtol_stays_put(self):
        for move in (MoveType.VTOL,MoveType.SUB):
            w=ready();u=w['unit'];u.move_type=move;u.vertical_speed=129
            u.mapflag=0
            self.assertTrue(movement.move_mech(u))
            self.assertEqual((1,64.5),(u.z,u.fz))
            self.assertTrue(u.mapflag & MECHMAPFLAG_MOVED)
            u.vertical_speed=0
            self.assertFalse(movement.move_mech(u))
        w=ready();u=w['unit'];u.move_type=MoveType.VTOL
        u.vertical_speed=u.speed=20;u.set_status(S.LANDED)
        before=(u.fx,u.fy,u.fz)
        self.assertFalse(movement.move_mech(u))
        self.assertEqual(before,(u.fx,u.fy,u.fz))

    def test_small_horizontal_motion_and_nonvertical_units(self):
        for speed in (.01,.5):
            w=ready();u=w['unit'];u.speed=speed
            self.assertTrue(movement.move_mech(u))
        w=ready();u=w['unit'];u.vertical_speed=129
        self.assertFalse(movement.move_mech(u))
        self.assertEqual(0,u.fz)

    def test_ice_break_notifies_the_actual_actor_and_drop_falls_once(self):
        for action,message in ((movement.break_thru_ice,'You break through the ice!'),(movement.drop_thru_ice,'You break the ice!')):
            w=ready();u=w['unit'];set_hex(w,'ICE',2)
            u.z=-1 if action==movement.break_thru_ice else 0
            calls=[];original=jump.mech_falls
            with patch.object(movement,'NOTIFY_HOOK',side_effect=lambda actor,text:calls.append((actor,text))),patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)),patch('systems.combat.roll_1d6',return_value=1),patch('systems.combat.roll_2d6',return_value=7),patch.object(jump,'mech_falls',wraps=original) as fall:
                action(u)
            self.assertIn((u,message),calls)
            self.assertEqual(WATER,w['map'].terrain(3,3))
            if action==movement.drop_thru_ice:
                self.assertEqual(1,fall.call_count)
                self.assertEqual((u,2),fall.call_args.args)

    def test_water_entry_schedules_sprint_exit_and_preserves_existing_transition(self):
        for state in ('active','pending','ordinary','mapless_engine'):
            w=immersed();u=w['unit'];u.speed=20;u.desired_speed=100
            if state!='ordinary':u.set_status2(S2.SPRINTING)
            existing=None
            if state=='pending':
                schedule_mode(w['engine'],u,S2.SPRINTING,False,7)
                existing=u._mode_event
            if state=='mapless_engine':u._engine=None
            with patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)):
                movement.new_hex_entered(u,0,1,-2)
            self.assertAlmostEqual(43 if state=='ordinary' else 172/3,u.desired_speed)
            if state=='active':
                self.assertEqual(30,w['engine'].event_time_remaining(EventType.MOVEMODE,u))
                advance(w,29);self.assertTrue(u.has_status2(S2.SPRINTING))
                advance(w,1);self.assertFalse(u.has_status2(S2.SPRINTING))
            elif state=='pending':self.assertIs(existing,u._mode_event)
            else:self.assertIsNone(u._mode_event)

    def test_water_slip_notification_depends_on_running_damage_modifier(self):
        for speed,expected_messages in ((43,0),(44,1)):
            w=immersed();u=w['unit'];u.speed=speed
            with patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=False)),patch('systems.combat.roll_1d6',return_value=1),patch('systems.combat.roll_2d6',return_value=7):
                movement.new_hex_entered(u,0,1,-2)
            self.assertEqual(1,u.last_fall_levels)
            self.assertEqual(expected_messages,len([m for m in u.movement_messages if m.startswith('Mech fell')]))

    def test_orbital_move_event_turns_and_rearms_without_ground_translation(self):
        w=ready();u=w['unit'];u.cocoon=2;u.desired_facing=90;u.speed=u.desired_speed=20
        before=(u.fx,u.fy)
        w['engine'].schedule_event(1,EventType.MOVE,movement.mech_move_event,data=u,data2=w['engine'])
        advance(w,1)
        self.assertGreater(u.facing,0)
        self.assertLess(u.facing,90)
        self.assertTrue(w['engine'].has_event(EventType.MOVE,u))
        self.assertEqual(before,(u.fx,u.fy))
        advance(w,29)
        self.assertEqual(90,u.facing)
        self.assertEqual(before,(u.fx,u.fy))
        self.assertFalse(w['engine'].has_event(EventType.MOVE,u))

    def test_rejected_hex_entry_does_not_run_new_flood_or_extinguish_effects(self):
        for axis in ('x','y',None):
            w=ready();u=w['unit']
            def retreat(*args):
                if axis is not None:setattr(u,axis,getattr(u,axis)-1)
            with patch.object(movement,'new_hex_entered',side_effect=retreat),patch('physics.flooding.flood_unit') as flood,patch('physics.flooding.extinguish_in_water') as extinguish:
                movement.on_hex_entered(u,2,2,1,1,0)
            self.assertEqual(1 if axis is None else 0,flood.call_count)
            self.assertEqual(1 if axis is None else 0,extinguish.call_count)


    def test_running_mode_turning_keeps_the_base_penalty_and_minimum(self):
        for speed,maximum,expected in ((53.75,64.5,2.25),(64.5,64.5,1.5),(1,1,1)):
            w=ready();u=w['unit'];u.speed=speed;u.set_status2(S2.SPRINTING);u.pilot.maneuvering_ace=False
            self.assertAlmostEqual(expected,movement.calculate_turn_rate(u,maximum),delta=1e-5)

    def test_water_slip_roll_receives_the_entering_unit_and_depth_modifier(self):
        w=immersed();u=w['unit'];u.speed=44
        with patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)) as roll:
            movement.new_hex_entered(u,0,1,-2)
        roll.assert_called_once_with(u,2)

    def test_ice_surfacing_marks_los_and_runs_shared_breakage_at_crossing(self):
        w=ready();u=w['unit'];set_hex(w,'ICE',2);u.z=-1;u.mapflag=0
        movement.break_thru_ice(u)
        self.assertTrue(u.mapflag & MECHMAPFLAG_MOVED)
        for old_z,current_z,breaks in ((-2,-1,True),(-3,-1,True),(-1,-1,False),(-2,-2,False)):
            w=ready();u=w['unit'];set_hex(w,'ICE',2);u.z=current_z;u.fz=current_z*64.5
            with patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)),patch.object(movement.random,'randint',return_value=6):
                movement.on_hex_entered(u,3,2,last_z=old_z)
            from entities.map import ICE
            self.assertEqual(WATER if breaks else ICE,w['map'].terrain(3,3))

    def test_water_sprint_exit_keeps_thirty_ticks_for_battlesuits(self):
        w=immersed();u=w['unit'];u.unit_type=UnitType.BSUIT;u.set_status2(S2.SPRINTING)
        with patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)):
            movement.new_hex_entered(u,0,1,-2)
        self.assertEqual(30,w['engine'].event_time_remaining(EventType.MOVEMODE,u))
