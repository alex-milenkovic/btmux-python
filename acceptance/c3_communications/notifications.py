from . import step,unit,eq,quiet,inbox
from .displays import view
from .routing import position
from .transmission import stun
from systems import notifications as notice,communications as radio,c3
from entities.mech import MechStatus as S,MechStatus2 as S2,CritStatus as C,Specials
from physics.hexmath import SCALEMAP,ZSCALE,hex_to_float


def passenger(w,ident=900,location=None):
    location=unit(w)._id if location is None else location
    w['store'].create(ident,'Passenger',location=location);actor=w['store'].actor(ident);w['world'].add(actor,location);return actor

def put(u,x,y,z=0):u.x=x;u.y=y;u.z=z;u.fx,u.fy=hex_to_float(x,y);u.fz=z*ZSCALE

@step(r'notification type (\w+) and state (.+)')
def notify_fixture(w,kind,state):
    a=unit(w);w.update(kind=kind,state=state,passenger=passenger(w))
    if 'stopped' in state:a.status&=~S.STARTED
    if 'destroyed' in state:a.status|=S.DESTROYED
    if state=='unconscious':a.status|=S.UNCONSCIOUS
    if state=='blinded':a.status|=S.BLINDED
    if state=='negative-ID':a._id=-1
    if 'pilot-outside' in state:w['world'].move(a.pilot._id,unit(w,'B')._id)
    if 'two-turrets' in state:a.aero_turrets=[unit(w,'B')._id,unit(w,'C')._id];w['engine'].arc_override=int(not state.startswith('no-'))

@step(r'the message hello is emitted')
def notify_run(w):
    a=unit(w)
    w['result']=notice.mech_printf(a,notice.MECHALL,'hello%d',17) if w['kind']=='PRINTF' else notice.mech_notify(a,{'ALL':2,'STARTED':1,'PILOT':0}[w['kind']],'hello')
    w['assert_observation']=notify_result

def notify_result(w,expected):
    a=unit(w);r=w['result'];p=w['passenger'];expected_ids={
        'none':[],'pilot-only':[a.pilot._id],'passenger-only-fallback':[p._id],
        'both-occupants':[a.pilot._id,p._id],'occupants':[a.pilot._id,p._id],
        'unit-contents-only':[a.pilot._id,p._id],'unit-and-both-turret-contents':[a.pilot._id,p._id,unit(w,'B').pilot._id,unit(w,'C').pilot._id],
        'same-gates-and-hello17':[a.pilot._id,p._id]}
    eq(r,expected_ids[expected]);message='hello17' if w['kind']=='PRINTF' else 'hello'
    for actor in (a.pilot,p,unit(w,'B').pilot,unit(w,'C').pilot):eq(getattr(actor,'inbox',[]),[message] if actor._id in r else [])

@step(r'broadcast fixture (.+)')
def broadcast_fixture(w,text):w['fixture']=text

@step(r'map or range broadcast executes')
def broadcast_run(w):
    a,b,c=unit(w),unit(w,'B'),unit(w,'C');s=w['fixture'];w['assert_observation']=broadcast_result
    if s.startswith('map-A'):
        w['map'].mechs_on_map[:]=[a,b];b.status&=~S.STARTED;notice.map_broadcast(w['map'],'hello')
    elif s.startswith('mech-source'):
        target=b if 'target-B' in s else None
        if target:unit(w,'D')
        notice.map_broadcast(w['map'],'hello',a,target)
    elif s.startswith(('2D','3D')):
        w['map'].mechs_on_map[:]=[a]
        position(a,5.01 if '5.01' in s else 0 if 'XY0' in s else 5)
        a.fz=(10 if 'Z10' in s else 6 if 'Z6' in s else 0)*SCALEMAP
        if 'unconscious' in s:a.status|=S.UNCONSCIOUS
        if 'stopped-and-started' in s:position(a,1);a.status&=~S.STARTED;position(b,2);w['map'].mechs_on_map.append(b)
        w['result']=notice.limited_broadcast(w['map'],0,0,0,5,'hello',2 if s.startswith('2D') else 3)
    elif s=='debug-C3-default':w['result']=c3.debug('hello')
    else:raise AssertionError(s)

