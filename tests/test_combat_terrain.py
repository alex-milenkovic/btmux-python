"""Terrain attacks consume source rolls before guards and nested attempts."""
import unittest
from core.game_loop import GameEngine
from core.randomness import use_source
from entities.map import GameMap, LIGHT_FOREST, HEAVY_FOREST, FIRE, ROUGH, GRASSLAND
from entities.mech import Mech, AmmoMode as A, MechStatus as S
from entities.weapon import get_weapon
from systems import terrain_combat as terrain
from tests.test_damage_failures import Draws


class TerrainTest(unittest.TestCase):
    def setUp(self):
        self.unit=Mech.create_test_mech()
        self.unit._engine=GameEngine()
        self.board=self.unit.map=GameMap(8,8)
        self.board.set_terrain(4,4,LIGHT_FOREST)

    def test_ignition_thresholds_and_excluded_weapon(self):
        for name,roll,mode,burns in (('Flamer',3,0,False),('Flamer',4,0,True),
                                    ('MediumLaser',4,0,False),('MediumLaser',5,0,True),
                                    ('SmallLaser',12,0,False),('AC/10',8,0,False),
                                    ('AC/10',9,0,True),('AC/10',5,A.AC_FLECHETTE_MODE,True)):
            self.board.set_terrain(4,4,LIGHT_FOREST)
            dice=Draws(roll,*([60] if burns else []))
            with use_source(dice):
                terrain.possibly_ignite(self.unit,get_weapon('IS.'+name).index,mode,4,4,True)
            self.assertEqual(burns,self.board.terrain(4,4)==FIRE)
            self.assertEqual([],dice.values)

    def test_clear_nested_ignition_and_damage_threshold(self):
        for dice,result in (((5,8,4),HEAVY_FOREST),((5,8,5,60),FIRE),
                            ((6,8),LIGHT_FOREST),((6,9),HEAVY_FOREST)):
            self.board.set_terrain(4,4,HEAVY_FOREST)
            with use_source(Draws(*dice)):
                terrain.possibly_clear(self.unit,get_weapon('IS.MediumLaser').index,0,8,4,4,True)
            self.assertEqual(result,self.board.terrain(4,4))

    def test_light_replacement_and_dispatcher_unused_roll(self):
        self.unit.set_status(S.LOCK_HEX_CLR)
        for replacement,expected in ((1,ROUGH),(2,GRASSLAND)):
            self.board.set_terrain(4,4,LIGHT_FOREST)
            dice=Draws(12,6,8,replacement)
            with use_source(dice):
                from systems.combat import possibly_ignite_or_clear
                possibly_ignite_or_clear(self.unit,get_weapon('IS.MediumLaser').index,0,8,4,4,0)
            self.assertEqual(expected,self.board.terrain(4,4))
            self.assertEqual([],dice.values)

    def test_mapless_dispatch_consumes_only_unused_draw(self):
        self.unit.map=None
        dice=Draws(8)
        with use_source(dice):
            terrain.possibly_ignite_or_clear(self.unit,get_weapon('IS.MediumLaser').index,0,8,4,4,0)
        self.assertEqual([],dice.values)
