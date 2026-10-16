"""Source float accumulators, sparse unit costs and session cost tables."""
import unittest
from entities.mech import Mech, UnitType as U, MoveType as M, Specials as S
from entities.crittypes import Special, i2special, i2ammo, i2weapon
from entities.weapon import get_weapon
from systems import economy


class CostTest(unittest.TestCase):
    def test_caseii_cost_uses_the_source_switch_numeric_constant(self):
        unit = Mech(tonnage=50, max_speed=0, num_sinks=10)
        baseline = economy.fasa_cost(unit).value
        # mech.h defines CASE_II=33 and the cost switch's CASEII=50.
        unit.sections[0].criticals[0].type = i2special(33)
        self.assertEqual(baseline, economy.fasa_cost(unit).value)
        unit.sections[0].criticals[0].type = i2special(50)
        self.assertEqual(baseline + 262500, economy.fasa_cost(unit).value)

    def test_sparse_cost_and_float32_final_truncation(self):
        for rating, expected in ((0, 705000), (200, 2604999)):
            unit = Mech(tonnage=50, max_speed=0, engine_rating=rating, num_sinks=10)
            result = economy.fasa_cost(unit)
            self.assertEqual(expected, result.value)
            self.assertEqual('Engine', next(row['label'] for row in result.components if row['label'] == 'Engine'))
        self.assertEqual(0, economy.fasa_cost(Mech(unit_type=U.AERO)).value)
        self.assertEqual(2**64 - 1, economy.fasa_cost(None).value)

    def test_exact_cost_storage_with_isolated_categories_and_sessions(self):
        first, second = economy.CostTables(), economy.CostTables()
        value = 2**53 + 1
        for kind in (1, 193, 394, 385, 512):
            first.set(kind, value)
            self.assertEqual(value, first.get(kind))
            self.assertEqual(0, second.get(kind))
        first.set(0, 5)
        self.assertEqual(0, first.get(0))
        with self.assertRaises(ValueError): first.set(1, -1)
        with self.assertRaises(ValueError): first.set(1, 2**64)

    def test_actuator_components_count_disabled_and_destroyed(self):
        unit = Mech(tonnage=50)
        for i in range(4): unit.sections[0].criticals[i].type = i2special(i)
        self.assertEqual(11500, economy.actuator_cost(unit, 0).value)
        self.assertEqual(17500, economy.actuator_cost(unit, 0, leg=True).value)

    def test_source_table_weapon_cost_and_empty_ammo_pruning(self):
        unit = Mech(tonnage=50, max_speed=0, num_sinks=10)
        weapon = get_weapon('IS.AC/5')
        for slot in unit.sections[0].criticals[:weapon.crits]: slot.type = i2weapon(weapon.index)
        slot = unit.sections[1].criticals[0]
        slot.type = i2ammo(weapon.index)
        dry = economy.fasa_cost(unit)
        slot.data = 1
        wet = economy.fasa_cost(unit)
        self.assertEqual(weapon.ammo_cost * 1.5, wet.value - dry.value)
        self.assertGreater(weapon.cost, 0)

    def test_clan_case_uninitialized_source_domain_is_explicit(self):
        unit = Mech(unit_type=U.BSUIT, specials=S.CLAN_TECH)
        with self.assertRaisesRegex(ValueError, 'uninitialized Clan CASE'):
            economy.fasa_cost(unit)
        index = get_weapon('IS.AC/5').index
        for sec in unit.sections: sec.criticals[0].type = i2ammo(index)
        self.assertEqual(2925000, economy.fasa_cost(unit).value)

    def test_small_cockpit_and_artemis_ammo_priorities(self):
        from entities.mech import AmmoMode as A, FireMode as F
        unit = Mech(tonnage=50, max_speed=0, num_sinks=10)
        base = economy.fasa_cost(unit).value
        unit.specials2 = 0x2000000
        self.assertEqual(37500, base - economy.fasa_cost(unit).value)
        weapon = get_weapon('IS.AC/5')
        slot = unit.sections[0].criticals[0]
        slot.type, slot.data, slot.ammomode = i2ammo(weapon.index), 1, A.ARTEMIS_MODE
        current = economy.fasa_cost(unit)
        self.assertEqual(9000, next(row['amount'] for row in current.components if row['label'] == weapon.name))
        slot.firemode = F.HALFTON_MODE
        current = economy.fasa_cost(unit)
        self.assertEqual(2250, next(row['amount'] for row in current.components if row['label'] == weapon.name))

    def test_debug_records_source_components_without_changing_price(self):
        from core.game_loop import GameEngine
        unit = Mech(tonnage=50,max_speed=0,num_sinks=10)
        engine = GameEngine()
        engine.register_entity(unit)
        expected = economy.fasa_cost(unit).value
        engine.cost_debug = True
        self.assertEqual(expected,economy.fasa_cost(unit).value)
        self.assertTrue(unit.debug_messages)
        self.assertTrue(unit.debug_messages[0].startswith('Addprice -'))
        self.assertEqual(unit.debug_messages,[r['text'] for r in engine.effects.channels])
        self.assertTrue(all(r['applied'] for r in unit.channel_requests))
