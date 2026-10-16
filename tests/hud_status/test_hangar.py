import unittest
from tools.core_simulation import CoreSession
from entities.map_objects import MapObject,add_object
from entities.mech import MechStatus as S

class HangarTests(unittest.TestCase):
    def setUp(self):
        self.s=CoreSession({'maps':[{'name':'outside','id':100,'size':[20,20]},{'name':'inside','id':101,'size':[20,20]}], 'units':[{'name':'u'},{'name':'tow'}], 'config':{'periodic_updates':False},'actions':[]})
        self.u=self.s.units['u'];self.tow=self.s.units['tow'];self.inside=self.s.maps['inside']
        add_object(self.u.map,4,MapObject(x=self.u.x,y=self.u.y,obj=self.inside._id));add_object(self.inside,6,MapObject(x=4,y=4,datac=ord('n')))
        self.u.carrying=self.tow._id
    def test_eighteen_ticks_moves_tow(self):
        from systems.hangar import enter_base
        self.assertTrue(enter_base(self.u)['ok'])
        self.s.engine.run_ticks(17);self.assertIs(self.u.map,self.s.maps['outside'])
        self.s.engine.run_ticks(1);self.assertIs(self.u.map,self.inside);self.assertIs(self.tow.map,self.inside)
        self.assertEqual((4,4),(self.u.x,self.u.y))
    def test_lock_threshold_and_live_recheck(self):
        from systems.hangar import enter_base
        self.inside.enter_lock='false';self.inside.cfmax=100;self.inside.cf=50
        self.assertFalse(enter_base(self.u)['ok'])
        self.inside.cf=49;self.assertTrue(enter_base(self.u)['ok'])
        self.inside.buildflag=8
        self.s.engine.run_ticks(18);self.assertIs(self.u.map,self.s.maps['outside'])
    def test_mechwarrior_ooc_entry_ends_at_personnel_transfer(self):
        from unittest.mock import patch,Mock
        from entities.mech import UnitType
        from systems.hangar import enter_base
        self.u.unit_type=UnitType.MW;self.u.carrying=-1;self.u.autonomous_map_refresh=Mock()
        self.assertTrue(enter_base(self.u)['ok'])
        with patch('systems.occupants.enter_mw_bay') as transfer:
            self.s.engine.run_ticks(18)
        transfer.assert_called_once_with(self.u,self.inside._id)
        self.u.autonomous_map_refresh.assert_not_called()
