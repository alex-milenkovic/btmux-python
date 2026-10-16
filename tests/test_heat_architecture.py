"""Heat environment, stagger history and workflow observation regressions."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.game_loop import mech_update
from entities.map import GameMap, WATER
from entities.mech import Mech, MechStatus
from systems import heat, stagger
from tools.heat_updates import Session

class HeatArchitecture(unittest.TestCase):
    def test_history_queries_work_without_engine_or_combat_entity(self):
        unit = SimpleNamespace(stagger_damage_list=[
            dict(amount=25, occurred_at=0, counted=False),
            dict(amount=5, occurred_at=1, counted=True),
        ])
        before = copy.deepcopy(vars(unit))
        self.assertEqual(stagger.current_damage(unit, 60), 25)
        self.assertEqual(stagger.current_damage(unit, 61, True), 5)
        self.assertEqual(vars(unit), before)
        stagger.mark_damage(unit, 1)
        self.assertEqual(stagger.current_damage(unit, 0, True), 30)

    def test_environment_selection_uses_both_special_flags_and_real_water(self):
        for mapped in (False, True):
            for special_unit in (False, True):
                for special_map in (False, True):
                    with self.subTest(mapped=mapped, unit=special_unit, board=special_map):
                        unit = Mech.create_test_mech()
                        board = GameMap(1, 1)
                        board.set_terrain(0, 0, WATER)
                        board.set_elevation(0, 0, 3)
                        board.add_mech(unit)
                        unit.set_hex_position(0, 0)
                        unit.z = -2
                        board.temp = 51
                        board.flags = 2 if special_map else 0
                        if special_unit:
                            unit.set_status(MechStatus.UNDERSPECIAL)
                        if not mapped:
                            unit.map = None
                        with patch('systems.heat.full_heat_update', return_value='result') as update:
                            self.assertEqual(heat.update_from_environment(unit, 17), 'result')
                        update.assert_called_once_with(
                            unit, tick=17, in_water=True, water_depth=-2,
                            map_temperature=51 if mapped and special_unit and special_map else 25,
                        )

    def test_dispatch_and_cli_maintenance_use_the_same_heat_entrypoint(self):
        session = Session({'units': [{'name': 'u'}], 'actions': []})
        unit = session.units['u']
        with patch('systems.heat.update_from_environment') as update:
            mech_update(session.engine, unit)
            session.maintain({'op': 'maintain', 'unit': 'u', 'kind': 'heat'})
        self.assertEqual(update.call_count, 2)
        for call in update.call_args_list:
            self.assertEqual(call.args, (unit, session.engine.tick))

    def test_unmapped_cli_unit_uses_standard_temperature(self):
        session = Session({
            'map': {'temperature': 51, 'special_rules': True},
            'clock': {'event': 2},
            'units': [{'name': 'u', 'map_valid': False,
                       'heat_state': {'weapon_heat': 20}}],
            'actions': [{'op': 'maintain', 'unit': 'u', 'kind': 'heat'}],
        })
        self.assertIsNone(session.units['u'].map)
        result = session.run()['final']['units']['u']
        self.assertEqual(result['minus_heat'], 10)
        self.assertEqual(result['heat'], 10)

    def test_snapshot_cannot_mutate_dump_selection(self):
        from systems.ammo_dump import DumpSelection
        session = Session({'units': [{'name': 'u'}], 'actions': []})
        unit = session.units['u']
        unit._dump_selection = DumpSelection('bin', 2, 3)
        snapshot = session.unit_snapshot(unit)
        snapshot['dump_scope']['location'] = 99
        self.assertEqual(unit._dump_selection, DumpSelection('bin', 2, 3))
        self.assertEqual(session.unit_snapshot(unit)['dump_scope']['location'], 2)
