"""Regression contracts reproduced by independent HUD subprocess workflows."""
import unittest
from entities.mech import Mech, Specials
from systems import hud, observation
from systems.equipment_display import catalog_rows
from systems.status_display import info_lines
from tools.sensors_los import SensorSession


class QARegressions(unittest.TestCase):
    def test_catalog_preserves_source_water_minimum(self):
        rows={row[1]:row for row in catalog_rows()}
        self.assertEqual(0,rows['IS.AC/5'][6])
        self.assertEqual(-1,rows['IS.StreakSRM-4'][6])
        self.assertEqual(-1,rows['IS.StreakSRM-6'][6])

    def test_c3_master_has_tag_without_dedicated_tag_flag(self):
        unit=Mech.create_test_mech();unit.specials=Specials.C3_MASTER_TECH
        self.assertEqual('Tm',hud.advtech(unit))

    def test_brief_nonzero_prefix_and_exact_zero(self):
        session=SensorSession({'units':[{'name':'u'}],'config':{'periodic_updates':False},'actions':[]})
        unit=session.units['u']
        self.assertTrue(observation.brief(unit,'C2junk')['ok'])
        for text in ('C00','C+0','C0 '):self.assertFalse(observation.brief(unit,text)['ok'])
        self.assertEqual(2,unit.brief)

    def test_report_heading_wraps_lateral_motion(self):
        session=SensorSession({'units':[{'name':'u'}],'config':{'periodic_updates':False},'actions':[]})
        unit=session.units['u'];unit.facing=350;unit.lateral=30
        self.assertEqual(20,observation.unit_report(unit,unit,0)['heading'])
        self.assertIn('Heading: 20 degrees','\n'.join(observation.report_lines(unit,unit,0)))

    def test_unconfigured_aircraft_fuel_defaults_to_zero(self):
        session=SensorSession({'units':[{'name':'u','class':'AERO','movement':'FLY'}],'config':{'periodic_updates':False},'actions':[]})
        unit=session.units['u']
        self.assertEqual(0,unit.fuel_orig)
        self.assertIn('Fuel: 0 (nan %)','\n'.join(info_lines(unit)))

    def test_sensor_sight_range_failure_is_not_accepted(self):
        session=SensorSession({'map':{'size':[100,100]},'units':[{'name':'u','at':[50,50,0],'facing':180,'weapons':[{'name':'IS.MediumLaser','section':0,'critical':4}]},{'name':'v','contact_id':'TT','at':[50,80,0]}], 'config':{'periodic_updates':False},'random':{'streams':{'attack_rolls':[7]}},'actions':[]})
        unit=session.units['u'];other=session.units['v'];session.map.losinfo[unit._id,other._id]=14
        result=session.action({'op':'command','unit':'u','name':'sight','args':['0','TT']})
        self.assertFalse(result['ok']);self.assertTrue(result['attack']['shot_aborted'])
        self.assertEqual(1000,result['attack']['bth_breakdown']['range_mod'])

    def test_initial_smoke_expires_through_the_real_queue(self):
        from tools.combat_resolution import CombatSession
        session=CombatSession({'map':{'size':[8,8],'hexes':[{'at':[2,2],'terrain':'ROAD','elevation':0,'overlay':'SMOKE','duration':2}]},'units':[{'name':'u','at':[5,5,0]}],'config':{'periodic_updates':False},'actions':[]})
        self.assertEqual(':',session.map.terrain(2,2))
        session.action({'op':'advance','seconds':3})
        self.assertEqual('#',session.map.terrain(2,2))
        self.assertEqual([],session.map.map_objects[1])
