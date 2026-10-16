"""Every historical table row and critical gate using real equipment effects."""
from six_support import *

def equipped():
    u=fighter(weapons=[dict(name='IS.MediumLaser',section=i,critical=j) for i in (0,1,2) for j in (0,1)])
    for s in u['sections'][:6]:s.update(armor=80,armor_orig=100)
    for loc in (3,5):u['sections'][loc]['slots']=[dict(index=0,special='HEAT_SINK'),dict(index=1,special='HEAT_SINK')]
    u['sections'][3]['slots'].append(dict(index=11,type=387))
    u['core']['carried_cargo']=1020
    return u

def tables():
    for outline,profiles in [(1,('legacy','FASA')),(2,('critproof',))]:
        for name,row in rows('locations',outline):
            for profile in profiles:
                u=equipped();loc=NAMES.index(row['location'].replace('_',' '));effect=row.get('effect','none') if profile!='critproof' else 'none'
                d=session(u,[op('clock',name='skip_seconds',seconds=7),dd('location',side=row['side'],roll=int(row['roll']),profile=profile)])
                c=Case(name+'/'+profile,d).expect('results.1',[loc,effect.startswith('deferred')])
                c.final(carried_cargo=1020,real_num_sinks=23 if effect.startswith('sink') else 25,**{'aerospace.spinning':effect=='control','aerospace.start_spin':7 if effect=='control' else 0})
                for i in (0,1,2):
                    c.expect(f'state.units.u.sections.{i}.slots.0.firemode',int(effect.startswith('weapon') and i==loc)).expect(f'state.units.u.sections.{i}.slots.1.firemode',0)
                for i in (3,5):c.expect(f'state.units.u.sections.{i}.slots.0.firemode',int(effect.startswith('sink') and i==loc))
                c.expect('state.units.u.sections.3.slots.11.type',387).expect('state.events',['ARTILLERY_HIT',0],'event_count')
                drawcheck(c,'crittable_chance',[]);drawcheck(c,'critical_rolls',[])
                drawcheck(c,'fighter_weapon_choice',[0] if effect.startswith('weapon') else [])
                yield c
    for name,row in rows('locations',3):
        config=row['configuration'];u=equipped();u['specials']=0x40000000 if 'critproof' in config else 0
        d=session(u,[dd('location',side='FRONT')]);d['config']['fasacrit']=int('on' in config);d['random']['streams']['hit_location_rolls']=[4,9]
        delegated='on' in config or 'critproof' in config
        yield drawcheck(Case(name,d).expect('results.0',[1 if delegated else 3,False]),'hit_location_rolls',[4,9] if delegated else [4],2,12)

def gates():
    for name,row in rows('criticals',1):
        armor,original,threshold,chance=[int(row[k]) for k in ('armor','original','threshold','chance')];u=fighter();u['sections'][0].update(armor=armor,armor_orig=original)
        d=session(u,[dd('crittable',section=0,threshold=threshold)]);d['random']['streams']['crittable_chance']=[chance]
        c=Case(name,d).expect('results.0',row['result']=='true')
        drawcheck(c,'crittable_chance',[] if row['draw']=='none' else [chance],1,71 if row['draw']=='1..71' else 11)
        yield c
    for outline in (2,3):
        for name,row in rows('criticals',outline):
            u=fighter();u['sections'][0].update(armor=0,armor_orig=0 if outline==2 else 100);f=row['overrides']
            if f=='critproof':u['specials']=0x40000000
            if f=='Move_NONE':u['movement']='NONE'
            d=session(u,[dd('crittable',section=0,threshold=90)])
            if f.startswith('vcrit'):d['config']['vcrit']=int(f[-1])
            yield drawcheck(Case(name,d).expect('results.0',outline==2 and f.startswith('vcrit')),'crittable_chance',[])
