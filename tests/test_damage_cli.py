"""Public damage session input and observation boundaries."""
import unittest
from tools.damage_criticals import DamageSession

class DamageCliTests(unittest.TestCase):
    def test_omitted_attacker_cocoon_damage_matches_explicit_self_damage(self):
        from core.events import EventType
        from physics.orbital import ood_event
        for amount, jump_speed, cocoon, falling in ((1, 0, 1, False), (3, 0, 0, True), (3, 10.75, -1, False)):
            observed = []
            for explicit in (False, True):
                with self.subTest(amount=amount, jump_speed=jump_speed, explicit=explicit):
                    session = self.session(random={'streams': {'damage_entry': [7], 'interception_rolls': [12]}})
                    unit = session.units['u']
                    unit.cocoon, unit.z, unit.fz, unit.jump_speed = 2, 10, 645, jump_speed
                    session.engine.schedule_event(1, EventType.OOD, ood_event, data=unit)
                    before = [(section.armor, section.internal) for section in unit.sections]
                    options = dict(section=4, amount=amount)
                    if explicit:
                        options['attacker'] = 'u'
                    self.assertEqual({'dealt': 0}, session.action(dict(op='diagnose', kind='damage', options=options)))
                    self.assertEqual([f'%cgYou hit the cocoon for {amount} points of damage!%cn', f'%ch%cyYour cocoon has been hit for {amount} points of damage!%cn'], unit.movement_messages[:2])
                    self.assertEqual(before, [(section.armor, section.internal) for section in unit.sections])
                    self.assertEqual(cocoon, unit.cocoon)
                    self.assertEqual(falling, session.engine.has_event(EventType.FALL, unit))
                    self.assertEqual(not falling, session.engine.has_event(EventType.OOD, unit))
                    observed.append(list(unit.movement_messages))
            self.assertEqual(*observed)


    def session(self, **kwargs):
        return DamageSession(dict(actions=[], config={'periodic_updates':False}, **kwargs))

    def test_cargo_diagnostic_is_source_noop(self):
        s=self.session()
        before=s.snapshot()
        result=s.action(dict(op='diagnose',kind='effect',options={'name':'cargo_hit'}))
        self.assertFalse(result['effect_applied'])
        after=s.snapshot()
        before['units']['u']['messages']=after['units']['u']['messages']
        self.assertEqual(before,after)

    def test_missing_service_is_explicit_and_inspection_consumes_no_dice(self):
        s=self.session()
        from systems.damage import external_effect
        external_effect(s.units['u'],'autoeject','create ejected pilot')
        first=s.snapshot(); self.assertEqual(first,s.snapshot())
        self.assertEqual(False,first['units']['u']['external_effects'][0]['applied'])
        self.assertEqual([],s.draws)

    def test_cockpit_name_resolves_for_aero(self):
        s=self.session(units=[{'name':'a','class':'AERO','sections':[{'index':'COCKPIT','armor':7}]}])
        self.assertEqual(7,s.units['a'].sections[4].armor)

    def test_fighter_explicit_internal_transfer_uses_armor_and_preserves_structure(self):
        s=self.session(units=[{'name':'u','class':'AERO','sections':[
            {'index':'Nose','armor':3,'internal':10},
            {'index':'Fuselage','armor':30,'internal':10}]}])
        s.action(dict(op='diagnose',kind='damage',options={
            'section':'Nose','amount':8,'internal':True,'transfer':True}))
        u=s.snapshot()['units']['u']
        self.assertEqual([u['sections'][i]['armor'] for i in (0,3)],[0,25])
        self.assertEqual([u['sections'][i]['internal'] for i in (0,3)],[10,10])

    def test_unknown_part_rejected(self):
        with self.assertRaises(ValueError):
            self.session(units=[{'name':'u','sections':[{'index':4,'slots':[{'index':0,'type':999999}]}]}])

    def test_finite_stream_exhaustion_fails(self):
        s=self.session(random={'streams':{'hit_location_rolls':[]}})
        with self.assertRaises(ValueError):
            s.action(dict(op='diagnose',kind='location'))

    def test_weapon_metadata_is_scoped_to_session(self):
        from entities.weapon import get_weapon
        original=get_weapon('IS.MediumLaser').damage
        s=self.session(units=[{'name':'u','weapons':[{'name':'IS.MediumLaser','metadata':{'damage':9}}]}])
        r=s.action(dict(op='diagnose',kind='percentage-failure',options={'weapon':'IS.MediumLaser','type':'DAMAGE','percentage':50}))
        self.assertEqual(4,r['modifier'])
        self.assertEqual(original,get_weapon('IS.MediumLaser').damage)

    def test_weapon_detail_explains_raw_mask_consequences(self):
        from entities.mech import FireMode
        s=self.session(units=[{'name':'u','weapons':['IS.MediumLaser'],'sections':[{'index':4,'slots':[{'index':0,'firemode':int(FireMode.DAMAGED_MODE),'weap_damage_flags':6}]}]}])
        text=s.action(dict(op='diagnose',kind='weapon-detail'))['text']
        self.assertIn('Focus misalignment (2 hits): -2 damage',text)
        self.assertIn('Explodes on 5 or less',text)

    def test_source_name_metadata_restores_catalog_even_after_failure(self):
        from entities.weapon import get_weapon, get_weapon_by_index
        original=get_weapon('IS.MediumLaser')
        alias='IS.CaselessAC/2'
        previous=get_weapon(alias)
        s=self.session(units=[{'name':'u','weapons':[{'name':original.name,
            'metadata':{'source_name':alias,'damage':9}}]}])
        def inspect_override():
            self.assertEqual(alias,get_weapon_by_index(original.index).name)
            self.assertEqual(9,get_weapon(alias).damage)
            raise RuntimeError('consumer failure')
        with self.assertRaises(RuntimeError):s.invoke(inspect_override)
        self.assertIs(original,get_weapon_by_index(original.index))
        self.assertIs(previous,get_weapon(alias))
        with self.assertRaises(ValueError):
            self.session(units=[{'name':'u','weapons':[{'name':original.name,'metadata':{'source_name':''}}]}])

    def test_damage_diagnostic_rejects_unknown_weapon(self):
        s=self.session()
        with self.assertRaises(ValueError):
            s.action(dict(op='diagnose',kind='damage',options={'amount':1,'weapon':'unknown'}))

    def test_dodamage_diagnostic_keeps_message_and_remainder(self):
        s=self.session(units=[{'name':'u','at':[3,3,0]},
                              {'name':'v','at':[3,2,0],'team':2}])
        result=s.action(dict(op='diagnose',kind='dodamage',options={'total':5,'cluster':3,'direction':4,'message':'Hit','broadcast':'takes a hit'}))
        self.assertEqual([3,2],result['sizes'])
        self.assertIn('Hit',s.snapshot()['units']['u']['messages'])
        self.assertIn('u [00] takes a hit',s.snapshot()['units']['v']['messages'])

    def test_real_vehicles_can_share_the_event_engine(self):
        from core.game_loop import GameEngine
        from entities.vehicle import Vehicle
        first,second=Vehicle(),Vehicle()
        engine=GameEngine();engine.register_entity(first);engine.register_entity(second)
        self.assertNotEqual(first._id,second._id)
