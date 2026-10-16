import unittest
from unittest.mock import patch
from tools.sensors_los import SensorSession
from systems import observation

class ScanTests(unittest.TestCase):
    def setUp(self):
        self.s=SensorSession({'units':[{'name':'viewer'},{'name':'target','contact_id':'TT','at':[2,4,0]}],'config':{'periodic_updates':False},'actions':[]})
        self.unit=self.s.units['viewer'];self.target=self.s.units['target']
    def test_enemy_armor_is_qualitative_and_report_has_source_lines(self):
        self.target.sections[0].armor=44;self.target.sections[0].armor_orig=99
        with patch('systems.observation.in_line_of_sight',return_value=True),patch('systems.observation.in_line_of_sight_nb',return_value=True):
            result=observation.scan(self.unit,'TT A')
        self.assertTrue(result['ok']);self.assertIn('XX',result['armor_display']['plain'])
        self.assertIn('      Range: 2.0 hex\t\tBearing:',result['message'])
        self.assertNotIn('armor',result['armor'][0])
    def test_empty_hex_is_a_normal_query_result(self):
        with patch('systems.observation.in_line_of_sight',return_value=True):
            result=observation.scan(self.unit,'3 3 H')
        self.assertTrue(result['ok']);self.assertTrue(result['building_queried']);self.assertTrue(result['mines_queried'])
        self.assertFalse(result.get('blocked'))
    def test_missing_view_target_has_distinct_message(self):
        self.unit.target=-1
        self.assertEqual('You do not have a default target set!',observation.view(self.unit)['message'])
        self.unit.target=self.target._id
        with patch('systems.observation.in_line_of_sight_nb',return_value=False):
            self.assertEqual("That target isn't seen well enough by the scannfers for viewing!",observation.view(self.unit)['message'])
    def test_arity_precedes_inoperable_scanner(self):
        self.unit.scan_range=0
        self.assertEqual('Wrong number of arguments to scan!',observation.scan(self.unit,'1 2 3 4')['message'])
        self.assertEqual('Wrong number of arguments to report!',observation.scan(self.unit,'1 2 3',report=True)['message'])
    def test_id_and_default_scan_have_distinct_gate_order(self):
        self.unit.scan_range=1;self.unit.target=self.target._id
        with patch('systems.observation.in_line_of_sight',return_value=True),patch('systems.observation.in_line_of_sight_nb',return_value=False):
            self.assertEqual("That target isn't seen well enough by the scanners for scanning!",observation.scan(self.unit,'TT')['message'])
            self.assertEqual('Target is out of scanner range.',observation.scan(self.unit)['message'])
            self.assertEqual('Target is out of scanner range.',observation.scan(self.unit,'TT Z')['message'])
    def test_coordinate_report_checks_hex_nb_before_target_lookup(self):
        with patch('systems.observation.in_line_of_sight',return_value=True),patch('systems.observation.in_line_of_sight_nb',return_value=False):
            self.assertEqual("That target isn't seen well enough by the scanners for a report!",observation.scan(self.unit,'3 3',report=True)['message'])
        with patch('systems.observation.in_line_of_sight',return_value=True),patch('systems.observation.in_line_of_sight_nb',return_value=True):
            self.assertEqual('No target found.',observation.scan(self.unit,'3 3',report=True)['message'])
    def test_default_hex_scan_requires_nb(self):
        from entities.mech import MechStatus as S
        self.unit.target=-1;self.unit.targ_x=3;self.unit.targ_y=3;self.unit.status|=S.LOCK_HEX
        with patch('systems.observation.in_line_of_sight',return_value=True),patch('systems.observation.in_line_of_sight_nb',return_value=False):
            self.assertEqual('Target hex is not in line of sight!',observation.scan(self.unit)['message'])
    def test_scan_towing_uses_scanned_units_identification(self):
        self.target.carrying=self.unit._id
        with patch('systems.observation.in_line_of_sight',return_value=True),patch('systems.observation.in_line_of_sight_nb',return_value=True),patch('systems.los.in_line_of_sight_nb',return_value=False):
            result=observation.scan(self.unit,'TT I')
        self.assertIn('Towing something [',result['message'])
        self.assertNotIn('Towing viewer',result['message'])
