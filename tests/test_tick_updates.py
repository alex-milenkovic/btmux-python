"""Standard dispatcher and heartbeat apply effects without movement events."""
from tests.movement_fixture import MovementTestCase
from entities.mech import MechStatus2 as S2,UnitType,WeaponState,Location
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke
from core.game_loop import wire_standard_systems,recycle_weaponry,mech_update
from unittest.mock import patch


class TickUpdates(MovementTestCase):
    def test_dispatch_calls_pilot_and_turret_boundaries(self):
        self.unit.set_status2(S2.AUTOTURN_TURRET)
        with patch('systems.stability.update_pilot_skill_rolls') as pilot, patch('systems.maneuver.update_autoturn_turret') as turret:
            mech_update(self.engine,self.unit)
        pilot.assert_called_once_with(self.engine,self.unit)
        turret.assert_called_once_with(self.unit,self.board)

    def test_recycle_completion_clears_temporary_failure_and_notifies(self):
        weapon=get_weapon('IS.MediumLaser')
        self.unit.weapons=[WeaponState(weapon_idx=weapon.index,section=Location.LARM,critical=4,recycle=4)]
        slot=self.unit.sections[Location.LARM].criticals[4]
        slot.type,slot.data=i2weapon(weapon.index),4
        set_part_temp_nuke(slot,1)
        self.engine.events.set_tick(4)
        recycle_weaponry(self.engine,self.unit)
        self.assertEqual((slot.data,self.unit.weapons[0].recycle,part_temp_nuke(slot)),(0,0,0))
        self.assertTrue(any('operational' in s for s in self.unit.movement_messages))

    def test_aircraft_does_not_run_ground_dispatch(self):
        self.unit.unit_type=UnitType.AERO
        with patch('physics.aerospace.update') as aero:
            mech_update(self.engine,self.unit)
        aero.assert_called_once_with(self.engine, self.unit)
