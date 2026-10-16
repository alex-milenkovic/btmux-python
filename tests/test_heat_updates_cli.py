"""Public heat simulation interface validates input and runs the real engine."""

import unittest
from unittest.mock import patch
from entities import weapon as weapon_catalog
from tools.heat_updates import Session


class HeatUpdatesCLI(unittest.TestCase):
    def test_due_low_band_inferno_check_preserves_ammo_effects_and_cadence(self):
        for heat in (10, 13.9):
            for roll in (3, 4):
                with self.subTest(heat=heat, roll=roll):
                    result = Session({
                        'units': [{'name': 'u', 'heat_state': {'heat': heat},
                            'equipment': [{'name': 'inferno-regression', 'category': 'MISSILE',
                                'damage': 2, 'ammo_per_ton': 30, 'section': 'RA', 'slot': 5}],
                            'bins': [{'weapon': 0, 'section': 'LT', 'slot': 1, 'rounds': 4, 'inferno': True}]}],
                        'config': {'periodic_updates': False, 'inferno_penalty': True},
                        'clock': {'event': 29},
                        'random': {'ammo_avoidance': [roll], 'shutdown_rolls': [], 'critical_rolls': [2] * 5},
                        'actions': [{'op': 'maintain', 'unit': 'u', 'kind': 'overheat'},
                                    {'op': 'advance', 'seconds': 1},
                                    {'op': 'maintain', 'unit': 'u', 'kind': 'overheat'},
                                    {'op': 'maintain', 'unit': 'u', 'kind': 'overheat'}],
                    }).run()
                    before = result['results'][0]['snapshot']['units']['u']
                    unit = result['final']['units']['u']
                    self.assertEqual(0, before['last_overheat_tick'])
                    self.assertEqual(4, before['bins'][0]['rounds'])
                    self.assertEqual(30, unit['last_overheat_tick'])
                    self.assertEqual(1, result['consumed']['ammo_avoidance'])
                    self.assertEqual(0, result['consumed']['shutdown_rolls'])
                    # Cook-off destroys the bin while preserving its raw data.
                    self.assertEqual(4, unit['bins'][0]['rounds'])
                    self.assertEqual(1 if roll == 3 else 0, unit['bins'][0]['condition'])
                    self.assertEqual(2 if roll == 3 else 0, unit['pilot_hits'])
                    self.assertEqual(30 if roll == 3 else 0, unit['weapon_heat'])
                    self.assertTrue(unit['started'])

    def test_relative_target_fixture_uses_real_position_without_default_at(self):
        result = Session({'units': [
            {'name': 'u', 'class': 'VEH_GROUND', 'movement': 'TRACK',
             'auto_turret': True, 'facing': 90, 'target_id': 't'},
            {'name': 't', 'relative_position': {'to': 'u', 'bearing': 0, 'range': 1}}],
            'actions': [{'op': 'advance', 'seconds': 2}]}).run()
        self.assertEqual(result['final']['units']['u']['turret_facing'], 271)  # FindBearing includes the C +1 degree bias

    def test_documented_vehicle_side_aliases_address_actual_front_and_rear(self):
        result = Session({'units': [{'name': 'u', 'class': 'VEH_GROUND', 'movement': 'TRACK',
            'events': {'burns': [{'section': 'FRONT', 'remaining': 1},
                                  {'section': 'REAR', 'remaining': 1}]}}],
            'config': {'periodic_updates': False}, 'random': {'fire_damage': [1, 2]},
            'actions': [{'op': 'advance', 'seconds': 1}]}).run()
        sections = result['final']['units']['u']['sections']
        self.assertEqual([s['front'] for s in sections], [100, 100, 99, 98, 100, 100, 100, 100])

    def test_water_diagnostic_preserves_surface_while_full_entry_settles(self):
        result = Session({'units': [{'name': 'u', 'events': {'inferno': 180}}],
            'config': {'periodic_updates': False}, 'map': {'default': ['WATER', 2]},
            'actions': [{'op': 'maintain', 'unit': 'u', 'kind': 'water_extinguish'},
                        {'op': 'enter_hex', 'unit': 'u', 'at': [3, 2, 0]}]}).run()
        direct, moved = [r['snapshot']['units']['u'] for r in result['results']]
        self.assertEqual((direct['at'][2], direct['jellied']), (0, True))
        self.assertEqual((moved['at'][2], moved['jellied']), (-2, False))

    def test_gravity_internal_dice_do_not_consume_extra_pilot_rolls(self):
        result = Session({'units': [{'name': 'u', 'speed': 75.25}],
            'config': {'periodic_updates': False}, 'clock': {'event': 30},
            'map': {'special_rules': True, 'gravity': 150},
            'random': {'pilot_rolls': [2], 'critical_rolls': [2, 2]},
            'actions': [{'op': 'maintain', 'unit': 'u', 'kind': 'pilot'}]}).run()
        self.assertEqual(result['consumed']['pilot_rolls'], 1)
        self.assertEqual(result['consumed']['critical_rolls'], 2)
        self.assertEqual([s['internal'] for s in result['final']['units']['u']['sections']],
                         [100, 100, 100, 100, 100, 98, 98, 100])

    def test_equipment_and_bins_reject_overlapping_physical_slots(self):
        weapon = dict(
            name="test.cli.overlap",
            category="BALLISTIC",
            damage=5,
            ammo_per_ton=20,
            section="LT",
            slot=1,
        )
        bin_fixture = dict(weapon=0, section="LT", slot=1, rounds=3)
        with patch.dict(weapon_catalog.WEAPON_CATALOG), patch.object(
            weapon_catalog, "WEAPON_INDEX", weapon_catalog.WEAPON_INDEX.copy()
        ):
            for extra, message in (
                ({"equipment": [weapon, weapon]}, "duplicate equipment slot"),
                (
                    {"equipment": [weapon], "bins": [bin_fixture]},
                    "duplicate equipment/bin slot",
                ),
            ):
                with self.subTest(message=message), self.assertRaisesRegex(
                    ValueError, message
                ):
                    Session({"units": [{"name": "u", **extra}], "actions": []})

    def test_history_rejects_reversed_clock_order(self):
        history = [
            dict(amount=20, wall=2, counted=False),
            dict(amount=10, wall=1, counted=True),
        ]
        with self.assertRaisesRegex(ValueError, "history must be chronological"):
            Session({"units": [{"name": "u", "history": history}], "actions": []})

    def test_duplicate_side_burns_are_rejected(self):
        burn = dict(section="LT", remaining=60)
        with self.assertRaisesRegex(ValueError, "duplicate side burn"):
            Session(
                {
                    "units": [{"name": "u", "events": {"burns": [burn, burn]}}],
                    "actions": [],
                }
            )

    def test_fixture_and_new_cutoff_events_retain_observed_source(self):
        result = Session(
            {
                "config": {"periodic_updates": False, "heartbeat": False},
                "units": [
                    {
                        "name": "u",
                        "events": {"cutoff": {"remaining": 1, "engage": True}},
                    }
                ],
                "actions": [
                    {"op": "advance", "seconds": 1},
                    {"op": "command", "unit": "u", "name": "heatcutoff", "args": []},
                    {"op": "advance", "seconds": 4},
                ],
            }
        ).run()
        first, command, last = result["results"]
        self.assertTrue(first["snapshot"]["units"]["u"]["cutoff"])
        self.assertEqual(first["messages"][-1]["source"], "heatcutoff")
        self.assertTrue(command["accepted"])
        self.assertFalse(last["snapshot"]["units"]["u"]["cutoff"])
        self.assertEqual(last["messages"][-1]["source"], "heatcutoff")

    def test_stagger_actions_observe_whole_hits_and_expire_on_wall_clock(self):
        result = Session(
            {
                "config": {"periodic_updates": False, "heartbeat": False},
                "units": [
                    {
                        "name": "u",
                        "history": [
                            {"amount": 25, "wall": 0, "counted": False},
                            {"amount": 15, "wall": 1, "counted": False},
                        ],
                    }
                ],
                "actions": [
                    {"op": "stagger", "unit": "u", "action": "MARK", "level": 1},
                    {"op": "maintain", "unit": "u", "kind": "stagger_totals"},
                    {"op": "heartbeat", "wall_seconds": 60},
                    {"op": "maintain", "unit": "u", "kind": "stagger_expiry"},
                    {"op": "stagger", "unit": "u", "action": "REMOVE", "level": 1},
                ],
            }
        ).run()
        totals = result["results"][1]
        self.assertEqual((totals["uncounted"], totals["counted"]), (15, 25))
        expired = result["results"][3]["snapshot"]["units"]["u"]
        self.assertEqual(
            expired["stagger"], [{"amount": 15, "wall": 1, "counted": False}]
        )
        self.assertEqual(result["final"]["units"]["u"]["stagger"], [])
        self.assertEqual(result["final"]["clock"]["event"], 0)

    def test_omitted_roll_stream_uses_seeded_two_dice_distribution(self):
        import random
        from tools.heat_updates import Dice

        expected = random.Random(19)
        dice = Dice({"seed": 19})
        rolls = [dice("pilot_rolls", 2, 12, None) for _ in range(20)]
        self.assertEqual(
            rolls, [expected.randint(1, 6) + expected.randint(1, 6) for _ in range(20)]
        )

    def test_reference_heat_workflow_assigns_balance(self):
        result = Session(
            {
                "units": [
                    {
                        "name": "u",
                        "heat_state": {
                            "heat": 100,
                            "plus_heat": 20,
                            "weapon_heat": 20,
                            "sink_capacity": 10,
                            "disabled_capacity": 0,
                        },
                    }
                ],
                "actions": [{"op": "advance", "seconds": 2}, {"op": "inspect"}],
            }
        ).run()
        unit = result["final"]["units"]["u"]
        self.assertEqual(unit["heat"], 10)
        self.assertEqual(unit["weapon_heat"], 19.66666603088379)  # C float store
        self.assertTrue(unit["started"])

    def test_unknown_field_and_impossible_capacity_are_errors(self):
        with self.assertRaises(ValueError):
            Session({"actions": [], "unknown": True})
        with self.assertRaises(ValueError):
            Session(
                {
                    "actions": [],
                    "units": [
                        {
                            "name": "u",
                            "heat_state": {"sink_capacity": 2, "disabled_capacity": 3},
                        }
                    ],
                }
            )

    def test_command_rejection_is_a_successful_workflow(self):
        result = Session(
            {
                "actions": [
                    {"op": "command", "unit": "u", "name": "dump", "args": ["all"]}
                ]
            }
        ).run()
        self.assertFalse(result["results"][0]["accepted"])

    def test_supplied_empty_dice_stream_fails_on_actual_draw(self):
        session = Session(
            {
                "random": {"shutdown_rolls": []},
                "clock": {"event": 30},
                "units": [{"name": "u", "heat_state": {"heat": 14}}],
                "actions": [{"op": "maintain", "unit": "u", "kind": "overheat"}],
            }
        )
        with self.assertRaises(ValueError):
            session.run()
