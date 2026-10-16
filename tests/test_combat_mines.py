"""Mine persistence, footprint and contact resolution from mine.c."""
import unittest
from unittest.mock import patch
from core.game_loop import GameEngine
from entities.map import GameMap, WATER, ICE
from entities.mech import Mech
from systems import mines


class MineTest(unittest.TestCase):
    def setUp(self):
        self.board = GameMap(12, 12)
        self.unit = Mech.create_test_mech()
        self.unit.map = self.board
        self.unit.x = self.unit.y = 4
        self.unit.z = 0
        self.unit.rtons = 50*1024
        self.unit._engine = GameEngine()
        self.unit._id = 40
        self.board.mechs_on_map = [self.unit]

    def test_decay_uses_updated_damage_and_old_persistence(self):
        for initial, damage, count in ((4, 4, 0), (5, 5, 1), (7, 7, 1), (8, 5, 1), (12, 8, 1)):
            with self.subTest(initial=initial):
                self.board.mines = []
                mines.map_add_mine(self.board, f'4 4 Standard {initial}')
                with patch('systems.mines.blast_hit_hexes') as blast:
                    self.assertEqual(1, mines.possible_mine_poof(self.unit, 'step'))
                self.assertEqual(damage, blast.call_args.args[1])
                self.assertEqual(count, len(self.board.mines))

    def test_ice_surface_and_signed_water_floor(self):
        mines.map_add_mine(self.board, '4 4 Standard 5')
        self.board.set_elevation(4, 4, 2)
        with patch('systems.mines.blast_hit_hexes'):
            for terrain, height, count in ((WATER,-1,0),(WATER,-2,1),(ICE,0,1),(ICE,1,0)):
                self.board.set_terrain(4, 4, terrain)
                self.unit.z = height
                self.assertEqual(count, mines.possible_mine_poof(self.unit, 'step'))

    def test_vibra_equality_only_at_same_hex(self):
        for threshold, x, count in ((50,4,1),(51,4,0),(50,5,0),(40,5,1),(41,5,0)):
            self.board.mines = []
            mines.map_add_mine(self.board, f'{x} 4 Vibra 10 {threshold}')
            with patch('systems.mines.blast_hit_hexes'):
                self.assertEqual(count, mines.possible_mine_poof(self.unit, 'step'))

    def test_channels_remove_all_matching_objects_without_owner_gate(self):
        for x, channel in ((3,7),(4,7),(5,8)):
            mines.map_add_mine(self.board, f'{x} 4 Command 10 {channel}', creator=x)
        with patch('systems.mines.blast_hit_hexes'):
            self.assertEqual(2, mines.explode_mines(self.unit, 7))
        self.assertEqual([8], [m.extra for m in self.board.mines])

    def test_trigger_reason_and_local_effect_attempts(self):
        mines.map_add_mine(self.board, '4 4 Trigger 50 2')
        self.assertEqual(0, mines.possible_mine_poof(self.unit, 'fall'))
        self.assertEqual(1, mines.possible_mine_poof(self.unit, 'land'))
        self.assertEqual(1, len(self.board.mines))
        self.assertTrue(self.unit.channel_requests[-1]['applied'])
        self.assertEqual('MineTriggers',self.unit.channel_requests[-1]['source_channel'])
        self.assertFalse(self.unit.action_requests[-1]['applied'])  # No local action configured.

    def test_artillery_does_not_replace_existing_mine_or_remote_coverage(self):
        mines.map_add_mine(self.board, '4 4 Trigger 50 2')
        mines.add_mine(self.board, 4, 4, 12)
        mines.add_mine(self.board, 5, 4, 12)
        self.assertEqual(2, len(self.board.mines))
        self.assertEqual(mines.MineType.TRIGGER, next(m for m in self.board.mines if (m.x,m.y)==(4,4)).type)

    def test_parser_rejects_zero_prefix_but_accepts_nonzero_atoi(self):
        with self.assertRaises(ValueError):
            mines.map_add_mine(self.board, '00 4 Standard 10')
        mines.map_add_mine(self.board, '4tail 4 Standard 10')
        self.assertEqual(4, self.board.mines[0].x)

    def test_normal_jump_landing_triggers_real_mine_once(self):
        from physics.jump import land_mech
        from entities.mech import MechStatus as S
        self.unit.set_status(S.JUMPING)
        mines.map_add_mine(self.board,'4 4 Standard 5')
        with patch('systems.mines.blast_hit_hexes') as blast:
            land_mech(self.unit)
        self.assertEqual(1,blast.call_count)

    def test_actual_fall_reaches_mine_after_settling(self):
        from physics.jump import mech_falls
        from entities.mech import MechStatus as S
        self.unit.set_status(S.COMBAT_SAFE)
        mines.map_add_mine(self.board,'4 4 Standard 5')
        with patch('systems.mines.blast_hit_hexes') as blast:
            mech_falls(self.unit,1)
        self.assertEqual(1,blast.call_count)
