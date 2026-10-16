"""Mode and maneuver fixture failures, ownership and declared unit states."""
import unittest
from acceptance.movement import context, maneuvers, modes
from entities.mech import MechStatus as S, MoveType, Location


def ready():
    w = {}
    context.fresh(w)
    return w


class TestModeManeuverFixtures(unittest.TestCase):
    def test_declared_prone_roll_must_be_consumed(self):
        for result in ('PASS', 'FAIL'):
            w = ready()
            maneuvers.drop_setup(w, '10', result)
            with self.subTest(result=result), self.assertRaises(AssertionError):
                maneuvers.drop(w)
        for result in ('PASS', 'FAIL'):
            w = ready()
            maneuvers.drop_setup(w, '21.6', result)
            maneuvers.drop(w)
            maneuvers.drop_result(w, '0' if result == 'PASS' else '1')

    def test_rejected_maneuvers_fail_the_acceptance_step(self):
        for operation in ('bootlegger', 'prone', 'thrash'):
            w = ready()
            if operation == 'bootlegger':
                maneuvers.boot_setup(w, '50', '0', '0')
                action = lambda: maneuvers.boot_request(w, 'R')
            elif operation == 'prone':
                maneuvers.drop_setup(w, '0', 'UNUSED')
                w['unit'].set_status(S.FALLEN)
                action = lambda: maneuvers.drop(w)
            else:
                action = lambda: maneuvers.thrash(w)
            with self.subTest(operation=operation), self.assertRaises(AssertionError):
                action()

    def test_successful_maneuvers_keep_the_session_engine(self):
        for operation in ('bootlegger', 'prone', 'thrash'):
            w = ready()
            w['unit']._engine = None
            if operation == 'bootlegger':
                maneuvers.boot_setup(w, '50', '4', '0')
                maneuvers.boot_request(w, 'R')
            elif operation == 'prone':
                maneuvers.drop_setup(w, '0', 'UNUSED')
                maneuvers.drop(w)
            else:
                maneuvers.thrash_setup(w, '50', '0', 'GROUND')
                maneuvers.thrash(w)
            self.assertIs(w['engine'], w['unit']._engine)

    def test_mounted_and_enemy_battlesuit_fixtures_represent_the_claimed_states(self):
        w = ready()
        maneuvers.thrash_setup(w, '50', '0', 'MOUNTED')
        self.assertIs(w['unit'], w['other'].swarm_target)
        self.assertIsInstance(w['other'].team, int)
        self.assertNotEqual(w['unit'].team, w['other'].team)
        with self.assertRaises(ValueError) as error:
            maneuvers.thrash_setup(ready(), '50', '0', 'BAD_STATE')
        self.assertEqual('BAD_STATE', str(error.exception))
        with self.assertRaises(ValueError) as error:
            maneuvers.thrash_setup(ready(), '50', '-1', 'GROUND')
        self.assertEqual('battlesuit range must be nonnegative', str(error.exception))

    def test_pending_evade_assertion_names_the_actual_transition(self):
        w = ready()
        modes.request_mode(w, 'evade')
        modes.mode_state(w, 'NONE', 'EVADE_ON')

    def test_condition_and_hull_setup_rejections_are_failures(self):
        w = ready()
        w['unit'].set_status(S.DESTROYED)
        with self.assertRaises(AssertionError):
            modes.condition(w, 'STANDING')
        w = ready()
        modes.quad(w, '64.5')
        w['unit'].set_status(S.FALLEN)
        with self.assertRaises(AssertionError):
            modes.hull_workflow(w, 'LOWER', '10')
        with self.assertRaises(ValueError) as error:
            modes.condition(ready(), 'BAD_CONDITION')
        self.assertEqual('BAD_CONDITION', str(error.exception))
        with self.assertRaises(ValueError) as error:
            modes.hull_workflow(ready(), 'BAD_WORKFLOW', '10')
        self.assertEqual('Unknown hull down workflow: BAD_WORKFLOW', str(error.exception))

    def test_front_leg_condition_uses_a_quad_and_water_condition_is_physically_immersed(self):
        for condition, move, loc in (('QUAD_FRONT_LEG_DESTROYED', MoveType.QUAD, Location.LARM), ('LEFT_LEG_DESTROYED', MoveType.BIPED, Location.LLEG)):
            w = ready()
            modes.condition(w, condition)
            self.assertEqual(move, w['unit'].move_type)
            self.assertTrue(w['unit'].is_section_destroyed(loc))
        w = ready()
        modes.condition(w, 'IN_WATER')
        u = w['unit']
        self.assertLess(u.z, 0)
        self.assertGreaterEqual(u.z, w['map'].base_elevation(u.x, u.y))

    def test_due_event_stops_at_the_scheduled_transition_tick(self):
        w = ready()
        modes.pending_mode(w, 'sprint', 'DESTROYED')
        due_tick = w['unit']._mode_event.tick
        modes.due_event(w)
        self.assertEqual(due_tick, w['engine'].events.tick)
