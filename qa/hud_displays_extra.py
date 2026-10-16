"""Extra procedure boundaries independent of generated acceptance bindings."""
from hud_displays_common import *
from hud_displays_contacts import pair,building
from hud_displays_catalog import definitions
import math


def extra():
    for token,ok,brief in [('C2junk',True,2),('C0 ',False,0),('C00',False,0),('C+0',False,0),('A6',True,24),('C3',True,3),('C-1',False,0)]:
        doc=document(actions=[command('brief',[token]),command('brief')]);case=Case('supplement/brief-'+token.replace(' ','space').replace('+','plus'),doc)
        case.expect('results.0.ok',ok).expect('results.1.contacts',brief%4).expect('results.1.autocontacts',brief//4);yield case
    for heading,lateral in [(350,30),(10,-30),(20,0)]:
        doc,u,t=pair();u['brief']=1;t.update(facing=heading,speed=21.5,heat=2.3,core=dict(lateral=lateral));doc['actions']=[hud('key=test'),hud('c'),command('report','TT'),command('contacts','h')]
        value=(heading+lateral)%360
        yield Case(f'supplement/virtual-heading-{heading}-{lateral}',doc).expect('results.1.records.0.payload|12',str(value)).expect('results.2.report.heading',value).expect('results.2.plain',f'Heading: {value} degrees','contains').expect('results.3.lines.1|13',f'{value:3d}')
    for maximum,vertical,desired in [(50,30,40),(50,0,0),(50,40,30)]:
        doc=document(actions=[hud('key=test'),hud('sgi')]);doc['units'][0].update(formed('VTOL'));doc['units'][0].update(core=dict(max_speed=maximum,fuel_orig=200),fuel=50,vertical_speed=vertical,desired_speed=desired)
        speed=int(math.sqrt(maximum**2-vertical**2));vs=int(math.sqrt(maximum**2-desired**2));case=Case(f'supplement/vtol-coupling-{vertical}',doc)
        for col,value in [(3,f'{speed*2/3:.3f}'),(4,f'{speed:.3f}'),(5,f'{-speed*2/3:.3f}'),(6,f'{vs:.3f}'),(7,'200')]:case.expect(f'results.1.records.0.payload|{col}',value)
        yield case
    for heat,value in [(8.9,'64.000'),(9,'96.000')]:
        doc=document(actions=[hud('key=test'),hud('sgi')]);doc['units'][0].update(heat=heat,specials=definitions()['TRIPLE_MYOMER_TECH'],core=dict(max_speed=64.5))
        yield Case('supplement/tsm-heat-'+str(heat),doc).expect('results.1.records.0.payload|4',value)
    doc=document(actions=[hud('  key=test'),hud(' GS'),hud('gs',macro=True),hud('key='),hud('gs')])
    case=Case('supplement/session-whitespace-case-macro-clear',doc);case.expect('results.0.ok',True).expect('results.1.ok',False).expect('results.2.wire','HUDINFO does not work from scode or macros.\r\n').expect('results.4.ok',False);yield case
    for kind,args in [('range','1'),('range','1 2 3'),('range','-1 0'),('vector','1'),('vector','1 2 3 4 5'),('vector','100 0'),('bearing','1 2 3')]:
        doc=document(actions=[command(kind,args)])
        yield Case('supplement/arity-'+kind+'-'+args.replace(' ','_'),doc).expect('results.0.ok',False)
    for args,vertical in [('2 2','absent'),('2 2 0','mark  0'),('2 2 2 2','absent'),('2 2 0 2 2 0','mark  0')]:
        doc=document([unit(at=[2,2,0])],[command('vector',args)]);case=Case('supplement/vector-'+args.replace(' ','_'),doc).expect('results.0.range',0.0)
        case.expect('results.0.message','mark' if vertical=='absent' else vertical,'excludes' if vertical=='absent' else 'contains');yield case
    for text in ['asc T','asc TTT','wsc','wsc ZZ']:
        doc,u,t=pair();doc['actions']=[hud('key=test'),hud(text)]
        yield Case('supplement/scan-id-'+text.replace(' ','_'),doc).expect('results.1.ok',False).expect('results.1.records',1,'length')
    for command_name in ('scan','report','lrs','tactical'):
        doc,u,t=pair();u['started']=False;doc['actions']=[command(command_name,'t' if command_name=='lrs' else 'TT' if command_name in ('scan','report') else '')]
        yield Case('supplement/offline-'+command_name,doc).expect('results.0.ok',False)
    for form in ('VTOL','VEHICLE-TRACK'):
        doc,u,t=pair();t.update(formed(form));t.update(heat=2.3,speed=21.5,facing=45,turret_facing=270,vertical_speed=-10.75);doc['actions']=[command('report','TT')]
        case=Case('supplement/report-'+form,doc).expect('results.0.report.heat',23.0).expect('results.0.report.turret',dict(facing=315,offset=-90)).expect('results.0.plain','Heat: 23 deg C.','contains')
        if form=='VTOL':case.expect('results.0.plain','Vertical speed: -10.8 KPH','contains')
        yield case
    # Saved truncation and target override are real parser/selection inputs.
    doc,u,t=pair();u['brief']=2;u['display']=dict(contact_options='e'*49+'z');doc['actions']=[command('contacts','+')]
    yield Case('supplement/options-truncate49',doc).expect('results.0.contacts',1,'length').expect('results.0.lines',dict(text='Ignoring',count=0),'count_contains')
    doc,u,t=pair();u.update(brief=2,target=20);t.update(destroyed=True,started=False);doc['actions']=[command('contacts','t')]
    yield Case('supplement/target-category-override',doc).expect('results.0.contacts',1,'length')
    doc,u,t=pair();u['brief']=2;t['name']='a';doc['diagnostic_cache'][0]['target']='a'
    for name,ident,dist in [('b',30,2),('far',40,8),('c',50,2)]:
        doc['units'].append(unit(name,ident,contact_id=name[:2].upper().ljust(2,'X'),at=[50,50+dist,0],team=2));doc['diagnostic_cache'].append(dict(viewer='u',target=name,flags=14))
    doc['actions']=[action('roster-hole'),command('contacts')]
    yield Case('supplement/contact-source-tie-swaps',doc).expect('results.1.contacts.*.name',['far','b','a','c'])
