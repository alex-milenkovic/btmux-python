"""Immutable artillery launches and source impact/scatter algorithms."""
import unittest
from unittest.mock import patch
from core.game_loop import GameEngine
from core.randomness import use_source
from entities.map import GameMap, SMOKE
from entities.mech import Mech, AmmoMode as A
from entities.weapon import get_weapon
from systems import artillery
from tests.test_damage_failures import Draws


class ArtilleryTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.board = GameMap(12,12)
        self.engine.register_entity(self.board)
        self.unit = Mech.create_test_mech()
        self.unit.map = self.board
        self.unit.x = self.unit.y = 3
        self.engine.register_entity(self.unit)
        self.weapon = get_weapon('IS.Sniper')

    def test_flight_deadline_and_launch_survives_shooter_removal(self):
        shot = artillery.artillery_shoot(self.engine, self.unit, 4,4, self.weapon.index,0,True)
        self.unit.x = 9
        self.engine.unregister_entity(self.unit)
        with patch('systems.artillery.artillery_hit_hex') as impact:
            self.engine.events.set_tick(9)
            self.engine.events.run_events()
            self.assertFalse(impact.called)
            self.engine.events.set_tick(10)
            self.engine.events.run_events()
            self.assertEqual(7, impact.call_count)
        self.assertEqual((3,3,4,4,0), (shot.from_x,shot.from_y,shot.to_x,shot.to_y,shot.mode))
        for distance, expected in ((0,10),(54.9,10),(55,11),(100,20)):
            self.assertEqual(expected, artillery.flight_time(distance))

    def test_removed_map_consumes_event_without_impact(self):
        artillery.artillery_shoot(self.engine,self.unit,4,4,self.weapon.index,0,True)
        self.engine.unregister_entity(self.board)
        with patch('systems.artillery.artillery_hit_hex') as impact:
            self.engine.events.set_tick(10)
            self.engine.events.run_events()
            self.assertFalse(impact.called)

    def test_direction_uses_absolute_difference_without_circular_wrap(self):
        self.assertEqual(['north','north','northeast','northwest'],
                         [artillery.artillery_direction(x) for x in (0,30,31,359)])

    def test_cluster_scatter_aggregates_twice_nominal_in_x_major_order(self):
        shot = artillery.ArtilleryShot(3,3,4,4,self.weapon.index,A.CLUSTER_MODE,True,self.unit._id,self.board)
        with use_source(Draws(0,0,0,0,-1,0,0,0,0,0,0,0)), \
             patch('systems.artillery.artillery_hit_hex') as impact:
            artillery.artillery_cluster_hit(self.engine,shot,3,4,4)
        self.assertEqual([(3,4,2),(4,4,4)], [(c.args[3],c.args[4],c.args[2]) for c in impact.call_args_list])

    def test_inner_smoke_priority_and_outer_mine_footprint(self):
        for mode, count in ((A.SMOKE_MODE,7),(A.SMOKE_MODE|A.MINE_MODE,1),
                            (A.CLUSTER_MODE|A.SMOKE_MODE|A.MINE_MODE,1)):
            self.board = GameMap(12,12)
            self.engine.register_entity(self.board)
            shot = artillery.ArtilleryShot(3,3,4,4,self.weapon.index,mode,True,self.unit._id,self.board)
            with patch('systems.artillery.number', side_effect=lambda name,lo,hi: max(lo,min(0,hi))):
                artillery.artillery_hit(self.engine,shot)
            self.assertEqual(count, len(self.board.decorations))
            self.assertTrue(all(d['terrain']==SMOKE for d in self.board.decorations.values()))
            self.assertEqual([],self.board.mines)

    def test_miss_uses_old_radians_and_integer_wind_weight(self):
        shot = artillery.ArtilleryShot(3,3,4,4,self.weapon.index,0,False,self.unit._id,self.board)
        self.board.windspeed=60
        self.board.winddir=180
        with use_source(Draws(0,2)), patch('systems.artillery.artillery_hit_hex') as impact:
            artillery.artillery_hit(self.engine,shot)
        # weight=16; distance=(2*16+10*84)/100=8; old direction 0 => east, clamp11.
        self.assertEqual((11,4),impact.call_args_list[0].args[3:5])

    def test_firing_spends_resources_now_and_schedules_impact_even_impossible_bth(self):
        from entities.mech import WeaponState, Location as L, MechStatus as S
        from entities.crittypes import i2weapon, i2ammo
        from systems.combat import fire_weapon
        self.unit.set_status(S.STARTED)
        self.unit.weapons=[WeaponState(weapon_idx=self.weapon.index,section=L.RARM,critical=4)]
        slot=self.unit.sections[L.RARM].criticals[4]
        slot.type=i2weapon(self.weapon.index)
        slot.brand=0
        ammo=self.unit.sections[L.RTORSO].criticals[8]
        ammo.type,ammo.data=i2ammo(self.weapon.index),10
        from entities.pilot import Pilot
        self.unit.pilot=Pilot()
        self.unit.pilot.artillery=12
        result=fire_weapon(self.unit,None,0,2,mapx=4,mapy=4,ishex=1,to_hit_roll=12,engine=self.engine)
        self.assertGreater(result.bth,12)
        self.assertEqual(1,len(self.board.projectiles))
        self.assertFalse(self.board.projectiles[0].is_hit)
        self.assertEqual(9,ammo.data)
        self.assertEqual(2*self.weapon.vrt,slot.data)
        self.assertEqual(self.weapon.heat,self.unit.weap_heat)
        self.assertEqual([],self.board.artillery_impacts)
