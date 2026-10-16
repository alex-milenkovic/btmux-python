"""C movement jump gates, trajectory scale, landing state and recovery."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from acceptance.movement.context import fresh, advance
from core.events import EventType
from entities.mech import Mech, MechStatus as S, MechStatus2 as S2, UnitType, Location, CritStatus
from entities.map import ICE, WATER, GRASSLAND
from physics import jump
from physics.movement import MP1, ZSCALE
from systems.piloting import PilotingResult


def ready():
    w = {}
    fresh(w)
    w['unit'].jump_mp = 4
    return w


def landing(w):
    u = w['unit']
    u.set_status(S.JUMPING)
    u._jump_queue = w['engine'].events
    u.going_x, u.going_y = 4, 5
    u.dfa_target = 999
    u.speed = 12
    return u


class TestJumpHardening(unittest.TestCase):
    def test_jump_rejects_each_independent_mode_posture_and_recovery_gate(self):
        for condition in ('mode', 'posture', 'stand', 'stabil', 'cocoon'):
            w = ready(); u = w['unit']
            if condition == 'mode': u.set_status2(S2.SPRINTING)
            if condition == 'posture': u.set_status(S.HULLDOWN)
            if condition == 'cocoon': u.cocoon = 1
            if condition in ('stand', 'stabil'):
                setattr(u, '_stand_event' if condition == 'stand' else '_stabil_event', w['engine'].schedule_event(10, EventType.STAND, lambda e: None, data=u))
            result = jump.mech_jump(u, 3, 4, w['engine'].events)
            self.assertFalse(result.success, condition)
            self.assertEqual('Movement modes, posture or recovery disallow jumping.', result.message)
            self.assertFalse(w['engine'].has_event(EventType.JUMP, u))

    def test_can_jump_rejections_preserve_specific_reasons(self):
        cases = [('class', 'This unit cannot jump in its current state.'), ('fortified', 'This unit cannot jump in its current state.'), ('carry', 'This unit cannot jump in its current state.'), ('swarm', 'This unit cannot jump in its current state.'), ('dump', 'This unit cannot jump in its current state.'), ('unjam', 'This unit cannot jump in its current state.'), ('ceiling', 'The ceiling is too low for jumping!'), ('off', 'Mech is not started'), ('destroyed', 'Mech is destroyed'), ('jumping', 'Already jumping'), ('fallen', 'Cannot jump while fallen')]
        for condition, message in cases:
            w=ready(); u=w['unit']
            if condition=='class': u.unit_type=UnitType.VTOL
            if condition=='fortified': u.set_status2(S2.FORTIFIED)
            if condition=='carry': u.carrying=1
            if condition=='swarm': u.swarm_target=Mech.create_test_mech()
            if condition=='dump': u.dumping=True
            if condition=='unjam': u.unjamming=True
            if condition=='ceiling': w['map'].flags=16
            if condition=='off': u.clear_status(S.STARTED)
            if condition=='destroyed': u.set_status(S.DESTROYED)
            if condition=='jumping': u.set_status(S.JUMPING)
            if condition=='fallen': u.set_status(S.FALLEN)
            self.assertEqual((False,message),jump.can_jump(u,3,4),condition)
        self.assertEqual((True,''),jump.can_jump(ready()['unit'],3,4))

    def test_off_map_and_unreachable_height_diagnostics(self):
        w=ready();u=w['unit']
        self.assertEqual('That would take you off the map!',jump.mech_jump(u,-1,4).message)
        w['map'].set_elevation(3,4,5)
        self.assertEqual('Target height is outside jump capability.',jump.mech_jump(u,3,4).message)
        self.assertFalse(u.is_jumping)

    def test_gravity_clamps_at_fifty_and_requires_the_gravity_status(self):
        for capability, gravity, active, expected in ((100,100,True,100),(10,49,True,20),(10,50,True,20),(10,200,False,10),(10,200,True,5)):
            w=ready();u=w['unit'];u.jump_mp=capability;w['map'].grav=gravity
            if active:u.set_status(S.UNDERGRAVITY)
            self.assertEqual(expected,jump.get_jump_mp(u))

    def test_jump_top_uses_both_c_caps_and_fixed_point_height(self):
        # mech.move.c:1272: min(JP+1-range/3, 2*range+2), in ZSCALE units.
        for capability, y, expected in ((4,5,4+1/3),(10,4,4),(4,6,4)):
            w=ready();u=w['unit'];u.jump_mp=capability
            self.assertTrue(jump.mech_jump(u,3,y).success)
            self.assertAlmostEqual(expected*ZSCALE,u.jump_top)

    def test_odd_jump_quadratic_and_degenerate_paths(self):
        self.assertEqual(10,jump.calculate_odd_jump_altitude(0,0,10,30,64,4))
        # quarter-way base=15; a top of 384 (6 levels) selects quadratic for JP4.
        self.assertEqual(303,jump.calculate_odd_jump_altitude(25,100,10,30,384,4))
        self.assertEqual(30,jump.calculate_odd_jump_altitude(100,100,10,30,384,4))

    def test_landing_cleans_jump_state_and_only_its_own_events(self):
        w=ready();u=landing(w);engine=w['engine']
        engine.schedule_event(1,EventType.JUMP,lambda e: None,data=u)
        other=Mech.create_test_mech()
        other_event=engine.schedule_event(1,EventType.JUMP,lambda e: None,data=other)
        self.assertTrue(jump.land_mech(u))
        self.assertFalse(u.is_jumping)
        self.assertEqual((-1,0,0,0),(u.dfa_target,u.going_x,u.going_y,u.speed))
        self.assertFalse(engine.has_event(EventType.JUMP,u))
        self.assertFalse(other_event.zombie)
        self.assertEqual('You finish your jump.',u.movement_messages[-1])
        self.assertEqual(12,engine.event_time_remaining(EventType.JUMPSTABIL,u))
        advance(w,11)
        self.assertIsNotNone(u._stabil_event)
        advance(w,1)
        self.assertIsNone(u._stabil_event)
        self.assertEqual('You have stabilized after your jump.',u.movement_messages[-1])

    def test_landing_does_not_replace_fall_recovery_or_create_one_without_a_jump(self):
        w=ready();u=landing(w)
        existing=w['engine'].schedule_event(8,EventType.JUMPSTABIL,jump._jumpstabil_callback,data=u)
        u._stabil_event=existing
        jump.land_mech(u)
        self.assertIs(existing,u._stabil_event)
        w=ready();u=w['unit']
        jump.land_mech(u,event_queue=w['engine'].events)
        self.assertIsNone(u._stabil_event)

    def test_landing_refreshes_surface_state_and_enters_water_below_ice(self):
        for terrain, depth, expected in ((WATER,2,-2),(ICE,2,0),(GRASSLAND,2,2)):
            w=ready();u=landing(w)
            w['map'].set_terrain(3,3,terrain);w['map'].set_elevation(3,3,depth)
            with patch('physics.movement.random.randint', return_value=6):
                jump.land_mech(u)
            self.assertEqual((terrain,depth,expected),(u.terrain,u.elev,u.z))

    def test_damaged_landing_roll_and_fall_severity(self):
        w=ready();u=landing(w);u.set_crit_status(CritStatus.GYRO_DAMAGED)
        with patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=False)) as roll, patch('systems.combat.roll_1d6',return_value=1),patch('systems.combat.roll_2d6',return_value=7):
            self.assertFalse(jump.land_mech(u))
        self.assertEqual((u,0),roll.call_args_list[0].args)
        self.assertEqual(1,u.last_fall_levels)

    def test_landing_swarm_roll_detaches_on_success_and_falls_on_failure(self):
        for success in (True,False):
            w=ready();u=landing(w)
            suit=Mech.create_test_mech();suit.unit_type=UnitType.BSUIT;suit.swarm_target=u
            w['map'].add_mech(suit)
            with patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=success)) as roll,patch('systems.combat.roll_1d6',return_value=1),patch('systems.combat.roll_2d6',return_value=7):
                result=jump.land_mech(u)
            self.assertEqual((u,4),roll.call_args_list[0].args)
            self.assertIsNone(suit.swarm_target)
            self.assertEqual(success,result)
            if not success:self.assertEqual(1,u.last_fall_levels)

    def test_dfa_landing_resolves_only_a_current_target_and_forwards_its_result(self):
        # This verifies the new land_mech integration boundary. Existing physical
        # attack internals retain their separately documented baseline limitations.
        for state in ('present','moved','missing','unconscious'):
            w=ready();u=landing(w);u.set_status(S.DFA_ATTACK)
            other=Mech.create_test_mech();other._id=20;other.set_hex_position(3,3);w['map'].add_mech(other)
            u.dfa_target=other._id
            if state=='moved':other.set_hex_position(4,3)
            if state=='missing':w['map'].remove_mech(other)
            if state=='unconscious':u.set_status(S.UNCONSCIOUS)
            with patch('systems.physical.dfa_attack',return_value=SimpleNamespace(messages=['DFA result'])) as attack,patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)),patch('systems.combat.roll_1d6',return_value=1):
                jump.land_mech(u)
            if state=='present':
                attack.assert_called_once_with(u,other)
                self.assertIn('DFA result',u.movement_messages)
            else:
                attack.assert_not_called()
                if state!='unconscious':self.assertIn('Your DFA target has moved or become invalid.',u.movement_messages)
            self.assertFalse(u.has_status(S.DFA_ATTACK))

    def test_positive_unit_length_and_quadratic_threshold_are_inclusive(self):
        self.assertEqual(84,jump.calculate_odd_jump_altitude(.5,1,10,30,64,4))
        self.assertEqual(256.875,jump.calculate_odd_jump_altitude(25,100,10,30,322.5,4))

    def test_update_jump_uses_map_scale_and_preserves_intermediate_coordinates(self):
        from physics.hexmath import float_to_hex
        for modifier, expected_distance in ((200,43),(0,21.5),(1,.215)):
            w=ready();u=w['unit'];w['map'].movemod=modifier
            self.assertTrue(jump.mech_jump(u,3,6).success)
            x,y=u.fx,u.fy
            self.assertTrue(jump.update_jump(u))
            self.assertAlmostEqual(expected_distance,u.fy-y)
            self.assertAlmostEqual(x,u.fx)
            self.assertEqual((3,3),(u.last_x,u.last_y))
            self.assertEqual(float_to_hex(u.fx,u.fy),(u.x,u.y))
            self.assertEqual(int(u.fz/ZSCALE+.5),u.z)
        w=ready();u=w['unit']
        self.assertFalse(jump.update_jump(u))

    def test_jump_callback_reschedules_under_the_jump_event_type(self):
        w=ready();u=w['unit']
        self.assertTrue(jump.mech_jump(u,3,6,w['engine'].events).success)
        advance(w,1)
        self.assertTrue(u.is_jumping)
        self.assertTrue(w['engine'].has_event(EventType.JUMP,u))

    def test_can_jump_preserves_all_allowed_ground_classes(self):
        for kind in (UnitType.MECH,UnitType.MW,UnitType.BSUIT,UnitType.VEH_GROUND):
            w=ready();u=w['unit'];u.unit_type=kind
            self.assertEqual((True,''),jump.can_jump(u,3,4))

    def test_jump_target_height_is_relative_and_shallow_submergence_is_inclusive(self):
        for start, terrain, height, success, expected in ((3,GRASSLAND,7,True,451.5),(-1,GRASSLAND,0,True,0),(-2,GRASSLAND,0,False,None),(0,ICE,2,True,0),(0,GRASSLAND,2,True,129)):
            w=ready();u=w['unit'];u.z=start;u.fz=start*ZSCALE
            w['map'].set_terrain(3,4,terrain);w['map'].set_elevation(3,4,height)
            result=jump.mech_jump(u,3,4)
            self.assertEqual(success,result.success)
            if success:
                self.assertEqual(expected,u.end_fz)
                self.assertEqual(0,u.cocoon)
                self.assertIsNone(u.swarm_target)
            else:self.assertEqual('Target height is outside jump capability.',result.message)

    def test_update_lands_when_progress_equals_the_integer_jump_length(self):
        w=ready();u=w['unit']
        self.assertTrue(jump.mech_jump(u,3,5).success)
        self.assertEqual(645,u.jump_length)
        for _ in range(29):self.assertTrue(jump.update_jump(u))
        self.assertFalse(jump.update_jump(u))
        self.assertFalse(u.is_jumping)
        self.assertEqual((3,5),(u.x,u.y))

    def test_stale_jump_callback_without_an_actor_is_a_no_op(self):
        jump._jump_event_callback(SimpleNamespace(data=None))

    def test_jump_empty_carry_sentinel_and_unrelated_map_flag_do_not_block(self):
        w=ready();u=w['unit'];u.carrying=0;w['map'].flags=1
        self.assertEqual((True,''),jump.can_jump(u,3,4))

    def test_cargo_loss_of_exactly_one_mp_is_allowed_but_larger_loss_is_refused(self):
        for load,allowed in ((5*1024,True),(int(5.25*1024),False)):
            w=ready();u=w['unit'];u.carried_cargo=load
            self.assertEqual(allowed,jump.can_jump(u,3,4)[0])
            result=jump.mech_jump(u,3,4)
            self.assertEqual(allowed,result.success)
            if allowed:self.assertEqual('Jump initiated to (3, 4), distance 1',result.message)
            else:self.assertEqual("No, with this cargo you won't!",result.message)

    def test_jump_range_and_missing_jet_reasons(self):
        w=ready();u=w['unit'];u.jump_mp=1
        self.assertEqual((True,''),jump.can_jump(u,3,4))
        self.assertEqual((False,'Target hex is current position'),jump.can_jump(u,3,3))
        u.jump_mp=0
        for walk,reason in ((0,'Mech has no jump capability'),(1,'Mech has no jump jets')):
            u.walk_speed=walk
            self.assertEqual((False,reason),jump.can_jump(u,3,4))

    def test_eastward_jump_updates_x_toward_its_target(self):
        w=ready();u=w['unit'];start=u.fx
        self.assertTrue(jump.mech_jump(u,5,3).success)
        self.assertTrue(jump.update_jump(u))
        self.assertGreater(u.fx,start)

    def test_landing_uses_bridge_deck_and_shallow_ice_surface(self):
        from entities.map import BRIDGE
        for terrain,depth,die,expected_terrain,expected_z in ((BRIDGE,3,6,BRIDGE,3),(ICE,1,6,ICE,0),(ICE,2,1,WATER,-2)):
            w=ready();u=landing(w)
            w['map'].set_terrain(3,3,terrain);w['map'].set_elevation(3,3,depth)
            with patch('physics.movement.random.randint',return_value=die),patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)),patch('systems.combat.roll_1d6',return_value=1),patch('systems.combat.roll_2d6',return_value=7):
                jump.land_mech(u)
            self.assertEqual((expected_terrain,expected_z),(u.terrain,u.z))

    def test_landing_stacking_applies_jump_damage_only_while_upright(self):
        from physics import collision
        for fallen in (False,True):
            w=ready();u=landing(w);u.jump_speed=43
            if fallen:u.set_status(S.FALLEN)
            others=[]
            for _ in range(3):
                other=Mech.create_test_mech();other.set_hex_position(3,3);other.set_status(S.STARTED);other.team=u.team
                w['map'].add_mech(other);others.append(other)
            def armor():return sum(s.armor+s.rear+s.internal for other in others for s in other.sections)
            before=armor()
            with patch.object(collision.random,'randint',return_value=0),patch('systems.combat.roll_1d6',return_value=1),patch('systems.combat.roll_2d6',return_value=7),patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)):
                jump.land_mech(u)
            self.assertEqual(0 if fallen else 14,before-armor())

    def test_mapless_low_level_jump_preserves_its_final_fixed_point_height(self):
        w=ready();u=w['unit'];w['map'].remove_mech(u);u.z=2;u.fz=129
        self.assertTrue(jump.mech_jump(u,3,5).success)
        for _ in range(30):jump.update_jump(u)
        self.assertFalse(u.is_jumping)
        self.assertEqual(129,u.fz)

    def test_bridge_landing_preserves_the_c_fixed_point_elevation_reset(self):
        # LandMech sets FZ from stored elevation minus one before DropSetElevation;
        # bridge_set_elevation then changes integer Z only (mech.update.c:71-82).
        from entities.map import BRIDGE
        w=ready();u=landing(w);u.fz=999
        w['map'].set_terrain(3,3,BRIDGE);w['map'].set_elevation(3,3,3)
        jump.land_mech(u)
        self.assertEqual((3,129),(u.z,u.fz))

    def test_landing_stacking_preserves_mech_punch_and_kick_damage_clusters(self):
        from physics import collision
        from systems import combat
        # C collision damage: 50t/4MP ->14, 30t/4MP ->11, in clusters of5.
        for tons,clusters,facing in ((50,[5,5,4],0),(30,[5,5,1],180)):
            w=ready();u=landing(w);u.jump_speed=43;u.tonnage=tons;u.measured_mass=tons*1024;u.facing=180
            others=[]
            for _ in range(3):
                other=Mech.create_test_mech();other.set_hex_position(3,3);other.set_status(S.STARTED);other.team=u.team;other.facing=facing
                w['map'].add_mech(other);others.append(other)
            original=combat.apply_damage_with_transfer
            with patch.object(collision.random,'randint',return_value=0),patch.object(combat,'roll_1d6',return_value=1) as dice,patch.object(combat,'roll_2d6',return_value=7),patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)),patch.object(combat,'apply_damage_with_transfer',wraps=original) as damage:
                jump.land_mech(u)
            expected=[(others[0],Location.LARM,amount) for amount in clusters]+[(u,Location.RLEG,2)]
            self.assertEqual(expected,[call.args for call in damage.call_args_list])
            self.assertEqual(4,dice.call_count)
            for call in damage.call_args_list:
                self.assertIs(u,call.kwargs['attacker'])
                self.assertFalse(call.kwargs['is_critical'])
                self.assertEqual(call.args[0] is not u and facing==0,call.kwargs['is_rear'])

    def test_registered_periodic_jump_advances_mechs_and_skips_other_entity_types(self):
        from entities.vehicle import Vehicle
        w=ready();u=w['unit'];other=Mech.create_test_mech();vehicle=Vehicle()
        w['engine'].register_entity(other);w['engine'].register_entity(vehicle)
        before_other=(other.fx,other.fy)
        self.assertTrue(jump.mech_jump(u,3,6).success)
        before=u.fy
        jump.register_jump_system(w['engine'])
        advance(w,1)
        self.assertAlmostEqual(21.5,u.fy-before)
        self.assertEqual(before_other,(other.fx,other.fy))
        self.assertTrue(w['engine'].unregister_periodic('jump'))

    def test_periodic_wrapper_returns_whether_the_jump_continues(self):
        w=ready();u=w['unit']
        self.assertFalse(jump.update_jump_periodic(u))
        self.assertTrue(jump.mech_jump(u,3,6).success)
        self.assertTrue(jump.update_jump_periodic(u))

    def test_landing_on_a_fallen_mech_uses_normal_locations_and_critical_flags(self):
        from physics import collision
        from systems import combat
        w=ready();u=landing(w);u.jump_speed=43
        others=[]
        for _ in range(3):
            other=Mech.create_test_mech();other.set_hex_position(3,3);other.facing=180
            other.set_status(S.STARTED|S.FALLEN);other.team=u.team
            w['map'].add_mech(other);others.append(other)
        with patch.object(collision.random,'randint',return_value=0),patch.object(combat,'roll_1d6',return_value=1),patch.object(combat,'roll_2d6',return_value=2),patch('systems.piloting.make_piloting_roll',return_value=PilotingResult(success=True)),patch.object(combat,'apply_damage_with_transfer',wraps=combat.apply_damage_with_transfer) as applied:
            jump.land_mech(u)
        expected=[(others[0],Location.CTORSO,n) for n in (5,5,4)]+[(u,Location.RLEG,2)]
        self.assertEqual(expected,[call.args for call in applied.call_args_list])
        self.assertEqual([True,True,True,False],[call.kwargs['is_critical'] for call in applied.call_args_list])
