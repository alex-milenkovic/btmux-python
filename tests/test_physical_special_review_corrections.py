"""Focused C1-C8 regressions from the Physical/Special Combat source review."""
import json
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.events import EventType as E
from core.randomness import float32, use_source
from entities.mech import Location as L, MechStatus as S, MoveType as M, UnitType as U
from entities.pilot import Pilot
from systems import physical as p, swarm, vehicle_combat, mines
from systems.combat import HitGroup as H
from tests import test_combat_physical_completion as physical_fixtures
from tests.test_damage_review_corrections import crew_session
from tools.combat_resolution import CombatSession


class PhysicalReviewCorrections(unittest.TestCase):
    setUp = physical_fixtures.PhysicalCommandsTest.setUp

    def test_moderate_motive_hit_clamps_again_after_real_cargo_refresh(self):
        from physics.cargo import cargo_max_speed
        for sign in (1, -1):
            with self.subTest(sign=sign):
                unit=CombatSession({'actions':[]}).units['u']
                unit.unit_type=U.VEH_GROUND;unit.move_type=M.TRACK
                unit.tonnage=50;unit.measured_mass=50*1024
                unit.max_speed=64.5;unit.speed=unit.desired_speed=sign*64.5
                unit.carried_cargo=0
                self.assertEqual(64.5,cargo_max_speed(unit))
                unit.cargo_inventory=[(385,0,10)]
                with use_source(lambda name,low,high,fallback:10):
                    vehicle_combat.motive_system_hit(unit)
                self.assertEqual(40800,unit.carried_cargo)
                maximum=float32(53.75*50*1024/(50*1024+40800))
                expected=maximum if sign>0 else -float32(maximum*2/3)
                self.assertEqual((expected,expected),(unit.speed,unit.desired_speed))
                self.assertEqual(2,unit.pilot_skill_base)

    def test_repeated_guards_keep_started_nonpilot_wizard_context(self):
        for command,args in (('punch','R'),('charge','-'),('grabclub','-')):
            with self.subTest(command=command):
                self.setUp()
                self.u.status|=S.UNCONSCIOUS;self.u.in_character=True
                caller=SimpleNamespace(inbox=[])
                if command=='grabclub':self.u.sections[L.LARM].specials|=p.CARRYING_CLUB
                result=self.s.invoke(p.physical_command,self.u,command,args,caller=caller,wizard=True)
                self.assertTrue(result['accepted'],result['text'])
                self.assertEqual([],caller.inbox)
                if command=='punch':
                    # The context is reset; a direct call still checks its pilot.
                    self.assertIn('unconscious',p.mech_punch(self.u,arm='R')[0].messages[0])

    def test_null_physical_command_is_silent_with_or_without_explicit_caller(self):
        with patch('core.effects.notify_actor') as notify:
            for actor in ({},{'caller':SimpleNamespace(inbox=[])}):
                self.assertEqual({'accepted':False,'text':''},p.physical_command(None,'punch',**actor))
            notify.assert_not_called()

    def test_physical_damage_delivers_hit_and_does_not_substitute_gunpilot(self):
        session=crew_session({'actions':[]})
        unit,target=session.units.values()
        for pilot in (unit.pilot,None):
            with self.subTest(pilot_present=pilot is not None):
                unit.pilot=pilot
                with patch.object(p,'apply_damage_with_transfer',wraps=p.apply_damage_with_transfer) as damage, \
                     patch('systems.piloting.valid_pilot',side_effect=AssertionError('unexpected pilot fallback')):
                    session.invoke(p.physical_damage,unit,target,7,p.PhysicalAttackType.PUNCH,L.LARM,location_roll=3)
                self.assertEqual(1,damage.call_args.kwargs['los'])
                self.assertIs(pilot if pilot is not None else -1,damage.call_args.kwargs['attack_pilot'])
        self.assertTrue(any('You hit ' in text for text in unit.movement_messages))

    def test_charge_and_dfa_packets_keep_inflicted_and_self_contexts(self):
        for attack in ('charge','dfa-hit','dfa-miss'):
            with self.subTest(attack=attack):
                self.setUp()
                self.u.speed=40
                if attack.startswith('dfa'):self.u.status|=S.JUMPING|S.DFA_ATTACK
                packets=[]
                def damage(victim,loc,amount,**context):
                    packets.append((victim,context));return amount
                with patch.object(p,'apply_damage_with_transfer',side_effect=damage):
                    if attack=='charge':self.s.invoke(p.charge_mech,self.u,self.v,roll=12)
                    else:self.s.invoke(p.dfa_attack,self.u,self.v,roll_override=12 if attack=='dfa-hit' else 2)
                self.assertTrue(packets)
                self.assertTrue(any(victim is self.u for victim,context in packets))
                self.assertEqual(attack!='dfa-miss',any(victim is self.v for victim,context in packets))
                for victim,context in packets:
                    inflicted=victim is self.v
                    self.assertEqual((1,1) if inflicted else (0,2),(context['los'],context['physical']))
                    self.assertIs(self.u.pilot if inflicted else -1,context['attack_pilot'])
                    self.assertIs(self.u,context['attacker'])

    def test_charge_reads_current_pilot_for_each_packet(self):
        original=self.u.pilot;packets=[]
        def damage(victim,loc,amount,**context):
            packets.append(context['attack_pilot']);self.u.pilot=None;return amount
        with patch.object(p,'apply_damage_with_transfer',side_effect=damage):
            self.s.invoke(p._apply_charge_clusters,self.v,self.u,H.FRONT,7)
        self.assertEqual([original,-1],packets)

    def test_failed_swarm_detach_has_self_los_without_pilot_credit(self):
        self.u.unit_type=U.BSUIT;self.u.swarm_target=self.v._id;self.v.swarmer=self.u._id
        with patch('systems.piloting.make_piloting_roll',return_value=SimpleNamespace(success=False)), \
             patch('systems.combat.apply_damage_with_transfer',wraps=p.apply_damage_with_transfer) as damage:
            self.s.invoke(swarm.detach,self.u)
        context=damage.call_args.kwargs
        self.assertEqual((1,-1,True),(context['los'],context['attack_pilot'],context['ignore_swarmers']))
        self.assertEqual(0,context.get('physical',0))
        self.assertIs(self.u,context['attacker'])
        self.assertTrue(any('You hit ' in text for text in self.u.movement_messages))

    def test_zero_damage_charge_refusal_reaches_only_aboard_pilot(self):
        session=crew_session({'actions':[]});unit,target=session.units.values()
        passenger=Pilot();passenger._id=50000;passenger.inbox=[]
        session.engine.personnel.add(passenger,unit._id)
        unit.speed=40
        with patch.object(p,'_charge_damage_to_target',return_value=0):
            result=session.invoke(p.charge_mech,unit,target,roll=12)
        self.assertIn('pulls away',result.messages[-1])
        self.assertEqual(result.messages[-1],unit.pilot.inbox[-1])
        self.assertEqual([],passenger.inbox)

    def test_raw_charge_and_arm_tokens_use_only_space_tab_delimiters(self):
        for raw,accepted in (('-foo\nbar',True),('-foo\tbar',False),('-foo bar',False)):
            with self.subTest(raw=raw):
                self.u.charge_target=self.v._id
                result=self.s.command(self.u,'charge',raw)
                self.assertEqual(accepted,result['accepted'])
                self.assertEqual(-1 if accepted else self.v._id,self.u.charge_target)
        result=self.s.command(self.u,'punch','R\n')
        self.assertFalse(result['accepted'])
        self.assertFalse(any(section.recycle for section in self.u.sections))


