"""Source booster counters, draw order, failure damage and regeneration."""
import unittest
from types import SimpleNamespace
from tools.combat_resolution import CombatSession
from entities.mech import MechStatus as S, Specials, MoveType, Location as L, FireMode
from entities.crittypes import i2special,Special
from core.events import EventType as E
from systems import combat_equipment as equipment


class BoostersTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[]})
        self.u=self.s.units['u']
        self.u.specials|=Specials.MASC_TECH
        self.u.specials2=0x40
        self.e=self.s.engine

    def test_on_off_speed_and_regen_boundary(self):
        self.u.desired_speed=30
        self.assertTrue(equipment.command(self.u,'masc')['accepted'])
        self.assertEqual(40,self.u.desired_speed)
        self.s.streams['booster_rolls']=[12]
        self.s.action({'op':'advance','seconds':1})
        self.e.events.set_tick(2)
        self.assertTrue(equipment.command(self.u,'masc')['accepted'])
        self.assertEqual(30,self.u.desired_speed)
        self.assertFalse(self.e.events.has_event_type_data(E.MASC_FAIL,self.u))
        self.e.events.set_tick(61)
        self.e.events.run_events()
        self.assertEqual(1,self.u.masc_counter)
        self.e.events.set_tick(62)
        self.e.events.run_events()
        self.assertEqual(0,self.u.masc_counter)
        self.assertEqual(60,self.e.events.time_until_type_data(E.MASC_REGEN,self.u))

    def test_supercharger_increments_masc_counter_even_when_stopped(self):
        self.u.clear_status(S.STARTED)
        self.s.streams['booster_rolls']=[2]
        self.s.invoke(equipment.booster_event,SimpleNamespace(data=self.u,data2='scharge'))
        self.assertEqual(1,self.u.masc_counter)
        self.assertEqual(0,getattr(self.u,'scharge_counter',0))
        self.assertTrue(self.u.specials2 & 0x40)
        self.assertFalse(self.e.events.has_event_type_data(E.SCHARGE_FAIL,self.u))
        self.assertEqual('booster_rolls',self.s.draws[-1]['name'])

    def test_masc_failure_destroys_quad_hips_but_only_rear_leg_bth_changes(self):
        from entities.mech import CritStatus
        self.u.crit_status|=CritStatus.SPEED_OK
        self.u.move_type=MoveType.QUAD
        self.u.desired_speed=10
        self.s.streams['booster_rolls']=[2]
        self.s.invoke(equipment.booster_event,SimpleNamespace(data=self.u,data2='masc'))
        self.assertTrue(self.u.crit_status & CritStatus.SPEED_OK)
        self.assertEqual(0,self.u.cached_max_speed)  # correct_speed recomputes the invalidated cache.
        self.assertFalse(self.u.specials & Specials.MASC_TECH)
        self.assertEqual((0,0,0),(self.u.speed,self.u.desired_speed,self.u.max_speed))
        for loc in (L.LARM,L.RARM,L.LLEG,L.RLEG):
            self.assertTrue(self.u.sections[loc].criticals[0].firemode & FireMode.DESTROYED_MODE)
        self.assertEqual(2,self.u.sections[L.LLEG].basetohit)
        self.assertEqual(0,self.u.sections[L.LARM].basetohit)

    def test_supercharger_failure_destroys_engine_slots_and_adds_heat(self):
        sec=self.u.sections[L.CTORSO]
        for i,kind in enumerate((Special.SUPERCHARGER,Special.ENGINE,Special.ENGINE)):
            sec.criticals[i].type=i2special(kind)
        self.s.streams.update(booster_rolls=[2],supercharger_crits=[2])
        self.s.invoke(equipment.booster_event,SimpleNamespace(data=self.u,data2='scharge'))
        self.assertEqual(10,self.u.engine_heat)
        self.assertFalse(self.u.specials2 & 0x40)
        self.assertTrue(all(sec.criticals[i].firemode & FireMode.DESTROYED_MODE for i in range(3)))
