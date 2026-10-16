"""Source status selection, equipment rendering and heat feature rows."""
from hud_displays_common import *
from hud_displays_equipment import slot_state


def status():
    for name,n,row,meta in examples('status'):
        doc=document(actions=[command('status','W')]);u=doc['units'][0];case=Case(name,doc,meta)
        if n==1:
            doc['actions']=[command('status','' if row['argument']=='no-argument' else row['argument'])]
            case.expect('results.0.components',row['components'].split(','))
        elif n==2:
            slot=slot_state(row['state'],row['ticks'])
            if row['state']=='damaged-slot':slot['firemode']=8
            u['sections']=[dict(index=0,slots=[slot])];case.expect('results.0.weapons.0.status',row['text'])
        elif n in (3,4):
            amount=int(row.get('amount',0))
            # IS.MachineGun holds 200 rounds per ton: half-ton gives 100.
            u['sections']=[dict(index=2,slots=[dict(index=0,ammo='IS.MachineGun',data=amount,firemode=128)])]
            if n==4:
                case.expect('results.0.ammunition',[])
                doc['actions'].append(action('display_diagnostic',kind='ammo_color',values=dict(current=0,maximum=100)))
                case.expect('results.1.color','%ch%cr')
            else:
                case.expect('results.0.ammunition.0.current',amount).expect('results.0.ammunition.0.maximum',100)
                case.expect('results.0.ammunition.0.color',{'bright-green':'%ch%cg','bright-yellow':'%ch%cy','bright-red':'%ch%cr'}[row['color']])
                case.expect('results.0.plain','||','contains')
        elif n==5:
            slot=slot_state(row['state'])
            if row['state']=='damaged-weapon':slot['firemode']=8
            u['sections']=[dict(index=0,slots=[slot])];doc['actions']=[command('critstatus','LARM')]
            case.expect('results.0.slots.*.number',[1,7,2,8,3,9,4,10,5,11,6,12]).expect('results.0.slots.0.suffix','' if row['suffix']=='absent' else row['suffix'])
        elif n==6:
            if row['types']!='none':
                u['weapons']=[dict(section=0,critical=4+i*2,name='IS.'+('SRM-6' if weapon=='SRM6' else weapon)) for i,weapon in enumerate(row['types'].split(','))]
            doc['actions']=[command('weaponspecs')]
            if row['result']=='You have no weapons!':case.expect('results.0.ok',False).expect('results.0.message',row['result'])
            else:case.expect('results.0.weapons.*.name',['IS.'+('SRM-6' if w=='SRM6' else w) for w in row['result'].split(',')])
        elif n==7:
            u.update(tonnage=60,real_mass=60,sections=[dict(index=0,slots=[dict(index=4+i,special='SWORD',firemode=1) for i in range(int(row['slots']))])])
            case.expect('results.0.physical.*.name','Sword[LA]','contains' if row['present']=='true' else 'excludes')
        else:
            u.update(plus_heat=5,minus_heat=int(row['minus']));doc['actions']=[command('status','H')]
            case.expect('results.0.heat_scale.start',int(row['start'])).expect('results.0.heat_scale.indicator',' ' if row['indicator']=='space' else '<')
        yield case
