import unittest
from tools.sensors_los import SensorSession
from systems.status_display import info_lines,advanced_status,status,target_lines
from entities.mech import UnitType as U,MoveType as M,Specials as SP,CritStatus as C,MechStatus as S

class StatusClasses(unittest.TestCase):
    def setUp(self):
        self.s=SensorSession({'units':[{'name':'viewer'},{'name':'secret','team':2,'at':[2,4,0]}],'config':{'periodic_updates':False},'actions':[]});self.u=self.s.units['viewer'];self.t=self.s.units['secret']
    def test_ground_and_infantry_use_distinct_information_layout(self):
        self.u.unit_type=U.VEH_GROUND;self.u.move_type=M.TRACK
        text='\n'.join(info_lines(self.u));self.assertNotIn('Vertical Speed',text);self.assertIn('Des. Speed:',text)
        self.u.unit_type=U.MW;self.u.move_type=M.BIPED
        text='\n'.join(info_lines(self.u));self.assertNotIn('Heat Sinks',text);self.assertIn('X, Y, Z:',text)
    def test_advanced_state_uses_damage_and_network(self):
        self.u.specials=SP.C3_MASTER_TECH;self.u.crit_status=C.C3_DESTROYED
        self.assertIn('%crC3M%cn','\n'.join(advanced_status(self.u)))
        self.u.specials=0;self.u.specials2=0x10;self.u.crit_status=C.NSS_DESTROYED
        self.assertIn('NullSigSys(%ch%crXX%cn)','\n'.join(advanced_status(self.u)))
    def test_status_uses_passive_guard_and_target_identity_mask(self):
        self.u.status=S.DESTROYED
        self.assertTrue(status(self.u,'H')['ok'])
        self.u.status=S.STARTED;self.u.target=self.t._id;self.u.map.losinfo[self.u._id,self.t._id]=0x8003
        self.assertIn('something','\n'.join(target_lines(self.u)))
        self.assertNotIn('secret','\n'.join(target_lines(self.u)))
    def test_status_retains_shared_live_scalar_fields(self):
        self.u.heat=6;self.u.speed=8;self.u.desired_speed=10
        result=status(self.u,'H')
        self.assertEqual((int(self.u.status),6,self.u.fuel,8,10,self.u.facing),
                         tuple(result[k] for k in ('status','heat','fuel','speed','desired_speed','facing')))
        self.assertEqual([self.u.x,self.u.y,self.u.z],result['position'])
        self.assertEqual(self.u.name,result['unit']['name'])
    def test_compact_weapons_keep_advanced_status_and_leftover_ammo(self):
        from entities.crittypes import i2ammo
        from entities.weapon import get_weapon
        self.u.specials|=SP.ECM_TECH
        self.u.weapons=[]
        for section in self.u.sections:
            for slot in section.criticals:slot.type=0
        slot=self.u.sections[0].criticals[0];slot.type=i2ammo(get_weapon('IS.SRM-6').index);slot.data=5
        result=status(self.u,'NW')
        self.assertTrue(result['lines'][0].startswith('AdvTech: ECM('))
        self.assertTrue(any(line.startswith('                                                  || ') for line in result['lines'][:-1]))
        self.assertFalse(any('WEAPON SYSTEMS' in line for line in result['lines']))