def broadcast_result(w,expected):
    got=[name for name in w['units'] if inbox(w,name)]
    if expected=='A-only-inbox':eq(got,['A'])
    elif expected=='C,D-inboxes':eq(got,['C','D'])
    elif expected=='B,C-inboxes':eq(got,['B','C'])
    elif expected=='count1-and-delivery':eq(w['result'],1);eq(got,['A'])
    elif expected=='count0':eq(w['result'],0);eq(got,[])
    elif expected=='count1-no-delivery':eq(w['result'],1);eq(got,[])
    elif expected=='count2-one-delivery':eq(w['result'],2);eq(got,['B'])
    elif expected=='no-output-or-external-request':eq(w['result'],None);eq(got,[]);assert all(not getattr(p,'external_effects',[]) for p in w['units'].values())
    else:raise AssertionError(expected)


def visibility_fixture(w,kind):
    a,b,o=unit(w),unit(w,'B'),unit(w,'C');a.name='Atlas';a.contact_id='AB';b.name='Defender';b.contact_id='DE'
    put(a,3,3);put(b,4,3);put(o,3,5)
    for target in (a,b):view(w,o,target,'invisible')
    # A real BAP reads through terrain, but cannot detect active null signature.
    o.sensor=[6,6];o.specials|=Specials.BEAGLE_PROBE_TECH
    if kind in ('target-only','neither'):a.status2|=S2.NULLSIGSYS_ON
    if kind in ('attacker-only','neither'):b.status2|=S2.NULLSIGSYS_ON
    if kind=='something':w['map'].set_elevation(3,4,5)
    return a,b,o

@step(r'broadcast state (.+)')
def los_fixture(w,text):w['state']=text

@step(r'the source broadcast executes')
def los_run(w):
    s=w['state'];w['assert_observation']=los_result
    if s.startswith('hex'):
        a=unit(w);w['map'].mechs_on_map[:]=[a];put(a,3,3)
        x,y=(3,4) if 'other' in s or 'height' in s else (3,3)
        if 'height3' in s:w['map'].set_elevation(x,y,3);put(a,3,3,4)
        message='$q end$' if 'unknown' in s else '$H' if s.endswith('-H') else '$h'
        quiet(w,notice.hex_broadcast,w['map'],x,y,message)
        w['observer']='A';return
    kind='neither' if 'unseen' in s and 'NB' not in s or 'neither' in s else 'attacker-only' if 'only-attacker' in s else 'target-only' if 'only-target' in s else 'something' if 'NB-unseen' in s else 'both'
    a,b,o=visibility_fixture(w,kind);w['observer']='C'
    if 'enemy' in s:o.team=2
    if s.startswith('single'):
        from systems.sensors import los_broadcast
        quiet(w,los_broadcast,a,"'s arm" if 'apostrophe' in s else 'moves')
    else:quiet(w,notice.pair_los_broadcast,a,b,'hits %s')

def los_result(w,expected):
    messages=inbox(w,w['observer'])
    if expected=='no-delivery':eq(messages,[]);return
    expected_text={'attacker-ID-and-someone':'Atlas [ab] hits someone','Someone-and-target-ID':'Someone hits Defender [de]',
                   'both-observer-specific-IDs':'Atlas [ab] hits Defender [de]',
                   'unknown-dollar-q-retained-terminal-dollar-removed':'$q end','sight-uses-Elevation-times-ZSCALE':'3,4'}.get(expected,expected)
    eq(messages,[expected_text])
    if expected=='sight-uses-Elevation-times-ZSCALE':
        from systems.targeting import find_range
        from systems.los import in_line_of_sight
        a=unit(w);fx,fy=hex_to_float(3,4);distance=find_range(a.fx,a.fy,a.fz,fx,fy,3*ZSCALE)
        eq(notice.sees_hex(a,w['map'],3,4),in_line_of_sight(a,None,3,4,distance))

