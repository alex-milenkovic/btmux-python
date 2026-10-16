"""Boundary regressions from the source review, beyond the example tables."""
from unittest.mock import patch
from tests.movement_fixture import MovementTestCase
from entities.mech import CritStatus as C,MechStatus as S,MechStatus2 as S2,Location,FireMode,MoveType
from systems import heat,heat_control,vehicle_fire,ammo_dump
from core.randomness import use_source


class HeatDependencyEdges(MovementTestCase):
    def test_heat_banner_packets_follow_the_unit_source_profile(self):
        from entities.mech import UnitType
        for kind in (UnitType.MECH, UnitType.AERO):
            for old, new, prefix, width, label in ((0, 20, '%ch%cr', 37, 'RED!'), (0, 15, '%ch%cy', 39, 'YELLOW'), (20, 0, '%cg', 38, 'GREEN')):
                with self.subTest(kind=kind, color=label):
                    self.setUp()
                    self.unit.unit_type = kind
                    self.unit.set_status(S.LANDED)
                    self.unit.heat = old
                    self.unit.weap_heat = new + 10
                    result = heat.full_heat_update(self.unit, 1)
                    lines = [prefix + '=' * width, 'Your Excess Heat indicator turns ' + label, '=' * width + '%c']
                    expected = lines if kind == UnitType.AERO else ['\n'.join(lines)]
                    self.assertEqual(expected, result.messages)
                    self.assertEqual(expected, self.unit.movement_messages)

    def test_aircraft_heat_injury_notice_precedes_damage_and_shutdown(self):
        from entities.mech import UnitType
        self.unit.unit_type = UnitType.AERO
        self.unit.set_status(S.LANDED)
        self.unit.weap_heat = 40
        self.unit.set_crit_status(C.LIFE_SUPPORT_DESTROYED)
        effects = []
        with use_source(lambda name, low, high, fallback: high), patch('systems.movement_commands.notify', side_effect=lambda unit, text, audience=2: effects.append(text)), patch('systems.piloting.head_hit_mw_damage', side_effect=lambda *args: effects.append('injury effect')):
            heat.full_heat_update(self.unit, 30)
        self.assertEqual(['You take personal injury from heat!!', 'injury effect'], effects[:2])
        self.assertEqual(['%ch%cr' + '=' * 37, 'Your Excess Heat indicator turns RED!', '=' * 37 + '%c'], effects[2:5])
        self.assertEqual('%ci%crReactor shutting down...%c', effects[5])

    def test_aircraft_shutdown_uses_historical_sky_notice(self):
        from entities.mech import UnitType
        self.unit.unit_type = UnitType.AERO
        self.unit.move_type = MoveType.FLY
        with patch('physics.jump.mech_falls') as fall:
            heat.apply_shutdown(self.unit)
        self.assertEqual(['%ci%crReactor shutting down...%c', '%chYou fall from the sky!!!!!%c'], self.unit.movement_messages)
        self.assertFalse(fall.call_args.kwargs['notify_fall'])

    def test_landing_upright_with_breached_leg_floods_and_falls_quietly(self):
        from entities.map import WATER
        from physics.jump import land_mech
        self.board.set_terrain(10, 10, WATER)
        self.board.set_elevation(10, 10, 1)
        self.unit.terrain, self.unit.elev = WATER, 1
        self.unit.sections[Location.LLEG].armor = 0
        self.unit.set_status(S.JUMPING)
        with use_source(lambda name, low, high, fallback: high), patch('systems.sensors.los_broadcast') as los:
            land_mech(self.unit)
        self.assertTrue(self.unit.is_fallen)
        messages = [call.args[1] for call in los.call_args_list]
        self.assertEqual(1, messages.count('crashes to the ground!'))
        self.assertNotIn('falls down!', messages)
        self.assertTrue(any('water pours in!' in message for message in messages))

    def test_destroying_last_jet_suppresses_generic_fall_notice(self):
        from entities.crittypes import i2special, Special
        from systems.damage import destroy_parts
        self.unit.jump_mp = 1
        self.unit.jump_speed = 10.75
        self.unit.set_status(S.JUMPING)
        self.unit.sections[Location.LARM].criticals[4].type = i2special(Special.JUMP_JET)
        with patch('physics.jump.mech_falls') as fall, patch('systems.sensors.los_broadcast') as los:
            destroy_parts(self.unit, self.unit, Location.LARM, self.engine)
        fall.assert_called_once_with(self.unit, levels=1, notify_fall=False)
        self.assertIn('falls from the sky!', [call.args[1] for call in los.call_args_list])


    def test_unattributed_ammo_critical_cleans_bin_without_damage_or_injury(self):
        from entities.weapon import get_weapon
        from entities.crittypes import i2ammo
        from systems.criticals import apply_ammo_critical
        from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke
        section=self.unit.sections[Location.LTORSO]
        slot=section.criticals[0]
        slot.type,slot.data=i2ammo(get_weapon('IS.AC/10').index),2
        slot.firemode=FireMode.BROKEN_MODE|FireMode.DAMAGED_MODE
        set_part_temp_nuke(slot,3)
        before=[(s.armor,s.internal) for s in self.unit.sections]
        apply_ammo_critical(self.unit,Location.LTORSO,0,attacker=None,engine=self.engine)
        self.assertEqual((slot.data,slot.firemode,part_temp_nuke(slot)),(2,FireMode.DESTROYED_MODE,0))
        self.assertEqual([(s.armor,s.internal) for s in self.unit.sections],before)
        self.assertEqual(self.unit.pilot_hits,0)

    def test_heat_ammo_uses_weapon_identity_and_explicit_full_salvo(self):
        from entities import weapon as catalog
        from entities.weapon import Weapon, WeaponType, register_weapon
        from entities.crittypes import i2ammo
        with patch.dict(catalog.WEAPON_CATALOG), patch.object(catalog, 'WEAPON_INDEX', catalog.WEAPON_INDEX.copy()):
            weapon = register_weapon(Weapon('qa.unlisted.missile', weapon_type=WeaponType.TMISSILE,
                                            damage=2, missiles=6, ammo_per_ton=30))
            slot = self.unit.sections[Location.LTORSO].criticals[0]
            slot.type, slot.data = i2ammo(weapon.index), 4
            self.assertEqual(heat.find_ammo_bins(self.unit)[0].missiles_per_shot, 1)
            weapon.ammo_full_salvo = 3
            self.assertEqual(heat.find_ammo_bins(self.unit)[0].missiles_per_shot, 3)

    def test_heat_notifications_precede_overheat_shutdown(self):
        self.unit.weap_heat=40
        self.unit.set_crit_status(C.LIFE_SUPPORT_DESTROYED)
        messages=[]
        with use_source(lambda name,low,high,fallback:high), patch('systems.movement_commands.notify',side_effect=lambda unit,text,audience=2:messages.append(text)):
            heat.full_heat_update(self.unit,30)
        self.assertLess(messages.index('You take personal injury from heat!'),messages.index('%ci%crReactor shutting down...%c'))
        self.assertLess(next(i for i,m in enumerate(messages) if 'Your Excess Heat indicator turns RED!' in m),messages.index('%ci%crReactor shutting down...%c'))

    def test_part_destruction_clears_temporary_failure(self):
        from systems.criticals import _destroy_part
        from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke
        slot=self.unit.sections[Location.LTORSO].criticals[0]
        slot.firemode=FireMode.BROKEN_MODE|FireMode.DAMAGED_MODE
        slot.weap_damage_flags=12
        set_part_temp_nuke(slot,3)
        _destroy_part(slot)
        self.assertEqual(part_temp_nuke(slot),0)
        self.assertEqual(slot.weap_damage_flags,0)
        self.assertEqual(slot.firemode,FireMode.DESTROYED_MODE)

    def test_shutdown_cancels_stand_and_move_and_searchlight(self):
        from core.events import EventType
        self.engine.schedule_event(10,EventType.MOVE,lambda e:None,data=self.unit)
        self.unit._stand_event=self.engine.schedule_event(10,EventType.STAND,lambda e:None,data=self.unit)
        self.unit.set_status2(S2.SLITE_ON)
        self.unit.set_crit_status(C.SLITE_LIT)
        heat.apply_shutdown(self.unit)
        self.assertFalse(self.engine.has_event(EventType.MOVE,self.unit))
        self.assertFalse(self.engine.has_event(EventType.STAND,self.unit))
        self.assertFalse(self.unit.has_status2(S2.SLITE_ON))
        self.assertFalse(self.unit.has_crit_status(C.SLITE_LIT))

    def test_cutoff_uses_conditional_consciousness_and_pilot_identity(self):
        from entities.pilot import Pilot
        visitor=Pilot()
        self.unit.set_status(S.UNCONSCIOUS)
        self.assertFalse(heat_control.heat_cutoff(self.engine,self.unit,self.unit.pilot)[0])
        self.assertTrue(heat_control.heat_cutoff(self.engine,self.unit,visitor)[0])
        self.unit._cutoff_event.cancel();self.unit._cutoff_event=None
        self.unit.in_character=True
        self.assertFalse(heat_control.heat_cutoff(self.engine,self.unit,visitor)[0])
        visitor.wizard=True
        self.assertTrue(heat_control.heat_cutoff(self.engine,self.unit,visitor)[0])

    def test_disabled_command_creates_no_transition(self):
        self.engine.heatcutoff_enabled=False
        self.assertFalse(heat_control.heat_cutoff(self.engine,self.unit)[0])
        self.assertIsNone(self.unit._cutoff_event)

    def test_switching_is_capped_by_request_and_available_capacity(self):
        self.unit.disabled_sinks=1;self.unit.minus_heat=9
        self.assertEqual(heat_control.enable_some_sinks(self.unit,100),1)
        self.assertEqual(heat_control.enable_some_sinks(self.unit,100),0)
        self.assertEqual(heat_control.disable_some_sinks(self.unit,1),1)
        self.assertEqual(self.unit.minus_heat,9)

    def test_motive_reverse_speed_uses_walking_cap(self):
        from systems.vehicle_combat import motive_system_hit
        self.unit.move_type=MoveType.TRACK
        self.unit.speed=self.unit.desired_speed=-43
        with use_source(lambda *args:10):motive_system_hit(self.unit)
        self.assertEqual(self.unit.speed, __import__('core.randomness', fromlist=['float32']).float32(-(64.5-10.75)*2/3))
        self.assertEqual(self.unit.speed,self.unit.desired_speed)

    def test_smoke_replacement_cancels_old_expiry(self):
        from physics.decorations import add_smoke
        from entities.map import WATER,SMOKE
        self.board.set_terrain(10,10,WATER)
        old=add_smoke(self.engine,self.board,10,10,3)
        self.engine.run_ticks(2)
        add_smoke(self.engine,self.board,10,10,4)
        self.assertTrue(old['event'].zombie)
        self.engine.run_ticks(1)
        self.assertEqual(self.board.terrain(10,10),SMOKE)
        self.engine.run_ticks(3)
        self.assertEqual(self.board.terrain(10,10),WATER)

    def test_inferno_extension_keeps_remaining_event_time(self):
        from systems.missile import inferno_burn
        inferno_burn(self.engine,self.unit,10)
        self.engine.run_ticks(3)
        inferno_burn(None,self.unit,4)
        self.assertEqual(self.unit._burn_event.tick,14)

    def test_full_salvo_absent_entry_preserves_base_damage(self):
        from entities.weapon import Weapon,WeaponType
        w=Weapon('metadata',weapon_type=WeaponType.TMISSILE,damage=2,missiles=6)
        w.ammo_full_salvo=None
        self.assertEqual(ammo_dump.find_max_ammo_damage(w),2)
        w.ammo_full_salvo=6
        self.assertEqual(ammo_dump.find_max_ammo_damage(w),12)

    def test_full_salvo_looks_up_weapon_identity_not_rack_size(self):
        from entities.weapon import Weapon,WeaponType
        unknown=Weapon('unlisted',weapon_type=WeaponType.TMISSILE,damage=2,missiles=6)
        listed=Weapon('IS.SRM-6',weapon_type=WeaponType.TMISSILE,damage=2,missiles=1)
        self.assertEqual(ammo_dump.find_max_ammo_damage(unknown),2)
        self.assertEqual(ammo_dump.find_max_ammo_damage(listed),12)

    def test_airborne_shutdown_uses_gravity_adjusted_jump_mp(self):
        self.unit.set_status(S.JUMPING|S.UNDERGRAVITY)
        self.unit.jump_speed=43
        self.board.grav=200
        with patch('physics.jump.mech_falls') as fall:
            heat.apply_shutdown(self.unit)
        fall.assert_called_once_with(self.unit,2,notify_fall=False)
