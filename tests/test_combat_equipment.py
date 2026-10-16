"""Equipment commands preserve delayed transitions and callback guards."""
import unittest
from tools.combat_resolution import CombatSession
from entities.mech import MechStatus as S, MechStatus2 as S2, Specials, CritStatus
from systems import combat_equipment as equipment


class EquipmentTest(unittest.TestCase):
    def setUp(self):
        self.s=CombatSession({'actions':[]})
        self.u=self.s.units['u']
        self.e=self.s.engine

    def advance(self,tick):
        self.e.events.set_tick(tick)
        self.e.events.run_events()

    def test_signature_delayed_toggle_and_duplicate_guard(self):
        self.u.specials2=0x11
        self.u.specials|=Specials.ECM_TECH
        self.assertTrue(equipment.command(self.u,'stealtharmor')['accepted'])
        self.assertFalse(equipment.command(self.u,'stealtharmor')['accepted'])
        self.advance(29)
        self.assertFalse(self.u.status2 & S2.STH_ARMOR_ON)
        self.advance(30)
        self.assertTrue(self.u.status2 & S2.STH_ARMOR_ON)
        self.assertTrue(equipment.command(self.u,'stealtharmor')['accepted'])
        self.u.crit_status|=CritStatus.ECM_DESTROYED
        self.advance(60)
        self.assertTrue(self.u.status2 & S2.STH_ARMOR_ON)

    def test_null_signature_shutdown_at_completion_does_not_reschedule(self):
        self.u.specials2=0x10
        self.assertTrue(equipment.command(self.u,'nullsig')['accepted'])
        self.u.clear_status(S.STARTED)
        self.advance(30)
        self.u.set_status(S.STARTED)
        self.advance(60)
        self.assertFalse(self.u.status2 & S2.NULLSIGSYS_ON)

    def test_dig_uses_source_bits_and_movement_cancels_both_views(self):
        from systems.movement_commands import speed
        self.assertTrue(equipment.command(self.u,'dig')['accepted'])
        self.assertTrue(self.u.digging)
        self.advance(19)
        self.assertFalse(self.u.dug_in)
        self.advance(20)
        self.assertTrue(self.u.dug_in)
        self.assertEqual(4,self.u.tank_crit_status & 12)
        speed(self.e,self.u,'walk')
        self.assertFalse(self.u.dug_in)
        self.assertEqual(0,self.u.tank_crit_status & 12)

    def test_turret_duplicate_allowed_but_later_lock_prevents_repair(self):
        self.u.tank_crit_status=2
        self.assertTrue(equipment.command(self.u,'fixturret')['accepted'])
        self.assertTrue(equipment.command(self.u,'fixturret')['accepted'])
        self.u.tank_crit_status|=1
        self.advance(60)
        self.assertEqual(3,self.u.tank_crit_status)

    def test_flip_changes_live_arc_flag_and_prone_guard_preserves_it(self):
        self.u.specials|=Specials.FLIPABLE_ARMS
        self.assertTrue(equipment.command(self.u,'fliparms')['accepted'])
        self.assertTrue(self.u.has_status(S.FLIPPED_ARMS))
        self.u.set_status(S.FALLEN)
        self.assertFalse(equipment.command(self.u,'fliparms')['accepted'])
        self.assertTrue(self.u.has_status(S.FLIPPED_ARMS))

    def test_self_destruct_encoding_distinguishes_256_and_257(self):
        from types import SimpleNamespace
        from core.events import EventType
        self.assertEqual('countdown-255',equipment.explode_event(SimpleNamespace(data=self.u,data2=256)))
        self.assertEqual(255,next(e.data2 for e in self.e.events._events.values() if e.event_type==EventType.EXPLODE))
        self.assertEqual('cancelled',equipment.explode_event(SimpleNamespace(data=self.u,data2=257)))

    def test_self_destruct_ammo_command_still_encodes_reactor_countdown(self):
        from entities.crittypes import i2ammo
        from entities.weapon import get_weapon
        from core.events import EventType
        slot=self.u.sections[4].criticals[8]
        slot.type=i2ammo(get_weapon('IS.Sniper').index)
        slot.data=5
        self.assertTrue(equipment.explode(self.u,'ammo')['accepted'])
        event=next(e for e in self.e.events._events.values() if e.event_type==EventType.EXPLODE)
        self.assertEqual(60,event.data2)
        self.assertEqual(1,event.tick)
        self.assertIsNone(self.u.pilot)
        self.assertFalse(equipment.explode(self.u,'stop')['accepted'])
