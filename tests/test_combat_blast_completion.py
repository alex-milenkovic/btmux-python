"""Artillery blast boundaries and shared mutable C selector arguments."""
import unittest
from unittest.mock import patch

from core.game_loop import GameEngine
from entities.map import GameMap, WATER, LIGHT_FOREST, FIRE
from entities.mech import Mech, Location
from physics.hexmath import hex_to_float
from systems.combat import HitGroup
from systems.damage import blast_hit_hexes, TABLE_PUNCH


class BlastCompletionTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.board = GameMap(8, 8)
        self.unit = Mech.create_test_mech()
        self.unit.x = self.unit.y = 3
        self.unit.fx, self.unit.fy = hex_to_float(3, 3)
        self.unit.z = 0
        self.board.mechs_on_map = [self.unit]

    def blast(self, **changes):
        args = dict(game_map=self.board, dam=10, singlehitsize=5, heatdam=0,
                    tx=3, ty=3, tomsg='hit', otmsg='hit', tomsg1=None,
                    otmsg1=None, table=TABLE_PUNCH, safeup=2, safedown=1,
                    isunderwater=False, engine=self.engine)
        args.update(changes)
        blast_hit_hexes(**args)

    def test_null_messages_and_strict_height_exclude_damage(self):
        with patch('systems.combat.apply_damage_with_transfer') as damage:
            for height in (-1, 2):
                self.unit.z = height
                self.blast()
            self.unit.z = 0
            self.blast(tomsg=None)
            self.blast(otmsg=None)
            self.assertEqual(0, damage.call_count)
            self.blast()
            self.assertEqual(2, damage.call_count)

    def test_underwater_uses_signed_floor(self):
        self.board.set_terrain(3, 3, WATER)
        self.board.set_elevation(3, 3, 2)
        self.unit.z = -2
        with patch('systems.combat.apply_damage_with_transfer') as damage:
            self.blast(isunderwater=True)
        self.assertEqual(10, sum(c.args[2] for c in damage.call_args_list))

    def test_rear_flag_persists_across_roster(self):
        other = Mech.create_test_mech()
        other.x = other.y = 3
        self.board.mechs_on_map.append(other)
        with patch('systems.damage._blast_arc', side_effect=[HitGroup.BACK, HitGroup.FRONT]), \
             patch('systems.combat.get_punch_location', return_value=Location.CTORSO), \
             patch('systems.combat.apply_damage_with_transfer') as damage:
            self.blast(dam=5)
        self.assertEqual([True, True], [c.kwargs['is_rear'] for c in damage.call_args_list])

    def test_null_neighbor_messages_still_ignite_woods(self):
        self.board.set_terrain(3, 4, LIGHT_FOREST)
        with patch('systems.combat.apply_damage_with_transfer'):
            self.blast(doneighbors=1)
        self.assertEqual(FIRE, self.board.terrain(3, 4))
        self.assertEqual(LIGHT_FOREST, self.board.rterrain(3, 4))
        event = self.board.decorations[3, 4]['event']
        from core.randomness import use_source
        from physics.decorations import expire_fire
        with use_source(lambda name,low,high,fallback: low):
            self.engine.events.set_tick(event.tick)
            self.engine.events.run_events()
            self.assertEqual(FIRE,self.board.terrain(3,4))
            while (3,4) in self.board.decorations:
                event=self.board.decorations[3,4]['event']
                self.engine.events.set_tick(event.tick)
                self.engine.events.run_events()
        self.assertEqual(' ',self.board.terrain(3,4))

    def test_signed_attenuation_truncates_before_neighbor_ignition(self):
        self.board.set_terrain(3, 4, LIGHT_FOREST)
        self.blast(dam=-1, doneighbors=1)
        self.assertNotIn((3, 4), self.board.decorations)
        self.blast(dam=-2, doneighbors=1)
        self.assertEqual(FIRE, self.board.terrain(3, 4))
