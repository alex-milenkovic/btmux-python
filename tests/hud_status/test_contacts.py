import unittest
from unittest.mock import patch
from tools.sensors_los import SensorSession
from systems import observation

class ContactTests(unittest.TestCase):
    def setUp(self):
        self.session=SensorSession({'units':[{'name':'viewer'},{'name':'LongVisibleName','contact_id':'AB','heat':2,'at':[2,4,0]}],'config':{'periodic_updates':False},'actions':[]})
        self.unit=self.session.units['viewer'];self.target=self.session.units['LongVisibleName'];self.unit.brief=2
    def test_legacy_fields_and_nb_mask(self):
        for nb,name,ident,relation,status in [(True,'LongVisibleN','ab','F','   + '),(False,'something','AB','E','     ')]:
            with patch('systems.targeting.in_line_of_sight',return_value=0x300),patch('systems.targeting.in_line_of_sight_nb',return_value=nb):
                result=observation.contacts(self.unit,'h')
            row=result['contacts'][0]
            self.assertEqual(name,row['name'][:12]);self.assertEqual(ident,row['contact_id']);self.assertEqual(status,row['status'])
            fields=result['message'].splitlines()[1].split('#')[-1].split(',')
            self.assertEqual(relation,fields[0]);self.assertEqual(15,len(fields))
    def test_navigation_precision_and_no_redundant_ground_distance(self):
        result=observation.navigation(self.unit,'range','2 4')
        self.assertEqual('Range to  2,4 is: 2.0 hexes.',result['message'])
        result=observation.navigation(self.unit,'vector','2 2 3')
        self.assertIn('mark +90.',result['message'])
    def test_verbose_condition_order(self):
        from systems.display_contacts import contact_lines
        with patch('systems.targeting.in_line_of_sight',return_value=0x300),patch('systems.targeting.in_line_of_sight_nb',return_value=True):
            row=observation.contacts(self.unit)['contacts'][0]
        row.update(destroyed=True,started=False,fallen=True,jumping=True,jump_heading=90)
        self.assertEqual(['      Mech Destroyed','      Mech Shutdown','      Mech has Fallen!',
                          '      Mech is Jumping!\tJump Heading: 90',' '],
                         contact_lines(self.unit,row,False,False)[-5:])
