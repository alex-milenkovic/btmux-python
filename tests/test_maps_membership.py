import io
import unittest
from entities.mech import Mech, MechStatus as S
from entities.map import GameMap
from entities.map_storage import save_dynamic,load_dynamic
from systems import map_membership as membership
from tests.test_maps_objects import fixture


def unit(engine,identity):
    mech=Mech(); mech._id=identity; engine.register_entity(mech)
    return mech


class MembershipTest(unittest.TestCase):
    def test_dropship_exit_and_trim_report_unavailable_persistent_effects(self):
        from entities.mech import UnitType
        engine,board=fixture(); ship=unit(engine,40); ship.unit_type=UnitType.DS
        board.add_mech(ship); board.external_effects.clear()
        board.remove_mech(ship)
        self.assertEqual('DS #40 has left map #10',board.channel_requests[-1]['text'])
        self.assertTrue(board.channel_requests[-1]['applied'])
        board.roster_ids=[41,-1]; board.mechs_on_map=[None,None]
        board.mechflags=[0,0]; board.slot_los=[[0,0],[0,0]]
        membership.eliminate_empties(board)
        self.assertEqual([41],board.roster_ids)
        self.assertEqual('',engine.inventory_store.raw(10))
        self.assertIn('Fixing done.',board.admin_requests[-1]['message'])
        count=len(board.external_effects)
        membership.eliminate_empties(board)
        self.assertEqual(count,len(board.external_effects))

    def test_add_reuses_negative_hole_and_retains_directed_row(self):
        engine,board=fixture(); a,b,c=[unit(engine,n) for n in (40,41,42)]
        board.add_mech(a); board.add_mech(b)
        board.roster_ids[0]=-1; board.mechs_on_map[0]=None
        board.slot_los[:]=[[5,17],[29,9]]
        board.add_mech(c)
        self.assertEqual(([42,41],0,10),(board.roster_ids,c.mapnumber,c.mapindex))
        self.assertEqual([[5,17],[29,9]],board.slot_los)
        self.assertEqual(29,board.losinfo[(41,42)])
        c.mapnumber=8
        board.add_mech(c)
        self.assertEqual(8,c.mapnumber)  # duplicate returns before any repair
        d=unit(engine,43); board.add_mech(d)
        self.assertEqual([[5,17,0],[29,9,0],[0,0,0]],board.slot_los)

    def test_remove_clears_locks_seen_rows_tower_and_only_one_tail(self):
        engine,board=fixture(); a,b,c=[unit(engine,n) for n in (40,41,42)]
        for mech in (a,b,c): board.add_mech(mech)
        board.slot_los[:]=[[1]*3 for _ in range(3)]
        board.roster_ids[1]=-1; board.mechs_on_map[1]=None
        a.target=42; a.set_status(S.LOCK_TARGET); a.num_seen=8; a.carrying=42
        c.set_status(S.LOCK_HEX|S.TOWED); c.num_seen=5
        board.remove_mech(c)
        self.assertEqual([40,-1],board.roster_ids)
        self.assertEqual((0,-1,0),(c.mapnumber,c.mapindex,c.num_seen))
        self.assertEqual((8,-1),(a.num_seen,a.carrying))
        self.assertFalse(a.status&S.LOCK_TARGET)
        self.assertFalse(c.status&(S.LOCK_MODES|S.TOWED))
        self.assertEqual(0,board.slot_los[0][2])

    def test_consistency_cleanup_retains_flags_matrix_and_all_empty_length(self):
        engine,board=fixture(); other=GameMap(9,9); other._id=20; engine.register_entity(other)
        a=unit(engine,40); board.add_mech(a); other.add_mech(a)
        board.mechflags[0]=9; board.slot_los[0][0]=63
        membership.consistency(a,engine.get_entities())
        self.assertEqual([-1],board.roster_ids)
        self.assertEqual(([9],[[63]]),(board.mechflags,board.slot_los))
        membership.eliminate_empties(board)
        self.assertEqual([-1],board.roster_ids)
        a.mapnumber=10
        membership.consistency(a,engine.get_entities())
        self.assertEqual((-1,[-1]),(a.mapindex,other.roster_ids))
        a.mapindex=0; membership.consistency(a,[])
        self.assertEqual(0,a.mapindex)
        a.mapindex=999; membership.consistency(a,[])
        self.assertEqual(-1,a.mapindex)

    def test_sensor_cache_and_dynamic_stream_use_same_los(self):
        engine,board=fixture(); a,b=[unit(engine,n) for n in (40,41)]
        board.add_mech(a); board.add_mech(b)
        board.losinfo[(40,41)]=123
        board.losinfo[(41,40)]=456
        self.assertEqual([[0,123],[456,0]],board.slot_los)
        restored=GameMap(9,9)
        load_dynamic(restored,save_dynamic(board),2,{40:a,41:b})
        self.assertEqual(123,restored.losinfo[(40,41)])
        restored.losinfo[(40,41)]=19
        self.assertEqual(19,restored.slot_los[0][1])
