"""Combat consumers retain source catalog identity and multi-hit routing."""
import unittest
from unittest.mock import patch
from tools.combat_resolution import CombatSession
from entities.mech import FireMode as F, Location as L
from entities.weapon import get_weapon
from systems import combat,tic,artillery


class RemainingConsumersTest(unittest.TestCase):
    def test_tic_explicit_contact_reaches_weapon_fire(self):
        s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0],
            'weapons':['IS.MediumLaser']},{'name':'v','at':[3,2,0],'team':2}]})
        u,v=s.units.values();u.tics[0].add(0);v.contact_id='BB'
        s.streams.update(attack_rolls=[12],hit_location_rolls=[7],damage_entry=[7])
        messages=s.invoke(tic.fire_tic,s.engine,u,'0','BB')
        self.assertEqual(1,u.shots_fired)
        self.assertGreater(v.damage_taken,0)

    def test_rac_hex_hits_route_every_slug(self):
        s=CombatSession({'actions':[]});u=s.units['u']
        with patch('systems.combat.hex_hit') as hit:
            s.invoke(combat.resolve_attack,u,None,get_weapon('IS.RotaryAC/5'),1,2,
                     to_hit_roll=12,cluster_roll=12,w_fire_mode=F.RAC_FOURSHOT_MODE,mapx=4,mapy=4)
        self.assertEqual(4,hit.call_count)
        self.assertEqual([5]*4,[c.args[5] for c in hit.call_args_list])

    def test_artillery_word_uses_c_indices_not_python_catalog_numbers(self):
        from types import SimpleNamespace
        for name,word in (('CL.ATM-12','a missile'),('CL.ArrowIVSystem','a round')):
            self.assertEqual(word,artillery.artillery_type(SimpleNamespace(weapon_index=get_weapon(name).index)))

    def test_nonmissile_miss_can_strike_battlearmor_host(self):
        from entities.mech import UnitType
        s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0]},
            {'name':'v','at':[3,2,0],'team':2},{'name':'host','at':[3,2,0],'team':2}]})
        u,v,host=s.units.values();v.unit_type=UnitType.BSUIT;v.swarm_target=host._id
        host.facing=host.desired_facing=180
        u.target=host._id  # redirected shot uses the stable host lock
        u.pilot.gunnery=0;s.streams.update(hit_location_rolls=[7],damage_entry=[7])
        r=s.invoke(combat.resolve_attack,u,v,get_weapon('IS.MediumLaser'),1,6,to_hit_roll=6)
        self.assertTrue(r.hit)
        self.assertEqual(host._id,r.target_id)
        self.assertEqual(0,v.damage_taken)
        self.assertEqual(3,host.damage_taken)

    def test_fired_target_receives_warning_and_bth_debug_is_opt_in(self):
        s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0],
            'prefs':512,'weapons':['IS.MediumLaser']},{'name':'v','at':[3,2,0],'team':2}]})
        u,v=s.units.values();s.streams.update(attack_rolls=[12],hit_location_rolls=[7],damage_entry=[7])
        s.invoke(combat.fire_weapon_number,s.engine,u,0)
        self.assertTrue(any('has fired' in m for m in v.movement_messages))
        self.assertTrue(any('BTHDebug:' in m for m in u.pilot.inbox))

    def test_building_damage_records_missing_object_service(self):
        s=CombatSession({'actions':[]});u=s.units['u']
        s.invoke(combat.hit_building,u,4,4,get_weapon('IS.MediumLaser').index,5)
        self.assertTrue(any('building' in e['service'].lower() and not e['applied'] for e in u.external_effects))

    def test_prone_command_triggers_step_mines(self):
        s=CombatSession({'actions':[],'map':{'mines':[{'x':3,'y':3,'type':'Standard','strength':8}]}})
        s.streams.update(physical_location=[3],damage_entry=[7])
        s.action({'op':'command','name':'prone'})
        self.assertEqual(5,s.units['u'].damage_taken)
        self.assertEqual(5,s.map.mines[0].strength)

    def test_ams_catches_up_other_recycles_before_setting_fresh_timer(self):
        from systems.missile import locate_ams_defenses
        s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0]},
            {'name':'v','at':[3,2,0],'team':2,'weapons':[{'name':'IS.Anti-MissileSystem','section':'RT','metadata':{'crits':1}}],
             'ammo':[{'weapon':'IS.Anti-MissileSystem','rounds':10}]}]})
        from entities.mech import MechStatus,Specials
        v=s.units['v'];v.status|=MechStatus.AMS_ENABLED;v.specials|=Specials.IS_ANTI_MISSILE_TECH
        v.sections[L.LARM].recycle=10
        s.engine.events.set_tick(5)
        defense=s.invoke(locate_ams_defenses,v)
        self.assertIsNotNone(defense)
        self.assertEqual(5,v.sections[L.LARM].recycle)
        self.assertEqual(defense.weapon.vrt,v.sections[L.RTORSO].criticals[0].data)

    def test_physical_result_is_broadcast_to_visible_observer_and_target_warned(self):
        from systems.physical import mech_punch
        s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0]},
            {'name':'v','at':[3,2,0],'team':2},{'name':'watcher','at':[4,3,0]}]})
        u,v,watcher=s.units.values();v.fx=u.fx;v.fy=u.fy-100
        s.streams.update(physical_attack=[12],physical_location=[3],damage_entry=[7])
        s.invoke(mech_punch,u,v,arm='r')
        self.assertTrue(any('tries to punch you' in m for m in v.movement_messages))
        self.assertTrue(any('punchs' in m for m in watcher.movement_messages))
        self.assertFalse(any('punchs' in m for m in v.movement_messages))

    def test_c3_track_notice_ignores_own_reference(self):
        from systems.combat_ranges import send_c3_track_emit
        s=CombatSession({'actions':[]});u,v=s.units.values()
        s.invoke(send_c3_track_emit,u,u._id)
        self.assertFalse(any('Using range data' in m for m in u.movement_messages))
        s.invoke(send_c3_track_emit,u,v._id)
        self.assertTrue(any('Using range data from v [01]' in m for m in u.movement_messages))

    def test_hex_scan_runs_mine_discovery_alongside_building_query(self):
        s=CombatSession({'actions':[],'map':{'mines':[{'x':3,'y':1,'type':'Standard','strength':8}]}})
        s.units['u'].in_character=True
        s.units['u'].pilot._id=50;s.units['u'].pilot.location=s.units['u']._id
        s.streams.update(mine_discovery=[9],perception_rolls=[12])
        r=s.action({'op':'command','name':'scan','args':['3','1','H']})
        self.assertTrue(r['mines_found'])
        self.assertTrue(r['building_queried'])
        self.assertTrue(any('bomblets' in m for m in s.units['u'].movement_messages))

    def test_failed_mine_discovery_reports_empty_hex(self):
        s=CombatSession({'actions':[]})
        s.action({'op':'diagnose','kind':'mine-discovery','options':{'range':1,'x':3,'y':1}})
        self.assertIn('You see nothing else of interest in the hex, either.',s.units['u'].pilot.inbox)

    def test_pod_removal_notifies_visible_observer(self):
        s=CombatSession({'actions':[]})
        u,v=s.units.values();u.sections[L.CTORSO].specials|=2
        s.streams['pod_rolls']=[12]
        s.action({'op':'command','name':'removepods','args':['CT','H']})
        self.assertTrue(any('knocks an iNarc pod' in m for m in v.movement_messages))

    def test_masc_failure_and_self_destruct_start_are_visible(self):
        from systems.combat_equipment import booster_event
        from entities.mech import Specials,MechStatus
        from types import SimpleNamespace
        s=CombatSession({'actions':[]});u,v=s.units.values()
        u.specials|=Specials.MASC_TECH;u.status|=MechStatus.MASC_ENABLED
        s.streams['booster_rolls']=[2]
        s.invoke(booster_event,SimpleNamespace(data=u,data2='masc'))
        self.assertFalse(any('stops suddenly' in m for m in v.movement_messages))
        s.action({'op':'command','name':'explode','args':['reactor']})
        self.assertTrue(any('loses reactions containment' in m for m in v.movement_messages))

    def test_blast_emits_its_observer_message(self):
        s=CombatSession({'actions':[]})
        s.streams.update(hit_location_rolls=[7],damage_entry=[7])
        s.action({'op':'diagnose','kind':'blast','options':{'damage':5,'x':3,'y':3}})
        self.assertTrue(any('u [00] is hit by the blast!' in m for m in s.units['v'].movement_messages))

    def test_enhanced_crystal_explosion_destroys_first_matching_run(self):
        from entities.mech import FireMode
        s=CombatSession({'actions':[],'units':[{'name':'u','weapons':[
            {'name':'IS.MediumLaser','section':'CT','critical':0},
            {'name':'IS.MediumLaser','section':'CT','critical':1}]},
            {'name':'v','at':[3,2,0],'team':2}]})
        u=s.units['u'];u.sections[L.CTORSO].criticals[1].weap_damage_flags=4
        s.streams.update(attack_rolls=[2],damage_entry=[7],critical_checks=[12])
        s.action({'op':'command','name':'fire','args':['1']})
        self.assertTrue(u.sections[L.CTORSO].criticals[0].firemode & FireMode.DESTROYED_MODE)
        self.assertFalse(u.sections[L.CTORSO].criticals[1].firemode & FireMode.DESTROYED_MODE)

    def test_short_hex_target_label_is_used_by_fire_result(self):
        from entities.mech import MechStatus as S
        s=CombatSession({'actions':[]});u=s.units['u']
        modes=S.LOCK_HEX_IGN|S.LOCK_HEX_CLR|S.LOCK_HEX|S.LOCK_BUILDING
        u.status &= ~modes
        for bit,label in ((0,'reg'),(S.LOCK_BUILDING,'bld'),(S.LOCK_HEX,'hex'),
                          (S.LOCK_HEX_CLR,'clr'),(S.LOCK_HEX_IGN,'ign')):
            u.status|=bit
            self.assertEqual(label,combat.short_hextarget(u))
        with patch('systems.combat.hex_hit'):
            r=s.invoke(combat.resolve_attack,u,None,get_weapon('IS.MediumLaser'),1,2,
                       to_hit_roll=12,mapx=3,mapy=1,ishex=True)
        self.assertEqual('ign',r.hex_target_label)

    def test_fire_broadcast_precedes_fired_flag_and_counter(self):
        from entities.mech import MechStatus as S
        s=CombatSession({'actions':[]});u,v=s.units.values();seen=[]
        def capture(*args,**kwargs):seen.append((bool(u.status&S.FIRED),u.shots_fired))
        s.streams.update(hit_location_rolls=[7],damage_entry=[7])
        with patch('systems.combat_firing.announce_shot',side_effect=capture):
            s.invoke(combat.resolve_attack,u,v,get_weapon('IS.MediumLaser'),1,2,to_hit_roll=12)
        self.assertEqual([(False,0)],seen)
        self.assertEqual(1,u.shots_fired)

    def test_legacy_vehicle_heat_explosion_runs_section_destruction(self):
        from systems.missile import heat_effect
        from entities.mech import UnitType,MoveType
        s=CombatSession({'actions':[]});u,v=s.units.values()
        v.unit_type=UnitType.VEH_GROUND;v.move_type=MoveType.TRACK
        s.invoke(heat_effect,s.engine,u,v,0,explosion_roll=9)
        self.assertTrue(v.is_destroyed)
        self.assertTrue(all(not sec.internal for sec in v.sections if sec.internal_orig))
        deaths=[e for e in v.channel_requests if e['source_channel']=='MechDeaths']
        self.assertEqual(1,len(deaths))
        self.assertTrue(deaths[0]['applied'])
        self.assertIn('(HEAT)',deaths[0]['text'])

    def test_artillery_launch_and_impact_reach_visible_recipients(self):
        s=CombatSession({'actions':[]});u,v=s.units.values()
        s.invoke(artillery.artillery_shoot,s.engine,u,3,2,get_weapon('IS.Sniper').index,0,True)
        self.assertTrue(any('shoots a round' in m for m in v.movement_messages))
        s.action({'op':'advance','seconds':10})
        self.assertTrue(any('YOUR HEX' in m for m in v.movement_messages))

    def test_inferno_notifies_target_and_visible_observer(self):
        from systems.missile import inferno_hit
        s=CombatSession({'actions':[]});u,v=s.units.values()
        s.invoke(inferno_hit,s.engine,u,v,1,1)
        self.assertTrue(any('sprayed with burning jelly' in m for m in v.movement_messages))
        self.assertTrue(any('bursts into flames' in m for m in u.movement_messages))

    def test_pending_pod_removal_prevents_firing(self):
        s=CombatSession({'actions':[],'units':[{'name':'u','weapons':['IS.MediumLaser']},
            {'name':'v','at':[3,2,0],'team':2}],
            'pending_events':[{'unit':'u','callback':'remove-pods','delay':60}]})
        r=s.action({'op':'command','name':'fire','args':['0']})
        # Dispatch is accepted; the inner FireWeapon gate refuses the shot.
        self.assertTrue(r['accepted'])
        self.assertFalse(r['attack']['hit'])
        self.assertIn('removing iNARC pods',r['text'])
        self.assertEqual(0,s.units['u'].shots_fired)
