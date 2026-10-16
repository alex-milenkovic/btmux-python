"""Focused completion rules, with independent C boundary expectations."""
import unittest

from core.events import EventType
from core.game_loop import GameEngine
from entities.map import GameMap
from entities.mech import Mech, MechStatus as S, CritStatus as C, Specials
from entities.pilot import Pilot
from systems.los import MECHLOSFLAG_SEEN, MECHLOSFLAG_SEESP, MECHLOSFLAG_SEEC2


SEES = MECHLOSFLAG_SEEN | MECHLOSFLAG_SEESP | MECHLOSFLAG_SEEC2


class SensorFixture(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.map = GameMap(80, 60)
        self.map._id = 100
        self.engine.register_entity(self.map)
        self.map.mapvis, self.map.maxvis, self.map.maplight = 30, 60, 2
        self.map.losinfo = {}
        self.a = self.unit('aa', 2, 1, 1)
        self.b = self.unit('bb', 2, 16, 2)
        self.a.facing = 180
        self.map.losinfo[self.a._id, self.b._id] = SEES

    def unit(self, name, x, y, team):
        u = Mech.create_test_mech(name)
        u.pilot = Pilot()
        u.team = team
        u.set_hex_position(x, y)
        u.set_status(S.STARTED)
        self.map.add_mech(u)
        self.engine.register_entity(u)
        return u


class TestSightCompletion(SensorFixture):
    def test_artillery_sight_uses_artillery_skill_and_adjustment(self):
        from entities.weapon import WEAPON_INDEX,WeaponType
        from entities.mech import WeaponState
        from entities.crittypes import i2weapon
        from systems.combat import fire_weapon_number
        index = next(i for i,w in enumerate(WEAPON_INDEX) if w.weapon_type == WeaponType.TARTILLERY)
        self.a.weapons.append(WeaponState(section=4,critical=0,weapon_idx=index))
        self.a.sections[4].criticals[0].type = i2weapon(index)
        self.a.targ_x,self.a.targ_y = 2,3
        self.a.set_status(S.LOCK_TARGET)
        self.a.pilot.artillery = 6
        self.a.fire_adjustment = 2
        result = fire_weapon_number(self.engine,self.a,0,sight=True,to_hit_roll=7)
        self.assertIsNotNone(result.bth_breakdown,result.messages)
        self.assertEqual(result.bth,9)  # 11 + (6-4) - 2 direct - 2 adjustment
        self.assertIsNone(result.target_id)
        self.assertFalse(result.hit)
        self.a.target=self.b._id
        result=fire_weapon_number(self.engine,self.a,0,sight=True,to_hit_roll=7)
        self.assertIsNone(result.bth_breakdown)
        self.assertIn('only target hexes',result.messages[0])

    def test_sight_needs_no_ammo_and_does_not_fire_recycling_weapon(self):
        from entities.weapon import WEAPON_INDEX
        from entities.mech import WeaponState
        from entities.crittypes import i2weapon
        from systems.combat import fire_weapon_number
        index = next(i for i,w in enumerate(WEAPON_INDEX) if w.name == 'IS.LRM-10')
        self.a.weapons.append(WeaponState(section=4,critical=0,weapon_idx=index))
        for crit in range(WEAPON_INDEX[index].crits):
            self.a.sections[4].criticals[crit].type = i2weapon(index)
        slot = self.a.sections[4].criticals[0]
        slot.type, slot.data = i2weapon(index), 8
        self.a.target = self.b._id
        before = [s.armor for s in self.b.sections]
        result = fire_weapon_number(self.engine,self.a,0,sight=True,to_hit_roll=7)
        self.assertIsNotNone(result.bth_breakdown,result.messages)
        self.assertEqual(result.target_id,self.b._id)
        self.assertTrue(result.messages[0].startswith('You aim '))
        self.assertEqual(result.roll,7)
        self.assertEqual(slot.data,8)
        self.assertEqual(self.a.weap_heat,0)
        self.assertFalse(self.a.has_status(S.FIRED))
        self.assertEqual(before,[s.armor for s in self.b.sections])


class TestTagCompletion(SensorFixture):
    def test_semiguided_sight_before_stabilization_after_stabilization_and_break(self):
        from entities.weapon import WEAPON_INDEX
        from entities.mech import WeaponState,AmmoMode
        from entities.crittypes import i2weapon
        from systems.combat import fire_weapon_number
        from systems.targeting import tag,stop_tag
        index=next(i for i,w in enumerate(WEAPON_INDEX) if w.name=='IS.LRM-10')
        self.a.weapons.append(WeaponState(section=4,critical=0,weapon_idx=index))
        for crit in range(WEAPON_INDEX[index].crits):
            self.a.sections[4].criticals[crit].type=i2weapon(index)
        slot=self.a.sections[4].criticals[0]
        slot.type,slot.ammomode=i2weapon(index),AmmoMode.SGUIDED_MODE
        self.a.target=self.b._id
        self.b.speed=75.25
        tagger=self.unit('cc',2,1,1)
        tagger.specials2|=0x8000
        self.map.losinfo[tagger._id,self.b._id]=SEES
        def movement():
            result=fire_weapon_number(self.engine,self.a,0,sight=True,to_hit_roll=7)
            self.assertIsNotNone(result.bth_breakdown,result.messages)
            return result.bth_breakdown.target_move
        self.assertEqual(movement(),3)
        self.assertTrue(tag(self.engine,tagger,self.b)[0])
        self.assertEqual(movement(),0)
        self.engine.run_ticks(30)
        self.assertEqual(movement(),0)
        stop_tag(tagger)
        self.assertEqual(movement(),3)

    def test_link_stabilize_cancel_and_cooldown(self):
        from systems.targeting import tag, tag_recycling
        self.a.specials2 |= 0x8000
        self.assertTrue(tag(self.engine, self.a, self.b)[0])
        self.assertEqual((self.a.tag_target, self.b.tagged_by), (self.b._id, self.a._id))
        self.engine.run_ticks(29)
        self.assertFalse(tag(self.engine, self.a, '-')[0])
        self.engine.run_ticks(1)
        self.assertFalse(tag_recycling(self.engine, self.a))
        self.assertTrue(any('stable lock' in m for m in self.a.movement_messages))
        self.assertTrue(tag(self.engine, self.a, '-')[0])
        self.assertEqual((self.a.tag_target, self.b.tagged_by), (0, 0))
        self.engine.run_ticks(29)
        self.assertTrue(tag_recycling(self.engine, self.a))
        self.engine.run_ticks(1)
        self.assertFalse(tag_recycling(self.engine, self.a))
        self.assertTrue(any('finished recycling' in m for m in self.a.movement_messages))

    def test_overwrite_does_not_clear_other_owner(self):
        from systems.targeting import tag, check_tag
        self.a.specials2 |= 0x8000
        tag(self.engine, self.a, self.b)
        self.b.tagged_by = 999
        check_tag(self.a)
        self.assertEqual(self.a.tag_target, 0)
        self.assertEqual(self.b.tagged_by, 999)
        self.assertTrue(self.engine.has_event(EventType.TAG_RECYCLE, self.a))

    def test_range_and_equipment_boundaries(self):
        from systems.targeting import tag, is_tag_destroyed
        self.a.specials |= Specials.C3_MASTER_TECH
        self.a.crit_status |= C.C3_DESTROYED
        self.assertTrue(is_tag_destroyed(self.a))
        self.assertFalse(tag(self.engine, self.a, self.b)[0])
        self.a.crit_status &= ~C.C3_DESTROYED
        self.b.set_hex_position(2, 17)
        self.assertFalse(tag(self.engine, self.a, self.b)[0])
        self.b.set_hex_position(2, 16)
        self.assertTrue(tag(self.engine, self.a, self.b)[0])


class TestLightCompletion(SensorFixture):
    def test_warmup_and_stopped_callback(self):
        from systems.sensors import slite
        self.a.specials |= Specials.SLITE_TECH
        self.assertTrue(slite(self.engine, self.a)[0])
        self.assertFalse(slite(self.engine, self.a)[0])
        self.engine.run_ticks(4)
        self.assertFalse(self.a.status2 & 0x20)
        self.a.clear_status(S.STARTED)
        self.engine.run_ticks(1)
        self.assertFalse(self.a.status2 & 0x20)

    def test_acquisition_and_retention_at_thirty(self):
        from systems.sensors import cause_lite, end_lite_check
        self.a.status2 |= 0x20
        self.b.sl_warn = True
        self.b.set_hex_position(2, 31)
        cause_lite(self.a, self.b)
        self.assertTrue(self.b.crit_status & C.SLITE_LIT)
        end_lite_check(self.b)
        self.assertTrue(self.b.crit_status & C.SLITE_LIT)
        self.a.status2 &= ~0x20
        end_lite_check(self.b)
        end_lite_check(self.b)
        self.assertFalse(self.b.crit_status & C.SLITE_LIT)
        self.assertEqual(len(self.b.movement_messages), 2)


class TestSensorControlsCompletion(SensorFixture):
    def test_flag_diagnostic_and_light_map_bounds(self):
        from systems.sensors import dump_flag
        self.assertEqual(dump_flag(0),'')
        self.assertEqual(dump_flag(0x80000009),'0,3,31')

    def test_gain_publishes_visibility_before_apparent_friend_notice(self):
        from systems.sensors import update_los_info
        self.b.team = self.a.team
        self.b.set_hex_position(2,2)
        self.a.brief = 4
        self.map.losinfo.clear()
        update_los_info(self.map)
        self.engine.run_ticks(1)
        messages = [m for m in self.a.movement_messages if 'Seen:' in m]
        self.assertEqual(len(messages),1)
        self.assertFalse(messages[0].startswith('%cr'))

    def test_invalid_map_los_notifies_and_repairs_index(self):
        from systems.los import in_line_of_sight
        self.map.remove_mech(self.a)
        self.a.mapindex = 99
        self.assertEqual(in_line_of_sight(self.a,None,2,2,1),0)
        self.assertEqual(self.a.mapindex,-1)
        self.assertIn('You are on an invalid map! Map index reset!',self.a.movement_messages)

    def test_pending_readout_and_legacy_bounds(self):
        from systems.targeting import set_sensors, show_sensor, sensor_info
        set_sensors(self.engine,self.a,'I E')
        text = show_sensor(self.engine,self.a,True)
        self.assertIn('Blocked by:',text)
        self.assertIn('Wanted',text)
        self.assertIn('Infrared',text)
        self.assertEqual(sensor_info(self.engine,self.a),'vvSR')
        self.a.specials2 |= 0x800
        set_sensors(self.engine,self.a,'H H')
        with self.assertRaises(ValueError): sensor_info(self.engine,self.a)

    def test_configured_weather_and_asymmetric_light_reset(self):
        from entities.map import map_update
        self.a.sensor = [1,1]
        self.map.maplight = 0
        self.map.visibility_config = '90 2 70 8 150 weather changed'
        self.engine.events.set_tick(25)
        map_update(self.engine,self.map)
        self.assertEqual(self.a.sensor,[0,1])
        self.assertEqual((self.map.mapvis,self.map.maxvis,self.map.winddir,self.map.windspeed,self.map.cloudbase),(60,60,70,8,150))
        self.assertIn('weather changed',self.a.movement_messages)

    def test_dropship_heights_and_scaled_infrared(self):
        from entities.mech import UnitType,MoveType
        from systems.los import actual_elevation,MECHLOSFLAG_PARTIAL
        from systems.sensors import infrared_tohit
        self.a.unit_type,self.a.move_type = UnitType.DS,MoveType.FLY
        self.assertEqual(actual_elevation(self.map,2,1,self.a),2.5)
        self.a.unit_type = UnitType.SPHEROID_DS
        self.assertEqual(actual_elevation(self.map,2,1,self.a),4.5)
        self.b.set_status(S.HULLDOWN)
        self.map.infrared_profile='scaled'
        self.b.plus_heat,self.b.minus_heat = 20,10
        self.assertEqual(infrared_tohit(self.a,self.b,self.map,MECHLOSFLAG_PARTIAL,2),3)
        self.map.infrared_profile='unscaled'
        self.assertEqual(infrared_tohit(self.a,self.b,self.map,MECHLOSFLAG_PARTIAL,2),7)

    def test_real_blind_deadline_and_notice_preferences(self):
        from systems.sensors import scramble_infra_and_liteamp,valid_to_notice
        self.a.sensor=[2,0]
        self.b.set_hex_position(2,2)
        scramble_infra_and_liteamp(self.b,4,0,'Infra flash','Light flash')
        self.assertTrue(self.a.has_status(S.BLINDED))
        self.engine.run_ticks(3)
        self.assertTrue(self.a.has_status(S.BLINDED))
        self.engine.run_ticks(1)
        self.assertFalse(self.a.has_status(S.BLINDED))
        self.assertIn('Your sight recovers.',self.a.movement_messages)
        for mode,expected in [(0,3),(1,6),(2,3),(3,6),(4,4),(5,4),(6,0)]:
            self.a.brief=mode*4
            self.assertEqual(valid_to_notice(self.a,self.b,1),expected)

    def test_register_starts_only_one_chain_and_populates_perception(self):
        self.engine.register_entity(self.a)
        self.assertTrue(self.engine.has_event(EventType.PLOS,self.a))
        self.assertEqual(self.a.per,6)
        self.a.clear_status(S.STARTED)
        self.engine.run_ticks(1)
        self.assertFalse(self.engine.has_event(EventType.PLOS,self.a))


class TestSpotCompletion(SensorFixture):
    def test_handshake_notice_uses_shooter_identity_as_seen_by_observer(self):
        from systems.spot import spot_lock_event
        from types import SimpleNamespace
        self.a.contact_id = 'AA'
        event=SimpleNamespace(data=self.a,data2=(self.engine,self.b,(self.a.fx,self.a.fy,self.b.fx,self.b.fy)))
        spot_lock_event(event)
        self.assertIn('Data link established with something [AA], you now have a forward observer.',self.a.movement_messages)
        self.map.losinfo[self.b._id,self.a._id]=SEES
        spot_lock_event(event)
        self.assertIn('Data link established with aa [AA], you now have a forward observer.',self.a.movement_messages)

    def test_ordinary_link_never_arms_watchdog(self):
        from systems.spot import mech_spot
        self.b.team=self.a.team
        self.b.spotter=self.b._id
        self.assertTrue(mech_spot(self.engine,self.a,self.b)[0])
        self.assertFalse(self.engine.has_event(EventType.SPOT_CHECK,self.a))

    def test_artillery_handshake_all_coordinates_must_change(self):
        from systems.spot import mech_spot
        from entities.weapon import get_weapons_by_type,WeaponType,WEAPON_INDEX
        artillery=get_weapons_by_type(WeaponType.TARTILLERY)[0]
        from entities.mech import WeaponState
        self.a.weapons=[WeaponState(weapon_idx=next(i for i,w in enumerate(WEAPON_INDEX) if w is artillery))]
        self.b.team=self.a.team
        self.b.spotter=self.b._id
        self.b.radio_range=10
        self.map.losinfo={}
        self.assertTrue(mech_spot(self.engine,self.a,self.b)[0])
        self.a.fx+=1
        self.engine.run_ticks(11)
        self.assertEqual(self.a.spotter,-1)
        self.engine.run_ticks(1)
        self.assertEqual(self.a.spotter,self.b._id)
        self.assertTrue(self.engine.has_event(EventType.SPOT_CHECK,self.a))
        self.b.spotter=999
        self.engine.run_ticks(10)
        self.assertEqual(self.a.spotter,self.b._id)

    def test_target_commands_clear_linked_adjustments(self):
        from systems.targeting import clear_target,set_target_hex
        self.a.spotter=self.a._id
        self.b.spotter=self.a._id
        for action in [lambda:clear_target(self.a,self.engine),lambda:set_target_hex(self.engine,self.a,3,3)]:
            self.b.fire_adjustment=5
            action()
            self.assertEqual(self.b.fire_adjustment,0)

    def test_semiguided_movement_keeps_negative_and_dangling_quirk(self):
        from systems.combat import calculate_bth
        from entities.weapon import get_weapon_by_index
        from entities.mech import AmmoMode
        weapon=get_weapon_by_index(0)
        self.b.speed=75.25
        self.b.tagged_by=999999
        result=calculate_bth(self.a,self.b,weapon,15,w_ammo_mode=AmmoMode.SGUIDED_MODE)
        self.assertEqual(result.target_move,0)
        self.b.tagged_by=self.a._id
        result=calculate_bth(self.a,self.b,weapon,15,w_ammo_mode=AmmoMode.SGUIDED_MODE)
        self.assertEqual(result.target_move,3)


class TestECMCompletion(SensorFixture):
    def test_live_section_predicate_and_mark_assignment(self):
        from systems.ecm import check_section_for_special,mark_for_los_update
        self.a.sections[0].specials=8
        self.a.sections[0].armor=1
        self.a.sections[0].internal=0
        self.assertEqual(check_section_for_special(self.a,8,0),1)
        self.a.sections[0].armor=0
        self.assertEqual(check_section_for_special(self.a,8,0),0)
        self.a.mapflag=8
        mark_for_los_update(self.a)
        self.assertEqual(self.a.mapflag,1)

    def test_missing_equipment_still_marks_but_stopped_does_not(self):
        from systems.ecm import mech_ecm
        self.a.mapflag=0
        mech_ecm(self.a)
        self.assertEqual(self.a.mapflag,1)
        self.a.mapflag=0
        self.a.clear_status(S.STARTED)
        mech_ecm(self.a)
        self.assertEqual(self.a.mapflag,0)

    def test_equipment_critical_dispatch_and_bloodhound_quirk(self):
        from systems.criticals import handle_critical_hit,EquipmentType
        from entities.mech import Location
        self.a.specials|=Specials.ECM_TECH
        self.a.status2|=1|2|0x40
        result=handle_critical_hit(self.a,Location.CTORSO,EquipmentType.ECM)
        self.assertTrue(result.effect_applied)
        self.assertEqual(self.a.status2 & (1|2|0x40),0)
        self.a.specials2|=0x800
        self.a.sensor=[8,8]
        handle_critical_hit(self.a,Location.CTORSO,EquipmentType.BLOODHOUND_PROBE)
        self.assertFalse(self.a.specials2 & 0x800)
        self.assertEqual(self.a.sensor,[8,8])


class TestSensorIdentity(unittest.TestCase):
    def test_live_units_never_share_identity_after_allocation_churn(self):
        units=[]
        for i in range(100):
            units.append(Mech.create_test_mech(str(i)))
            scratch=[object() for _ in range(10)]
            del scratch
        self.assertEqual(len({u._id for u in units}),100)
