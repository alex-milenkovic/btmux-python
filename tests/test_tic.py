"""
Tests for systems/tic.py (TIC trigger groups, mech.tic.c port) and the
M4 field/constant prep on entities/mech.py.
"""

import os
import sys
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entities.mech import (
    AmmoMode, CritStatus, FireMode, Location, Mech, MechStatus,
    NUM_SECTIONS, WeaponState,
)
from systems.tic import (
    MAX_WEAPONS_PER_MECH, NUM_TICS, add_tic, clear_tic, del_tic, fire_tic,
    list_tic,
)


def make_mech(num_weapons=6, name="TicMech"):
    """A started test mech with `num_weapons` weapon slots."""
    mech = Mech.create_test_mech(name=name)
    from entities.map import GameMap
    from entities.pilot import Pilot
    from core.game_loop import GameEngine
    engine = GameEngine()
    board = GameMap(8, 8)
    board._id = 1000
    engine.register_entity(board)
    board.add_mech(mech)
    engine.register_entity(mech)
    mech.pilot = Pilot()
    from entities.crittypes import i2weapon
    for i in range(num_weapons):
        mech.sections[Location.RARM].criticals[i].type = i2weapon(0)
        mech.weapons.append(
            WeaponState(section=Location.RARM, critical=i, weapon_idx=0))
    mech.set_status(MechStatus.STARTED)
    return mech


# =============================================================================
# addtic
# =============================================================================

class TestAddTic(unittest.TestCase):

    def setUp(self):
        self.mech = make_mech()

    def test_add_single(self):
        msgs = add_tic(self.mech, 0, "2")
        self.assertEqual(msgs, ["Weapon #2 added to TIC 0!"])
        self.assertEqual(self.mech.tics[0], {2})

    def test_add_range(self):
        msgs = add_tic(self.mech, 1, "1-3")
        self.assertEqual(msgs, ["Weapons #1 - #3 added to TIC 1!"])
        self.assertEqual(self.mech.tics[1], {1, 2, 3})

    def test_reversed_range_swaps(self):
        msgs = add_tic(self.mech, 1, "3-1")
        self.assertEqual(msgs, ["Weapons #1 - #3 added to TIC 1!"])
        self.assertEqual(self.mech.tics[1], {1, 2, 3})

    def test_comma_list(self):
        msgs = add_tic(self.mech, 2, "0,2-3,5")
        self.assertEqual(msgs, [
            "Weapon #0 added to TIC 2!",
            "Weapons #2 - #3 added to TIC 2!",
            "Weapon #5 added to TIC 2!",
        ])
        self.assertEqual(self.mech.tics[2], {0, 2, 3, 5})

    def test_idempotent_add(self):
        add_tic(self.mech, 0, "1")
        add_tic(self.mech, 0, "1")
        self.assertEqual(self.mech.tics[0], {1})

    def test_invalid_tic_number(self):
        self.assertEqual(add_tic(self.mech, 4, "0"), ["Invalid tic number!"])
        self.assertEqual(add_tic(self.mech, -1, "0"), ["Invalid tic number!"])
        self.assertEqual(self.mech.tics, [set(), set(), set(), set()])

    def test_invalid_first_number_in_range(self):
        msgs = add_tic(self.mech, 0, "%d-2" % MAX_WEAPONS_PER_MECH)
        self.assertEqual(msgs, ["Invalid first number in range (96)"])

    def test_invalid_second_number_in_range(self):
        msgs = add_tic(self.mech, 0, "2-96")
        self.assertEqual(msgs, ["Invalid second number in range (96)"])

    def test_invalid_value(self):
        msgs = add_tic(self.mech, 0, "abc")
        self.assertEqual(msgs, ["Invalid value: abc"])

    def test_invalid_weapon_number(self):
        self.assertEqual(add_tic(self.mech, 0, "97"),
                         ["Invalid weapon number: 97"])
        self.assertEqual(add_tic(self.mech, 0, "-5"),
                         ["Invalid weapon number: -5"])

    def test_doesnt_have_weapons_quirk_prints_i2_plus_1(self):
        # 6 weapons on the mech; asking for weapon 8 prints i2+1 = 9
        # (verbatim C quirk, mech.utils.c:2252-2305).
        self.assertEqual(add_tic(self.mech, 0, "8"),
                         ["Error: the mech doesn't HAVE 9 weapons!"])
        # Range form validates only the HIGH endpoint, same message.
        self.assertEqual(add_tic(self.mech, 0, "0-8"),
                         ["Error: the mech doesn't HAVE 9 weapons!"])
        self.assertEqual(self.mech.tics[0], set())

    def test_error_aborts_comma_tail(self):
        # DOCHECK returns out of multi_weap_sel before the tail recursion.
        msgs = add_tic(self.mech, 0, "99,1")
        self.assertEqual(msgs, ["Invalid weapon number: 99"])
        self.assertEqual(self.mech.tics[0], set())


