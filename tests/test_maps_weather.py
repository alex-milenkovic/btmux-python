import unittest
from core.randomness import use_source
from entities.map import GameMap
from entities.mech import Mech,MoveType
from entities.weapon import WeaponType as W
from tests.test_maps_objects import fixture
from physics import weather


class WeatherTest(unittest.TestCase):
    def test_classification_and_raw_high_wind_bitwise_arithmetic(self):
        self.assertEqual({'heavy_precip','fog'},weather.validate_conditions({'precip','heavy_precip','fog'}))
        self.assertEqual({'blizzard','fog'},weather.calc_effects({'heavy_precip','fog'},0,61))
        self.assertEqual({'winds','heavy_snow'},weather.calc_effects({'heavy_precip'},0,60))
        self.assertEqual({'high_winds','rain'},weather.calc_effects({'precip'},1,61))
        self.assertEqual(2,weather.gun_effects({'high_winds':1},W.TAMMO))
        self.assertEqual(0,weather.gun_effects({'high_winds':2},W.TAMMO))
        self.assertEqual(0,weather.gun_effects({'heavy_rain':1},W.TAMMO))
        self.assertEqual(4,weather.gun_effects({'rain':1,'fog':1,'sand':1},W.TBEAM))

    def test_ground_pilot_and_heat_signs(self):
        board=GameMap(9,9); unit=Mech(); unit.map=board; unit.x=unit.y=1
        board.layers[1,1]={'deep_snow','mud','rapids'}
        effects={'heavy_rain':2,'high_winds':4,'heavy_snow':8}
        self.assertEqual(5,weather.pilot_effects(unit,effects))
        unit.move_type=MoveType.HOVER
        self.assertEqual(1,weather.pilot_effects(unit,effects))
        unit.z=1
        self.assertEqual(0,weather.pilot_effects(unit,effects))
        unit.minus_heat=10; board.temp=-41
        weather.heat_effects(board,unit,effects,leg_sinks=1)
        self.assertEqual(8,unit.minus_heat)
        board.temp=61
        weather.heat_effects(board,unit,{'blizzard':1},leg_sinks=0)
        self.assertEqual(4,unit.minus_heat)

    def test_melt_threshold_preserves_other_layers_and_actual_steam_event(self):
        engine,board=fixture(); board.layers[1,1]={'deep_snow','mud'}; board.layer_data[1,1]=1090
        draws=[]
        def draw(name,low,high,fallback): draws.append((name,low,high)); return high
        with use_source(draw): weather.melt(board,1,1,90,emit=True,steam=True,ice=False)
        self.assertEqual({'snow','mud'},board.layers[1,1])
        self.assertEqual(1000,board.layer_data[1,1])
        self.assertEqual([],draws)
        self.assertEqual(':',board.terrain(1,1))
        self.assertEqual(90,board.map_objects[1][0].event.tick)
        with use_source(draw): weather.melt(board,1,1,1000,emit=True,steam=True,ice=False)
        self.assertEqual({'mud'},board.layers[1,1])
        self.assertEqual([('snow_steam',0,50)],draws)
        self.assertEqual(140,board.map_objects[1][0].datas)

    def test_ice_breaks_after_defined_melt_with_signed_steam_suppression(self):
        engine,board=fixture(); board.set_terrain(1,1,'-'); board.set_elevation(1,1,2)
        board.layers[1,1]={'snow'}; board.layer_data[1,1]=200
        weather.melt(board,1,1,1,emit=True,steam=True,ice=True)
        self.assertEqual(199,board.layer_data[1,1])
        self.assertEqual('~',board.terrain(1,1))
        self.assertEqual(-2,board.base_elevation(1,1))
        self.assertEqual([],board.map_objects[1])

    def test_growth_draw_order_skips_and_pre_validation_values(self):
        board=GameMap(2,2); board.set_terrain(0,1,'~')
        board.layers[0,0]={'mud'}; board.layers[1,0]={'snow','deep_snow','mud'}
        board.layer_data[1,0]=100
        values=iter([2,3,4]); draws=[]
        def draw(name,low,high,fallback): draws.append((low,high)); return next(values)
        with use_source(draw): weather.grow(board,2,4)
        self.assertEqual([(2,4)]*3,draws)
        self.assertEqual({'snow'},board.layers[0,0])
        self.assertEqual({'snow','mud'},board.layers[1,0])
        self.assertEqual(103,board.layer_data[1,0])
        self.assertEqual([(0,0),(1,0),(1,1)],[(e['x'],e['y']) for e in board.snow_validation_trace])
        self.assertEqual(['deep_snow','mud','snow'],board.snow_validation_trace[1]['layers'])
