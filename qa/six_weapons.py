"""Physical arcs, ordinary cooldown, aim commands and live BTH readouts."""
from six_support import *

ARC_POS={'front':[10,6,10],'left':[6,10,10],'right':[14,10,10],'rear':[10,14,10]}

def pair(section=0,at=None,rear=False,weapon='IS.MediumLaser'):
    u=fighter(contact_id='AA',pilot_details=dict(gunnery=0),weapons=[dict(name=weapon,section=section,fire_mode=32 if rear else 0)])
    target=fighter(name='target',id=20,contact_id='BB',team=2,at=at or [10,9,10])
    return session(u,units=[u,target])

def weapons():
    for name,row in rows('weapons',1):
        section=NAMES.index(row['section'].replace('_',' '));rear=row['mount']=='rear'
        allowed=row['arcs'].split('-')
        for arc,at in ARC_POS.items():
            ok=arc in allowed;d=pair(section,at,rear);d['actions']=[cmd('sight','0 BB'),cmd('fire','0 BB')]
            c=Case(name+'/'+arc,d).result(accepted=ok).result(1,accepted=ok)
            c.expect('state.units.u.sections.'+str(section)+'.slots.0.data',0,'greater' if ok else 'equal').final(shots_fired=int(ok),weap_heat=3 if ok else 0)
            if ok:c.expect('results.1.attack.hit',True)
            else:drawcheck(c,'attack_rolls',[])
            yield c
    for name,row in rows('weapons',2):
        f=row['fixture'];d=pair(1);u=d['units'][0];u['sections'][1]['armor']=3 if f=='armor0-functional-ready-valid-arc' else 15 if f.startswith('armor-positive') else 0
        if 'recycle5' in f:
            u['sections'][1]['slots']=[dict(index=0,data=5)];d['actions']=[advance(5),inspect()]
            c=Case(name,d).expect('state.units.u.sections.1.slots.0.data',0 if f.startswith('armor-positive') else 5)
            if f.startswith('armor-positive'):
                d['actions'].append(cmd('fire','0 BB'));c.checks.clear()
                c.expect('results.1.units.u.sections.1.slots.0.data',0).result(2,accepted=True).final(shots_fired=1)
        else:
            destroyed='destroyed' in f;u['sections'][1]['slots']=[dict(index=0,firemode=int(destroyed))]
            d['actions']=([damage(1,3)] if not destroyed else [])+[cmd('fire','0 BB'),inspect(),advance(30),inspect()]
            ix=0 if destroyed else 1;c=Case(name,d).result(ix,accepted=not destroyed)
            if not destroyed:
                c.expect('results.2.units.u.sections.1.slots.0.data',0,'greater').expect('state.units.u.sections.1.slots.0.data',0,'greater').expect('state.units.u.weapons.0.usable',False)
            else:c.final(shots_fired=0,weap_heat=0)
        yield c
    for name,row in rows('weapons',3):
        loc=int(row['index']);d=pair();d['units'][1].update(started=False,facing=0)
        d['actions']=[cmd('lock','BB'),cmd('aim',row['location']),dd('aim-location',target='target')]
        yield Case(name,d).result(accepted=True).result(1,accepted=True).expect('results.2',[loc,True,False]).final(aim=loc,aim_type=5)
    for name,row in rows('weapons',4):
        loc=NAMES.index(row['aim'].replace('_',' '));side=row['side'];facing={'FRONT':180,'BACK':0,'LEFTSIDE':270,'RIGHTSIDE':90}[side]
        d=pair();d['units'][1]['facing']=facing;d['actions']=[cmd('lock','BB'),cmd('aim',row['aim']),dd('tc-location',target='target')]
        yield drawcheck(Case(name,d).result(accepted=True).result(1,accepted=True).expect('results.2',[NAMES.index(row['location'].replace('_',' ')),side=='BACK',False]),'tc_location',[3],1,6)
    for name,row in rows('weapons',5):
        mismatch=row['fixture']=='mismatched-type';d=pair();d['units'][1]['facing']=180;d['actions']=[cmd('lock','BB'),cmd('aim','Engine')]
        if mismatch:d['actions'].append(op('configure',unit='u',values=dict(aim_type=0)))
        d['actions'].append(dd('tc-location',target='target'));d['random']['streams']['tc_location']=[2]
        yield drawcheck(Case(name,d).expect('results.'+str(len(d['actions'])-1),[0,False,False]),'tc_location',[] if mismatch else [2],1,6)
    for name,row in rows('weapons',6):
        missile=row['weapon']=='Missile';d=pair(weapon='IS.SRM-2' if missile else 'IS.MediumLaser');u,target=d['units'];target['started']=row['mobility']=='mobile'
        if row['tc']=='on':
            u['sections'][0]['slots']=[dict(index=0,firemode=16)];u['sections'][3]['slots']=[dict(index=0,special='TARGETING_COMPUTER')]
        d['actions']=[cmd('lock','BB'),cmd('aim',row['aim']),cmd('sight','0 BB')]
        c=Case(name,d).result(accepted=True).result(1,accepted=True).expect('results.2.attack.bth_breakdown.aim_mod',int(row['modifier']))
        # SIGHT reports impossible aim totals without attempting a damaging shot.
        c.final(shots_fired=0,weap_heat=0);yield c
