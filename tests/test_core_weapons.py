"""Critical slots determine enumeration, readiness, and partial failure."""
import unittest
from entities.mech import Mech, FireMode as F, UnitType as U, WeaponState
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from systems import weapon_inventory as inventory


def mount(unit, name='IS.PPC', loc=0, first=0, count=None):
    weapon = get_weapon(name)
    size = weapon.crits if unit.unit_type == U.MECH else 1
    for slot in unit.sections[loc].criticals[first:first + (size if count is None else count)]:
        slot.type = i2weapon(weapon.index)
    return weapon


class WeaponInventoryTest(unittest.TestCase):
    def test_runs_split_and_invalid_section_is_skipped(self):
        unit = Mech()
        weapon = mount(unit, count=6)
        self.assertEqual([0, 3], [r.critical for r in inventory.find_weapons(unit, 0)])
        unit.sections[0].criticals[5].type = 0
        self.assertIsNone(inventory.find_weapons(unit, 0))
        other = mount(unit, 'IS.SmallLaser', 1)
        self.assertEqual(other.index, inventory.find_weapon_index(unit, 0))
        self.assertEqual(-1, inventory.find_weapon_index(unit, -1))
        self.assertNotEqual(weapon.index, other.index)

    def test_nine_crit_split_and_nonmech_single_slots(self):
        unit = Mech()
        mount(unit, 'CL.LB20-XAC', count=2)
        self.assertEqual(1, len(inventory.find_weapons(unit, 0)))
        unit.unit_type = U.VEH_GROUND
        self.assertEqual(2, len(inventory.find_weapons(unit, 0)))

    def test_lookup_readiness_sight_and_physical_priority(self):
        from systems.weapon_modes import find_weapon_number_on_mech
        unit = Mech()
        weapon = mount(unit)
        slot = unit.sections[0].criticals[0]
        slot.data, unit.sections[0].recycle = 1, 1
        self.assertEqual(-4, find_weapon_number_on_mech(unit, 0)[0])
        self.assertEqual(weapon.index, find_weapon_number_on_mech(unit, 0, sight=True)[0])
        slot.data = 0
        self.assertEqual(-5, find_weapon_number_on_mech(unit, 0)[0])
        slot.firemode = F.BROKEN_MODE
        self.assertEqual(-2, find_weapon_number_on_mech(unit, 0, sight=True)[0])

    def test_from_index_checks_ordinal_but_returns_first_critical(self):
        unit = Mech()
        weapon = mount(unit, first=3)
        self.assertEqual((True, 0, 3), inventory.find_weapon_from_index(unit, weapon.index))
        unit.sections[0].criticals[0].firemode = F.DESTROYED_MODE
        self.assertEqual((False, 0, 3), inventory.find_weapon_from_index(unit, weapon.index))
        mount(unit, loc=1, first=5)
        self.assertEqual((True, 1, 5), inventory.find_weapon_from_index(unit, weapon.index))

    def test_nonfunctional_threshold_and_disabled_precedence(self):
        unit = Mech()
        mount(unit, 'IS.LB10-XAC')
        slots = unit.sections[0].criticals
        slots[0].firemode = F.DESTROYED_MODE | F.DISABLED_MODE
        self.assertEqual(-1, inventory.weapon_is_nonfunctional(unit, 0, 0))
        slots[1].firemode = F.DISABLED_MODE
        self.assertEqual(1, inventory.weapon_is_nonfunctional(unit, 0, 0))
        slots[1].firemode = slots[2].firemode = F.DESTROYED_MODE
        self.assertEqual(2, inventory.weapon_is_nonfunctional(unit, 0, 0))
        slots[0].firemode = slots[1].firemode = slots[2].firemode = F.BROKEN_MODE | F.DAMAGED_MODE
        self.assertEqual(0, inventory.weapon_is_nonfunctional(unit, 0, 0))

    def test_state_mirror_reordered_without_losing_mount_state(self):
        unit = Mech()
        weapon = mount(unit, loc=2)
        other = mount(unit, 'IS.SmallLaser', loc=0)
        state = WeaponState(section=2, critical=0, weapon_idx=weapon.index, ammo_section=4)
        unit.weapons = [state]
        inventory.sync_weapon_states(unit)
        self.assertEqual([other.index, weapon.index], [w.weapon_idx for w in unit.weapons])
        self.assertIs(state, unit.weapons[1])
        self.assertEqual(4, unit.weapons[1].ammo_section)

    def test_first_weapon_crit_walks_all_twelve_slots_in_head(self):
        from systems.criticals import find_first_weapon_crit
        unit = Mech()
        weapon = mount(unit,'IS.SmallLaser',loc=7,first=10)
        self.assertEqual(10,find_first_weapon_crit(unit,7,-1,0,i2weapon(weapon.index),1))

    def test_full_recycle_returns_first_section_and_weapon_priority(self):
        from systems.physical import mech_full_no_recycle
        unit = Mech()
        mount(unit,loc=2)
        unit.sections[2].internal=1
        unit.sections[2].criticals[0].data=1
        unit.sections[1].recycle=1
        self.assertEqual(2,mech_full_no_recycle(unit,3))
        self.assertEqual(1,mech_full_no_recycle(unit,1))
        unit.sections[2].recycle=1
        unit.sections[1].recycle=0
        self.assertEqual(1,mech_full_no_recycle(unit,3))
