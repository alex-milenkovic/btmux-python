"""Public command formation and real per-person reception in a fresh process."""
import json
import subprocess
import sys
import tempfile
import unittest


class CommunicationsCLITest(unittest.TestCase):
    def test_commands_form_network_and_deliver_both_radio_kinds(self):
        with tempfile.TemporaryDirectory() as root:
            document = dict(pilots={'root':root+'/people'}, construction={'root':root+'/templates'},
                            file_root=root+'/maps', config={'periodic_updates':False},
                            units=[dict(name=name,id=ident,contact_id=name*2,character=ident+100,
                                        at=[3,3,0],started=True,in_character=True,
                                        communications={'specials2':32,'radio_type':114}) for name,ident in (('A',10),('B',11))],
                            characters=[dict(id=ident+100,name=name+' pilot',location=ident) for name,ident in (('A',10),('B',11))],
                            actions=[{'op':'command','unit':'B','name':'c3i','args':'AA'},
                                     {'op':'command','unit':'B','name':'c3imessage','args':'  hello'},
                                     {'op':'command','unit':'A','name':'setchannelfreq','args':'a=17'},
                                     {'op':'command','unit':'B','name':'setchannelfreq','args':'a=17'},
                                     {'op':'command','unit':'A','name':'sendchannel','args':'a=radio hello'}])
            run = subprocess.run([sys.executable,'-m','tools.communications'],input=json.dumps(document),text=True,capture_output=True)
            self.assertEqual(0,run.returncode,run.stderr)
            result=json.loads(run.stdout)
            self.assertTrue(all(row['ok'] for row in result['results']),result['results'])
            self.assertEqual([11],result['state']['units']['A']['communications']['c3i']['peers'])
            self.assertIn('%chC3i/B [BB]: hello%cn',result['state']['inboxes']['110'])
            self.assertTrue(any('radio hello' in text for text in result['state']['inboxes']['111']))

    def run_document(self,document):
        with tempfile.TemporaryDirectory() as root:
            document.setdefault('map',{'size':[30,30]})
            document.update(pilots={'root':root+'/people'},construction={'root':root+'/templates'},file_root=root+'/maps')
            run=subprocess.run([sys.executable,'-m','tools.communications'],input=json.dumps(document),text=True,capture_output=True)
            self.assertEqual(0,run.returncode,run.stderr)
            return json.loads(run.stdout)

    def test_joined_network_changes_real_sight_and_fire_then_shutdown_removes_contribution(self):
        from entities.mech import Specials
        units=[];characters=[]
        for name,ident,y,team in [('A',10,15,1),('B',11,9,1),('T',12,7,2)]:
            units.append(dict(name=name,id=ident,at=[3,y,0],contact_id=name*2,team=team,character=ident+100,
                in_character=True,communications={'specials':int(Specials.C3_SLAVE_TECH),'working_c3_masters':int(name=='A')},
                weapons=[{'name':'IS.MediumLaser','section':'LA'}] if name=='A' else []))
            characters.append(dict(id=ident+100,name=name+' pilot',location=ident,connected=True,
                values={'Reflexes':5,'Intuition':5,'Gunnery-Laser':4,'Gunnery-Battlemech':4}))
        result=self.run_document(dict(config={'periodic_updates':True},units=units,characters=characters,
            random={'seed':0},actions=[{'op':'advance','seconds':5},
                {'op':'command','unit':'B','name':'c3','args':'AA'},
                {'op':'command','unit':'A','name':'sight','args':['0','TT']},
                {'op':'command','unit':'A','name':'fire','args':['0','TT']},
                {'op':'command','unit':'B','name':'shutdown','args':[]},
                {'op':'command','unit':'A','name':'sight','args':['0','TT']}]))
        result['results']=result['results'][1:]
        self.assertTrue(result['results'][0]['ok'],result['results'])
        for row in result['results'][1:3]:
            self.assertTrue(row['accepted'],row)
            self.assertEqual('SHORT',row['attack']['bth_breakdown']['range_bracket'])
            self.assertEqual(11,row['attack']['bth_breakdown']['c3_ref'])
        self.assertEqual('LONG',result['results'][-1]['attack']['bth_breakdown']['range_bracket'])
        self.assertEqual([11],result['state']['units']['A']['communications']['c3']['peers'])
        self.assertTrue(any('Using range data from B' in text for text in result['state']['inboxes']['110']))

    def test_full_c3_capacity_uses_requested_identities_before_registration(self):
        units=[dict(name=chr(65+i),id=10*(i+1),contact_id=chr(65+i)*2,
                    at=[3,3,0],team=1,
                    communications={'specials':128 if i==0 else 256,
                                    'working_c3_masters':4 if i==0 else 0})
               for i in range(13)]
        actions=[dict(op='command',unit=chr(65+i),name='c3',args='AA') for i in range(1,13)]
        result=self.run_document(dict(config={'periodic_updates':False},units=units,actions=actions))
        self.assertTrue(all(row['ok'] for row in result['results'][:11]))
        self.assertIn('maximum capacity',result['results'][11]['error'])
        self.assertEqual(list(range(20,121,10)),result['state']['units']['A']['communications']['c3']['peers'])
        self.assertEqual([],result['state']['units']['M']['communications']['c3']['peers'])

    def test_public_channel_settings_drive_multihop_delivery_and_bearing(self):
        units=[];characters=[];actions=[]
        for name,ident,y in [('A',10,3),('B',11,8),('C',12,13)]:
            units.append(dict(name=name,id=ident,at=[3,y,0],contact_id=name*2,team=1,character=ident+100,
                              communications={'radio_type':114,'radio_range':5}))
            characters.append(dict(id=ident+100,name=name+' pilot',location=ident))
            actions.extend([{'op':'command','unit':name,'name':'setchannelfreq','args':'a=17'},
                            {'op':'command','unit':name,'name':'setchannelmode','args':'a='+('DE' if name=='B' else 'DI' if name=='C' else 'D')}])
        actions.extend([{'op':'command','unit':'A','name':'setchanneltitle','args':'a=Ops'},
                        {'op':'command','unit':'A','name':'sendchannel','args':'a=hold'}])
        result=self.run_document(dict(config={'periodic_updates':False},units=units,characters=characters,actions=actions))
        self.assertTrue(all(row['ok'] for row in result['results']),result['results'])
        self.assertEqual(['[A:000] {R-path:[BB]-h:000} <Ops> hold%c'],result['state']['inboxes']['112'][-1:])

    def test_master_critical_immediately_removes_public_sight_and_fire_benefit(self):
        from entities.mech import Specials, CritStatus, FireMode, Location
        units=[];characters=[]
        for name,ident,y,team in [('A',10,15,1),('B',11,9,1),('T',12,7,2)]:
            units.append(dict(name=name,id=ident,at=[3,y,0],contact_id=name*2,team=team,character=ident+100,
                in_character=True,communications={'specials':int(Specials.C3_MASTER_TECH if name=='A' else Specials.C3_SLAVE_TECH),
                                                 'working_c3_masters':int(name=='A')},
                sections=[{'index':'LT','slots':[{'index':i,'special':'C3_MASTER'} for i in range(5)]}] if name=='A' else [],
                weapons=[{'name':'IS.MediumLaser','section':'LA'}] if name=='A' else []))
            characters.append(dict(id=ident+100,name=name+' pilot',location=ident,connected=True,
                values={'Reflexes':5,'Intuition':5,'Gunnery-Laser':4,'Gunnery-Battlemech':4}))
        result=self.run_document(dict(config={'periodic_updates':True},units=units,characters=characters,
            random={'seed':0},actions=[{'op':'advance','seconds':5},
                {'op':'command','unit':'B','name':'c3','args':'AA'},
                {'op':'command','unit':'A','name':'sight','args':['0','TT']},
                {'op':'diagnose','unit':'A','kind':'slot','options':{'section':'LT','slot':0}},
                {'op':'command','unit':'A','name':'sight','args':['0','TT']},
                {'op':'command','unit':'A','name':'fire','args':['0','TT']}]))
        rows=result['results']
        self.assertTrue(rows[1]['ok'],rows)
        self.assertEqual('SHORT',rows[2]['attack']['bth_breakdown']['range_bracket'])
        self.assertTrue(rows[3]['effect_applied'],rows[3])
        for row in rows[4:]:
            self.assertTrue(row['accepted'],row)
            self.assertEqual('LONG',row['attack']['bth_breakdown']['range_bracket'])
            self.assertEqual(-1,row['attack']['bth_breakdown']['c3_ref'])
        state=result['state']['units']['A']
        self.assertEqual(0,state['working_c3_masters'])
        self.assertTrue(state['crit_status'] & CritStatus.C3_DESTROYED)
        self.assertTrue(state['sections'][Location.LTORSO]['slots'][0]['firemode'] & FireMode.DESTROYED_MODE)


    def test_scheduled_fire_diagnostic_executes_at_its_deadline(self):
        result=self.run_document(dict(config={'periodic_updates':False},
            units=[dict(name='A',id=10,at=[3,3,0],sections=[dict(index=0,armor=10,internal=10)])],
            random={'streams':{'fire_damage':[1],'damage_entry':[7],'tow_rolls':[12],'sensor.perception_xp':[1]*100,'sensor.detect':[1]*100}},
            actions=[dict(op='schedule',unit='A',callback='vehicle_burn_event',delay=1),
                     dict(op='advance',seconds=1)]))
        self.assertIsNot(result['results'][1].get('ok'),False,result['results'])
        self.assertEqual(9,result['state']['units']['A']['sections'][0]['armor'])
        self.assertEqual([1],[d['value'] for d in result['draws'] if d['name']=='fire_damage'])


if __name__ == '__main__':
    unittest.main()
