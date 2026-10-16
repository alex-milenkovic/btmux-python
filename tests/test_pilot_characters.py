"""Character records feed real existing pilot consumers."""
import unittest
from data.characters import CharacterStore
from systems.characters import set_value
from systems import piloting
from entities.mech import Mech,MechStatus
from core.game_loop import GameEngine
from core.randomness import use_source,use_simulation


class PilotCharacterTest(unittest.TestCase):
    def setUp(self):
        self.store=CharacterStore();self.store.create(101,'Alice',location=10)
        for name in ('Build','Reflexes','Intuition','Learn','Charisma'):set_value(self.store,101,name,5)
        self.unit=Mech();self.unit._id=10;self.unit.in_character=True
        self.unit.pilot=self.store.actor(101);self.unit._engine=GameEngine()

    def advantage_unit(self):
        from entities.map import GameMap
        unit=Mech.create_test_mech();unit._id=10;unit.in_character=True
        unit.pilot=self.store.actor(101);unit.status=MechStatus.STARTED
        board=GameMap(12,12);board._id=1000
        engine=GameEngine();engine.register_entity(board)
        board.add_mech(unit);engine.register_entity(unit)
        return unit

    def test_persisted_speed_and_ace_change_sprint_speed_and_turning(self):
        from entities.mech import MechStatus2
        from physics.cargo import cargo_max_speed
        from physics.movement import calculate_turn_rate
        from systems.maneuver import can_move_laterally
        unit=self.advantage_unit();unit.max_speed=64.5;unit.speed=10
        normal_turn=calculate_turn_rate(unit,64.5)
        unit.status2=MechStatus2.SPRINTING
        for speed,ace,expected_speed,turn_fraction in ((0,0,86,.5),(1,0,96.75,2/3),(2,0,86,.5),(0,1,86,1),(0,2,86,.5)):
            with self.subTest(speed=speed,ace=ace):
                set_value(self.store,101,'Speed_Demon',speed)
                set_value(self.store,101,'Maneuvering_Ace',ace)
                self.assertEqual(ace==1,can_move_laterally(unit))
                self.assertEqual(expected_speed,cargo_max_speed(unit))
                self.assertEqual(int(normal_turn*32*turn_fraction)/32,calculate_turn_rate(unit,64.5))

    def test_persisted_dodge_advantage_controls_real_mode_command(self):
        from systems.movement_commands import set_mode
        from entities.mech import MechStatus2
        for raw in (0,1,2):
            with self.subTest(raw=raw):
                unit=self.advantage_unit()
                set_value(self.store,101,'Dodge_Maneuver',raw)
                ok,message=set_mode(unit._engine,unit,'dodge')
                self.assertEqual(raw==1,ok,message)
                if ok:
                    unit._engine.process_tick()
                    self.assertTrue(unit.status2&MechStatus2.DODGING)

    def test_persisted_melee_advantage_changes_physical_damage(self):
        from systems.physical import calculate_dfa_damage
        unit=self.advantage_unit();unit.tonnage=55;unit.rtons=55*1024
        unit.pilot.melee_specialist=True
        for raw,damage in ((0,17),(1,18),(2,17)):
            set_value(self.store,101,'Melee_Specialist',raw)
            self.assertEqual((damage,11),calculate_dfa_damage(unit))

    def test_persisted_pain_resistance_reduces_explosion_injury(self):
        from systems.criticals import ammo_explosion
        from entities.mech import Location
        for raw,damage in ((0,2),(1,1),(2,2)):
            with self.subTest(raw=raw):
                unit=self.advantage_unit()
                set_value(self.store,101,'Pain_Resistance',raw)
                set_value(self.store,101,'Bruise',0)
                with use_source(lambda name,lo,hi,fallback:hi):
                    result=ammo_explosion(unit,Location.LARM,1,1,attacker=unit)
                self.assertEqual(damage,result.pilot_damage)
                self.assertEqual(damage*10,self.store.retrieve(101).get('Bruise'))

    def test_persisted_pain_resistance_applies_to_explosive_weapon_critical(self):
        from systems.criticals import apply_weapon_critical
        from entities.mech import Location
        from entities.weapon import get_weapon
        weapon=get_weapon('IS.GaussRifle')
        for raw,damage in ((0,2),(1,1),(2,2)):
            unit=self.advantage_unit()
            for slot in unit.sections[Location.LARM].criticals[:weapon.crits]:slot.type=weapon.index+1
            set_value(self.store,101,'Pain_Resistance',raw)
            set_value(self.store,101,'Bruise',0)
            with use_source(lambda name,lo,hi,fallback:hi):
                result=apply_weapon_critical(unit,Location.LARM,0)
            self.assertEqual(damage,result.pilot_damage)
            self.assertEqual(damage*10,self.store.retrieve(101).get('Bruise'))

    def test_character_skill_changes_actual_machine_lookup(self):
        self.unit._engine.extended_piloting = True
        set_value(self.store,101,'Piloting-Biped',4)
        self.assertEqual(4,piloting.find_pilot_piloting(self.unit))
        set_value(self.store,101,'Reflexes',6)
        self.assertEqual(3,piloting.find_pilot_piloting(self.unit))
        self.unit.pilot.piloting=99
        self.assertEqual(3,piloting.find_pilot_piloting(self.unit))

    def test_ic_health_consciousness_and_repeated_initial_return(self):
        dice=iter([1,1]);seen=[]
        def draws(name,lo,hi,fallback):seen.append(name);return next(dice)
        with use_simulation(self.unit._engine.randomness),use_source(draws):
            piloting.head_hit_mw_damage(self.unit,None,1)
        s=self.store.retrieve(101)
        self.assertEqual((10,0,1),(s.get('Bruise'),s.get('Lethal'),self.unit.pilot_hits))
        self.assertTrue(self.unit.has_status(MechStatus.UNCONSCIOUS))
        self.assertEqual(['character_d6']*2,seen)
        self.assertEqual(0,self.unit._engine.randomness.total_rolls)
        deadlines=[e.tick for e in self.unit._engine.events.pending_events()]
        with use_source(lambda *args: (_ for _ in ()).throw(AssertionError('initial reroll'))):
            piloting.head_hit_mw_damage(self.unit,None,1)
        self.assertEqual(deadlines,[e.tick for e in self.unit._engine.events.pending_events()])
        self.assertEqual(20,self.store.retrieve(101).get('Bruise'))

    def test_exact_toughness_and_ic_targets(self):
        set_value(self.store,101,'Bruise',20);set_value(self.store,101,'Pain_Resistance',1)
        self.assertEqual(4,piloting.mw_ic_bth(self.unit))
        for toughness,expected in ((1,3),(2,2)):
            set_value(self.store,101,'Toughness',toughness);seen=[]
            with use_source(lambda name,lo,hi,fallback:(seen.append(name) or 6)):
                self.assertTrue(piloting.handle_mw_conc(self.unit))
            self.assertEqual(expected,len(seen))

    def test_negative_unit_damage_ignored_and_lethal_survivor(self):
        self.unit._id=-1
        piloting.head_hit_mw_damage(self.unit,None,2);piloting.mw_lethal_damage(self.unit,None,4)
        self.assertEqual((0,0),(self.unit.pilot_hits,self.store.retrieve(101).get('Bruise')))
        self.unit._id=10
        with use_source(lambda *args:6):piloting.mw_lethal_damage(self.unit,None,4)
        s=self.store.retrieve(101)
        self.assertEqual((45,20,4),(s.get('Bruise'),s.get('Lethal'),self.unit.pilot_hits))
        piloting.fix_pilotdamage(self.unit,self.unit.pilot)
        self.assertEqual(6,self.unit.pilot_hits)

    def test_normal_mw_startup_uses_character_body_skills_and_raw_sixth_sense(self):
        from systems.startup import startup
        from entities.mech import UnitType,Specials
        self.unit.unit_type=UnitType.MW;self.unit.pilot_owner=self.unit.pilot
        self.unit.boot_messages=[];self.unit.specials=Specials.NONE
        set_value(self.store,101,'Bruise',10);set_value(self.store,101,'Sixth_Sense',2)
        set_value(self.store,101,'Perception',3);set_value(self.store,101,'Comm-Conventional',4)
        from entities.map import GameMap
        board=GameMap(12,12);board._id=1000;self.unit._engine.register_entity(board)
        board.add_mech(self.unit)
        self.unit._engine.register_entity(self.unit)
        with use_source(lambda *args:6):
            ok,message=startup(self.unit._engine,self.unit)
            self.assertTrue(ok,message)
            self.unit._engine.process_tick()
        self.assertTrue(self.unit.is_started)
        self.assertEqual(1,self.unit.pilot_hits)
        self.assertEqual((46,1),(self.unit.sections[4].internal,self.unit.sections[7].armor_orig+1))
        self.assertEqual((4,5),(self.unit.comm,self.unit.per))
        self.assertTrue(self.unit.specials&Specials.SS_ABILITY)

    def test_fatal_ic_injury_kills_real_contents_without_incrementing_hits(self):
        from systems.occupants import Personnel
        world=Personnel(self.unit._engine,self.store,afterlife=900)
        world.add(self.unit,1000);world.add(self.unit.pilot,10)
        set_value(self.store,101,'Bruise',45);set_value(self.store,101,'Lethal',45)
        with use_source(lambda *args: (_ for _ in ()).throw(AssertionError('fatal consciousness draw'))):
            piloting.head_hit_mw_damage(self.unit,None,1)
        self.assertEqual((50,49,0),(self.store.retrieve(101).get('Bruise'),self.store.retrieve(101).get('Lethal'),self.unit.pilot_hits))
        self.assertTrue(self.unit.is_destroyed);self.assertFalse(self.store.actor(101).alive)
        self.assertEqual(900,self.store.actor(101).location)
