"""Ammo capacity and grouped inventory preserve slot mode priorities."""
import unittest
from entities.mech import Mech, AmmoMode as A, FireMode as F
from entities.crittypes import i2ammo
from entities.weapon import get_weapon
from systems import combat_ammunition as ammo


class AmmunitionInventoryTest(unittest.TestCase):
    def test_capacity_priority_and_half_up(self):
        self.assertEqual([11, 5, 22, 5, 13, 16, 5], [
            ammo.ammo_capacity(base, fire, mode) for base, fire, mode in (
                (11, 0, 0), (11, F.HALFTON_MODE, 0), (11, 0, A.AC_CASELESS_MODE),
                (11, 0, A.AC_AP_MODE | A.AC_CASELESS_MODE), (11, 0, A.MML_LRM_MODE),
                (13, 0, A.MML_LRM_MODE), (11, F.HALFTON_MODE, A.MML_LRM_MODE))])

    def test_all_twelve_slots_group_modes_keep_broken_capacity(self):
        unit = Mech()
        weapon = get_weapon('IS.AC/10')
        for loc, pos, rounds, mode in ((7, 10, 4, 0), (7, 11, 6, 0), (0, 0, 2, A.AC_CASELESS_MODE)):
            slot = unit.sections[loc].criticals[pos]
            slot.type, slot.data, slot.ammomode = i2ammo(weapon.index), rounds, mode
        unit.sections[7].criticals[11].firemode = F.BROKEN_MODE
        groups = ammo.find_ammunition(unit, True)
        self.assertEqual([(2, 20), (4, 20)], [(g.current, g.maximum) for g in groups])
        self.assertEqual(6, ammo.find_rounds_for_weapon(unit, weapon.index))
        unit.sections[0].criticals[0].data = 0
        self.assertEqual(1, len(ammo.find_ammunition(unit)))
        self.assertEqual(2, len(ammo.find_ammunition(unit, True)))

    def test_heat_selection_includes_upper_slots_and_disabled_bins(self):
        from systems.heat import find_destructive_ammo
        unit = Mech()
        weapon = get_weapon('IS.AC/10')
        for loc, pos, rounds in ((0, 0, 4), (7, 11, 5)):
            slot = unit.sections[loc].criticals[pos]
            slot.type, slot.data = i2ammo(weapon.index), rounds
        unit.sections[7].criticals[11].firemode = F.DISABLED_MODE
        chosen = find_destructive_ammo(unit)
        self.assertEqual((7, 11), (chosen.location, chosen.slot))