# =============================================================================
# deltic
# =============================================================================

class TestDelTic(unittest.TestCase):

    def setUp(self):
        self.mech = make_mech()
        self.mech.tics[2] = {1, 2, 3}

    def test_delete_single(self):
        msgs = del_tic(self.mech, 2, "2")
        self.assertEqual(msgs, ["Weapon #2 removed from TIC 2!"])
        self.assertEqual(self.mech.tics[2], {1, 3})

    def test_delete_range(self):
        msgs = del_tic(self.mech, 2, "1-3")
        self.assertEqual(msgs, ["Weapons #1 - #3 removed from TIC 2!"])
        self.assertEqual(self.mech.tics[2], set())

    def test_one_arg_clears_whole_tic(self):
        # Verbatim C quirk: `deltic 2` falls through to cleartic.
        self.mech.tics[0] = {5}
        msgs = del_tic(self.mech, "2")
        self.assertEqual(msgs, ["TIC #2 cleared!"])
        self.assertEqual(self.mech.tics[2], set())
        self.assertEqual(self.mech.tics[0], {5})  # others untouched

    def test_bad_argc(self):
        self.assertEqual(del_tic(self.mech),
                         ["Invalid number of arguments to the function!"])
        self.assertEqual(del_tic(self.mech, "1", "2", "3"),
                         ["Invalid number of arguments to the function!"])

    def test_invalid_tic_number(self):
        self.assertEqual(del_tic(self.mech, 5, "1"), ["Invalid tic number!"])


# =============================================================================
# cleartic
# =============================================================================

class TestClearTic(unittest.TestCase):

    def setUp(self):
        self.mech = make_mech()
        for i in range(NUM_TICS):
            self.mech.tics[i] = {i}

    def test_clear_single(self):
        msgs = clear_tic(self.mech, "1")
        self.assertEqual(msgs, ["TIC #1 cleared!"])
        self.assertEqual(self.mech.tics[1], set())
        self.assertEqual(self.mech.tics[0], {0})

    def test_clear_range(self):
        msgs = clear_tic(self.mech, "0-2")
        self.assertEqual(msgs, ["TIC #0 cleared!", "TIC #1 cleared!",
                                "TIC #2 cleared!"])
        self.assertEqual(self.mech.tics[3], {3})

    def test_clear_comma_list(self):
        msgs = clear_tic(self.mech, "0,3")
        self.assertEqual(msgs, ["TIC #0 cleared!", "TIC #3 cleared!"])
        self.assertEqual(self.mech.tics[1], {1})

    def test_there_are_only_n_tics_quirk(self):
        # Verbatim C quirk: the message prints i2 — the offending tic
        # number — NOT the tic count (mech.utils.c:2252-2305).
        self.assertEqual(clear_tic(self.mech, "7"),
                         ["There are only 7 tics!"])
        self.assertEqual(clear_tic(self.mech, "2-9"),
                         ["There are only 9 tics!"])

    def test_argc_check(self):
        self.assertEqual(clear_tic(self.mech, "1 2"),
                         ["Invalid number of arguments to function"])


