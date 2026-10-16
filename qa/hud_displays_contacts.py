"""Independent contact/scan fixtures and source field-order assertions."""
from hud_displays_common import *
import struct


def f32(value):return struct.unpack('f',struct.pack('f',value))[0]


def pair(distance=2,nb=True):
    u=unit();u['at']=[50,50,0]
    target=unit('target',20,team=2);target['at']=[50,50+int(distance),0]
    target['real']=[f32(152*93.097730906827152),f32(161.25+322.5*(50+distance)),0]
    doc=document([u,target]);doc['diagnostic_cache']=[dict(viewer='u',target='target',flags=14 if nb else 32782)]
    return doc,u,target


def building(doc,xy=(50,53),flags=0):
    doc['map']['map_objects']=[dict(kind='BUILDING',x=xy[0],y=xy[1],obj=2000)]
    doc['map'].setdefault('name','outside')
    doc['maps']=[doc.pop('map'),dict(name='building',id=2000,size=[8,8],cf=75,cfmax=100,buildflag=flags,
        map_objects=[dict(kind='ENTRA',x=2,y=2,datac=ord('n'))])]


def contacts():
    for name,n,row,meta in examples('contacts'):
        doc,u,t=pair();case=Case(name,doc,meta)
        if n==1:
            u['brief']=int(row['brief']);t['name']='near';t['team']=0
            far=unit('far',30,team=2);far.update(contact_id='FF',at=[50,58,0])
            wreck=unit('wreck',40,team=2,destroyed=True);wreck.update(contact_id='WW',at=[50,51,0])
            doc['units'] += [far,wreck];doc['diagnostic_cache']=[dict(viewer='u',target=v,flags=14) for v in ('near','far','wreck')]
            building(doc);doc['actions']=[command('contacts','' if row['filter']=='no-argument' else row['filter'])]
            case.expect('results.0.contacts.*.name',row['names'].split(',')).expect('results.0.heading',row['framing']=='true')
        elif n==2:
            u['brief']=1;u['crit_status']=0x01000000 if row['spin']=='true' else 0
            states=row['states'];t['started']=not states.startswith('offline');t['core']={}
            if 'swarming' in states:t.update(swarm_target='u',carrying=10);t['status']=8|32|64|128|0x4000;t['status2']=0x20;t['heat']=2;t['crit_status']=0x400000;t['sections']=[dict(index=0,specials=1)]
            if 'lit-hulldown' in states:t.update(crit_status=0x800,hulldown=True,status2=2)
            if 'staggering' in states:t['core']['stagger_damage']=20
            if 'target-spinning' in states:t['crit_status']=0x01000000
            if 'starting' in states:doc['actions'].append(action('schedule',unit='target',callback='mech_startup_event',delay=10,data=1))
            index=len(doc['actions']);doc['actions'].append(command('contacts'))
            case.expect(f'results.{index}.contacts.0.status',row['chars'].replace('_',' '))
        elif n==3:
            t.update(team=0,contact_id='AB',heat=2);t['display']=dict(template_name='LongVisibleName')
            # Actual names are fixture object names, not template labels.
            t['name']='LongVisibleName';doc['diagnostic_cache'][0].update(target=t['name'],flags=14 if row['nb']=='true' else 32782)
            u['brief']=1;doc['actions']=[command('contacts','h')]
            case.expect('results.0.lines.1|0','#HUDINFO:CON#'+row['relation']).expect('results.0.lines.1|4',row['id']).expect('results.0.lines.1|6',row['name'].ljust(12)).expect('results.0.lines.1|14',row['status'].replace('_',' '))
            for col,val in [(1,'P'),(2,'S'),(3,'v'),(5,'B')]:case.expect(f'results.0.lines.1|{col}',val)
        else:
            t['name']='enemy';wreck=unit('wreck',30,destroyed=True,team=2);wreck.update(contact_id='WW',at=[50,51,0]);doc['units'].append(wreck)
            doc['diagnostic_cache']=[dict(viewer='u',target=v,flags=14) for v in ('enemy','wreck')]
            if row['saved']!='unset':u['display']=dict(contact_options=row['saved'])
            doc['actions']=[command('contacts','+')]
            case.expect('results.0.contacts.*.name',row['names'].split(','))
            case.expect('results.0.lines',dict(text='Ignoring ',count=int(row['warnings'])),'count_contains')
        yield case


