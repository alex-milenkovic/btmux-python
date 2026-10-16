"""Turret callers isolate locks while retaining physical weapon effects."""
from unittest.mock import patch
from types import SimpleNamespace
from tests.movement_fixture import MovementTestCase
from entities.mech import MechStatus as S
from systems import turrets as t


class TurretTests(MovementTestCase):
    def setUp(self):
        super().setUp()
        self.board._id=self.unit.mapindex=100
        self.actor=SimpleNamespace(_id=77,valid=True,connected=True,is_player=True,location=40,wizard=False,gunnery=2)
        self.turret=t.Turret(_id=40,parent=self.unit._id,gunner=77,arcs=1,target=88)
        self.unit.target=99
        self.unit.pilot._id=76
        self.unit.in_character=False

    def test_context_restores_entire_status_even_when_delegate_raises(self):
        self.unit.set_status(S.FIRED)
        before=self.unit.status
        def broken(unit,name,args,actor):
            self.assertEqual(unit.target,88)
            self.assertEqual(self.engine.pilot_override,77)
            unit.target=55
            unit.clear_status(S.FIRED)
            unit.heat+=3
            raise ValueError('delegate failed')
        with patch('systems.turrets.delegate',side_effect=broken):
            with self.assertRaisesRegex(ValueError,'delegate failed'):
                t.command(self.engine,self.turret,self.actor,'RANGE')
        self.assertEqual((self.unit.target,self.unit.status,self.unit.heat),(99,before,3))
        self.assertEqual(self.turret.target,55)
        self.assertEqual((self.engine.pilot_override,self.engine.arc_override),(0,0))

    def test_inactive_tic_is_silent_with_no_parent_or_gunner(self):
        self.turret.parent=-1;self.turret.gunner=-1
        self.assertEqual(t.command(self.engine,self.turret,self.actor,'FIRETIC'),dict(ok=True,messages=[]))

    def test_ic_fire_retains_actual_pilot_only_guard(self):
        self.unit.in_character=True
        result=t.command(self.engine,self.turret,self.actor,'FIRE','0')
        self.assertFalse(result['ok'])
        self.assertIn('only the pilot',result['message'])
        self.assertEqual(self.unit.target,99)

    def test_gunnery_override_uses_turret_room_actor_and_mechskills_precedence(self):
        from systems.piloting import find_pilot_gunnery
        from entities.weapon import get_weapon
        def inspect(unit,name,args,actor):
            self.assertEqual(find_pilot_gunnery(unit,get_weapon('IS.MediumLaser')),2)
            unit.quiet=True;unit.mechskills='5 3'
            self.assertEqual(find_pilot_gunnery(unit,get_weapon('IS.MediumLaser')),3)
            return dict(ok=True)
        with patch('systems.turrets.delegate',side_effect=inspect):
            t.command(self.engine,self.turret,self.actor,'SIGHT','0')
        self.assertIsNone(getattr(self.unit,'gun_pilot',None))

    def test_real_fire_delivers_feedback_to_bridge_and_turret_room(self):
        from entities.mech import Mech,UnitType,WeaponState
        from entities.weapon import get_weapon
        from entities.crittypes import i2weapon
        from systems.occupants import Personnel
        from data.characters import CharacterStore
        unit=self.unit;unit.unit_type=UnitType.DS
        target=Mech.create_test_mech();target.set_hex_position(10,9);target.team=2
        self.board.add_mech(target);self.engine.register_entity(target)
        self.board.mapvis=60;self.board.maxvis=100;self.board.maplight=2
        from systems.los import MECHLOSFLAG_SEESP,MECHLOSFLAG_SEESS
        self.board.losinfo[unit._id,target._id]=MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS
        self.turret.target=target._id
        weapon=get_weapon('IS.MediumLaser')
        unit.weapons=[WeaponState(weapon_idx=weapon.index,section=5,critical=0)]
        unit.sections[5].criticals[0].type=i2weapon(weapon.index)
        world=Personnel(self.engine,CharacterStore())
        world.add(unit,100);world.add(unit.pilot,unit._id);world.add(self.turret,unit._id);world.add(self.actor,40)
        unit.aero_turrets=[40]
        result=t.command(self.engine,self.turret,self.actor,'FIRE','0')
        self.assertTrue(result['ok'],result)
        for actor in (unit.pilot,self.actor):
            self.assertEqual(sum('You fire MediumLaser at ' in msg for msg in actor.inbox),1)
