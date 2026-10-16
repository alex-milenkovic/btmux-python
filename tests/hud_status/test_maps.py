import unittest
from entities.map import GameMap
from entities.mech import Mech, MoveType
from systems.map_display import tactical, hud_tactical, lrs_glyph, palette

class MapTests(unittest.TestCase):
    def setUp(self):
        from tools.core_simulation import CoreSession
        self.session=CoreSession({'maps':[{'name':'map','id':100,'size':[8,8]}],
            'units':[{'name':'map','at':[3,3,0]}],'config':{'periodic_updates':False},'actions':[]})
        self.unit=self.session.units['map'];self.board=self.unit.map
        self.unit.tac_range=self.unit.lrs_range=20
    def test_hex_geometry_labels_and_self(self):
        result=tactical(self.unit,'')
        self.assertEqual(20,len(result['rows']))
        self.assertTrue(any('**' in line for line in result['rows']))
        self.assertTrue(any('/' in line and '\\' in line for line in result['rows']))
        self.assertEqual(64,len(result['cells']))
    def test_hud_height_one_has_no_rows(self):
        result=hud_tactical(self.unit,'1')
        self.assertTrue(result['ok']);self.assertEqual([],result['rows'])
        self.assertEqual([0,3,7,2],result['start'][:4])
    def test_map_commands_keep_live_navigation_fields(self):
        from systems.observation import map_readout
        self.unit.speed=7;self.unit.vertical_speed=2;self.unit.facing=60
        for kind,args in [('tactical',''),('navigate',''),('lrs','m')]:
            result=map_readout(self.unit,kind,args)
            self.assertEqual([3,3,0],result['position'])
            self.assertEqual((7,2,60),tuple(result[k] for k in ('speed','vertical_speed','facing')))
    def test_mode_errors_and_palette_isolation(self):
        self.assertFalse(tactical(self.unit,'z')['ok'])
        self.board.dark=True
        self.assertFalse(tactical(self.unit,'c')['ok'])
        default,_=palette('')
        modified,_=palette('n')
        self.assertEqual('',modified[0]);self.assertNotEqual(default,modified)
        self.assertEqual(2,len(palette('!')[1]));self.assertEqual(default,palette('')[0])
    def test_flight_fallthrough(self):
        other=Mech.create_test_mech('other');other.move_type=MoveType.FLY;other.team=2
        self.assertEqual('B',lrs_glyph(self.unit,other,False))
        self.assertEqual('*',lrs_glyph(self.unit,self.unit,True))
    def test_lrs_elevation_color_uses_cell_terrain_and_resets(self):
        from systems.map_display import lrs
        self.board.set_terrain(4,4,'~');self.board.set_elevation(4,4,2)
        result=lrs(self.unit,'c')
        self.assertTrue(any('%cb2' in row for row in result['rows']))
        self.assertTrue(any('%cn' in row for row in result['rows']))
    def test_unknown_tactical_cells_use_unknown_palette_entry(self):
        from systems.map_display import color_rows
        colors,_=palette('');colors[13]='G';colors[1]='b'
        self.assertEqual(['%ch%cg??%cn'],color_rows(['??'],colors))
    def test_lrs_masks_same_team_color_without_identification(self):
        from unittest.mock import patch
        from systems.map_display import lrs
        other=Mech.create_test_mech('other');self.board.add_mech(other);other.set_hex_position(4,4)
        other.team=self.unit.team;self.unit.command_actor.ansimap=True
        with patch('systems.map_display.in_line_of_sight',return_value=True),patch('systems.map_display.in_line_of_sight_nb',return_value=False):
            rows=lrs(self.unit,'m')['rows']
        self.assertTrue(any('%crB' in row for row in rows))
    def test_navigate_ignores_tactical_size_preference(self):
        self.unit.command_actor.tacsize='invalid'
        self.assertEqual([],tactical(self.unit,'',navigate=True)['warnings'])
