"""Finite-domain heat/stagger invariants; run separately from unit discovery.

Local seeded history generation gives reproducible concrete counterexamples.
No application clocks, random sources or weapon catalogs are modified globally.
"""
import copy
from itertools import product
import random
from types import SimpleNamespace
import unittest

from core.events import EventQueue
from entities.map import GameMap, GRASSLAND, WATER, ICE, BRIDGE, SMOKE
from entities.mech import Specials
from physics.decorations import add_smoke
from systems import heat_control
from systems import stagger as history


class HeatUpdatesProperties(unittest.TestCase):
    def test_sink_switching_conserves_capacity_and_dissipation_offset(self):
        for capacity, special in product(range(0, 25), (
            Specials(0), Specials.DOUBLE_HEAT_TECH, Specials.CLAN_TECH,
        )):
            for disabled, request in product(range(capacity + 1), (-5, 0, 1, 2, 3, 4, 5, 100)):
                for switch in (heat_control.enable_some_sinks, heat_control.disable_some_sinks):
                    with self.subTest(capacity=capacity, disabled=disabled, request=request,
                                      special=special, switch=switch.__name__):
                        unit = SimpleNamespace(effective_heat_sinks=capacity, disabled_sinks=disabled,
                                               minus_heat=-3.5, specials=special)
                        amount = switch(unit, request)
                        self.assertGreaterEqual(amount, 0)
                        self.assertLessEqual(amount, max(0, request))
                        self.assertLessEqual(amount, 2 if not special else 4)
                        self.assertEqual(abs(unit.disabled_sinks - disabled), amount)
                        self.assertGreaterEqual(unit.disabled_sinks, 0)
                        self.assertLessEqual(unit.disabled_sinks, capacity)
                        self.assertEqual(unit.disabled_sinks + heat_control.active_capacity(unit), capacity)
                        self.assertEqual(unit.disabled_sinks + unit.minus_heat, disabled - 3.5)

    def test_repeated_sink_recovery_terminates_and_is_idempotent(self):
        for capacity, special in product(range(41), (Specials(0), Specials.DOUBLE_HEAT_TECH)):
            unit = SimpleNamespace(effective_heat_sinks=capacity, disabled_sinks=capacity,
                                   minus_heat=0, specials=special)
            for _ in range(capacity + 1):
                heat_control.enable_some_sinks(unit, 100)
            with self.subTest(capacity=capacity, special=special):
                self.assertEqual((unit.disabled_sinks, unit.minus_heat), (0, capacity))
                before = vars(unit).copy()
                self.assertEqual(heat_control.enable_some_sinks(unit, 100), 0)
                self.assertEqual(vars(unit), before)

    def histories(self):
        draw = random.Random(9743)
        yield []
        for _ in range(100):
            yield [dict(amount=draw.randint(1, 55), occurred_at=stamp,
                        counted=bool(draw.getrandbits(1)), attacker=stamp)
                   for stamp in sorted(draw.randrange(-70, 1) for _ in range(draw.randrange(1, 20)))]

    def test_marking_preserves_whole_hits_and_conserves_counted_partition(self):
        for nodes in self.histories():
            for level in range(5):
                with self.subTest(nodes=nodes, level=level):
                    unit = SimpleNamespace(stagger_damage_list=copy.deepcopy(nodes))
                    total = history.current_damage(unit, 0) + history.current_damage(unit, 0, True)
                    history.mark_damage(unit, level)
                    after = unit.stagger_damage_list
                    self.assertEqual(len(nodes), len(after))
                    for old, new in zip(nodes, after):
                        self.assertEqual({k: v for k, v in old.items() if k != 'counted'},
                                         {k: v for k, v in new.items() if k != 'counted'})
                        self.assertTrue(not old['counted'] or new['counted'])
                    self.assertEqual(total, history.current_damage(unit, 0) + history.current_damage(unit, 0, True))
                    marked = [old['amount'] for old, new in zip(nodes, after)
                              if not old['counted'] and new['counted']]
                    if marked:
                        self.assertLess(sum(marked[:-1]), level * 20)
                    if any(not node['counted'] for node in after):
                        self.assertGreaterEqual(sum(marked), level * 20)

    def test_removal_leaves_ordered_suffix_and_crosses_threshold_by_whole_hit(self):
        for nodes in self.histories():
            for level in range(5):
                with self.subTest(nodes=nodes, level=level):
                    unit = SimpleNamespace(stagger_damage_list=copy.deepcopy(nodes))
                    history.remove_damage(unit, level)
                    removed = len(nodes) - len(unit.stagger_damage_list)
                    self.assertEqual(unit.stagger_damage_list, nodes[removed:])
                    if removed:
                        self.assertLess(sum(n['amount'] for n in nodes[:removed - 1]), level * 20)
                    if unit.stagger_damage_list:
                        self.assertGreaterEqual(sum(n['amount'] for n in nodes[:removed]), level * 20)

    def test_expiry_is_idempotent_and_only_removes_oldest_hits(self):
        for nodes in self.histories():
            for now in (-1, 0, 1, 59, 60, 61):
                with self.subTest(nodes=nodes, now=now):
                    unit = SimpleNamespace(stagger_damage_list=copy.deepcopy(nodes))
                    history.clear_expired(unit, now)
                    expected = [n for n in nodes if now - n['occurred_at'] < 60]
                    self.assertEqual(unit.stagger_damage_list, expected)
                    history.clear_expired(unit, now)
                    self.assertEqual(unit.stagger_damage_list, expected)
                    history.clear_all(unit)
                    history.clear_all(unit)
                    self.assertEqual(unit.stagger_damage_list, [])

    def test_smoke_replacement_preserves_underlay_until_latest_expiry(self):
        for terrain, first, replacement in product((GRASSLAND, WATER, ICE, BRIDGE),
                                                   range(1, 5), range(1, 7)):
            with self.subTest(terrain=terrain, first=first, replacement=replacement):
                engine = SimpleNamespace(events=EventQueue())
                board = GameMap(2, 1)
                board.set_terrain(0, 0, terrain)
                board.set_elevation(0, 0, 3)
                untouched = board.terrain(1, 0)
                old = add_smoke(engine, board, 0, 0, first)
                new = add_smoke(engine, board, 0, 0, replacement)
                self.assertTrue(old['event'].zombie)
                self.assertEqual(new['underlying'], terrain)
                for tick in range(1, max(first, replacement) + 2):
                    engine.events.muxevent_run()
                    self.assertEqual(board.terrain(0, 0), SMOKE if tick < replacement else terrain)
                    self.assertEqual(board.rterrain(0, 0), terrain)
                    self.assertEqual(board.terrain(1, 0), untouched)
                    self.assertEqual(board.elevation(0, 0), 3)
                self.assertEqual(board.decorations, {})
                self.assertEqual(engine.events.pending_count, 0)
