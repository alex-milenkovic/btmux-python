"""
Tests for the maneuver system (systems/maneuver.py).

Covers:
- rotate_torso: gates, L/R/C semantics, status bits (mech.move.c:749-796)
- set_turret: vehicle-only gate, relative storage, instant set, report
  (mech.move.c:720-747, btmacros.h:235)
- update_autoturn_turret: bail conditions and snap (mech.update.c:2932-2965)
- set_lateral: eligibility matrix, mode table, pending-event abort,
  delayed application (mech.move.c:39-103, mech.events.c:298-317)
- set_turnmode: gate, turn rate boost, slowdown speed cost
  (mech.move.c:105-131, mech.update.c:885-888, 1039-1054)
"""

import unittest
from types import SimpleNamespace

from core.game_loop import GameEngine, LATERAL_TICK
from core.events import EventType
from entities.mech import (
    Mech, MechStatus, MoveType, UnitType, Location, SectionConfig,
    VehicleLocation,
)
from entities.vehicle import Vehicle, TankCritStatus
from entities.map import GameMap
from physics.hexmath import find_bearing
from physics.movement import update_heading, update_speed, MP1
from systems.maneuver import (
    acceptable_degree, has_maneuvering_ace,
    rotate_torso, set_turret, update_autoturn_turret,
    set_lateral, lateral_event, can_move_laterally, LATERAL_NAMES,
    set_turnmode,
)


def make_mech(engine=None, **overrides):
    """A started test mech with defaults suitable for maneuver tests."""
    mech = Mech.create_test_mech()
    mech.set_status(MechStatus.STARTED)
    mech.max_speed = 64.5
    mech.pilot = SimpleNamespace(maneuvering_ace=False)
    mech.measured_mass = mech.tonnage * 1024
    board = GameMap(20, 20)
    board._id = 100
    if engine is not None: engine.register_entity(board)
    board.add_mech(mech)
    for key, value in overrides.items():
        setattr(mech, key, value)
    return mech


def make_ace():
    """A pilot object carrying the Maneuvering Ace advantage."""
    return SimpleNamespace(maneuvering_ace=True)


def make_turreted_vehicle(engine=None, **overrides):
    """A started vehicle with an intact turret."""
    veh = Vehicle()
    veh.sections[VehicleLocation.TURRET].internal = 3
    veh.sections[VehicleLocation.TURRET].internal_orig = 3
    veh.set_status(MechStatus.STARTED)
    veh.pilot = SimpleNamespace(maneuvering_ace=False)
    board = GameMap(20, 20)
    board._id = 100
    if engine is not None: engine.register_entity(board)
    board.add_mech(veh)
    for key, value in overrides.items():
        setattr(veh, key, value)
    return veh


