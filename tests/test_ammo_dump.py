"""Dump event cadence and rear-hit ignition use real ammo and damage paths."""
from tests.movement_fixture import MovementTestCase
from entities.mech import Location, WeaponState, FireMode, MechStatus
from entities.weapon import get_weapon
from entities.crittypes import i2ammo
from core.randomness import use_source
from systems import ammo_dump


class AmmoDump(MovementTestCase):
    def test_rear_hit_ignores_canceled_dump_with_stale_mirrors(self):
        from systems.combat import apply_damage_with_transfer
        self.unit.sections[Location.CTORSO].rear = 100
        ammo_dump.mech_dump(self.engine, self.unit, 'LT 1')
        self.unit._dump_event.cancel()
        self.assertTrue(self.unit.dumping)
        draws = []
        def draw(name, lo, hi, fallback):
            draws.append(name)
            return lo
        with use_source(draw):
            apply_damage_with_transfer(self.unit, Location.CTORSO, 1, True, weapon=self.weapon, engine=self.engine)
        self.assertEqual((99, 3), (self.unit.sections[Location.CTORSO].rear, self.slot.data))
        self.assertNotIn('dump_candidates', draws)
        self.assertFalse(self.unit.dumping)
        self.assertFalse(any('ignites' in message for message in self.unit.movement_messages))

    def test_dump_ignition_recovers_selection_from_live_queue(self):
        self.unit.sections[Location.CTORSO].rear = 100
        ammo_dump.mech_dump(self.engine, self.unit, 'LT 1')
        self.unit._dump_event = self.unit._dump_selection = None
        self.unit.dumping = False
        with use_source(lambda name, lo, hi, fallback: lo):
            self.assertEqual(10, ammo_dump.blow_dumping_ammo(self.unit, self.unit, Location.CTORSO))
        self.assertEqual(2, self.slot.data)

    def test_terminal_rear_overflow_never_ignites_after_destruction(self):
        from core.events import EventType
        from systems.combat import apply_damage_with_transfer
        from unittest.mock import patch
        for entry in (Location.CTORSO, Location.LTORSO):
            with self.subTest(entry=entry):
                self.setUp()
                self.slot.data = 0
                safe_bin = self.unit.sections[Location.RTORSO].criticals[0]
                safe_bin.type, safe_bin.data = i2ammo(self.weapon.index), 3
                for location in (Location.CTORSO, Location.LTORSO):
                    self.unit.sections[location].rear = 0
                    self.unit.sections[location].internal = 1
                self.assertTrue(ammo_dump.mech_dump(self.engine, self.unit, 'RT 1')[0])
                draws = []
                def draw(name, lo, hi, fallback):
                    draws.append(name)
                    return lo
                with use_source(draw), patch.object(ammo_dump, 'rear_hit', wraps=ammo_dump.rear_hit) as rear_hit:
                    apply_damage_with_transfer(self.unit, entry, 4, True, weapon=self.weapon, engine=self.engine)
                self.assertTrue(self.unit.is_destroyed)
                self.assertFalse(self.engine.has_event(EventType.DUMP, self.unit))
                self.assertEqual(3, safe_bin.data)
                self.assertNotIn('dump_candidates', draws)
                if entry == Location.CTORSO:
                    rear_hit.assert_not_called()
                self.assertFalse(any('ignites' in message for message in self.unit.movement_messages))


    def setUp(self):
        super().setUp()
        self.weapon = get_weapon('IS.AC/10')
        self.addCleanup(setattr, self.weapon, 'ammo_per_ton', self.weapon.ammo_per_ton)
        self.weapon.ammo_per_ton = 5  # phase fixture, with a valid source-catalog identity
        self.unit.weapons = [WeaponState(weapon_idx=self.weapon.index,section=Location.RARM,critical=4)]
        self.slot=self.unit.sections[Location.LTORSO].criticals[0]
        self.slot.type,self.slot.data=i2ammo(self.weapon.index),3

    def test_rate_uses_absolute_event_phase(self):
        self.engine.events.set_tick(5)
        self.assertTrue(ammo_dump.mech_dump(self.engine,self.unit,'all')[0])
        self.engine.run_ticks(1)
        self.assertEqual(self.slot.data,2)
        self.assertTrue(self.unit.dumping)

    def test_integer_rate_and_completion(self):
        self.weapon.ammo_per_ton=60
        ammo_dump.mech_dump(self.engine,self.unit,'LT 1')
        self.engine.run_ticks(2)
        self.assertEqual(self.slot.data,0)
        self.assertFalse(self.unit.dumping)

    def test_all_replaces_bin_and_stop_preserves_rounds(self):
        self.assertTrue(ammo_dump.mech_dump(self.engine,self.unit,'LT 1')[0])
        old=self.unit._dump_event
        self.assertTrue(ammo_dump.mech_dump(self.engine,self.unit,'all')[0])
        self.assertTrue(old.zombie)
        self.assertFalse(ammo_dump.mech_dump(self.engine,self.unit,'all')[0])
        self.assertTrue(ammo_dump.mech_dump(self.engine,self.unit,'stop')[0])
        self.engine.run_ticks(10)
        self.assertEqual(self.slot.data,3)

    def test_stopped_callback_cancels_without_decrement(self):
        ammo_dump.mech_dump(self.engine,self.unit,'all')
        self.unit.clear_status(MechStatus.STARTED)
        self.engine.run_ticks(1)
        self.assertFalse(self.unit.dumping)
        self.assertEqual(self.slot.data,3)

    def test_broken_all_is_accepted_but_callback_does_no_work(self):
        self.slot.firemode |= FireMode.BROKEN_MODE
        self.assertTrue(ammo_dump.mech_dump(self.engine,self.unit,'all')[0])
        self.engine.run_ticks(1)
        self.assertEqual(self.slot.data,3)
        self.assertFalse(self.unit.dumping)

    def test_rear_weapon_hit_ignites_one_round_without_probability_gate(self):
        from systems.combat import apply_damage_with_transfer
        self.unit.sections[Location.CTORSO].rear=100
        ammo_dump.mech_dump(self.engine,self.unit,'LT 1')
        with use_source(lambda name,lo,hi,fallback: lo):
            apply_damage_with_transfer(self.unit,Location.CTORSO,1,True,weapon=self.weapon,engine=self.engine)
        self.assertEqual(self.unit.sections[Location.CTORSO].rear,89)
        self.assertEqual(self.slot.data,2)
        self.assertFalse(self.unit.dumping)
