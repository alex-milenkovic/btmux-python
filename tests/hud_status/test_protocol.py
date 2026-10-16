import unittest
from entities.mech import Mech, MechStatus as S, FireMode as F
from entities.crittypes import i2weapon
from entities.weapon import get_weapon
from systems.hud import HudSession
from systems.equipment_display import weapon_status, ammo_modes

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.unit=Mech.create_test_mech('HUD')
        self.unit.contact_id='aB'
        self.session=HudSession(lambda:self.unit)
    def test_key_validation_framing_and_precedence(self):
        self.assertEqual('#HUD hudinfo version 0.8\r\n',self.session.request('')['wire'])
        self.assertEqual('#HUD:???:???:E# No session key set\r\n',self.session.request('bad!')['wire'])
        self.assertEqual('#HUD:abc:KEY:R# Key set\r\n',self.session.request('key=abc')['wire'])
        self.assertIn('Invalid key',self.session.request('key=ä')['wire'])
        self.assertEqual('abc',self.session.key)
        self.assertIn('GS: subcommand not found',self.session.request('GS')['wire'])
        self.assertIn('Command takes no arguments',self.session.request('gs x')['wire'])
        self.unit.status|=S.UNCONSCIOUS
        self.assertIn('unconscious',self.session.request('gs')['wire'])
    def test_general_wire_has_twenty_source_fields(self):
        self.session.request('key=t')
        self.unit.speed=12.345;self.unit.plus_heat=2.19;self.unit.vertical_speed=-3.5
        result=self.session.request('gs')
        fields=result['records'][0]['payload'].split(',')
        self.assertEqual(20,len(fields));self.assertEqual('12.35',fields[6]);self.assertEqual('21',fields[8])
        self.assertEqual(['-3.50','-3.50'],fields[11:13]);self.assertEqual('-',fields[-1])
    def test_weapon_priority_and_floor(self):
        slot=self.unit.sections[0].criticals[4]
        slot.type=i2weapon(get_weapon('IS.MediumLaser').index);slot.data=3
        self.assertEqual('1',weapon_status(self.unit,0,4))
        slot.firemode=F.DISABLED_MODE
        self.assertEqual('D',weapon_status(self.unit,0,4))
        slot.firemode|=F.DESTROYED_MODE
        self.assertEqual('*',weapon_status(self.unit,0,4))
    def test_empty_lists_end_once_and_sessions_are_independent(self):
        self.unit.weapons=[]
        for section in self.unit.sections:
            for slot in section.criticals:slot.type=0
        self.session.request('key=one')
        other=HudSession(lambda:self.unit);other.request('key=two')
        self.assertEqual('one',self.session.key)
        result=self.session.request('we')
        self.assertEqual([{'class':'WE','type':'D','payload':'Done'}],result['records'])