class TestRotateTorso(unittest.TestCase):
    """rotate_torso gates and L/R/C semantics (mech.move.c:749-796)."""

    def setUp(self):
        self.engine = GameEngine()
        self.mech = make_mech(self.engine)

    def test_bsuit_gets_huh(self):
        self.mech.unit_type = UnitType.BSUIT
        ok, msg = rotate_torso(self.engine, self.mech, 'l')
        self.assertFalse(ok)
        self.assertEqual(msg, "Huh?")

    def test_mechwarrior_can_rotate_torso(self):
        self.mech.unit_type = UnitType.MW
        ok, msg = rotate_torso(self.engine, self.mech, 'l')
        self.assertTrue(ok)
        self.assertTrue(self.mech.has_status(MechStatus.TORSO_LEFT))

    def test_vehicle_has_no_torso(self):
        self.mech.unit_type = UnitType.VEH_GROUND
        ok, msg = rotate_torso(self.engine, self.mech, 'r')
        self.assertFalse(ok)
        self.assertEqual(msg, "You don't have a torso.")

    def test_fallen_cannot_twist(self):
        self.mech.set_status(MechStatus.FALLEN)
        ok, msg = rotate_torso(self.engine, self.mech, 'l')
        self.assertFalse(ok)
        self.assertEqual(
            msg, "You're lying flat on your face, "
                 "you can't rotate your torso.")

    def test_quad_cannot_twist(self):
        self.mech.move_type = MoveType.QUAD
        ok, msg = rotate_torso(self.engine, self.mech, 'l')
        self.assertFalse(ok)
        self.assertEqual(msg, "Quads can't rotate their torsos.")

    def test_twist_left_sets_bit(self):
        ok, msg = rotate_torso(self.engine, self.mech, 'l')
        self.assertTrue(ok)
        self.assertEqual(msg, "You rotate your torso left.")
        self.assertTrue(self.mech.has_status(MechStatus.TORSO_LEFT))
        self.assertFalse(self.mech.has_status(MechStatus.TORSO_RIGHT))

    def test_twist_right_sets_bit(self):
        ok, msg = rotate_torso(self.engine, self.mech, 'r')
        self.assertTrue(ok)
        self.assertEqual(msg, "You rotate your torso right.")
        self.assertTrue(self.mech.has_status(MechStatus.TORSO_RIGHT))
        self.assertFalse(self.mech.has_status(MechStatus.TORSO_LEFT))

    def test_twist_beyond_60_left(self):
        rotate_torso(self.engine, self.mech, 'l')
        ok, msg = rotate_torso(self.engine, self.mech, 'l')
        self.assertFalse(ok)
        self.assertEqual(msg, "You cannot rotate torso beyond 60 degrees!")
        self.assertTrue(self.mech.has_status(MechStatus.TORSO_LEFT))

    def test_twist_beyond_60_right(self):
        rotate_torso(self.engine, self.mech, 'r')
        ok, msg = rotate_torso(self.engine, self.mech, 'r')
        self.assertFalse(ok)
        self.assertEqual(msg, "You cannot rotate torso beyond 60 degrees!")

    def test_opposite_command_centers(self):
        rotate_torso(self.engine, self.mech, 'l')
        ok, msg = rotate_torso(self.engine, self.mech, 'r')
        self.assertTrue(ok)
        self.assertEqual(msg, "You rotate your torso right.")
        self.assertFalse(self.mech.has_status(MechStatus.TORSO_LEFT))
        self.assertFalse(self.mech.has_status(MechStatus.TORSO_RIGHT))

    def test_center_clears_both(self):
        rotate_torso(self.engine, self.mech, 'r')
        ok, msg = rotate_torso(self.engine, self.mech, 'c')
        self.assertTrue(ok)
        self.assertEqual(msg, "You center your torso.")
        self.assertFalse(self.mech.has_status(MechStatus.TORSO_LEFT))
        self.assertFalse(self.mech.has_status(MechStatus.TORSO_RIGHT))

    def test_instant_and_free(self):
        """Twisting schedules no event."""
        rotate_torso(self.engine, self.mech, 'l')
        self.assertEqual(self.engine.events.count_data(self.mech), 0)


class TestSetTurret(unittest.TestCase):
    """set_turret gates and relative storage (mech.move.c:720-747)."""

    def setUp(self):
        self.engine = GameEngine()
        self.veh = make_turreted_vehicle(getattr(self, "engine", None))

    def test_mech_has_no_turret(self):
        mech = make_mech()
        ok, msg = set_turret(self.engine, mech, 90)
        self.assertFalse(ok)
        self.assertEqual(msg, "You don't have a turret.")

    def test_mechwarrior_has_no_turret(self):
        mech = make_mech(unit_type=UnitType.MW)
        ok, msg = set_turret(self.engine, mech, 90)
        self.assertFalse(ok)
        self.assertEqual(msg, "You don't have a turret.")

    def test_turretless_vehicle_refused(self):
        bare = make_turreted_vehicle()
        bare.sections[VehicleLocation.TURRET].internal = 0
        bare.sections[VehicleLocation.TURRET].internal_orig = 0
        ok, msg = set_turret(self.engine, bare, 90)
        self.assertFalse(ok)
        self.assertEqual(msg, "You don't have a turret.")

    def test_jammed_turret_refused(self):
        self.veh.tank_crit_status |= TankCritStatus.TURRET_JAMMED
        ok, msg = set_turret(self.engine, self.veh, 90)
        self.assertFalse(ok)
        self.assertEqual(msg, "Your turret is jammed in position.")

    def test_locked_turret_refused(self):
        self.veh.tank_crit_status |= TankCritStatus.TURRET_LOCKED
        ok, msg = set_turret(self.engine, self.veh, 90)
        self.assertFalse(ok)
        self.assertEqual(msg, "Your turret is locked in position.")

    def test_relative_storage(self):
        """Turret facing is stored relative to hull (btmacros.h:235)."""
        self.veh.facing = 90
        ok, msg = set_turret(self.engine, self.veh, 180)
        self.assertTrue(ok)
        self.assertEqual(self.veh.turret_facing, 90)
        self.assertEqual(msg, "Turret facing changed to 180.")

    def test_relative_storage_wraps(self):
        self.veh.facing = 90
        set_turret(self.engine, self.veh, 30)
        self.assertEqual(self.veh.turret_facing,
                         acceptable_degree(30 - 90))   # 300

    def test_instant_no_event(self):
        set_turret(self.engine, self.veh, 180)
        self.assertEqual(self.engine.events.count_data(self.veh), 0)

    def test_report_form(self):
        self.veh.facing = 90
        self.veh.turret_facing = 90
        ok, msg = set_turret(self.engine, self.veh, None)
        self.assertTrue(ok)
        self.assertEqual(msg, "Your turret is currently facing 180.")
        self.assertEqual(self.veh.turret_facing, 90)   # unchanged