# =============================================================================
# firetic
# =============================================================================

class TestFireTic(unittest.TestCase):

    def setUp(self):
        self.engine = object()
        self.mech = make_mech()

    def test_fires_each_weapon_ascending(self):
        self.mech.tics[1] = {3, 0, 5}
        with patch('systems.tic.fire_weapon_number') as fwn:
            msgs = fire_tic(self.engine, self.mech, "1")
        self.assertEqual(fwn.call_args_list, [
            call(self.engine, self.mech, 0, raw_args=('1',), caller=None, wizard=False, _guarded=True),
            call(self.engine, self.mech, 3, raw_args=('1',), caller=None, wizard=False, _guarded=True),
            call(self.engine, self.mech, 5, raw_args=('1',), caller=None, wizard=False, _guarded=True),
        ])
        self.assertIn("Firing weapons in tic #1!", msgs)

    def test_forwarded_vector_includes_tic_spec(self):
        # Verbatim C quirk (firetic_sub: temp_args = args): the tic spec
        # itself occupies forwarded slot 0, so the C's args[1] target is
        # our fire_args[0] — and with NO extra args the target is None
        # (C case 1), not the tic spec.
        self.mech.tics[0] = {2}
        sentinel = object()
        with patch('systems.tic.fire_weapon_number') as fwn:
            fire_tic(self.engine, self.mech, "0", sentinel)
        fwn.assert_called_once_with(self.engine, self.mech, 2,
                                    raw_args=('0', sentinel), caller=None,
                                    wizard=False, _guarded=True)
        with patch('systems.tic.fire_weapon_number') as fwn:
            fire_tic(self.engine, self.mech, "0")
        fwn.assert_called_once_with(self.engine, self.mech, 2,
                                    raw_args=('0',), caller=None,
                                    wizard=False, _guarded=True)

    def test_result_messages_are_collected(self):
        self.mech.tics[0] = {1}
        result = Mock()
        result.messages = ["You do not have a default target set!"]
        with patch('systems.tic.fire_weapon_number', return_value=result):
            msgs = fire_tic(self.engine, self.mech, "0")
        self.assertEqual(msgs, [
            "Firing weapons in tic #0!",
            "You do not have a default target set!",
        ])

    def test_empty_tic_clicks(self):
        with patch('systems.tic.fire_weapon_number') as fwn:
            msgs = fire_tic(self.engine, self.mech, "2")
        fwn.assert_not_called()
        self.assertEqual(msgs, ["Firing weapons in tic #2!",
                                "*Click* (the tic contained no weapons)"])

    def test_tic_out_of_range(self):
        self.assertEqual(fire_tic(self.engine, self.mech, "4"),
                         ["TIC out of range!"])
        self.assertEqual(fire_tic(self.engine, self.mech, "-1"),
                         ["TIC out of range!"])

    def test_tic_range_spec_fires_multiple_tics(self):
        self.mech.tics[0] = {0}
        self.mech.tics[1] = {1}
        with patch('systems.tic.fire_weapon_number') as fwn:
            msgs = fire_tic(self.engine, self.mech, "0-1")
        self.assertEqual(fwn.call_count, 2)
        self.assertIn("Firing weapons in tic #0!", msgs)
        self.assertIn("Firing weapons in tic #1!", msgs)

    def test_fall_mid_tic_aborts_with_message(self):
        self.mech.tics[0] = {0, 1, 2}

        def fall(engine, mech, weapnum, **kwargs):
            mech.set_status(MechStatus.FALLEN)
            return Mock(messages=[])

        with patch('systems.tic.fire_weapon_number', side_effect=fall) as fwn:
            msgs = fire_tic(self.engine, self.mech, "0")
        self.assertEqual(fwn.call_count, 1)
        self.assertIn("That fall causes you to stop your fire!", msgs)

    def test_fall_message_suppressed_when_shutdown(self):
        self.mech.tics[0] = {0, 1}

        def fall_and_shutdown(engine, mech, weapnum, **kwargs):
            mech.set_status(MechStatus.FALLEN)
            mech.clear_status(MechStatus.STARTED)
            return Mock(messages=[])

        with patch('systems.tic.fire_weapon_number',
                   side_effect=fall_and_shutdown) as fwn:
            msgs = fire_tic(self.engine, self.mech, "0")
        self.assertEqual(fwn.call_count, 1)
        self.assertNotIn("That fall causes you to stop your fire!", msgs)

    def test_shutdown_mid_tic_aborts_silently(self):
        self.mech.tics[0] = {0, 1, 2}

        def shutdown(engine, mech, weapnum, **kwargs):
            mech.clear_status(MechStatus.STARTED)
            return Mock(messages=[])

        with patch('systems.tic.fire_weapon_number',
                   side_effect=shutdown) as fwn:
            msgs = fire_tic(self.engine, self.mech, "0")
        self.assertEqual(fwn.call_count, 1)
        self.assertEqual(msgs, ["Firing weapons in tic #0!"])


