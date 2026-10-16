"""
Tests for the ECM/ECCM enable commands (systems/ecm.py, ported from
mech.advanced.c:37-138): all six toggles — on/off, mutual exclusion,
destroyed gates, not-equipped messages — and the no-immediate-check_ecm
shape.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from entities.mech import CritStatus, Mech, Specials, MechStatus
from entities.map import GameMap
from entities.pilot import Pilot

def ready_mech(name):
    mech = Mech.create_test_mech(name=name)
    mech.pilot = Pilot()
    mech.set_status(MechStatus.STARTED)
    from core.game_loop import GameEngine
    engine=GameEngine()
    board=GameMap(8,8);board._id=100
    engine.register_entity(board)
    engine.register_entity(mech)
    board.add_mech(mech)
    return mech

from systems.ecm import (
    ANGEL_ECCM_ENABLED, ANGEL_ECM_ENABLED, ECCM_ENABLED, ECM_ENABLED,
    PER_ECCM_ENABLED, PER_ECM_ENABLED,
    mech_angeleccm, mech_angelecm, mech_eccm, mech_ecm, mech_pereccm,
    mech_perecm,
)
from systems.sensors import FC_INFILTRATORII_STEALTH_TECH


def s2(mech):
    return getattr(mech, 'status2', 0)


class TestGuardianECM(unittest.TestCase):

    def setUp(self):
        self.mech = ready_mech(name="Guardian")
        self.mech.specials |= Specials.ECM_TECH

    def test_ecm_on(self):
        msgs = mech_ecm(self.mech)
        self.assertEqual(msgs, ["You turn your ECM suite online (ECM mode)."])
        self.assertTrue(s2(self.mech) & ECM_ENABLED)

    def test_ecm_off(self):
        mech_ecm(self.mech)
        msgs = mech_ecm(self.mech)
        self.assertEqual(msgs, ["You turn your ECM suite offline."])
        self.assertFalse(s2(self.mech) & ECM_ENABLED)

    def test_eccm_on(self):
        msgs = mech_eccm(self.mech)
        self.assertEqual(msgs,
                         ["You turn your ECM suite online (ECCM mode)."])
        self.assertTrue(s2(self.mech) & ECCM_ENABLED)

    def test_eccm_off(self):
        mech_eccm(self.mech)
        msgs = mech_eccm(self.mech)
        self.assertEqual(msgs, ["You turn your ECM suite offline."])
        self.assertFalse(s2(self.mech) & ECCM_ENABLED)

    def test_mutual_exclusion(self):
        mech_eccm(self.mech)
        mech_ecm(self.mech)                 # enabling ECM clears ECCM
        self.assertTrue(s2(self.mech) & ECM_ENABLED)
        self.assertFalse(s2(self.mech) & ECCM_ENABLED)
        mech_eccm(self.mech)                # and vice versa
        self.assertTrue(s2(self.mech) & ECCM_ENABLED)
        self.assertFalse(s2(self.mech) & ECM_ENABLED)

    def test_destroyed_gate(self):
        self.mech.set_crit_status(CritStatus.ECM_DESTROYED)
        for cmd in (mech_ecm, mech_eccm):
            msgs = cmd(self.mech)
            self.assertEqual(
                msgs, ["Your Guardian ECM has been destroyed already!"])
        self.assertEqual(s2(self.mech) & (ECM_ENABLED | ECCM_ENABLED), 0)

    def test_not_equipped(self):
        bare = ready_mech(name="Bare")
        for cmd in (mech_ecm, mech_eccm):
            msgs = cmd(bare)
            self.assertEqual(
                msgs, ["This unit isn't equipped with an ECM suite!"])
        self.assertEqual(s2(bare), 0)

    def test_no_immediate_check_ecm(self):
        # The toggles only mark for LOS update; the periodic ECM scan
        # recomputes (mech.advanced.c:67-78).
        with patch('systems.ecm.check_ecm') as chk:
            mech_ecm(self.mech)
            mech_eccm(self.mech)
        chk.assert_not_called()

    def test_marks_for_los_update(self):
        with patch('systems.ecm.mark_for_los_update') as mark:
            mech_ecm(self.mech)   # on
            mech_ecm(self.mech)   # off — marked on both paths
        self.assertEqual(mark.call_count, 2)


class TestAngelECM(unittest.TestCase):

    def setUp(self):
        self.mech = ready_mech(name="Angel")
        self.mech.specials2 |= 0x1000

    def test_angelecm_on_off(self):
        msgs = mech_angelecm(self.mech)
        self.assertEqual(
            msgs, ["You turn your Angel ECM suite online (ECM mode)."])
        self.assertTrue(s2(self.mech) & ANGEL_ECM_ENABLED)
        msgs = mech_angelecm(self.mech)
        self.assertEqual(msgs, ["You turn your Angel ECM suite offline."])
        self.assertFalse(s2(self.mech) & ANGEL_ECM_ENABLED)

    def test_angeleccm_on_off(self):
        msgs = mech_angeleccm(self.mech)
        self.assertEqual(
            msgs, ["You turn your Angel ECM suite online (ECCM mode)."])
        self.assertTrue(s2(self.mech) & ANGEL_ECCM_ENABLED)
        msgs = mech_angeleccm(self.mech)
        self.assertEqual(msgs, ["You turn your Angel ECM suite offline."])
        self.assertFalse(s2(self.mech) & ANGEL_ECCM_ENABLED)

    def test_mutual_exclusion(self):
        mech_angeleccm(self.mech)
        mech_angelecm(self.mech)
        self.assertTrue(s2(self.mech) & ANGEL_ECM_ENABLED)
        self.assertFalse(s2(self.mech) & ANGEL_ECCM_ENABLED)
        mech_angeleccm(self.mech)
        self.assertTrue(s2(self.mech) & ANGEL_ECCM_ENABLED)
        self.assertFalse(s2(self.mech) & ANGEL_ECM_ENABLED)

    def test_destroyed_gate_covers_both_toggles(self):
        # NB: BOTH angel toggles gate on ANGEL_ECM_DESTROYED.
        self.mech.set_crit_status(CritStatus.ANGEL_ECM_DESTROYED)
        for cmd in (mech_angelecm, mech_angeleccm):
            msgs = cmd(self.mech)
            self.assertEqual(
                msgs, ["Your Angel ECM has been destroyed already!"])
        self.assertEqual(
            s2(self.mech) & (ANGEL_ECM_ENABLED | ANGEL_ECCM_ENABLED), 0)

    def test_not_equipped(self):
        bare = ready_mech(name="Bare")
        for cmd in (mech_angelecm, mech_angeleccm):
            msgs = cmd(bare)
            self.assertEqual(
                msgs, ["This unit isn't equipped with an Angel ECM suite!"])


class TestPersonalECM(unittest.TestCase):

    def setUp(self):
        self.mech = ready_mech(name="Infiltrator")
        self.mech.infantry_specials = FC_INFILTRATORII_STEALTH_TECH

    def test_perecm_on_off(self):
        msgs = mech_perecm(self.mech)
        self.assertEqual(
            msgs, ["You turn your Personal ECM suite online (ECM mode)."])
        self.assertTrue(s2(self.mech) & PER_ECM_ENABLED)
        msgs = mech_perecm(self.mech)
        self.assertEqual(msgs, ["You turn your Personal ECM suite offline."])
        self.assertFalse(s2(self.mech) & PER_ECM_ENABLED)

    def test_pereccm_on_off(self):
        msgs = mech_pereccm(self.mech)
        self.assertEqual(
            msgs, ["You turn your Personal ECM suite online (ECCM mode)."])
        self.assertTrue(s2(self.mech) & PER_ECCM_ENABLED)
        msgs = mech_pereccm(self.mech)
        self.assertEqual(msgs, ["You turn your Personal ECM suite offline."])
        self.assertFalse(s2(self.mech) & PER_ECCM_ENABLED)

    def test_mutual_exclusion(self):
        mech_pereccm(self.mech)
        mech_perecm(self.mech)
        self.assertTrue(s2(self.mech) & PER_ECM_ENABLED)
        self.assertFalse(s2(self.mech) & PER_ECCM_ENABLED)
        mech_pereccm(self.mech)
        self.assertTrue(s2(self.mech) & PER_ECCM_ENABLED)
        self.assertFalse(s2(self.mech) & PER_ECM_ENABLED)

    def test_no_destroyed_gate(self):
        # The personal pair has NO destroyed gate in the C — even with
        # both ECM crit-status bits set the toggle works.
        self.mech.set_crit_status(CritStatus.ECM_DESTROYED)
        self.mech.set_crit_status(CritStatus.ANGEL_ECM_DESTROYED)
        msgs = mech_perecm(self.mech)
        self.assertEqual(
            msgs, ["You turn your Personal ECM suite online (ECM mode)."])
        self.assertTrue(s2(self.mech) & PER_ECM_ENABLED)

    def test_not_equipped(self):
        bare = ready_mech(name="Bare")
        for cmd in (mech_perecm, mech_pereccm):
            msgs = cmd(bare)
            self.assertEqual(
                msgs,
                ["This unit isn't equipped with a Personal ECM suite!"])


if __name__ == '__main__':
    unittest.main()