class TestUpdateAutoturnTurret(unittest.TestCase):
    """Autoturn turret snap and bails (mech.update.c:2932-2965)."""

    def setUp(self):
        self.map = GameMap(20, 20)
        self.veh = make_turreted_vehicle(getattr(self, "engine", None))
        self.veh.set_hex_position(5, 5)
        self.veh.facing = 0
        self.veh.status2 = 0x4000  # C AUTOTURN_TURRET is a status2 bit.
        self.target = Mech.create_test_mech()
        self.target.set_hex_position(5, 10)
        self.map._id = 100
        self.target._id = 2
        self.map.add_mech(self.target)
        self.map.add_mech(self.veh)
        self.veh.target = self.target._id

    def expected_facing(self):
        return acceptable_degree(
            find_bearing(self.veh.fx, self.veh.fy,
                         self.target.fx, self.target.fy) - self.veh.facing)

    def test_snap_to_locked_target(self):
        self.assertTrue(update_autoturn_turret(self.veh, self.map))
        self.assertEqual(self.veh.turret_facing, self.expected_facing())

    def test_snap_is_relative_to_hull(self):
        self.veh.facing = 90
        self.assertTrue(update_autoturn_turret(self.veh, self.map))
        self.assertEqual(self.veh.turret_facing, self.expected_facing())

    def test_snap_to_locked_hex(self):
        self.veh.target = -1
        self.veh.targ_x = 5
        self.veh.targ_y = 10
        self.assertTrue(update_autoturn_turret(self.veh, self.map))
        self.assertNotEqual(self.veh.turret_facing, 0)

    def test_dispatcher_owns_the_autoturn_flag_gate(self):
        from core.game_loop import mech_update
        from unittest.mock import patch
        self.veh.status2 = 0
        with patch('systems.maneuver.update_autoturn_turret') as update:
            mech_update(GameEngine(), self.veh)
        update.assert_not_called()

    def test_bails_when_not_started(self):
        self.veh.clear_status(MechStatus.STARTED)
        self.assertFalse(update_autoturn_turret(self.veh, self.map))

    def test_bails_when_unconscious(self):
        self.veh.set_status(MechStatus.UNCONSCIOUS)
        self.assertFalse(update_autoturn_turret(self.veh, self.map))

    def test_bails_when_blinded(self):
        self.veh.set_status(MechStatus.BLINDED)
        self.assertFalse(update_autoturn_turret(self.veh, self.map))

    def test_bails_when_jammed(self):
        self.veh.tank_crit_status |= TankCritStatus.TURRET_JAMMED
        self.assertFalse(update_autoturn_turret(self.veh, self.map))

    def test_bails_when_locked(self):
        self.veh.tank_crit_status |= TankCritStatus.TURRET_LOCKED
        self.assertFalse(update_autoturn_turret(self.veh, self.map))

    def test_bails_without_turret(self):
        self.veh.sections[VehicleLocation.TURRET].internal = 0  # C tests current internal.
        self.assertFalse(update_autoturn_turret(self.veh, self.map))

    def test_bails_without_lock(self):
        self.veh.target = -1
        self.assertFalse(update_autoturn_turret(self.veh, self.map))
        self.assertEqual(self.veh.turret_facing, 0)