def hud_contacts():
    for name,n,row,meta in examples('hud_contacts'):
        doc,u,t=pair(float(row.get('range',2)),row.get('nb','true')=='true');doc['actions']=[hud('key=test')];case=Case(name,doc,meta)
        if n==1:
            t.update(name='Atlas',heat=2);doc['diagnostic_cache'][0]['target']='Atlas';doc['actions'].append(hud('c'))
            case.expect('results.1.records.0.payload|4',row['name']).expect('results.1.records.0.payload|17','2').expect('results.1.records.0.payload|18','+','contains')
            case.expect('results.1.records.0.payload',r'^(?:[^,]*,){18}[^,]*$','regex')
        elif n==2:
            flags={'primary':10,'secondary':12,'both':14,'none':8}[row['sensors']];doc['diagnostic_cache'][0]['flags']=flags
            if row['arcs']=='forward-turret':u.update({'class':'VEH_GROUND','movement':'TRACK','facing':180})
            elif row['arcs']=='left-rear':u.update(facing=300,status=8|4)
            elif row['arcs']=='right':u['facing']=90
            doc['actions'].append(hud('c'))
            if row['sensor_text']=='omitted':case.expect('results.1.records',1,'length')
            elif row['arcs']=='left-rear':
                # Explicit formatter fixture; real geometry still returns only left.
                case.meta.update(diagnostic=True)
                case.expect('results.1.records.0.payload|1','l').expect('results.1.records.0.payload|2',row['sensor_text'])
                doc['actions'] += [action('inspect'),action('display_diagnostic',kind='arc_string',values=dict(mask=10)),action('inspect')]
                case.expect('results.3.text',row['arc_text']).expect('results.3.diagnostic',True).expect('results.4','results.2','same')
            else:case.expect('results.1.records.0.payload|1',row['arc_text']).expect('results.1.records.0.payload|2',row['sensor_text'])
        elif n==3:
            doc['units']=[u];building(doc,flags=(16 if row['invisible']=='true' else 0)|(4 if row['hidden']=='true' else 0)|(8 if row['safe']=='true' else 0)|(1 if row['cs']=='true' else 0))
            doc.pop('diagnostic_cache');doc['actions'].append(action('bay_configure',map='building',values=dict(enter_lock='false' if row['locked']=='true' else 'true')))
            if row['los']=='blocked':doc['maps'][0]['hexes']=[dict(at=[50,51],terrain='MOUNTAINS',elevation=9)]
            doc['actions'].append(hud('cb'))
            if row['result']=='omitted':case.expect('results.2.records',1,'length')
            else:case.expect('results.2.records.0.payload|9',row['result'])
        else:
            u['scan_range']=20;u['observer']=row.get('observer')=='true'
            if row.get('form')=='MW':t.update(formed('MW'))
            if n==5:
                t['sections']=[dict(index=0,armor=int(row['current']),armor_orig=99,internal=10,internal_orig=10,slots=[dict(index=4,weapon='IS.MediumLaser',data=int(row['ticks']))])]
            doc['actions'] += [hud('asc TT'),hud('wsc TT'),action('inspect')]
            if row.get('outcome','list')=='list':
                for i in (1,2):case.expect(f'results.{i}.ok',True).expect(f'results.{i}.records.-1.type','D')
                if n==5:case.expect('results.1.records.0.payload|1',row['armor']).expect('results.2.records.0.payload|3',row['weapon'])
            else:
                for i,cls in [(1,'ASC'),(2,'WSC')]:record(case,i,cls,'E',row['outcome'])
            expected=int(row.get('notices','1'))*2
            case.expect('state.units.target.messages',dict(text='You are being scanned',count=expected),'count_contains')
        yield case
