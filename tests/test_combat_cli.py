"""Public combat JSON contract and production command routing."""
import unittest
from tools.combat_resolution import CombatSession
from entities.mech import Location as L
from entities.crittypes import i2special,Special


class CombatCliTest(unittest.TestCase):
    def test_defaults_are_mapped_piloted_intact_units_with_stable_enemy_lock(self):
        s=CombatSession({'actions':[]})
        self.assertEqual((12,12),(s.map.map_width,s.map.map_height))
        self.assertEqual({'u','v'},set(s.units))
        u,v=s.units['u'],s.units['v']
        self.assertEqual((3,3,0),(u.x,u.y,u.z))
        self.assertEqual((3,2,0),(v.x,v.y,v.z))
        self.assertEqual(v._id,u.target)
        self.assertEqual(i2special(Special.SHOULDER_OR_HIP),u.sections[L.LARM].criticals[0].type)
        self.assertEqual([],u.weapons)

    def test_commands_and_map_state_reach_real_resolution(self):
        s=CombatSession({'actions':[]})
        self.assertTrue(s.action({'op':'command','name':'lock','args':['4junk','4','I']})['accepted'])
        self.assertTrue(s.action({'op':'command','name':'mechprefs','args':['AmmoWarn','OFF']})['accepted'])
        self.assertTrue(s.action({'op':'command','name':'addmine','args':['3','3','Standard','8']})['accepted'])
        before=s.snapshot()['units']['u']['sections'][L.RLEG]['armor']
        s.streams.update(physical_location=[1],damage_entry=[7])
        s.action({'op':'diagnose','kind':'mine-contact','options':{'reason':'step'}})
        snap=s.snapshot()
        self.assertEqual(5,snap['map']['mines'][0]['strength'])
        self.assertEqual(before-5,snap['units']['u']['sections'][L.RLEG]['armor'])
        self.assertEqual(16,snap['units']['u']['prefs'])

    def test_weapon_fire_is_a_delayed_projectile_in_public_snapshot(self):
        s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0],
             'weapons':[{'name':'IS.Sniper','section':'CT','metadata':{'crits':1}}],
             'ammo':[{'weapon':'IS.Sniper','rounds':10}]}]})
        s.action({'op':'command','name':'lock','args':['3','1','H']})
        s.streams['attack_rolls']=[12]
        r=s.action({'op':'command','name':'fire','args':['0']})
        self.assertTrue(r['accepted'])
        snap=s.snapshot()
        self.assertEqual(1,len(snap['map']['projectiles']))
        self.assertEqual([],snap['map']['artillery_impacts'])

    def test_rejection_is_data_but_invalid_fixture_and_dice_raise(self):
        s=CombatSession({'actions':[]})
        self.assertFalse(s.action({'op':'command','name':'fire','args':['99']})['accepted'])
        with self.assertRaises(ValueError):CombatSession({'actions':[],'units':[{'name':'u','tonnage':float('nan')}]})
        with self.assertRaises(ValueError):s.action({'op':'diagnose','kind':'mine-contact','options':{'reason':'fly'}})
        with self.assertRaises(ValueError):s.action({'op':'unknown'})

    def test_range_and_bth_diagnostics_use_mounted_metadata(self):
        s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0],
            'weapons':[{'name':'IS.MediumLaser','metadata':{'range_short':2,'range_medium':4,'range_long':6}}]},
            {'name':'v','at':[3,2,0],'team':2}]})
        r=s.action({'op':'diagnose','kind':'combat-range','options':{'weapon':0,'target':'v','distance':5}})
        self.assertEqual(('LONG',4),(r['bracket'],r['modifier']))
        self.assertEqual(8,r['extreme'])
        b=s.action({'op':'diagnose','kind':'combat-bth','options':{'weapon':0,'target':'v','distance':5}})
        self.assertEqual(4,b['range_mod'])

    def test_pending_callback_and_inspection_have_real_deadlines_without_mutation(self):
        s=CombatSession({'actions':[],'config':{'periodic_updates':False},
            'pending_events':[{'unit':'u','callback':'explode','delay':5,'data':10}]})
        before=(len(s.draws),s.engine.muxevent_tick)
        a=s.action({'op':'inspect'});b=s.action({'op':'inspect'})
        self.assertEqual(a,b);self.assertEqual(before,(len(s.draws),s.engine.muxevent_tick))
        self.assertIn({'kind':'EXPLODE','deadline':5},a['units']['u']['events'])
        self.assertIn('hexes',a['map'])
        self.assertIn('shots_fired',a['units']['u'])

    def test_physical_command_and_relationship_fixture_are_available(self):
        s=CombatSession({'actions':[],'units':[{'name':'u','at':[3,3,0],'charge_target':'v'},
            {'name':'v','at':[3,2,0],'team':2}]})
        self.assertEqual(s.units['v']._id,s.units['u'].charge_target)
        self.assertTrue(s.action({'op':'command','name':'charge','args':['-']})['accepted'])
        s.action({'op':'configure','values':{'charge_distance':2.5,'masc_counter':3}})
        self.assertEqual(2.5,s.snapshot()['units']['u']['charge_distance'])

    def test_unknown_callbacks_and_invalid_diagnostic_options_are_rejected(self):
        with self.assertRaises(ValueError):CombatSession({'actions':[],'pending_events':[{'unit':'u','callback':'arbitrary','delay':1}]})
        s=CombatSession({'actions':[]})
        with self.assertRaises(ValueError):s.action({'op':'diagnose','kind':'combat-range','options':[]})

    def test_tic_guard_rejection_is_not_reported_as_accepted(self):
        from entities.mech import MechStatus2
        s=CombatSession({'actions':[]})
        s.units['u'].status2|=MechStatus2.WEAPONS_HOLD
        self.assertFalse(s.action({'op':'command','name':'firetic','args':['0']})['accepted'])
        self.assertFalse(s.action({'op':'command','name':'addtic','args':['0','99']})['accepted'])

    def test_new_charge_timeout_uses_live_config(self):
        from physics.movement import move_mech
        s=CombatSession({'actions':[],'config':{'newcharge':1}})
        u,v=s.units.values();u.charge_target=v._id;u.charge_timer=61
        s.invoke(move_mech,u)
        self.assertEqual(-1,u.charge_target)

    def test_weapon_diagnostics_require_a_mount_and_include_critical_bth(self):
        s=CombatSession({'actions':[],'units':[{'name':'u','weapons':['IS.MediumLaser']},
            {'name':'v','at':[3,2,0],'team':2}]})
        for kind in ('combat-range','combat-bth','combat-attack','missile-hit','missile-index','terrain-hit'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                s.action({'op':'diagnose','kind':kind,'options':{}})
        u=s.units['u'];ws=u.weapons[0]
        u.sections[ws.section].criticals[ws.critical].weap_damage_flags=1
        b=s.action({'op':'diagnose','kind':'combat-bth','options':{'weapon':0,'target':'v'}})
        self.assertEqual(1,b['critical_bth'])
        self.assertEqual(1,b['other_mods'])
        s.action({'op':'diagnose','kind':'combat-attack',
                  'options':{'weapon':0,'target':'v','roll':12,'tc_roll':1}})
        with self.assertRaises(ValueError):
            s.action({'op':'diagnose','kind':'combat-attack',
                      'options':{'weapon':0,'target':'v','roll':12,'tc_roll':7}})

    def test_configured_preferences_update_the_live_warning_consumer(self):
        s=CombatSession({'actions':[]})
        s.action({'op':'configure','values':{'prefs':16}})
        self.assertFalse(s.units['u'].ammo_warnings)

    def test_explicit_dfa_contact_uses_map_identity(self):
        from entities.mech import MechStatus
        s=CombatSession({'actions':[],'units':[{'name':'u','jump_mp':3,'jump_speed':32.25},
            {'name':'v','at':[3,2,0],'team':2}]})
        u,v=s.units.values();v.contact_id='BB'
        r=s.action({'op':'command','name':'jump','args':['BB']})
        self.assertTrue(r['accepted'],r)
        self.assertEqual(v._id,u.dfa_target)
        self.assertTrue(u.status & MechStatus.DFA_ATTACK)

    def test_melee_advantage_fixture_reaches_pilot_damage_consumer(self):
        session=CombatSession({'actions':[], 'units':[{'name':'u','melee_specialist':True},
            {'name':'v','at':[3,2,0],'team':2}]})
        session.streams.update(physical_location=[1],damage_entry=[7])
        result=session.action({'op':'diagnose','kind':'physical-damage',
            'options':{'target':'v','attack':'punch'}})
        self.assertEqual(6,result['damage_dealt'])
        with self.assertRaises(ValueError):
            CombatSession({'actions':[], 'units':[{'name':'u','pilot':False,'melee_specialist':True}]})
