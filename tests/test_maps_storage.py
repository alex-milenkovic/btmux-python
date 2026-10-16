import io
import unittest

from entities.map import GameMap
from entities.map_storage import Coding, BitTable, save_dynamic, load_dynamic


class CodingTest(unittest.TestCase):
    def test_reuse_inverse_and_init_retains_counter(self):
        coding = Coding()
        self.assertEqual([0,1,0], [coding.index(t,e) for t,e in [(' ',0),('~',2),(' ',0)]])
        self.assertEqual(('~',2), coding.inverse(1))
        coding.initialize()
        self.assertEqual(('\0',0), coding.inverse(1))
        self.assertEqual(2, coding.index(' ',0))

    def test_safe_dictionary_limit(self):
        coding = Coding()
        for i in range(255): coding.index(chr(i//10),i%10)
        with self.assertRaisesRegex(ValueError,'255'): coding.index(chr(26),0)


class BitsTest(unittest.TestCase):
    def test_corrected_floor_index_mask_and_selective_clear(self):
        bits = BitTable(9,2)
        bits.set(1,0,1); bits.set(1,0,2)
        self.assertEqual(12,bits.rows[0][0])
        self.assertEqual(4,bits.query(1,0,1))
        bits.clear(1)
        self.assertEqual(0,bits.query(1,0,1))
        self.assertEqual(8,bits.query(1,0,2))
        self.assertEqual(3,bits.size())

    def test_empty_pruning_and_attached_corrected_load(self):
        bits = BitTable(9,2)
        bits.set(0,0,1); bits.unset(0,0,1)
        self.assertEqual(b'',bits.save())
        self.assertEqual(0,bits.size())
        bits.set(7,1,2)
        saved = bits.save()
        self.assertEqual(9,saved[0])
        detached = BitTable.load(io.BytesIO(saved[1:]),9,2)
        self.assertEqual([None,bytearray([0,128,0])],detached.rows)
        self.assertTrue(detached.attached)

    def test_defined_null_queries_and_corrected_edge(self):
        bits = BitTable(4,1)
        self.assertEqual(0,bits.query(3,0,1))
        bits.set(3,0,1)
        self.assertEqual(64,bits.query(3,0,1))
        bits.unset(3,0,1)
        bits.unset(0,0,1)
        self.assertEqual(1,bits.size())


class DynamicStreamTest(unittest.TestCase):
    def test_directed_los_holes_and_exact_bytes(self):
        board = GameMap(9,2)
        board.roster_ids=[10,-1]; board.mechflags=[1,2]
        board.slot_los=[[0,0x1234],[0xabcd,0]]
        wire=save_dynamic(board)
        self.assertEqual(bytes.fromhex('0a000000ffffffff010200003412cdab000069421367'),wire)
        copy=GameMap(9,2)
        load_dynamic(copy,wire,2,{})
        self.assertEqual(board.roster_ids,copy.roster_ids)
        self.assertEqual(board.slot_los,copy.slot_los)
        for size in (3,9,13,len(wire)-1):
            with self.assertRaisesRegex(ValueError,'load_mapdynamic.*reading #'): load_dynamic(copy,wire[:size],2,{})
        with self.assertRaisesRegex(ValueError,'Magic number mismatch'): load_dynamic(copy,b'abcd',0,{})
        load_dynamic(copy,bytes.fromhex('69421367'),0,{})
        self.assertEqual(([],[],[]),(copy.roster_ids,copy.mechflags,copy.slot_los))

class SizeTest(unittest.TestCase):
    def test_explicit_lp64_profile_counts_headers_not_cells(self):
        from entities.map_storage import source_sizes
        from entities.map import GameMap
        from entities.map_objects import add_object,MapObject
        small=GameMap(1,1); large=GameMap(100,100)
        self.assertEqual(source_sizes(small),source_sizes(large))
        baseline=source_sizes(small)
        add_object(small,4,MapObject())
        small.roster_ids=[40,-1,41]
        actual=source_sizes(small)
        self.assertEqual(69,actual['mechs'])
        self.assertEqual(48,actual['objects'])
        small._terrain=None
        self.assertEqual(baseline['map']-8,source_sizes(small)['map'])
