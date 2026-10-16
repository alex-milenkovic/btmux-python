"""Text selector parsing and command boundaries for modes and TICs."""
import unittest
from unittest.mock import patch
from core.game_loop import GameEngine
from entities.mech import Mech,WeaponState,MechStatus as S,FireMode as F
from entities.pilot import Pilot
from entities.map import GameMap
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from systems import weapon_modes as modes,tic


class SelectorTest(unittest.TestCase):
    def setUp(self):
        self.u=Mech.create_test_mech()
        self.u.pilot=Pilot()
        self.u.map=GameMap(8,8)
        self.u.set_status(S.STARTED)
        self.e=GameEngine()
        self.u.map._id=1000
        self.e.register_entity(self.u.map)
        self.e.register_entity(self.u)
        self.u.mapindex=self.u.map._id
        weapon=get_weapon('IS.UltraAC/5')
        self.u.weapons=[]
        for loc in (0,1,2):
            for crit in range(4, 4 + weapon.crits):
                self.u.sections[loc].criticals[crit].type=i2weapon(weapon.index)
            self.u.weapons.append(WeaponState(weapon_idx=weapon.index,section=loc,critical=4))

    def test_selector_prefix_zero_duplicate_and_abort(self):
        for text,expected in (('00',[]),('+0',[]),('1junk',[1]),('2-0',[0,1,2]),('0,0',[]),('0,99,1',[0])):
            for ws in self.u.weapons:self.u.sections[ws.section].criticals[4].firemode=0
            modes.mode_command(self.u,'ultra',text)
            selected=[i for i,ws in enumerate(self.u.weapons) if self.u.sections[ws.section].criticals[4].firemode & F.ULTRA_MODE]
            self.assertEqual(expected,selected)

    def test_per_weapon_failure_continues_but_unstarted_command_does_not(self):
        self.u.sections[0].criticals[4].data=2
        modes.mode_command(self.u,'ultra','0,1')
        self.assertTrue(self.u.sections[1].criticals[4].firemode & F.ULTRA_MODE)
        self.u.clear_status(S.STARTED)
        modes.mode_command(self.u,'ultra','2')
        self.assertEqual(0,self.u.sections[2].criticals[4].firemode)

    def test_rac_first_character_and_no_common_command_guard(self):
        weapon=get_weapon('IS.RotaryAC/5')
        self.u.weapons[0].weapon_idx=weapon.index
        for slot in self.u.sections[0].criticals[4:]:
            slot.type=0
        for crit in range(4, 4 + weapon.crits):
            self.u.sections[0].criticals[crit].type=i2weapon(weapon.index)
        self.u.clear_status(S.STARTED)
        modes.mode_command(self.u,'rac','0 2foo')
        self.assertTrue(self.u.sections[0].criticals[4].firemode & F.RAC_TWOSHOT_MODE)

    def test_list_rows_use_source_two_column_callback_order(self):
        weapon=get_weapon('IS.UltraAC/5')
        for loc in (3,4):
            for crit in range(4,4 + weapon.crits):
                self.u.sections[loc].criticals[crit].type=i2weapon(weapon.index)
        self.u.tics[0]=set(range(5))
        rows,_=tic.list_tic(self.u,'0')
        self.assertEqual([0,3,1,4,2],[row[0] for row in rows])

    def test_empty_tic_still_checks_started_and_hold(self):
        self.u.clear_status(S.STARTED)
        messages=tic.fire_tic(self.e,self.u,'0')
        self.assertTrue(any('Reactor' in message for message in messages))
        self.assertFalse(any('Click' in message for message in messages))

    def test_fall_aborts_comma_tail_after_first_real_fire_callback(self):
        self.u.tics[0]={0,1}
        self.u.tics[1]={2}
        def fire(*args,**kwargs):self.u.set_status(S.FALLEN)
        with patch('systems.tic.fire_weapon_number',side_effect=fire) as callback:
            tic.fire_tic(self.e,self.u,'0,1')
        self.assertEqual(1,callback.call_count)
