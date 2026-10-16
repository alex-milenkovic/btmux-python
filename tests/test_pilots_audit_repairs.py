"""Focused AUD-PILOTS boundaries and observable source effect ordering."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from core.game_loop import GameEngine, update_recycling
from data.characters import CharacterStore, Stats, ALL, SKILLS
from data.character_values import code, XP_MAX
from entities.mech import Mech, UnitType as U, MechStatus as S
from systems import characters as c, experience as xp, piloting, swarm


class PilotsAuditRepairs(unittest.TestCase):
    def setUp(self):
        self.store=CharacterStore();self.store.create(101,'Alice',wizard=True,location=10)
        self.store.store(101,Stats.fresh(),ALL)
        self.actor=self.store.actor(101)
        self.unit=Mech.create_test_mech();self.unit._id=10
        self.engine=GameEngine();self.engine.register_entity(self.unit)
        self.unit.pilot=self.actor;self.unit.in_character=True;self.unit.status=S.STARTED

    def test_sentinel_bypasses_modifier_cache_and_raw_xp_accepts_nonskills(self):
        self.store.records[101]['categories']['skills']=f'Running:0,{-XP_MAX},0/Build:7,43,0/'
        self.assertEqual(18,c.skill_target(self.store,101,'Running',8))
        self.assertIsNone(self.store.cache)
        self.assertEqual(43,c.raw_xp(self.store,101,code('Build')))
        self.assertEqual(0,c.raw_xp(self.store,101,-1))
        self.assertEqual(0,c.control(self.store,101,'get',name='1tail'))
        with self.assertRaisesRegex(ValueError,'INVALID VALUE'):
            c.control(self.store,101,'get',name='00')

    def test_health_masks_ignore_legal_skill_category_collisions(self):
        self.store.records[101]['categories'].update(
            health='15,5',attrs='5,5,5,5,5',advs='Pain_Resistance:1/',
            skills='Build:1/Bruise:255/Lethal:255/Pain_Resistance:0/')
        piloting.fix_pilotdamage(self.unit,self.actor)
        self.assertEqual(2,self.unit.pilot_hits)
        self.assertEqual(4,piloting.mw_ic_bth(self.unit))

    def test_recycle_keeps_full_new_delay_and_dead_member_noop(self):
        self.unit.unit_type=U.BSUIT
        self.engine.events._tick=5;self.unit.last_weapon_recycle=0
        for section in self.unit.sections:section.recycle=2
        self.unit.sections[7].internal=0
        swarm.start_recycle(self.unit,20)
        update_recycling(self.engine,self.unit)
        self.assertEqual([20]*7,[section.recycle for section in self.unit.sections[:7]])
        self.assertEqual(0,self.unit.sections[7].recycle)
        for section in self.unit.sections:section.internal=0
        self.engine.events._tick=10
        swarm.start_recycle(self.unit,30)
        self.assertEqual(5,self.unit.last_weapon_recycle)

    def test_source_display_delivery_and_threshold_numeric_prefix(self):
        result=c.control(self.store,101,'status')
        self.assertEqual(result['messages'],self.actor.inbox)
        self.assertTrue(any('%cgAttributes' in line and 'Characteristics' in line for line in self.actor.inbox))
        c.threshold_control(self.store,'Running 25tail',caller=101)
        self.assertTrue(self.store.log_requests[-1]['applied'])
        with self.assertRaisesRegex(ValueError,'Invalid value'):
            c.threshold_control(self.store,'Running -0',caller=101)
        self.assertEqual('Invalid value!',self.actor.inbox[-1])

    def test_channels_repeat_and_float32_speed_boundary(self):
        self.engine.sim_now=101
        for _ in range(2):xp.piloting(self.actor,self.unit,2,True)
        self.assertEqual(2,len(self.engine.effects.channels))
        self.assertEqual('Alice gained 2 Piloting-Battlemech XP',self.engine.effects.channels[0]['text'])
        self.assertEqual(2,xp.movement_value(21.5000001))
        xp.tech(self.actor,None,3)
        self.assertEqual('Alice gained 3 technician-weapons XP (changing mech #-1)',self.store.effects.channels[-1]['text'])

    def test_initialization_reports_exact_error_and_retains_partial_body(self):
        from systems.personal_damage import initialize_pc
        self.unit.unit_type=U.MW
        self.store.records[101]['pcequip']='12x4'
        error=initialize_pc(self.actor,self.unit)
        self.assertEqual('Invalid armor char for Alice(#101) in 12x4 (pos 3,x)',error)
        self.assertEqual(error,self.engine.effects.channels[-1]['text'])
        self.assertEqual([0]*8,[section.armor for section in self.unit.sections])
