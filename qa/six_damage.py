"""Armor exhaustion, routing and shared pilot/engine consequences via CLI."""
from six_support import *

def invariant(c):
    for i in range(6):
        for key in ('internal','internal_orig'):c.expect(f'state.units.u.sections.{i}.{key}',10)
    return c

def damages():
    for outline in (1,2):
        for name,row in rows('damage',outline):
            loc=NAMES.index(row['section'].replace('_',' '));u=fighter();u['sections'][loc]['armor']=int(row.get('armor',0));u['sections'][3]['armor']=int(row['fuselage'])
            amount=int(row['damage']);d=session(u,[damage(loc,amount)]);c=invariant(Case(name,d))
            c.expect('state.units.u.sections.3.armor',int(row['fuselage_after'] if outline==1 else row['after']))
            if outline==1:c.expect(f'state.units.u.sections.{loc}.armor',int(row['after']))
            c.final(destroyed=row['result']=='destroyed',pilot_hits=1 if outline==1 and loc==4 else 0)
            if outline==1 and loc==5:c.final(speed=0,max_speed=0,vertical_speed=0,fallen=True).expect('state.events',['FALL',1],'event_count')
            if outline==2 and loc in (4,5):c.final(max_speed=60,fallen=False).expect('state.events',['FALL',0],'event_count')
            yield c
    for name,row in rows('damage',3):
        f=row['fixture'];u=fighter();actions=[];loc=0;amount=8;options={};nose=3;body=30
        if 'Right_Wing' in f or 'Left_Wing' in f:
            loc=2 if 'Right_Wing' in f else 1;amount=5;options['rear']=True;nose=24;body=25 if loc==2 else 30
        elif f.startswith('Fuselage3'):
            loc=3;u['sections'][3]['armor']=3;options['transfer']=True;nose=24;body=0
        elif f.startswith('empty-Fuselage'):
            loc=3;u['sections'][3]['armor']=0;u['si']=50;amount=1;nose=24;body=0
        elif f.startswith('all-positive'):
            amount=0;nose=24
        elif f.startswith('Engine0'):
            loc=5;u['sections'][5]['armor']=0;u['sections'][3]['slots']=[dict(index=0,special='HEAT_SINK')];amount=1;options.update(critical=True,rear=True);nose=24;body=29
        else:
            u['sections'][0]['armor']=3
            options.update(internal='internal-only' in f,transfer='transfer-enabled' in f or 'explicit-transfer' in f or 'CASE' in f)
            if 'CASE' in f:u['sections'][0]['config']=1
            body=25 if options['transfer'] and 'CASE' not in f else 30;nose=0
        actions=[damage(loc,amount,**options)] if amount else [inspect()]
        d=session(u,actions);d['random']['streams']['critical_rolls']=[8]
        c=invariant(Case(name,d)).expect('state.units.u.sections.0.armor',nose).expect('state.units.u.sections.3.armor',body)
        c.final(destroyed=f.startswith(('Fuselage3','empty-Fuselage')))
        if 'Wing' in f:c.expect('state.units.u.sections.2.armor',15).expect('state.units.u.sections.1.armor',10 if loc==1 else 15)
        if f.startswith('Engine0'):c.expect('state.units.u.sections.3.slots.0.firemode',1).final(fallen=False,max_speed=60).expect('state.events',['FALL',0],'event_count')
        yield c
    for name,row in rows('damage',4):
        airborne=row['flight']=='airborne';u=fighter(at=[10,10,10 if airborne else 0],aerospace=dict(landed=not airborne,speed=40,vertical_speed=5));u['sections'][5]['armor']=3
        c=invariant(Case(name,session(u,[damage(5,3)]))).final(speed=0,max_speed=0,vertical_speed=0,fallen=True)
        c.expect('state.events',['FALL',int(airborne)],'event_count').text('state.units.u.messages','You feel the thrust die..' if airborne else 'The computer reports engine destroyed!')
        yield c
    for name,row in rows('damage',5):
        loc=NAMES.index(row['section'].replace('_',' '));u=fighter(weapons=[dict(name='IS.MediumLaser',section=loc)]);u['sections'][loc]['armor']=3
        yield invariant(Case(name,session(u,[damage(loc,8)]))).expect(f'state.units.u.sections.{loc}.armor',0).expect(f'state.units.u.sections.{loc}.slots.0.firemode',0).expect('state.units.u.weapons.0.usable',True)
    for loc in (1,3):
        u=fighter(si=50);u['sections'][loc]['armor']=3
        c=Case('procedures/two-hit-'+NAMES[loc],session(u,[damage(loc,8),inspect(),damage(loc,8 if loc==1 else 1)]))
        c.expect('results.1.units.u.destroyed',False).expect('results.1.units.u.sections.3.armor',30 if loc==1 else 0).expect('state.units.u.sections.3.armor',22 if loc==1 else 0).final(destroyed=loc==3)
        yield invariant(c)
    # The historical FALL callback accelerates only when power is unavailable.
    for fuel in (1000,0):
        u=fighter(started=bool(fuel),core=dict(fuel=fuel));u['sections'][5]['armor']=3
        actions=[damage(5,3),advance(2),inspect(),advance(1),inspect(),advance(3)]
        c=Case('procedures/engine-fall-fuel'+str(fuel),session(u,actions)).expect('results.2.units.u.at.2',10).expect('results.4.units.u.at.2',10 if fuel else 8).expect('results.4.events',dict(kind='FALL',deadline=6,data2=0 if fuel else -2),'has_record').expect('state.events',['FALL',0 if fuel else 1],'event_count')
        yield c
