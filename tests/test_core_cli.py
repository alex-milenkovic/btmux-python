"""Public core workflows: input validation, clocks and independent session state."""
import json
import os
import subprocess
import sys
import unittest


def execute(document):
    process = subprocess.run([sys.executable,'-m','tools.core_simulation'],input=json.dumps(document),
        text=True,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    return process, json.loads(process.stdout) if process.stdout else None


class CoreCliTest(unittest.TestCase):
    def test_public_skill_modes_reach_firing_and_piloting(self):
        from tools.core_simulation import CoreSession
        from systems.piloting import make_piloting_roll
        for config, gun, pilot, gun_name, pilot_name in (
                ({}, 3, 4, 'Gunnery-Battlemech', 'Piloting-Battlemech'),
                ({'extended_gunnery': False, 'extended_piloting': False}, 3, 4, 'Gunnery-Battlemech', 'Piloting-Battlemech'),
                ({'extended_gunnery': True, 'extended_piloting': True}, 8, 9, 'Gunnery-Laser', 'Piloting-Biped'),
                ({'extended_gunnery': True}, 8, 4, 'Gunnery-Laser', 'Piloting-Battlemech'),
                ({'extended_piloting': True}, 3, 9, 'Gunnery-Battlemech', 'Piloting-Biped')):
            with self.subTest(config=config):
                document = {'config': dict(periodic_updates=False, lock_tick=0, **config),
                    'units': [{'name': 'u', 'target': 2, 'weapons': ['IS.MediumLaser'],
                        'pilot_details': {'skills': {'Gunnery-Battlemech': 3, 'Gunnery-Laser': 8,
                            'Piloting-Battlemech': 4, 'Piloting-Biped': 9}}},
                        {'name': 'v', 'at': [3, 2, 0], 'team': 2}],
                    'random': {'streams': {'attack_rolls': [2], 'failure_weapon_chance': [1], 'terrain_rolls': [12, 12, 12], 'pilot_rolls': [8]}},
                    'actions': [{'op': 'command', 'unit': 'u', 'name': 'fire', 'args': ['0']}]}
                process, data = execute(document)
                self.assertEqual(0, process.returncode, process.stderr)
                shot = data['results'][0]
                self.assertTrue(shot['accepted'], shot['text'])
                self.assertEqual(gun, shot['attack']['bth_breakdown']['base'])
                self.assertEqual(1, data['state']['units']['u']['shots_fired'])
                selected = data['state']['units']['u']['skills']
                self.assertEqual((gun, pilot, gun_name, pilot_name),
                    (selected['gunnery'], selected['piloting'], selected['gunnery_name'], selected['piloting_name']))
                session = CoreSession(document)
                roll = session.invoke(make_piloting_roll, session.units['u'], award_xp=False)
                self.assertEqual((pilot, pilot <= 8), (roll.target, roll.success))

    def test_inspection_is_repeatable_without_random_or_clock_mutation(self):
        document = {'actions':[{'op':'inspect'},{'op':'inspect'}]}
        process, data = execute(document)
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertEqual(data['results'][0],data['results'][1])
        self.assertEqual(dict(wall=0,event=0,global_tick=0),data['state']['clocks'])
        self.assertEqual(0,data['state']['random']['words_consumed'])
        self.assertEqual(data,execute(document)[1])

    def test_raw_number_rejection_consumption_and_exhaustion(self):
        document = {'random':{'raw32':[0xffffffff,0]},'actions':[
            {'op':'diagnose','kind':'Number','args':[1,6]}]}
        process, data = execute(document)
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertEqual(1,data['results'][0])
        self.assertEqual(2,data['state']['random']['words_consumed'])
        document['actions'].append(document['actions'][0])
        process, data = execute(document)
        self.assertNotEqual(0,process.returncode)
        self.assertIsNone(data)
        self.assertIn('exhausted',process.stderr)

    def test_sparse_cost_legacy_cache_and_large_price_use_runtime(self):
        document = {'config':{'periodic_updates':False},'units':[{'name':'u','profile':'sparse',
            'max_speed':0,'core':{'engine_rating':200,'bv':777,'bv_last':0}}], 'actions':[
                {'op':'diagnose','kind':'CalcFasaCost'},
                {'op':'diagnose','kind':'CalculateBV','args':[100,100,29]},
                {'op':'diagnose','kind':'CalculateBV','args':[100,100,30]},
                {'op':'diagnose','kind':'SetPartCost','args':[1,18446744073709551615]},
                {'op':'diagnose','kind':'GetPartCost','args':[1]}]}
        process, data = execute(document)
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertEqual([2604999,777,50],[row['value'] for row in data['results'][:3]])
        self.assertEqual(18446744073709551615,data['results'][-1])
        self.assertEqual(777,data['state']['units']['u']['bv'])

    def test_stopped_unit_without_pilot_uses_eligible_caller(self):
        process, data = execute({'units':[{'name':'u','started':False,'pilot':False}], 'actions':[
            {'op':'command','name':'startup'}, {'op':'advance','seconds':29}, {'op':'inspect'},
            {'op':'advance','seconds':1}]})
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertTrue(data['results'][0]['accepted'])
        self.assertFalse(data['results'][2]['units']['u']['started'])
        self.assertTrue(data['state']['units']['u']['started'])
        self.assertEqual(6,len(data['state']['units']['u']['boot_messages']))

    def test_unknown_inputs_and_nan_fail_without_success_output(self):
        for document in ({'actions':[{'op':'diagnose','kind':'bogus'}]},
                         {'actions':[],'units':[{'name':'u','core':{'bv':float('nan')}}]},
                         {'actions':[],'random':{'seed':True}}):
            process, data = execute(document)
            self.assertNotEqual(0,process.returncode)
            self.assertIsNone(data)

    def test_callbacks_remain_pending_while_executing_and_clear_once(self):
        process, data = execute({'units':[{'name':'u','class':'VEH_GROUND'}],'actions':[
            {'op':'schedule','callback':'unstun_crew_event','delay':1},
            {'op':'schedule','callback':'unstun_crew_event','delay':1},
            {'op':'advance','seconds':1}]})
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertEqual(1,data['state']['units']['u']['messages'].count("Your head clears and you're able to control your vehicle again."))
        self.assertEqual(0,sum(data['state']['event_history']))

    def test_map_transfer_keeps_rosters_and_reports_world_teleport_boundary(self):
        process, data = execute({'maps':[
            {'name':'hangar','id':1000,'flags':1,'cf':10,'leave_target':1001},
            {'name':'outside','id':1001,'entrances':[{'target':1000,'x':5,'y':6,'name':'Bay'}]}],
            'actions':[{'op':'diagnose','kind':'Leave_Hangar'}]})
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertEqual('outside',data['state']['units']['u']['map'])
        self.assertEqual([],data['state']['maps']['hangar']['roster'])
        self.assertEqual([1],data['state']['maps']['outside']['roster'])

    def test_template_replay_preserves_template_input_and_recomputes_live_unit(self):
        document = {'units':[{'name':'u','core':{'template_ref':'intact'}}],
            'templates':[{'name':'intact','unit':{'name':'u','core':{'engine_rating':200},'max_speed':64.5}}],
            'actions':[{'op':'inspect'},{'op':'command','name':'recalculate'}]}
        process, data = execute(document)
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertTrue(data['results'][1]['result'])
        self.assertEqual(data['results'][0]['templates'],data['state']['templates'])

    def test_empty_kill_reason_and_rejected_repair_are_valid_commands(self):
        process, data = execute({'units':[{'name':'u'},{'name':'v'}], 'actions':[
            {'op':'diagnose','kind':'ChannelEmitKill','args':['v','']},
            {'op':'command','name':'repair','args':'CT 99'}]})
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertFalse(data['results'][1]['accepted'])
        self.assertIn('()',data['state']['units']['u']['channel_requests'][0]['text'])

    def test_undefined_source_numeric_inputs_are_rejected(self):
        for action in ({'op':'diagnose','kind':'MNumber','args':[2,1]},
                       {'op':'section','unit':'u','value':{'index':'CT','slots':[{'index':0,'data':256}]}},
                       {'op':'diagnose','kind':'history_input','args':[[2**31-1,1]]},
                       {'op':'schedule','callback':'mech_lateral_event','delay':1,'data':9}):
            process, data = execute({'actions':[action]})
            self.assertNotEqual(0,process.returncode)
            self.assertIsNone(data)

    def test_source_lateral_index_and_inherited_pilot_metadata(self):
        process,data=execute({'units':[{'name':'u','started':False,'pilot_wizard':True,
            'melee_specialist':True,'pilot_details':{'skills':{'Sixth_Sense':1}}}], 'actions':[
                {'op':'command','name':'startup','args':'over'},
                {'op':'advance','seconds':1},
                {'op':'schedule','callback':'mech_lateral_event','delay':1,'data':2},
                {'op':'advance','seconds':1}]})
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertTrue(data['results'][0]['accepted'])
        unit=data['state']['units']['u']
        self.assertTrue(unit['pilot']['wizard'])
        self.assertTrue(unit['pilot']['melee_specialist'])
        self.assertEqual(60,unit['lateral'])
        from entities.mech import Specials
        self.assertTrue(unit['specials'] & Specials.SS_ABILITY)

    def test_source_ranges_and_optional_part_and_skill_arguments(self):
        process,data=execute({'config':{'extended_gunnery':True},'actions':[
            {'op':'diagnose','kind':'FindHexRange','args':[0.5,0.5,0.5,323.0]},
            {'op':'diagnose','kind':'FindGunnerySkillName','args':[-1]},
            {'op':'diagnose','kind':'UnitPartsList','args':[0]},
            {'op':'diagnose','kind':'UnitPartsList','args':[1]},
            {'op':'diagnose','kind':'GetPartWeight','args':[0,False]},
            {'op':'diagnose','kind':'find_mech_in_hex','args':[3,3,3]}]})
        self.assertEqual(0,process.returncode,process.stderr)
        self.assertEqual(1.0,data['results'][0])
        self.assertIsNone(data['results'][1])
        self.assertEqual(data['results'][2],data['results'][3])
        self.assertEqual(102,data['results'][4])
        self.assertIsNone(data['results'][5])
