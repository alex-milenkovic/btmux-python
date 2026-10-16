"""Legacy and newer BV are separate algorithms with different source quirks."""
import unittest
from unittest.mock import patch
from dataclasses import replace
from entities.mech import Mech, UnitType as U, MoveType as M, Specials as S
from entities.crittypes import i2weapon, i2ammo
from entities.weapon import get_weapon_by_index, WEAPON_INDEX
from entities.pilot import Pilot
from systems import battle_value as bv


def empty(): return Mech(tonnage=50, max_speed=0, num_sinks=10)


class BattleValueTest(unittest.TestCase):
    def test_debug_preserves_add_and_subtract_identity_for_signed_values(self):
        from types import SimpleNamespace
        from systems.economy import calculation
        unit = empty()
        unit._engine = SimpleNamespace(cost_debug=True)
        for subtract in (False, True):
            for value in (0, -5, 5):
                result = calculation(unit, 'AddDefBV', 100)
                result.add('signed', value, subtract=subtract)
                self.assertEqual(100-value if subtract else 100+value, result.value)
                prefix, separator = ('SubDefBV', '-') if subtract else ('AddDefBV', ' ')
                self.assertEqual(f'{prefix} {"signed":>25}{separator}{value:8.2f}', unit.debug_messages[-1])

    def test_defensive_brackets_current_points_and_jump_equality(self):
        unit = empty()
        unit.sections[0].armor, unit.sections[0].internal = 100, 50
        unit.measured_mass = unit.tonnage * 1024  # nominal load isolates the BV brackets
        from physics.cargo import CACHE_FLAGS
        for mp, expected in ((2,350),(3,385),(5,420),(7,455),(10,490),(18,525),(25,560)):
            unit.max_speed = mp * 10.75
            unit.clear_crit_status(CACHE_FLAGS)
            self.assertAlmostEqual(expected, bv.defensive_bv(unit).value, places=4)
        unit.max_speed = unit.jump_speed = 21.5
        unit.clear_crit_status(CACHE_FLAGS)
        self.assertEqual(350, bv.defensive_bv(unit).value)
        unit.jump_speed = 32.25
        self.assertEqual(385, bv.defensive_bv(unit).value)

    def test_offensive_integer_halving_and_reverse_stable_ties(self):
        unit = empty()
        for i in range(2): unit.sections[0].criticals[i].type = i2weapon(i)
        first, second = WEAPON_INDEX[:2]
        try:
            WEAPON_INDEX[0] = replace(first,bv=101,heat=5)
            WEAPON_INDEX[1] = replace(second,bv=80,heat=5)
            for sinks, expected in ((0,140),(1,191),(6,231)):
                unit.num_sinks = sinks
                self.assertEqual(expected,bv.offensive_bv(unit).value)
            WEAPON_INDEX[0] = replace(first,bv=50,heat=0)
            WEAPON_INDEX[1] = replace(second,bv=50,heat=5)
            unit.num_sinks = 0
            result = bv.offensive_bv(unit)
            self.assertEqual(100,result.value)
            self.assertEqual(second.name,result.components[0]['label'])
        finally: WEAPON_INDEX[0], WEAPON_INDEX[1] = first, second

    def test_legacy_cache_boundary_and_no_cache_writeback(self):
        unit = empty()
        unit.bv, unit.bv_last, unit.pilot = 777, 0, Pilot(gunnery=4,piloting=5)
        self.assertEqual(777,bv.calculate_bv(unit,100,100,tick=29).value)
        self.assertEqual(0,unit.bv_last)
        self.assertEqual(50,bv.calculate_bv(unit,100,100,tick=30).value)
        self.assertEqual((777,30),(unit.bv,unit.bv_last))
        self.assertEqual(50,bv.calculate_bv(unit,4,5,tick=40).value)
        self.assertEqual(30,unit.bv_last)

    def test_legacy_and_new_defense_count_destroyed_ammo_differently(self):
        from entities.mech import FireMode
        from entities.weapon import get_weapon
        unit = empty()
        unit.sections[4].criticals[0].type = i2ammo(get_weapon('IS.AC/5').index)
        unit.sections[4].criticals[0].firemode = FireMode.DESTROYED_MODE
        self.assertEqual(10,bv.defensive_bv(unit).value)
        self.assertEqual(50,bv.calculate_bv(unit,4,5).value)
