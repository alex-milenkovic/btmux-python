"""Boundary branches beyond representative feature rows."""
import unittest
from entities.mech import Mech, UnitType as U, MoveType, Location as L, Specials, MechStatus as S, FireMode
from entities.crittypes import Special, i2special
from core.game_loop import GameEngine
from core.randomness import use_source
from core.events import EventType
from systems import damage, criticals
from systems.combat import apply_damage_with_transfer
from tests.test_damage_failures import Draws

class DamageSourceEdges(unittest.TestCase):
    def setUp(self):
        self.u=Mech.create_test_mech();self.e=GameEngine();self.e.register_entity(self.u)
        for section in self.u.sections:
            for slot in section.criticals:slot.type=0

    def test_airborne_engine_exhaustion_stops_thrust_and_schedules_fall(self):
        self.u.unit_type=U.AERO;self.u.move_type=MoveType.FLY;self.u.z=20
        self.u.sections[5].armor=5
        with use_source(Draws(7)):apply_damage_with_transfer(self.u,5,5,engine=self.e)
        self.assertEqual(0,self.u.max_speed)
        self.assertTrue(any(e.event_type==EventType.FALL for e in self.e.events._events.values()))

    def test_mw_armor_bypasses_ordinary_mech_armor(self):
        self.u.unit_type=U.MW
        self.u.sections[L.LTORSO].armor=3
        with use_source(Draws(7)):
            from systems.combat import apply_damage_to_location
            apply_damage_to_location(self.u,L.LTORSO,2)
        self.assertEqual(3,self.u.sections[L.LTORSO].armor)

    def test_repairability_uses_current_structure_not_stale_section_flags(self):
        self.u.sections[4].armor=self.u.sections[4].internal=0
        self.u.engine_heat=10
        criticals.handle_engine_critical(self.u,2)
        self.assertEqual('DESTROYED',self.u.kill_reason)

    def test_split_marker_crit_reaches_parent_without_independent_marker_destruction(self):
        from entities.weapon import get_weapon
        from entities.crittypes import i2weapon
        weapon=get_weapon('IS.AC/20')
        self.u.sections[L.LTORSO].criticals[0].type=i2weapon(weapon.index)
        marker=self.u.sections[L.LARM].criticals[0]
        marker.type=i2special(Special.SPLIT_CRIT_RIGHT);marker.data=0
        with use_source(Draws(12)):
            criticals.apply_critical_to_slot(self.u,L.LARM,0)
        self.assertTrue(self.u.sections[L.LTORSO].criticals[0].firemode&FireMode.DESTROYED_MODE)

    def test_cockpit_hit_cancels_events_and_clears_target(self):
        self.u.set_status(S.STARTED);self.u.target=99
        self.e.events.schedule(20,EventType.MOVE,lambda e:None,self.u)
        self.u.sections[7].criticals[0].type=i2special(Special.COCKPIT)
        criticals.apply_critical_to_slot(self.u,7,0,self.u)
        self.assertEqual(-1,self.u.target)
        self.assertIsNone(self.u.pilot)
        self.assertFalse(any(not e.zombie and e.data is self.u for e in self.e.events._events.values()))

    def test_incendiary_weapon_critical_requires_incendiary_bin(self):
        from entities.weapon import get_weapon
        from entities.crittypes import i2weapon,i2ammo
        from entities.mech import AmmoMode
        weapon=get_weapon('IS.AC/5')
        for slot in self.u.sections[2].criticals[:weapon.crits]:slot.type=i2weapon(weapon.index)
        self.u.sections[2].criticals[0].ammomode=AmmoMode.AC_INCENDIARY_MODE
        self.u.sections[2].criticals[0].data=20
        self.u.sections[3].criticals[0].type=i2ammo(weapon.index)
        self.u.sections[3].criticals[0].data=10
        with use_source(Draws(2)):
            result=criticals.apply_weapon_critical(self.u,2,0,self.u)
        self.assertFalse(self.u.sections[2].criticals[0].firemode&FireMode.DESTROYED_MODE)

    def test_internal_penetration_breaches_without_chance_roll(self):
        self.u.set_status(S.UNDERSPECIAL | S.UNDERVACUUM)
        self.u.sections[2].armor=1
        with use_source(Draws(7,7)):
            apply_damage_with_transfer(self.u,2,2,engine=self.e)
        from entities.mech import SectionConfig
        self.assertTrue(self.u.sections[2].config & SectionConfig.SECTION_BREACHED)

    def test_motive_destruction_cancels_standing(self):
        from systems.vehicle_combat import motive_system_hit
        self.u.unit_type=U.VEH_GROUND; self.u.move_type=MoveType.TRACK
        self.e.events.schedule(20,EventType.STAND,lambda e:None,self.u)
        with use_source(Draws(12)): motive_system_hit(self.u)
        self.assertFalse(any(not e.zombie and e.event_type==EventType.STAND for e in self.e.events._events.values()))

    def test_c3_counts_update_after_slot_destruction_without_duplicate_loss(self):
        for loc in (2,3):
            for slot in self.u.sections[loc].criticals[:5]:slot.type=i2special(Special.C3_MASTER)
        self.assertEqual(2,criticals.count_total_c3_masters(self.u))
        self.u.working_c3_masters=2
        criticals.apply_critical_to_slot(self.u,2,0)
        self.assertEqual(1,self.u.working_c3_masters)
        self.assertEqual(['%ch%cyCRITICAL HIT!!%c','One of your C3 systems has been destroyed!'],self.u.movement_messages)
        criticals.apply_critical_to_slot(self.u,2,1)
        self.assertEqual(1,self.u.working_c3_masters)
        self.assertEqual(2,self.u.total_c3_masters)
        self.assertEqual(['%ch%cyCRITICAL HIT!!%c','One of your C3 systems has been destroyed!',
                          '%ch%cyCRITICAL HIT!!%c','Your destroyed C3 system takes another hit!'],self.u.movement_messages)

    def test_c3_total_counts_broken_groups_independently_of_working_count(self):
        for slot in self.u.sections[2].criticals[:10]:slot.type=i2special(Special.C3_MASTER)
        self.u.sections[2].criticals[0].firemode|=FireMode.DESTROYED_MODE
        self.assertEqual(2,criticals.count_total_c3_masters(self.u))
        # The source intentionally retains the cumulative working-slot count.
        self.assertEqual(0,criticals.count_working_c3_masters(self.u))
