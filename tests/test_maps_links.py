import unittest
from tests.test_maps_objects import fixture
from entities.map import GameMap
from entities.mech import Mech
from entities.map_objects import bits_for,MapObject,add_object
from systems import map_links as links


class LinksTest(unittest.TestCase):
    def test_coordinate_partial_writes_and_reverse_entrances(self):
        board=GameMap(9,7)
        self.assertEqual((False,1,None),links.parse_coord(board,2,'1,x'))
        self.assertEqual((True,99,-2),links.parse_coord(board,0,'99,-2'))
        self.assertEqual((True,0,3),links.parse_coord(board,3,'abc'))
        self.assertEqual(4,links.add_entrances(board,'0 2 2 99 ignored'))
        self.assertEqual([(119,8,3),(115,4,4),(101,6,3),(110,4,0)],[(o.datac,o.x,o.y) for o in board.map_objects[6]])

    def test_recursive_links_share_objects_bits_and_parent_and_reject_cycle(self):
        engine,board=fixture(); child=GameMap(9,9,'Depot'); child._id=20; engine.register_entity(child)
        bits_for(board).set(1,1,1)
        attributes={10:{'BUILDLINKS':'20 -1 10 999'},20:{'BUILDCOORD':'1,1','BUILDENTRANCE':'0 0 -1 0'}}
        self.assertEqual([1,1,3],links.update_links(board,attributes))
        self.assertEqual(20,board.map_objects[4][0].obj)
        self.assertEqual((10,10),(child.onmap,child.map_objects[5][0].obj))
        self.assertEqual(12,bits_for(board).query(1,1,3))
        self.assertEqual((1,1),(links.by_target(board,20).x,links.by_target(board,20).y))
        attributes[20]['BUILDLINKS']='10'; attributes[10]['BUILDCOORD']='1,1'
        with self.assertRaisesRegex(ValueError,'cycle'): links.update_links(board,attributes)

    def test_linked_and_team_specific_landing_block(self):
        engine,board=fixture(); mech=Mech(); mech.team=2
        self.assertFalse(links.linked(board)); links.set_linked(board); links.set_linked(board)
        self.assertEqual(2,len(board.map_objects[7]))
        self.assertTrue(links.linked(board))
        links.block_lz(board,'1 1 0 2',creator=45)
        self.assertFalse(links.blocked_lz(mech,board,1,1))
        mech.team=3
        self.assertTrue(links.blocked_lz(mech,board,1,1))
        self.assertFalse(links.blocked_lz(mech,board,2,1))

    def test_typed_hangar_exit_moves_unit_and_preserves_carrying(self):
        from systems.map_transitions import check_edge_of_map
        from entities.mech import MechStatus as S
        engine,exterior=fixture(); interior=GameMap(9,9,'Depot'); interior._id=20
        interior.cf=interior.cfmax=100; engine.register_entity(interior)
        links.update_links(exterior,{10:{'BUILDLINKS':'20'},20:{'BUILDCOORD':'1,1','BUILDENTRANCE':'0 0 0 0'}})
        tower=Mech(); tow=Mech()
        for unit in (tower,tow):
            unit.in_character=False; engine.register_entity(unit); interior.add_mech(unit)
        tower.carrying=tow._id; tow.set_status(S.TOWED)
        tower.x=-1; tower.y=4
        check_edge_of_map(tower)
        self.assertIs(exterior,tower.map)
        self.assertIs(exterior,tow.map)
        self.assertEqual((1,1),(tower.x,tower.y))
        self.assertEqual(tow._id,tower.carrying)
        self.assertTrue(tow.has_status(S.TOWED))
