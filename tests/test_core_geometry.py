"""Float32 and integer boundary vectors from unmodified source function bodies."""
import unittest
from physics import hexmath as h


class SourceGeometryTest(unittest.TestCase):
    def test_signed_exact_multiples_and_source_bearing_rounding(self):
        self.assertEqual([360, 360, 359, 359, 0, 0, 1],
                         [h.acceptable_degree(value) for value in (-720, -360, -361, -1, 0, 360, 721)])
        points = ((1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1), (.001, -1))
        self.assertEqual([91, 270, 136, 46, 225, 315, 1], [h.find_bearing(0, 0, *xy) for xy in points])

    def test_float32_centers(self):
        self.assertEqual((186.19546508789062, 161.25), h.hex_to_float(0, 0))
        self.assertEqual((465.4886474609375, 322.5), h.hex_to_float(1, 1))
        self.assertEqual((14150.85546875, 16286.25), h.hex_to_float(50, 50))
        self.assertEqual((-93.097732543945312, -322.5), h.hex_to_float(-1, -1))

    def test_source_trig_constant_and_negative_bearing_correction(self):
        self.assertEqual((6.3975785451475531e-05, -100), h.find_components(100, 0))
        self.assertEqual((100, .00012795157090295106), h.find_components(100, 90))
        self.assertEqual((-1.7454226016998291, -99.984764099121094), h.find_components(100, -361))
        self.assertEqual((917.8277587890625, 200.00004577636719), h.find_xy(100, 200, 90, 3))
        self.assertEqual((83.02764892578125, -767.3526611328125), h.find_xy(100, 200, -361, 3))
        self.assertEqual((83.201675415039062, -767.3526611328125), h.find_xy(100, 200, 359, 3))

    def test_coordinate_boundaries_are_rounded_at_source_assignments(self):
        vectors = ((279.29315185546875, 0), (279.29318237304688, 0), (279.293212890625, 1),
                   (651.68408203125, 1), (651.68414306640625, 2), (651.6842041015625, 2))
        for x, expected in vectors:
            self.assertEqual((expected, 0), h.float_to_hex(x, 0))
        self.assertEqual((-1, -1), h.float_to_hex(-.01, -.01))
        with self.assertRaisesRegex(ValueError, 'short'):
            h.float_to_hex(1e10, 0)

    def test_3d_range_and_absolute_z_bearing(self):
        self.assertEqual(1.0772237777709961, h.find_range3d(1, 20, 300, 10, 200, 3))
        self.assertEqual(59, h.find_z_bearing(1, 20, 300, 10, 200, 3))
        self.assertEqual([0, 90, 90], [h.find_z_bearing(0, 0, 0, 0, 0, z) for z in (0, -1, 1)])

    def test_swarm_threshold_straddles_adjacent_float32_positions(self):
        self.assertEqual(1.8999999761581421, h.find_range3d(1024.0750732421875, 0, 0, 1636.8250732421875, 0, 0))
        self.assertEqual(1.9000003337860107, h.find_range3d(1024.0750732421875, 0, 0, 1636.8251953125, 0, 0))

    def test_integer_hex_metric_tc_and_same_column(self):
        self.assertEqual(4, h.my_hex_dist(2, 1, 2, 5, 19))
        self.assertEqual(7, h.my_hex_dist(0, 0, 3, 4, 1))
        self.assertEqual(5, h.my_hex_dist(0, 0, 6, 1, -1))


if __name__ == '__main__': unittest.main()