class TestLateralEligibility(unittest.TestCase):
    """can_move_laterally matrix (mech.move.c:79-81)."""

    def test_quad_all_legs_intact(self):
        mech = make_mech(move_type=MoveType.QUAD)
        self.assertTrue(can_move_laterally(mech))

    def test_quad_missing_leg(self):
        mech = make_mech(move_type=MoveType.QUAD)
        mech.sections[Location.RLEG].armor =         mech.sections[Location.RLEG].internal = 0
        self.assertFalse(can_move_laterally(mech))

    def test_quad_missing_front_leg(self):
        """Quad front legs live in the arm slots."""
        mech = make_mech(move_type=MoveType.QUAD)
        mech.sections[Location.LARM].armor =         mech.sections[Location.LARM].internal = 0
        self.assertFalse(can_move_laterally(mech))

    def test_vtol_eligible(self):
        mech = make_mech(move_type=MoveType.VTOL, unit_type=UnitType.VTOL)
        self.assertTrue(can_move_laterally(mech))

    def test_plain_biped_ineligible(self):
        mech = make_mech()
        self.assertFalse(can_move_laterally(mech))

    def test_hover_movetype_does_not_qualify(self):
        """The C's bugged comparison is type-vs-movetype: a HOVER
        *move type* does not pass it (mech.move.c:80)."""
        mech = make_mech(move_type=MoveType.HOVER)
        self.assertFalse(can_move_laterally(mech))

    def test_c_bug_unit_class_3_qualifies(self):
        """MechType(mech) == MOVE_HOVER as literally written: unit class
        3 (naval vehicle) passes the check (mech.move.c:80)."""
        mech = make_mech(unit_type=UnitType.VEH_NAVAL)
        self.assertTrue(can_move_laterally(mech))

    def test_maneuvering_ace_eligible(self):
        mech = make_mech()
        mech.pilot = make_ace()
        self.assertTrue(can_move_laterally(mech))


class TestSetLateral(unittest.TestCase):
    """set_lateral command flow (mech.move.c:39-103)."""

    def setUp(self):
        self.engine = GameEngine()
        self.mech = make_mech(self.engine, move_type=MoveType.QUAD)

    def test_ineligible_message(self):
        biped = make_mech(self.engine)
        ok, msg = set_lateral(self.engine, biped, 'nw')
        self.assertFalse(ok)
        self.assertEqual(msg, "You cannot alter your lateral movement!")

    def test_mode_table(self):
        """All aliases resolve to the specced offsets."""
        expected = {
            'nw': 300, 'fl': 300,
            'ne': 60, 'fr': 60,
            'sw': 240, 'rl': 240,
            'se': 120, 'rr': 120,
        }
        for alias, ofs in expected.items():
            engine = GameEngine()
            mech = make_mech(engine, move_type=MoveType.QUAD)
            ok, msg = set_lateral(engine, mech, alias)
            self.assertTrue(ok, alias)
            self.assertEqual(mech._lateral_event.data2, ofs, alias)
            self.assertEqual(
                msg,
                "Wanted lateral movement mode changed to %s (%d offset)."
                % (LATERAL_NAMES[ofs], ofs), alias)

    def test_dash_means_straight(self):
        self.mech.lateral = 60
        ok, msg = set_lateral(self.engine, self.mech, '-')
        self.assertTrue(ok)
        self.assertEqual(
            msg, "Wanted lateral movement mode changed to None (0 offset).")

    def test_same_mode_already(self):
        self.mech.lateral = 60
        ok, msg = set_lateral(self.engine, self.mech, 'ne')
        self.assertFalse(ok)
        self.assertEqual(msg, "You are going that way already!")

    def test_delayed_application(self):
        """The change lands only when the LATERAL event fires at
        LATERAL_TICK (6)."""
        ok, _ = set_lateral(self.engine, self.mech, 'nw')
        self.assertTrue(ok)
        self.assertEqual(self.mech.lateral, 0)   # not yet
        self.assertTrue(self.engine.has_event(EventType.LATERAL, self.mech))
        self.engine.run_ticks(LATERAL_TICK + 1)
        self.assertEqual(self.mech.lateral, 300)
        self.assertFalse(self.engine.has_event(EventType.LATERAL, self.mech))

    def test_current_mode_aborts_pending_change(self):
        set_lateral(self.engine, self.mech, 'nw')
        ok, msg = set_lateral(self.engine, self.mech, '-')
        self.assertTrue(ok)
        self.assertEqual(msg, "Lateral mode change aborted.")
        self.engine.run_ticks(LATERAL_TICK + 1)
        self.assertEqual(self.mech.lateral, 0)   # change never lands
        self.assertFalse(self.engine.has_event(EventType.LATERAL, self.mech))

    def test_event_callback_message(self):
        """mech.events.c:298-317 completion message."""
        event = SimpleNamespace(data=self.mech, data2=300)
        msg = lateral_event(event)
        self.assertEqual(
            msg,
            "Lateral movement mode change to Front/Left (300 offset) "
            "completed.")
        self.assertEqual(self.mech.lateral, 300)

    def test_event_callback_bails_when_not_started(self):
        self.mech.clear_status(MechStatus.STARTED)
        event = SimpleNamespace(data=self.mech, data2=300)
        self.assertIsNone(lateral_event(event))
        self.assertEqual(self.mech.lateral, 0)