@step(r'ordinary firing fixture (.+)')
def shot_fixture(w,text):
    w['fixture']=text
    kind='neither' if 'neither' in text else 'target-only' if 'defender-only' in text else 'attacker-only' if 'attacker-only' in text else 'both'
    a,b,o=visibility_fixture(w,kind)
    if 'unconscious' in text:o.status|=S.UNCONSCIOUS
    # Real installed weapon and target lock are consumed by the public firing function.
    from entities.mech import WeaponState,Location
    from entities.weapon import get_weapon
    weapon=get_weapon('IS.MediumLaser');a.weapons=[WeaponState(section=Location.LARM,critical=0,weapon_idx=weapon.index)]
    for i in range(3):a.sections[Location.LARM].criticals[i].type=weapon.index+1
    a.target=b._id;a.targ_x=b.x;a.targ_y=b.y
    from physics.hexmath import find_bearing
    a.facing=find_bearing(a.fx,a.fy,b.fx,b.fy)
    a.desired_facing=a.facing
    if text.startswith('hex'):
        a.target=-1;a.status|=S.LOCK_HEX;o.sensor=[0,0]
        if 'defender-only' in text:
            w['map'].cloudbase=10;put(a,3,3,20)
    from systems.characters import set_value
    for skill,value in [('Reflexes',5),('Intuition',5),('Gunnery-Battlemech',4),('Gunnery-Laser',4)]:set_value(w['store'],a.pilot._id,skill,value)
    w['before']=a.shots_hit

@step(r'one shot resolves')
def shot_run(w):
    from systems.combat import fire_weapon_number
    a,b=unit(w),unit(w,'B');target=(str(b.x),str(b.y)) if w['fixture'].startswith('hex') else b
    w['result']=quiet(w,fire_weapon_number,w['engine'],a,0,target,to_hit_roll=2 if 'miss' in w['fixture'] else 12)
    assert w['result'].bth_breakdown is not None,w['result'].messages
    w['assert_observation']=shot_result

def shot_result(w,expected):
    a=unit(w);messages=inbox(w,'C')
    if expected.startswith('no-observer'):eq(messages,[])
    else:
        match={'observer-hits-text-hit-counter-plus1':'Atlas [ab] hits Defender [de] with a MediumLaser',
               'Something-misses-target-ID':'Something misses Defender [de] with a MediumLaser',
               'attacker-fires-at-something':'Atlas [ab] fires a MediumLaser at something!',
               'attacker-fires-at-hex-no-shot-counter':'Atlas [ab] fires a MediumLaser at hex 4 3!',
               'Something-fires-at-hex':'Something fires a MediumLaser at hex 4 3!'}[expected]
        assert match in messages,(match,messages)
    if 'hit-counter-plus1' in expected:eq(a.shots_hit,w['before']+1)
    if 'no-shot-counter' in expected:eq(a.shots_hit,w['before'])

@step(r'flag-controlled common check state (.+)')
def common_fixture(w,state):
    a=unit(w);w['state']=state;w['actor']=a.pilot
    w['flags']=radio.MECH_USUALO if 'USUALO' in state else radio.MECH_USUALS if 'USUALS' in state else radio.MECH_USUAL if 'USUAL' in state else 0
    if state=='null-unit':w['flags']=radio.MECH_USUAL
    if 'destroyed' in state:a.status|=S.DESTROYED
    if 'stopped' in state:a.status&=~S.STARTED
    if 'blinded' in state:a.status|=S.BLINDED
    if 'unconscious' in state:a.status|=S.UNCONSCIOUS
    if 'passenger' in state or 'nonpilot' in state:w['actor']=passenger(w)
    if '-wizard-' in state:w['actor'].wizard=True
    if state.startswith('OOC'):a.in_character=False
    if state.startswith('negative-map'):a.mapindex=-1
    if state.startswith('unresolved'):a.map=None;a.mapindex=2345
    if 'last-use99' in state:a.last_use=99

@step(r'the source command eligibility check runs')
def common_run(w):
    before=len(getattr(w['actor'],'inbox',[]))
    w['result']=radio.common_checks(None if w['state']=='null-unit' else unit(w),w['actor'],w['flags'])
    w['common_messages']=getattr(w['actor'],'inbox',[])[before:]
    w['assert_observation']=common_result

def common_result(w,expected):
    r=w['result']
    if expected.startswith('eligible'):eq(r,None)
    elif expected=='rejected':
        eq(r,'');eq(w['common_messages'],[])
    elif expected=='invalid-map-shutdown-reset-minus1':
        eq(r,'')
        eq(w['common_messages'],['You are on an invalid map! Map index reset!','Mech has been shutdown!'])
        eq(unit(w).mapindex,-1);eq(unit(w).is_started,False)
    else:assert {'destroyed-error':'destroyed','reactor-error':'Reactor','blinded-error':'blinded','unconscious-error':'unconscious','pilot-only-error':'only the pilot','no-map-error':'no map'}[expected] in r,r
    if 'last-use0' in expected:eq(unit(w).last_use,0)
