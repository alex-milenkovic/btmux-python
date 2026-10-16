"""Map terrain visibility is independent of cached unit contacts."""
from tests.test_sensor_completion import SensorFixture
from entities.map import LIGHT_FOREST, HEAVY_FOREST, WATER, MOUNTAINS, FIRE
from entities.mech import CritStatus, UnitType, MoveType


class TestMapVisibility(SensorFixture):
    def test_overlapping_lights_cover_odd_and_even_neighbors_without_stale_state(self):
        from systems.los import calculate_los_map
        self.b.set_hex_position(3,3)
        self.b.set_crit_status(CritStatus.JELLIED)
        other=self.unit('cc',2,3,2)
        other.set_crit_status(CritStatus.JELLIED)
        odd={(3,3),(3,2),(4,2),(4,3),(3,4),(2,3),(2,2)}
        even={(2,3),(2,2),(3,3),(3,4),(2,4),(1,4),(1,3)}
        def lit():
            result=calculate_los_map(self.map,self.a,1,1,4,4)
            return {result.position(i) for i,flag in enumerate(result.cells) if flag&8}
        self.assertEqual(lit(),odd|even)
        self.b.clear_crit_status(CritStatus.JELLIED)
        self.assertEqual(lit(),even)
        other.clear_crit_status(CritStatus.JELLIED)
        self.assertEqual(lit(),set())

    def render(self, pair, vis=3, light=2, height=5):
        from systems.los import calculate_los_map
        self.a.sensor = pair
        self.map.mapvis, self.map.maplight = vis, light
        return calculate_los_map(self.map, self.a, 2, 2, 1, height)

    def test_clear_range_and_nonvisual_sensor_shortcuts(self):
        for pair, light, expected in [([0,0],2,[7,7,1,1,1]), ([1,1],0,[7]*5),
                                      ([5,5],2,[1]*5), ([2,0],2,[7]*5)]:
            with self.subTest(pair=pair):
                self.assertEqual(self.render(pair, light=light).cells, expected)
        self.a.crit_status |= CritStatus.CLAIRVOYANT
        self.assertEqual(self.render([6,6]).cells, [7]*5)

    def test_hill_and_sensor_specific_barriers(self):
        cases = [(0, ' ', 3, [7,1,1]), (0,LIGHT_FOREST,0,[7,7,7]),
                 (3,MOUNTAINS,0,[7,1,1]), (1,WATER,1,[7,1,1]), (0,WATER,1,[7,7,7])]
        for sn, terrain, elevation, expected in cases:
            with self.subTest(sn=sn, terrain=terrain):
                self.map.set_terrain(2,2,terrain)
                self.map.set_elevation(2,2,elevation)
                self.assertEqual(self.render([sn,sn],vis=30,light=0,height=3).cells,expected)

    def test_lit_islands_keep_visual_ray_alive(self):
        self.b.set_hex_position(2,5)
        self.b.set_crit_status(CritStatus.JELLIED)
        self.assertEqual(self.render([0,0],light=0).cells,[7,7,15,15,15])

    def test_rectangle_bounds_indexing_and_hidden_data(self):
        from systems.los import calculate_los_map
        result = self.render([5,5])
        self.assertEqual(result.index(2,4),2)
        self.assertEqual(result.render(self.map)[0], {'x':2,'y':2,'terrain':None,'elevation':None})
        with self.assertRaises(ValueError): result.index(3,2)
        for rectangle in [(0,0,71,45),(0,0,70,46),(0,0,0,10),(-1,0,2,2),(79,59,2,2)]:
            with self.assertRaises(ValueError): calculate_los_map(self.map,self.a,*rectangle)
        self.assertEqual(len(calculate_los_map(self.map,self.a,0,0,70,45).cells),3150)
