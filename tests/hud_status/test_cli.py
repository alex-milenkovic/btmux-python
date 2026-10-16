import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

class CliTests(unittest.TestCase):
    def test_connection_keys_queries_and_engine_commands(self):
        from tools.hud_status import DisplaySession
        Path('./tmp').mkdir(exist_ok=True)
        with TemporaryDirectory() as root:
            s=DisplaySession({'hud_display':{'root':root},'sessions':[{'name':'one','unit':'u'},{'name':'two','unit':'u'}],'units':[{'name':'u'}],'config':{'periodic_updates':False},'actions':[]})
            self.assertIn('Key set',s.action({'op':'hudinfo','session':'one','text':'key=abc'})['wire'])
            self.assertIn('No session key',s.action({'op':'hudinfo','session':'two','text':'gs'})['wire'])
            self.assertIn('#HUD:abc:GS:R#',s.action({'op':'hudinfo','session':'one','text':'gs'})['wire'])
            status=s.action({'op':'command','unit':'u','name':'status','args':['H']})
            self.assertTrue(status['ok']);self.assertIn('Temp:',status['plain'])
            result=s.action({'op':'status_query','unit':'u','kind':'critslot','section':'LARM','slot':1,'flag':'STATUS'})
            self.assertEqual('Operational',result['text'])
    def test_unrecognized_input_is_not_success(self):
        from tools.hud_status import DisplaySession
        with self.assertRaises(ValueError):DisplaySession({'hud_display':{'expected':'ok'},'actions':[]})