class TestSetTurnMode(unittest.TestCase):
    """set_turnmode gate and effects (mech.move.c:105-131)."""

    def setUp(self):
        self.engine = GameEngine()
        self.mech = make_mech(self.engine)
        self.mech.turn_mode = False

    def test_gate_without_ace(self):
        ok, msg = set_turnmode(self.engine, self.mech, 'tight')
        self.assertFalse(ok)
        self.assertEqual(msg, "You're not skilled enough to do that.")
        self.assertFalse(self.mech.turn_mode)

    def test_tight(self):
        self.mech.pilot = make_ace()
        ok, msg = set_turnmode(self.engine, self.mech, 'tight')
        self.assertTrue(ok)
        self.assertEqual(msg, "You brace for tighter turns.")
        self.assertTrue(self.mech.turn_mode)

    def test_normal(self):
        self.mech.pilot = make_ace()
        self.mech.turn_mode = True
        ok, msg = set_turnmode(self.engine, self.mech, 'normal')
        self.assertTrue(ok)
        self.assertEqual(msg, "You assume a normal turn mode.")
        self.assertFalse(self.mech.turn_mode)

    def test_report(self):
        self.mech.pilot = make_ace()
        self.mech.turn_mode = True
        ok, msg = set_turnmode(self.engine, self.mech, None)
        self.assertTrue(ok)
        self.assertEqual(msg, "Your turning type is : TIGHT")
        self.mech.turn_mode = False
        ok, msg = set_turnmode(self.engine, self.mech, 'status')
        self.assertEqual(msg, "Your turning type is : NORMAL")

    def test_tight_turns_faster(self):
        """offset * 3 // 2 for braced aces (mech.update.c:885-888)."""
        normal = make_mech(facing=0, desired_facing=90, speed=0.0)
        update_heading(normal)

        tight = make_mech(facing=0, desired_facing=90, speed=0.0)
        tight.pilot = make_ace()
        tight.turn_mode = True
        update_heading(tight)

        self.assertGreater(tight.facing, normal.facing)

    def test_tight_without_ace_no_boost(self):
        normal = make_mech(facing=0, desired_facing=90, speed=0.0)
        update_heading(normal)

        pretender = make_mech(facing=0, desired_facing=90, speed=0.0)
        pretender.turn_mode = True     # no ace pilot
        update_heading(pretender)

        self.assertEqual(pretender.facing, normal.facing)

    def test_tight_speed_cost_under_slowdown_2(self):
        """CHEAD consumes the heading-update flag; tight adds another .4 MP."""
        from entities.mech import CritStatus
        mech = make_mech(facing=0, desired_facing=180, speed=19.35, desired_speed=64.5)
        mech.pilot = make_ace()
        mech.turn_mode = True
        mech.set_crit_status(CritStatus.CHEAD)
        update_speed(mech)
        control = make_mech(facing=0, desired_facing=180, speed=19.35, desired_speed=64.5)
        control.pilot = make_ace()
        control.set_crit_status(CritStatus.CHEAD)
        update_speed(control)
        self.assertLess(mech.speed, control.speed)
        self.assertFalse(mech.has_crit_status(CritStatus.CHEAD))

    def test_tight_speed_cost_gated_on_config(self):
        """No cost when btech_slowdown != 2."""
        mech = make_mech(facing=0, desired_facing=180,
                         speed=64.5, desired_speed=64.5)
        mech.pilot = make_ace()
        mech.turn_mode = True
        mech.engine = SimpleNamespace(btech_slowdown=0)
        update_speed(mech)
        self.assertEqual(mech.speed, 64.5)


if __name__ == '__main__':
    unittest.main()