# =============================================================================
# listtic
# =============================================================================

class TestListTic(unittest.TestCase):

    def setUp(self):
        self.mech = make_mech()

    def test_rows(self):
        self.mech.tics[0] = {0, 2}
        rows, msgs = list_tic(self.mech, "0")
        # weapon_idx 0 = "IS.SmallLaser"; &name[3] drops the tech prefix.
        self.assertEqual(rows, [(0, "RA", "SmallLaser", ""),
                                (2, "RA", "SmallLaser", "")])
        self.assertEqual(msgs, [])

    def test_nonfunctional_marker(self):
        self.mech.tics[0] = {1}
        ws = self.mech.weapons[1]
        crit = self.mech.sections[ws.section].criticals[ws.critical]
        crit.firemode |= FireMode.DESTROYED_MODE
        rows, _ = list_tic(self.mech, "0")
        self.assertEqual(rows[0][3], "(*)")

    def test_stale_weapon_numbers_pruned(self):
        # listtic_fun's -1 branch: stale numbers are removed as a display
        # side effect.
        self.mech.tics[0] = {0, 50}
        rows, msgs = list_tic(self.mech, "0")
        self.assertEqual([r[0] for r in rows if isinstance(r, tuple)], [0])
        self.assertEqual(self.mech.tics[0], {0})
        self.assertEqual(rows[1], "Unknown - error of some sort occured")
        self.assertEqual(msgs, ["Unknown - error of some sort occured"])

    def test_empty_tic(self):
        rows, msgs = list_tic(self.mech, "3")
        self.assertEqual(rows, [])
        self.assertEqual(msgs, ["No weapons in tic."])

    def test_all_stale_keeps_source_error_rows(self):
        self.mech.tics[1] = {40, 41}
        rows, msgs = list_tic(self.mech, "1")
        self.assertEqual(rows, ["Unknown - error of some sort occured"] * 2)
        self.assertEqual(msgs, ["Unknown - error of some sort occured"] * 2)
        self.assertEqual(self.mech.tics[1], set())

    def test_out_of_range(self):
        rows, msgs = list_tic(self.mech, "4")
        self.assertEqual((rows, msgs), ([], ["TIC out of range!"]))

    def test_argc_check(self):
        rows, msgs = list_tic(self.mech, "1 2")
        self.assertEqual((rows, msgs), ([], ["Invalid number of arguments!"]))


# =============================================================================
# M4 field/constant prep (entities/mech.py)
# =============================================================================

