"""Source MT, rejection sampling, roll accounting and independent streams."""
import unittest
from unittest.mock import patch

from core.randomness import MT19937, RandomState, number, roll, use_simulation, use_source


class CoreRandomnessTest(unittest.TestCase):
    def test_movement_cli_accepts_new_source_consumers_and_seeds_shared_mt(self):
        from tools.movement import Dice, Session
        dice = Dice({'fuel_check':[1]},True)
        self.assertEqual(1,dice('fuel_check',0,1,lambda:0))
        with self.assertRaisesRegex(ValueError,'exhausted'):
            dice('fuel_check',0,1,lambda:0)
        session = Session({'random':{'seed':123},'actions':[]})
        self.assertEqual(2991312382,session.engine.randomness.mt.int32())

    def test_default_seed_and_first_twist_boundary(self):
        generator = MT19937()
        words = [generator.int32() for _ in range(626)]
        self.assertEqual([3499211612, 581869302, 3890346734, 3586334585, 545404204], words[:5])
        self.assertEqual([4020325887, 4178893912, 610818241], words[623:])
        self.assertEqual(626, generator.words_consumed)

    def test_array_initialization(self):
        generator = MT19937()
        generator.init_by_array([0x123, 0x234, 0x345, 0x456])
        self.assertEqual([1067595299, 955945823, 477289528, 4107218783, 4228976476],
                         [generator.int32() for _ in range(5)])
        with self.assertRaises(ValueError):
            generator.init_by_array([])

    def test_seed_masks_and_restarts_stream(self):
        generator = MT19937(5489 + (1 << 32))
        self.assertEqual(3499211612, generator.int32())
        generator.seed(5489)
        self.assertEqual(3499211612, generator.int32())
        self.assertEqual(1, generator.words_consumed)

    def test_mixed_generators_consume_shared_words(self):
        generator = MT19937(5489)
        self.assertEqual(1749605806, generator.int31())
        self.assertEqual(0.13547700413863104, generator.real1())
        self.assertEqual(0.90579193411394954, generator.real2())
        self.assertEqual(0.83500858990009874, generator.real3())
        self.assertEqual(0.12698681629350606, generator.res53())
        self.assertEqual(6, generator.words_consumed)

    def test_real_endpoint_contracts(self):
        generator = MT19937()
        with patch.object(generator, 'int32', side_effect=[0, 0xffffffff] * 3):
            self.assertEqual(0, generator.real1())
            self.assertEqual(1, generator.real1())
            self.assertEqual(0, generator.real2())
            self.assertLess(generator.real2(), 1)
            self.assertGreater(generator.real3(), 0)
            self.assertLess(generator.real3(), 1)

    def test_number_rejects_high_candidate_and_reuses_no_modulo(self):
        state = RandomState()
        with patch.object(state.mt, 'int32', side_effect=[0xffffffff, 0x80000000]) as words:
            self.assertEqual(5, state.number(1, 6))
            self.assertEqual(2, words.call_count)

    def test_finite_raw_words_count_rejections_and_forbid_fallback(self):
        state = RandomState()
        state.mt.use_words([0xffffffff, 0x80000000])
        self.assertEqual(5, state.number(1, 6))
        self.assertEqual(2, state.mt.words_consumed)
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            state.mt.int32()
        with self.assertRaises(ValueError):
            state.mt.use_words([1 << 32])
        state.mt.seed(5489)
        self.assertEqual(3499211612, state.mt.int32())

    def test_number_equal_negative_and_maximal_range(self):
        state = RandomState()
        with patch.object(state.mt, 'int32', side_effect=[0, 0xffffffff]) as words:
            self.assertEqual(0, state.number(7, 7))
            self.assertEqual(0, words.call_count)
            self.assertEqual(-2, state.number(-2, 2))
            self.assertEqual(0xffffffff, state.number(0, 0xffffffff))

    def test_number_unsupported_inputs(self):
        state = RandomState()
        for low, high in ((2, 1), (0, 1 << 32), (1.5, 2), (-(1 << 31)-1, 0)):
            with self.subTest(low=low, high=high), self.assertRaises(ValueError):
                state.number(low, high)

    def test_roll_uses_two_numbers_and_init_preserves_statistics(self):
        state = RandomState()
        with patch.object(state, 'number', side_effect=[6, 6, 1, 6]):
            self.assertEqual(12, state.roll())
            self.assertEqual(7, state.roll())
        state.init_stat(5489)
        self.assertEqual(2, state.total_rolls)
        self.assertEqual(1, state.rolls[5])
        self.assertEqual(1, state.rolls[10])
        self.assertEqual(3499211612, state.mt.int32())

    def test_stats_empty_and_ordered_rows_do_not_draw(self):
        state = RandomState()
        self.assertEqual(['No rolls to show statistics for!'], state.show_stat())
        state.record_roll(7)
        rows = state.stat_rows()
        self.assertEqual(list(range(2, 13)), [row['roll'] for row in rows])
        self.assertEqual(100, rows[5]['current_percent'])
        self.assertEqual(100, rows[0]['hit_percent'])
        self.assertAlmostEqual(100 / 36, rows[-1]['hit_percent'], places=5)
        self.assertEqual(0, state.mt.words_consumed)
        self.assertTrue(state.show_stat()[-1].endswith('1'))

    def test_contexts_are_independent_and_restore(self):
        first, second = RandomState(5489), RandomState(5489)
        with use_simulation(first):
            a = number(0, 0xffffffff)
            with use_simulation(second):
                self.assertEqual(a, number(0, 0xffffffff))
            self.assertEqual(581869302, number(0, 0xffffffff))
        self.assertEqual((2, 1), (first.mt.words_consumed, second.mt.words_consumed))

    def test_injected_roll_sum_counts_once_without_mt_draw(self):
        state = RandomState()
        def source(name, low, high, fallback):
            self.assertEqual(('pilot_rolls', 2, 12), (name, low, high))
            return 9
        with use_simulation(state), use_source(source):
            self.assertEqual(9, roll('pilot_rolls'))
        self.assertEqual((1, 0), (state.total_rolls, state.mt.words_consumed))

    def test_nested_legacy_roll_fallback_does_not_double_count(self):
        state = RandomState()
        with use_simulation(state), use_source(lambda name, low, high, fallback: fallback()):
            result = roll('attack_rolls', fallback=lambda: roll())
        self.assertEqual(1, state.total_rolls)
        self.assertEqual(1, state.rolls[result-2])

    def test_number_draw_is_not_a_roll_even_with_bounds_two_to_twelve(self):
        from core.randomness import draw
        state = RandomState()
        with use_simulation(state):
            draw('number_only', 2, 12, lambda: 7)
        self.assertEqual(0, state.total_rolls)

    def test_engine_commands_share_combat_pilot_and_sensor_stream(self):
        from core.game_loop import GameEngine
        from entities.mech import Mech, MechStatus
        from entities.pilot import Pilot
        from systems.combat import roll_2d6
        from systems.piloting import make_piloting_roll
        from systems.sensors import m_number
        engine = GameEngine()
        unit = Mech(pilot=Pilot())
        unit.status |= MechStatus.STARTED
        engine.register_entity(unit)
        engine.events.set_tick(6)
        expected = RandomState(5489)
        combat_roll, pilot_roll = expected.roll(), expected.roll()
        cached = expected.mt.int31()
        observed = engine.inject_command(unit, lambda: (
            roll_2d6(), make_piloting_roll(unit).roll, m_number(unit, 1, 6)))
        self.assertEqual((combat_roll, pilot_roll, 1+cached%6), observed)
        self.assertEqual(expected.mt.words_consumed, engine.randomness.mt.words_consumed)
        self.assertEqual(expected.rolls, engine.randomness.rolls)

    def test_mnumber_initial_window_and_engine_tick_override_map_clock(self):
        from core.game_loop import GameEngine
        from entities.mech import Mech
        from entities.map import GameMap
        from systems.sensors import m_number
        engine = GameEngine()
        unit = Mech()
        engine.register_entity(unit)
        unit.map = GameMap(12, 12)
        unit.map.current_tick = 100
        unit.rnd = 11
        engine.global_tick = 99
        self.assertEqual(6, engine.inject_command(unit, lambda: m_number(unit, 1, 6)))
        self.assertEqual(0, engine.randomness.mt.words_consumed)
        engine.events.set_tick(6)
        with use_source(lambda name, low, high, fallback: 20):
            self.assertEqual(3, engine.inject_command(unit, lambda: m_number(unit, 1, 6)))
        self.assertEqual(1, unit.last_rnd_update)


class StatisticsPrecisionTest(unittest.TestCase):
    def test_hit_probabilities_round_only_at_source_float_assignment(self):
        state = RandomState()
        state.record_roll(2)
        expected = [100.0,97.22222137451172,91.66666412353516,83.33333587646484,
                    72.22222137451172,58.33333206176758,41.66666793823242,
                    27.77777862548828,16.66666603088379,8.333333015441895,2.777777671813965]
        self.assertEqual(expected,[row['hit_percent'] for row in state.stat_rows()])


if __name__ == '__main__':
    unittest.main()
