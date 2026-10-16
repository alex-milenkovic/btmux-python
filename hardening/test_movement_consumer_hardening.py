"""Movement-state integration with heat, targeting, damage and physical gates."""
import unittest
from unittest.mock import patch
from acceptance.movement.context import fresh
from entities.mech import Mech, MechStatus2 as S2, Location, UnitType
from core.events import EventType
from systems import targeting, heat, physical, damage, combat
from systems.los import MECHLOSFLAG_SEESP, MECHLOSFLAG_SEEC2
from systems.movement_commands import schedule_mode


def ready():
    w={};fresh(w);return w


class TestMovementConsumers(unittest.TestCase):
    def test_both_stride_modes_generate_heat_for_any_nonzero_signed_speed(self):
        for flag in (S2.SPRINTING,S2.EVADING):
            for speed in (-.01,0,.01):
                w=ready();u=w['unit'];u.set_status2(flag);u.speed=speed
                self.assertEqual(3 if speed else 0,heat.calculate_movement_heat(u))
        w=ready();u=w['unit'];u.speed=10
        self.assertEqual(1,heat.calculate_movement_heat(u))

    def test_swarm_target_accepts_host_object_or_id_and_rejects_other_targets(self):
        for representation in ('object','id',None,0,-1):
            for same_host in (True,False):
                w=ready();u=w['unit'];u.unit_type=UnitType.BSUIT
                host=Mech.create_test_mech();host._id=20;host.set_hex_position(3,4);w['map'].add_mech(host)
                target=host
                if not same_host:
                    target=Mech.create_test_mech();target._id=21;target.set_hex_position(3,5);w['map'].add_mech(target)
                w['map'].losinfo={(u._id,target._id):MECHLOSFLAG_SEESP|MECHLOSFLAG_SEEC2}
                u.swarm_target=host if representation=='object' else host._id if representation=='id' else representation
                result=targeting.set_target(w['engine'],u,target)
                allowed=same_host or representation not in ('object','id')
                self.assertEqual(allowed,result[0])
                if allowed:self.assertEqual(target._id,u.target)
                else:self.assertEqual("You're a bit too busy holding on for dear life to lock a target!",result[1])

    def test_hex_lock_refuses_a_mounted_unit_but_accepts_empty_sentinels(self):
        for value in (None,0,-1,20,Mech.create_test_mech()):
            w=ready();u=w['unit'];u.unit_type=UnitType.BSUIT;u.swarm_target=value
            result=targeting.set_target_hex(w['engine'],u,3,4,'H')
            self.assertEqual(value in (None,0,-1),result[0])
            if value not in (None,0,-1):self.assertEqual("You're a bit too busy holding on for dear life to lock a target!",result[1])

    def test_physical_guard_checks_standing_dodge_and_pending_mode_independently(self):
        for condition in ('stand','dodge','mode','expired'):
            w=ready();u=w['unit']
            if condition in ('stand','expired'):
                u._stand_event=w['engine'].schedule_event(10,EventType.STAND,lambda e:None,data=u)
                if condition=='expired':u._stand_event.cancel()
            if condition=='dodge':u.set_status2(S2.DODGING)
            if condition=='mode':schedule_mode(w['engine'],u,S2.SPRINTING,True)
            result=physical.phys_common_checks(u)
            self.assertEqual(condition=='expired',result[0])
            if condition=='stand':self.assertEqual('You are still trying to stand up!',result[1])
            if condition in ('mode','dodge'):self.assertEqual('You cannot use physicals while using a special movement mode.',result[1])

    def test_positive_damage_interrupts_modes_but_zero_damage_preserves_them(self):
        for operation in ('internal','external'):
            for amount in (0,1):
                w=ready();u=w['unit'];u.set_status2(S2.SPRINTING)
                with patch('systems.combat.roll_2d6',return_value=7):
                    if operation=='internal':damage.cause_internal_damage(u,u,Location.CTORSO,amount,crits_already_rolled=True)
                    else:combat.apply_damage_with_transfer(u,Location.CTORSO,amount,attacker=u)
                self.assertEqual(amount==0,u.has_status2(S2.SPRINTING))

    def test_positive_swarm_host_id_one_blocks_locking_another_target(self):
        for object_form in (False,True):
            w=ready();u=w['unit'];u._id=10;u.unit_type=UnitType.BSUIT
            host=Mech.create_test_mech();host._id=1;host.set_hex_position(3,4);w['map'].add_mech(host)
            target=Mech.create_test_mech();target._id=21;target.set_hex_position(3,5);w['map'].add_mech(target)
            w['map'].losinfo={(10,21):MECHLOSFLAG_SEESP|MECHLOSFLAG_SEEC2}
            u.swarm_target=host if object_form else 1
            self.assertEqual((False,"You're a bit too busy holding on for dear life to lock a target!"),targeting.set_target(w['engine'],u,target))


    def test_jump_heat_uses_persistent_jump_capability_and_minimum(self):
        from physics import jump
        for capability,expected in ((1,3),(4,4),(6,6)):
            w=ready();u=w['unit'];u.jump_mp=capability
            self.assertTrue(jump.mech_jump(u,3,4).success)
            self.assertAlmostEqual(expected,heat.calculate_movement_heat(u),delta=1e-5)


    def test_trip_refuses_a_target_with_a_live_stand_event(self):
        from entities.mech import MechStatus as S
        for state in ('live','expired','legacy'):
            w=ready();u=w['unit'];u._id=10
            target=Mech.create_test_mech();target._id=20;target.set_hex_position(3,3);target.set_status(S.STARTED);target.fy=u.fy-10
            w['map'].add_mech(target)
            w['map'].losinfo={(10,20):MECHLOSFLAG_SEESP|MECHLOSFLAG_SEEC2}
            target._stand_event=w['engine'].schedule_event(10,EventType.STAND,lambda e:None,data=target)
            if state!='live':target._stand_event.cancel()
            if state=='legacy':target.standing_up=True
            result=physical.physical_attack(u,5,3,physical.PhysicalAttackType.TRIP,Location.RLEG,target,roll=2,location_roll=1)
            if state!='expired':self.assertEqual(['Your target is already down!'],result.messages)
            else:
                self.assertNotIn('Your target is already down!',result.messages)
                self.assertTrue(result.success,result.messages)

    def test_physical_guard_preserves_the_legacy_standing_state(self):
        w=ready();u=w['unit'];u.standing_up=True
        self.assertEqual((False,'You are still trying to stand up!'),physical.phys_common_checks(u))


    def test_cocoon_interception_requires_positive_armor_and_includes_one_point(self):
        for initial,expected_cocoon,expected_armor in ((0,0,15),(-1,-1,15),(1,-1,20)):
            w=ready();u=w['unit'];u.cocoon=initial;u.z=10;u.jump_mp=1
            u.sections[Location.CTORSO].armor=20
            with patch.object(combat,'roll_2d6',return_value=9):
                dealt=combat.apply_damage_with_transfer(u,Location.CTORSO,5,attacker=u)
            self.assertEqual((expected_cocoon,expected_armor),(u.cocoon,u.sections[Location.CTORSO].armor))
            self.assertEqual(0 if initial>0 else 5,dealt)

    def test_target_mode_adjustment_adds_to_existing_weapon_bth(self):
        from entities.weapon import IS_MEDIUM_LASER
        for flag,expected in ((S2.SPRINTING,-2),(S2.EVADING,3),(S2.DODGING,2),(S2.NONE,2)):
            w=ready();u=w['unit'];u.base_to_hit=2;target=Mech.create_test_mech();target.set_status2(flag)
            result=combat.calculate_bth(u,target,IS_MEDIUM_LASER,1)
            self.assertEqual(expected,result.other_mods)
        w=ready();u=w['unit'];u.base_to_hit=2
        self.assertEqual(2,combat.calculate_bth(u,None,IS_MEDIUM_LASER,1).other_mods)

    def test_weapons_refuse_active_stride_modes_and_pending_mode_events(self):
        from data.templates import create_mech_from_template,get_template
        from entities.mech import MechStatus as S
        for condition in ('sprint','evade','pending'):
            w=ready();u=create_mech_from_template(get_template('TestMech'));u.set_status(S.STARTED)
            if condition=='sprint':u.set_status2(S2.SPRINTING)
            if condition=='evade':u.set_status2(S2.EVADING)
            if condition=='pending':schedule_mode(w['engine'],u,S2.SPRINTING,True)
            weapon=u.weapons[0];slot=u.sections[weapon.section].criticals[weapon.critical]
            before=(slot.data,u.weap_heat)
            result=combat.fire_weapon(u,Mech.create_test_mech(),0,1)
            self.assertEqual(['Movement modes disallow weapons fire.'],result.messages)
            self.assertEqual(before,(slot.data,u.weap_heat))

    def test_surface_weapon_dispatch_reports_unknown_indices_and_ignores_other_terrain(self):
        from acceptance.movement.context import set_hex
        from entities.map import GRASSLAND,ICE,BRIDGE
        for name,terrain in (('possibly_blow_ice','ICE'),('possibly_blow_bridge','BRIDGE')):
            w=ready();u=w['unit'];action=getattr(combat,name)
            set_hex(w,terrain,2,(4,4))
            with self.assertRaisesRegex(ValueError,'^Unknown weapon index$'):
                action(u,10**9,4,4)
            set_hex(w,'GRASSLAND',2,(4,4))
            # A terrain-mismatched dispatcher must not even look up the weapon.
            action(u,10**9,4,4)
            self.assertEqual(GRASSLAND,w['map'].terrain(4,4))