class TestMechM4Fields(unittest.TestCase):

    def test_new_field_defaults(self):
        mech = Mech()
        self.assertEqual(mech.spotter, -1)
        self.assertEqual(mech.fire_adjustment, 0)
        self.assertEqual(mech.aim, NUM_SECTIONS)   # no-aim sentinel
        self.assertEqual(mech.aim_type, 0)
        self.assertEqual(mech.targcomp, 0)
        self.assertEqual(mech.charge_target, -1)
        self.assertEqual(mech.charge_timer, 0)
        self.assertEqual(mech.charge_distance, 0.0)
        self.assertFalse(mech.autoturn_turret)
        self.assertFalse(mech.turn_mode)
        self.assertEqual(mech.tics, [set(), set(), set(), set()])
        self.assertEqual(len(mech.tics), NUM_TICS)

    def test_tics_are_per_instance(self):
        m1 = Mech()
        m2 = Mech()
        m1.tics[0].add(1)
        self.assertEqual(m2.tics[0], set())
        self.assertIsNot(m1.tics, m2.tics)
        self.assertIsNot(m1.tics[0], m2.tics[0])

    def test_status_bit_values(self):
        self.assertEqual(MechStatus.AMS_ENABLED, 0x800)      # mech.h:998
        self.assertEqual(CritStatus.JELLIED, 0x00400000)     # mech.h:1110

    def test_fire_mode_values_and_aggregates(self):
        self.assertEqual(FireMode.ON_TC, 0x10)
        self.assertEqual(FireMode.RAC_MODES,
                         FireMode.RAC_TWOSHOT_MODE |
                         FireMode.RAC_FOURSHOT_MODE |
                         FireMode.RAC_SIXSHOT_MODE)
        self.assertEqual(FireMode.FIRE_MODES,
                         FireMode.HOTLOAD_MODE | FireMode.ULTRA_MODE |
                         FireMode.RFAC_MODE | FireMode.GATTLING_MODE |
                         FireMode.RAC_MODES | FireMode.HEAT_MODE)

    def test_ammo_mode_spot_values(self):
        self.assertEqual(AmmoMode.LBX_MODE, 0x1)
        self.assertEqual(AmmoMode.INFERNO_MODE, 0x40)
        self.assertEqual(AmmoMode.AC_AP_MODE, 0x2000)
        self.assertEqual(AmmoMode.AC_PRECISION_MODE, 0x10000)
        self.assertEqual(AmmoMode.MML_LRM_MODE, 0x400000)

    def test_inferno_mode_matches_criticals_constant(self):
        from systems.criticals import AMMO_INFERNO_MODE
        self.assertEqual(AmmoMode.INFERNO_MODE, AMMO_INFERNO_MODE)

    def test_ammo_mode_aggregates(self):
        self.assertEqual(AmmoMode.ARTILLERY_MODES,
                         AmmoMode.CLUSTER_MODE | AmmoMode.MINE_MODE |
                         AmmoMode.SMOKE_MODE)
        self.assertEqual(AmmoMode.INARC_MODES,
                         AmmoMode.INARC_EXPLO_MODE |
                         AmmoMode.INARC_HAYWIRE_MODE |
                         AmmoMode.INARC_ECM_MODE |
                         AmmoMode.INARC_NEMESIS_MODE)
        self.assertEqual(AmmoMode.MISSILE_MODES,
                         AmmoMode.ARTEMIS_MODE | AmmoMode.NARC_MODE |
                         AmmoMode.INFERNO_MODE | AmmoMode.SWARM_MODE |
                         AmmoMode.SWARM1_MODE | AmmoMode.STINGER_MODE |
                         AmmoMode.SGUIDED_MODE)
        self.assertEqual(AmmoMode.AC_MODES,
                         AmmoMode.AC_AP_MODE | AmmoMode.AC_FLECHETTE_MODE |
                         AmmoMode.AC_INCENDIARY_MODE |
                         AmmoMode.AC_PRECISION_MODE |
                         AmmoMode.AC_CASELESS_MODE)
        self.assertEqual(AmmoMode.ATM_MODES,
                         AmmoMode.ATM_ER_MODE | AmmoMode.ATM_HE_MODE)
        self.assertEqual(AmmoMode.AMMO_MODES,
                         AmmoMode.LBX_MODE | AmmoMode.AC_MODES |
                         AmmoMode.MISSILE_MODES | AmmoMode.INARC_MODES |
                         AmmoMode.ARTILLERY_MODES | AmmoMode.ATM_MODES |
                         AmmoMode.MML_LRM_MODE)


if __name__ == '__main__':
    unittest.main()
