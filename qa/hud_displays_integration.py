"""Real delayed entry, firing, repair, overlay and catalog workflows."""
from hud_displays_common import *
from hud_displays_contacts import pair,building
from hud_displays_tactical import cell


def entry():
    doc=document([unit(at=[50,50,0]),unit('tow',20,at=[50,50,0])]);u=doc['units'][0];u['carrying']=20
    building(doc,(50,50));doc['maps'][1]['bay']=dict(enter_lock='true');return doc


def integration():
    for name,n,row,meta in examples('integration'):
        doc=entry() if n<4 else document();case=Case(name,doc,meta)
        if n==1:
            doc['actions']=[command('enterbase'),command('enterbase'),action('inspect'),action('advance',seconds=int(row['ticks'])),action('inspect')]
            case.expect('results.0.scheduled',True).expect('results.0.due',18).expect('results.1.ok',False)
            case.expect('results.2.events',dict(kind='ENTER_HANGAR',deadline=18,unit='u'),'has_fields')
            for peer in ('u','tow'):case.expect('state.units.'+peer+'.mapindex',2000 if row['map']=='inside' else 1000)
            case.expect('state.units.u.messages',dict(text='You enter the building.',count=int(row['count'])),'count_contains')
        elif n==2:
            doc['maps'][1].update(cf=int(row['cf']),buildflag=8 if row['safe']=='true' else 0,bay=dict(enter_lock='false'))
            doc['actions']=[command('enterbase')];case.expect('results.0.ok',row['scheduled']=='true')
            case.expect('state.events',dict(text='ENTER_HANGAR',count=1 if row['scheduled']=='true' else 0),'count_contains')
        elif n==3:
            state=row['state'];doc['actions']=[command('enterbase')]
            if state=='moved-off-entrance':doc['actions'].append(action('place',unit='u',at=[51,50,0]))
            elif state=='locked-safe-destination':doc['actions'] += [action('bay_configure',map='building',values=dict(enter_lock='false')),action('map_value',map='building',values=dict(buildflag=8))]
            else:doc['actions'].append(action('configure',unit='u',values=dict(started=False) if state=='shutdown' else dict(status=8|64)))
            doc['actions'].append(action('advance',seconds=18));case.expect('results.0.scheduled',True).expect('state.units.u.mapindex',1000).expect('state.units.u.messages',dict(text='You enter the building.',count=0),'count_contains')
        elif n==4:
            workflow=row['workflow']
            if workflow=='weapon-fire-and-recycle':
                doc,u,t=pair();case.doc=doc;u.update(facing=180,target=20,weapons=[dict(name='IS.MediumLaser',section=0,critical=4)])
                doc['actions']=[hud('key=test'),hud('we'),command('fire','0 TT'),hud('we'),action('advance',seconds=60),hud('we')]
                case.expect('results.2.accepted',True).expect('results.1.records.0.payload|4','R').expect('results.3.records.0.payload|4',r'^\d+$','regex').expect('results.5.records.0.payload|4','R')
            elif workflow=='real-section-armor-repair':
                u=doc['units'][0];u.update(character=101,started=False,repair=dict(stall=True),measured_mass=51200,sections=[dict(index=4,internal=10,internal_orig=10,armor=7,armor_orig=10)])
                doc['characters']=[dict(id=101,name='Technician',tech=True,location=10,values={'Build':5,'Reflexes':5,'Intuition':5,'Learn':5,'Technician-Battlemech':6})]
                doc['repair_economy']=dict(objects=[dict(id=1000,ECONPARTS='[547,0,3]')]);doc['random']['streams']['tech_rolls']=[12]
                doc['actions']=[hud('key=test'),command('fixarmor','CT'),command('status','A'),action('inspect'),action('advance',seconds=540),hud('as'),action('inspect')]
                case.expect('results.1.ok',True).expect('results.2.armor.text','%cb','contains').expect('results.5.wire','CT,10,','contains').expect('state.units.u.sections.4.armor',10)
                for loc in (0,1,2,3,5,6,7):case.expect(f'results.6.units.u.sections.{loc}',f'results.3.units.u.sections.{loc}','same')
            elif workflow=='timed-fire-overlay-expiry':
                doc['units'][0]['at']=[50,50,0];doc['map']['hexes']=[dict(at=[50,49],terrain='ROAD',elevation=0,overlay='FIRE',duration=2)]
                doc['actions']=[command('tactical','u'),action('advance',seconds=61),command('tactical','u')];cell(case,0,50,49,'&&','##');cell(case,2,50,49,'##','##')
            else:
                doc,u,t=pair();case.doc=doc;doc.pop('diagnostic_cache');u['target']=20;doc['config']['periodic_updates']=True
                doc['map']['hexes']=[dict(at=[50,54],terrain='MOUNTAINS',elevation=9)]
                doc['actions']=[command('contacts'),action('place',unit='target',at=[0,0,0]),action('advance',seconds=2),command('contacts'),command('status','S')]
                case.expect('results.0.contacts',1,'length').expect('results.3.contacts',[]).expect('results.4.plain','NOT in line of sight!','contains')
        elif n==5:
            service=row['service']
            if service=='MUX-expression-lock':
                doc=entry();case.doc=doc;doc['maps'][1]['bay']=dict(enter_lock='[unsupported()]');doc['actions']=[command('enterbase')];index=0
            elif service=='MUX-custom-template-expression':doc['units'][0]['display']=dict(status_expression=True);doc['actions']=[command('status','A')];index=0
            else:
                doc,u,t=pair();case.doc=doc;t['communications']=dict(autopilot=99,freq=[123]+[0]*15)
                doc['actions']=[command('scan','TT')];index=0
            case.expect(f'results.{index}.blocked',service,'contains').expect(f'results.{index}.effects_complete',False)
        else:
            doc['construction']=dict(catalog=True)
            doc['actions']=[action('template',kind='load',unit='u',reference='CHP-W5'),action('construction_pilot',unit='u',actor=dict(gunnery=4,piloting=5)),command('status','A'),command('critstatus','Cockpit'),hud('key=test'),hud('oas'),hud('as'),action('status_query',unit='u',kind='critslot',section='Cockpit',slot=6,flag='NAME')]
            case.expect('results.0.ok',True)
            for loc,value in enumerate([24,15,15,30,16,20]):
                case.expect(f'state.units.u.sections.{loc}.armor',value)
                for index in (5,6):case.expect(f'results.{index}.records.{loc}.payload|1',str(value))
            case.expect('results.5.records',7,'length').expect('results.6.records',7,'length').expect('results.7.ok',False)
            for label in ('Nose','Left Wing','Right Wing','Fuselage','Cockpit','Engine'):case.expect('results.2.plain',label,'contains')
        yield case
