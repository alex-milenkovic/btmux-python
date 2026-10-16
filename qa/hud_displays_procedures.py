"""Additional status, query, armor, equipment and local entry procedures."""
from hud_displays_common import *
from hud_displays_contacts import pair,building,f32
from hud_displays_integration import entry
from hud_displays_catalog import definitions


def procedures():
    doc=document([unit(at=[50,50,0],facing=37,desired_facing=83,speed=12.25,desired_speed=13.75,vertical_speed=4.25,plus_heat=1.99,minus_heat=2.99,target=20),unit('target',20,at=[50,51,0],team=2)], [hud('key=test'),hud('gs'),action('place',unit='u',at=[50,50,0],real=[f32(152*93.097730906827152),16366.875,0]),hud('gs'),command('findcenter')])
    case=Case('supplement/all-gs-fields-and-center',doc)
    case.expect('results.1.records.0.payload',['AA',50,50,0,37,83,'12.25','13.75',19,29,'-','4.25','4.25','0.000',180,0,'','-','-','-'],'csv').expect('results.3.records.0.payload|13','0.250').expect('results.3.records.0.payload|14','0').expect('results.4.message','0.25','contains');yield case
    for form,section,loc,maximum in [('biped','LA',0,12),('biped','H',7,6),('biped','LL',5,6),('quad','FL',0,6),('MW','LA',0,2),('AERO','Cockpit',4,5),('AERO','Engine',5,12),('VTOL','Rotor',5,12),('VEHICLE-TRACK','Front',2,12),('NAVAL-HULL','Front',2,12),('BSUIT','Suit 1',0,12),('DS','Nose',5,12)]:
        doc=document();doc['units'][0].update(formed(form));doc['units'][0]['sections']=[dict(index=loc,internal=10,internal_orig=10,slots=[dict(index=maximum-1,special='HEAT_SINK')])]
        doc['actions']=[action('status_query',unit='u',kind='critslot',section=section,slot=maximum,flag='NAME'),action('status_query',unit='u',kind='critslot',section=section,slot=maximum+1,flag='NAME'),action('status_query',unit='u',kind='critstatus',section=section)]
        yield Case('supplement/slot-limits-'+form+'-'+section,doc).expect('results.0.ok',True).expect('results.0.text','Heat','contains').expect('results.1.text','#-1 INVALID CRITICAL').expect('results.2.text',r'^(?:[^,]*,){'+str(maximum-1)+r'}[^,]*$','regex')
    for kind in ('armorstatus','sectstatus','critstatus','weaponstatus'):
        for empty in (False,True):
            q=action('status_query',unit='u',kind=kind)
            if empty:q['section']=''
            doc=document(actions=[q]);yield Case(f'supplement/query-{kind}-'+('empty' if empty else 'absent'),doc).expect('results.0.text','' if kind=='weaponstatus' and not empty else '#-1 INVALID SECTION')
    for flag,expected in [('data','13'),('MAXAMMO','100'),('HALFTON','1'),('STATUS','Disabled'),('MODE','#-1 NOT AMMO OR WEAPON')]:
        doc=document(actions=[action('status_query',unit='u',kind='critslot',section='LA',slot=5,flag=flag)]);doc['units'][0]['sections']=[dict(index=0,slots=[dict(index=4,ammo='IS.MachineGun',data=13,firemode=128|2|1)])]
        yield Case('supplement/half-ammo-'+flag,doc).expect('results.0.text',expected)
    for index,flag in enumerate(('NAME','nAmE','unknown')):
        doc=document(actions=[action('status_query',unit='u',kind='critslot',section='LA',slot=5,flag=flag)]);doc['units'][0]['sections']=[dict(index=0,slots=[dict(index=4,special='HEAT_SINK')])]
        yield Case('supplement/query-name-'+str(index),doc).expect('results.0.text','HeatSink')
    for component,event,payload,expected in [('front',47,0,'LA,?,O,O'),('rear',47,8,'LA,O,?,O'),('internal',48,0,'LA,O,O,?')]:
        doc,u,t=pair();t['sections']=[dict(index=0,armor=10,armor_orig=10,rear=10,rear_orig=10,internal=10,internal_orig=10)]
        doc['actions']=[hud('key=test'),action('repair_diagnose',kind='schedule',unit='target',type=event,payload=payload,delay=100),hud('asc TT')]
        yield Case('supplement/repair-component-'+component,doc).expect('results.2.records.0.payload',expected)
    for template,expected in [('7 &1+0',' 7'),('7 &3+0','  17'),('7 &&',' &'),('7 @0A',' A'),('7 !01B',' B'),('7 &+0\n7 &-0 &4:0',' 17\r\n  3    9')]:
        doc=document(actions=[command('status','A')]);doc['units'][0].update(sections=[dict(index=0,armor=17,armor_orig=20,rear=3,rear_orig=5,internal=9,internal_orig=10)],display=dict(status_template=template))
        yield Case('supplement/custom-grammar-'+str(len(template))+'-'+re.sub(r'[^a-zA-Z0-9]','',template),doc).expect('results.0.armor.plain',expected)
    for value,expected in [(0,'**'),(4,'xx'),(9,'OO')]:
        doc,u,t=pair();t.update(formed('AERO'));t['display']=dict(status_template='7 &:0',display_si=value,display_si_orig=9);doc['actions']=[command('scan','TT A')]
        yield Case('supplement/legacy-si-'+str(value),doc).expect('results.0.armor_display.plain','    '+expected).expect('state.units.target.si',0)
    for form,label in [('biped','Mech Name:'),('quad','Mech Name:'),('MW','MechWarrior:'),('BSUIT','Squad Name:'),('AERO','Max thrust:'),('DS','Max thrust:'),('SPHEROID_DS','Max thrust:'),('VTOL','Movement Type: VTOL'),('VEHICLE-TRACK','Movement Type: Tracked'),('NAVAL-HULL','Movement Type: Displacement Hull')]:
        doc=document(actions=[command('status','R')]);doc['units'][0].update(formed(form));doc['units'][0]['display']=dict(template_name='Design Identity')
        yield Case('supplement/status-class-'+form,doc).expect('results.0.ok',True).expect('results.0.plain',label,'contains')
    for original in (False,True):
        doc=document(actions=[command('status','NA' if original else 'A')]);doc['units'][0].update(sections=[dict(index=0,armor=3,armor_orig=17)],display=dict(status_template='7 &+0'))
        case=Case('supplement/status-original-'+str(original),doc).expect('state.units.u.sections.0.armor',3)
        if original:case.expect('results.0.plain','17|8','contains')
        else:case.expect('results.0.armor.plain','  3')
        yield case
    for aim_type,expected in [(0,'Left Arm'),(1,'None')]:
        doc,u,t=pair();u.update(target=20,display=dict(aim=0,aim_type=aim_type,pkiller=True,turn_mode=1),pilot_details=dict(maneuvering_ace=True),charge_target=20,charge_timer=5);doc['config']['newcharge']=1;doc['actions']=[command('status','S')]
        case=Case('supplement/aim-type-'+str(aim_type),doc).expect('results.0.plain','Aimed Shot Location: '+expected,'contains').expect('results.0.plain','Weapon Safeties are OFF.','contains').expect('results.0.plain','Turn Mode: TIGHT','contains').expect('results.0.plain','ChargeTimer: 2','contains');yield case
    for kind,flag in [('Hex',0x20000),('Building at',0x10000)]:
        doc=document(actions=[action('configure',unit='u',values=dict(targ_x=4,targ_y=6,status=8|flag)),command('status','S')]);yield Case('supplement/target-'+kind.replace(' ','_'),doc).expect('results.1.plain',f'Target: {kind} 4 6','contains')
    doc=document([unit(**formed('MW'))],[command('critstatus','LA')]);yield Case('supplement/mw-critstatus',doc).expect('results.0.message','Huh?')
    for name,setup in [('no-link',None),('missing-entrance','entrance'),('bad-direction','direction'),('jumping','jumping'),('fallen','fallen'),('flying','flying'),('dropship','dropship'),('vtol-no-fuel','fuel')]:
        doc=entry();u=doc['units'][0]
        if setup is None:doc['maps'][0]['map_objects']=[]
        elif setup=='entrance':doc['maps'][1]['map_objects']=[]
        elif setup in ('jumping','fallen'):u['status']=8|(64 if setup=='jumping' else 128)
        else:
            if setup in ('flying','dropship','fuel'):u.update(formed('DS' if setup=='dropship' else 'VTOL'));u['aerospace']=dict(landed=setup!='flying');u['fuel']=0 if setup=='fuel' else 100
        doc['actions']=[command('enterbase','s' if setup=='direction' else '')]
        yield Case('supplement/entry-guard-'+name,doc).expect('results.0.ok',False).expect('state.events',dict(text='ENTER_HANGAR',count=0),'count_contains')