class SpecialCombatReviewCorrections(unittest.TestCase):
    def session(self,**fields):
        return CombatSession({'actions':[],'units':[dict(name='u',caller_is_pilot=False,**fields)]})

    def test_direct_and_inherited_refusals_use_one_nonpilot_inbox(self):
        session=self.session(in_character=True,equipment=['Guardian','Angel','Personal','searchlight'])
        unit=session.units['u'];caller=unit.command_actor
        for name in ('ultra','mechprefs','shownarcpods','punch','ecm','eccm','angelecm','angeleccm','perecm','pereccm','slite'):
            with self.subTest(command=name):
                result=session.command(unit,name,'0' if name=='ultra' else '')
                self.assertFalse(result['accepted'])
                self.assertIn('only the pilot',result['text'])
                self.assertEqual(result['text'],caller.inbox[-1])
                self.assertIs(caller,unit.command_actor)
        self.assertEqual([],getattr(unit.pilot,'inbox',[]))
        self.assertEqual(caller.inbox,session.snapshot()['units']['u']['caller_messages'])

    def test_inherited_commands_allow_started_nonpilot_wizard_when_pilot_unconscious(self):
        for name,equipment in (('ecm','Guardian'),('slite','searchlight')):
            with self.subTest(command=name):
                session=self.session(in_character=True,conscious=False,caller_wizard=True,equipment=[equipment])
                result=session.command(session.units['u'],name,'')
                self.assertTrue(result['accepted'],result['text'])

    def test_nonpilot_preferences_admin_notice_order_and_both_mine_discovery_paths(self):
        session=self.session();unit=session.units['u'];caller=unit.command_actor
        self.assertTrue(session.command(unit,'mechprefs','')['accepted'])
        self.assertTrue(session.command(unit,'mechprefs','AmmoWarn OFF')['accepted'])
        self.assertEqual(16,unit.prefs)
        self.assertTrue(caller.inbox)
        original=mines.recalculate_minefields
        def recalculate(board):
            self.assertIn('Standard mine added',caller.inbox[-1])
            self.assertNotIn((4,4),board.mine_hexes)
            original(board)
        with patch.object(mines,'recalculate_minefields',side_effect=recalculate):
            self.assertTrue(session.command(unit,'addmine','4 4 Standard 8')['accepted'])
        self.assertIn((4,4),session.map.mine_hexes)
        for action in ({'op':'diagnose','kind':'mine-discovery','options':{'range':1,'x':3,'y':1}},
                       {'op':'command','name':'scan','args':'3 1 H'}):
            with self.subTest(path=action['op']):
                before=len(caller.inbox)
                session.action(action)
                self.assertEqual(before+1,len(caller.inbox))
                self.assertIn('nothing else of interest',caller.inbox[-1])
                self.assertIs(caller,unit.command_actor)
        self.assertEqual([],getattr(unit.pilot,'inbox',[]))

    def test_raw_self_destruct_buffer_retains_leading_whitespace(self):
        for raw in (' stop override','\tstop override'):
            with self.subTest(raw=raw):
                session=self.session(caller_wizard=True);unit=session.units['u']
                session.engine.events.schedule(5,E.EXPLODE,lambda event:None,unit,10)
                result=session.command(unit,'explode',raw)
                self.assertFalse(result['accepted'])
                self.assertIn('already undergoing',unit.command_actor.inbox[-1])
                self.assertTrue(session.engine.events.has_event_type_data(E.EXPLODE,unit))
                self.assertTrue(session.command(unit,'explode','stop override')['accepted'])
                self.assertFalse(session.engine.events.has_event_type_data(E.EXPLODE,unit))
        for raw,reactor in ((' ammo',True),('\tammo',True),('ammo extra',False)):
            with self.subTest(raw=raw):
                session=self.session();unit=session.units['u']
                result=session.command(unit,'explode',raw)
                self.assertEqual(reactor,result['accepted'])
                if reactor:self.assertIn('reactor',unit.debug_messages[-1])
                else:self.assertIn("no 'damaging' ammo",unit.command_actor.inbox[-1])

    def test_false_caller_cli_returns_structured_results_and_delivered_messages(self):
        document={'units':[{'name':'u','in_character':True,'caller_is_pilot':False},
                           {'name':'v','caller_is_pilot':False}],
                  'actions':[{'op':'command','unit':'u','name':'ultra','args':'0'},
                             {'op':'command','unit':'v','name':'mechprefs','args':'AmmoWarn OFF'},
                             {'op':'command','unit':'v','name':'addmine','args':'4 4 Standard 8'}]}
        process=subprocess.run([sys.executable,'-B','-m','tools.combat_resolution'],
                               input=json.dumps(document),text=True,capture_output=True,timeout=30)
        self.assertEqual(0,process.returncode,process.stderr)
        result=json.loads(process.stdout)
        self.assertEqual([False,True,True],[row['accepted'] for row in result['results']])
        self.assertIn('only the pilot',result['state']['units']['u']['caller_messages'][-1])
        self.assertIn('Standard mine added',result['state']['units']['v']['caller_messages'][-1])
        self.assertIn([4,4],result['state']['map']['mine_hexes'])
