"""Command guards precede target routing and preserve source side effects."""
import unittest
from tools.combat_resolution import CombatSession
from entities.mech import CritStatus,MechStatus2 as S2,MechStatus as S


class FiringCompletionTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0],
            'weapons':[{'name':'IS.MediumLaser','section':'LA'}]},
            {'name':'v','at':[3,2,0],'team':2}]})
        self.u,self.v=self.s.units.values()
        self.s.streams.update(attack_rolls=[12],hit_location_rolls=[7]*20)

    def fire(self,*args):return self.s.action({'op':'command','name':'fire','args':list(args) or ['0']})

    def test_sight_ignores_mech_stun_but_respects_vehicle_crew_stun(self):
        self.u.crit_status |= CritStatus.MECH_STUNNED
        self.assertFalse(self.fire()['accepted'])
        sight = {'op':'command','name':'sight','args':['0']}
        self.assertTrue(self.s.action(sight)['accepted'])
        from systems.vehicle_combat import handle_crew_stunned
        handle_crew_stunned(self.u)
        reply=self.s.action(sight)
        self.assertTrue(reply['accepted'])  # FireWeaponNumber dispatched successfully.
        self.assertIsNone(reply['attack']['bth_breakdown'])
        self.assertIn('stunned',' '.join(reply['attack']['messages']))

    def test_hidden_reveal_precedes_bad_weapon_but_weapons_hold_stops_before_reveal(self):
        self.u.crit_status|=CritStatus.HIDDEN
        self.u.status2|=S2.WEAPONS_HOLD
        self.assertFalse(self.fire('99')['accepted'])
        self.assertTrue(self.u.crit_status&CritStatus.HIDDEN)
        self.u.status2&=~S2.WEAPONS_HOLD
        self.assertFalse(self.fire('99')['accepted'])
        self.assertFalse(self.u.crit_status&CritStatus.HIDDEN)

    def test_explicit_off_lock_contact_is_allowed_and_all_branches_check_friendly_safety(self):
        from systems.combat import fire_weapon_number
        self.u.target=-1
        r=self.s.invoke(fire_weapon_number,self.s.engine,self.u,0,self.v,to_hit_roll=12)
        self.assertTrue(r.hit)
        slot=self.u.sections[0].criticals[0]
        slot.data=0
        self.v.team=self.u.team
        self.u.prefs=128
        r=self.s.invoke(fire_weapon_number,self.s.engine,self.u,0,self.v,to_hit_roll=12)
        self.assertIsNone(r.bth_breakdown)
        self.assertIn('FFSafeties',' '.join(r.messages))

    def test_club_and_pending_ammo_event_stop_before_draw(self):
        from core.events import EventType
        self.u.sections[0].specials|=0x20
        self.assertFalse(self.fire()['accepted'])
        self.assertEqual([12],self.s.streams['attack_rolls'])
        self.u.sections[0].specials&=~0x20
        self.s.engine.events.schedule(60,EventType.UNJAM_AMMO,lambda event:None,self.u)
        self.assertTrue(self.fire()['accepted'])
        self.assertEqual([12],self.s.streams['attack_rolls'])

    def test_own_swarmer_id_rejected_on_default_target(self):
        self.v.swarming=self.u._id
        self.assertFalse(self.fire()['accepted'])

    def test_explicit_hex_uses_default_hex_occupant_but_requested_coordinates(self):
        from systems.combat import fire_weapon_number
        self.u.target=-1
        self.u.targ_x,self.u.targ_y=3,2
        self.u.status|=S.LOCK_HEX
        result=self.s.invoke(fire_weapon_number,self.s.engine,self.u,0,('3junk','1'),to_hit_roll=12)
        self.assertTrue(result.hit)
        self.assertEqual(self.v._id,result.target_id)

    def test_impossible_unit_and_hex_consume_attack_draw_but_no_resources(self):
        from unittest.mock import patch
        from systems.combat import fire_weapon,BTHBreakdown
        for target in (self.v,None):
            self.s.streams['attack_rolls']=[7]
            with patch('systems.combat.calculate_bth',return_value=BTHBreakdown(base=13,total=13)):
                result=self.s.invoke(fire_weapon,self.u,target,0,1,ishex=int(target is None),mapx=3,mapy=1)
            self.assertTrue(result.roll_impossible)
            self.assertEqual(7,result.roll)
            self.assertEqual([],self.s.streams['attack_rolls'])
            self.assertEqual(0,self.u.weap_heat)
            self.assertEqual(0,self.u.sections[0].criticals[0].data)

    def test_sight_consumes_named_draw_without_resources(self):
        from systems.combat import fire_weapon
        armor=sum(section.armor for section in self.v.sections)
        self.s.streams['attack_rolls']=[7]
        result=self.s.invoke(fire_weapon,self.u,self.v,0,1,sight=True)
        self.assertEqual(7,result.roll)
        self.assertEqual([],self.s.streams['attack_rolls'])
        self.assertEqual(0,self.u.weap_heat)
        self.assertEqual(0,self.u.shots_fired)
        self.assertFalse(self.u.has_status(S.FIRED))
        self.assertEqual(armor,sum(section.armor for section in self.v.sections))

    def test_coolant_default_heat_mode_self_targets_and_reduces_heat(self):
        s=CombatSession({'actions':[],'units':[{'name':'u','weapons':['IS.CoolantGun'],
            'ammo':[{'weapon':'IS.CoolantGun','rounds':5}]}]})
        from entities.mech import FireMode
        u=s.units['u'];ws=u.weapons[0]
        u.sections[ws.section].criticals[ws.critical].firemode|=FireMode.HEAT_MODE
        u.weap_heat=10
        s.streams['attack_rolls']=[12]
        result=s.action({'op':'command','name':'fire','args':['0']})
        self.assertTrue(result['accepted'])
        self.assertEqual(7,u.weap_heat)
        self.assertEqual(u._id,result['attack']['target_id'])

    def test_risky_jam_returns_without_heat_ammo_or_recycle(self):
        from entities.mech import FireMode
        from systems.combat import fire_weapon
        from systems.enhanced_crits import part_temp_nuke,FAIL_AMMOJAMMED
        s=CombatSession({'actions':[],'units':[{'name':'u','weapons':[{'name':'IS.RotaryAC/5','metadata':{'crits':1}}],
            'ammo':[{'weapon':'IS.RotaryAC/5','rounds':10}]},{'name':'v','team':2}]})
        u,v=s.units.values();ws=u.weapons[0]
        slot=u.sections[ws.section].criticals[ws.critical]
        slot.firemode|=FireMode.RAC_SIXSHOT_MODE
        result=s.invoke(fire_weapon,u,v,0,1,to_hit_roll=4)
        self.assertTrue(result.shot_aborted)
        self.assertEqual(FAIL_AMMOJAMMED,part_temp_nuke(slot))
        self.assertEqual((0,0),(u.weap_heat,slot.data))
        from systems.combat_ammunition import count_ammo
        self.assertEqual(10,count_ammo(u,ws.weapon_idx))

    def test_fired_and_counter_are_set_before_damage_callback(self):
        from unittest.mock import patch
        from systems.combat import fire_weapon
        seen=[]
        def damage(*args,**kwargs):seen.append((self.u.has_status(S.FIRED),self.u.shots_fired))
        with patch('systems.combat._apply_single_hit',side_effect=damage):
            self.s.invoke(fire_weapon,self.u,self.v,0,1,to_hit_roll=12)
        self.assertEqual([(True,1)],seen)

    def test_aerospace_nose_weapons_have_forward_arc_and_reject_rear(self):
        from systems.combat import is_in_weapon_arc
        from entities.mech import UnitType
        from physics.hexmath import hex_to_float
        for kind,loc in ((UnitType.AERO,0),(UnitType.DS,5),(UnitType.SPHEROID_DS,5)):
            self.u.unit_type=kind
            self.assertTrue(is_in_weapon_arc(self.u,*hex_to_float(3,2),loc,0))
            self.assertFalse(is_in_weapon_arc(self.u,*hex_to_float(3,4),loc,0))

    def test_opening_cocoon_uses_jump_speed_in_source_units(self):
        from systems.combat_firing import begin_shot
        self.u.z=2;self.u.cocoon=1;self.u.jump_mp=0;self.u.jump_speed=10.75
        begin_shot(self.u)
        self.assertEqual(-1,self.u.cocoon)
        self.u.cocoon=1;self.u.jump_mp=1;self.u.jump_speed=10.749
        begin_shot(self.u)
        self.assertEqual(0,self.u.cocoon)
        self.assertIn('FALL',[e['kind'] for e in self.s.snapshot()['units']['u']['events']])
