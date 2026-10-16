import math,re
from . import step,unit,eq,quiet
from .displays import view
from systems import c3
from entities.mech import MechStatus as S,CritStatus as C,Specials
from physics.hexmath import SCALEMAP,ZSCALE,hex_to_float,find_bearing
from systems.targeting import fa_mech_range,find_range


def join(w,peer,ordinary=True):
    result=c3.command(peer,peer.pilot,'join',unit(w).contact_id,ordinary)
    assert result['ok'],result

@step(r'real range (\d+) and ordered peer observations (.+)')
def range_fixture(w,real,text):
    a=unit(w);t=unit(w,'target');w['target']=t;w['real']=float(real)
    for entry in text.split(';'):
        name,description=entry.split(':');p=unit(w,name);join(w,p)
        distance=float(description.split('-')[0]);p.fx=a.fx+(float(real)-distance)*SCALEMAP;p.fy=a.fy;p.fz=a.fz
        view(w,p,t,'invisible' if 'invisible' in description else 'something' if 'something' in description else 'clear')
        if 'unconscious' in description:p.status|=S.UNCONSCIOUS
        if 'stopped' in description:p.status&=~S.STARTED
        if 'AngelECM' in description:p.status2|=0x800
    t.fx=a.fx+float(real)*SCALEMAP;t.fy=a.fy;t.fz=a.fz

@step(r'C3 shared range is queried')
def query(w):w['result']=c3.range_query(unit(w),w['target'],w['real'])

@step(r'range and source are (.+)')
def result(w,text):
    distance,name=text.split(',');actual,ref=w['result'];assert math.isclose(actual,float(distance),abs_tol=1e-6),(actual,distance)
    eq(ref,int(name) if name.isdigit() else unit(w,name)._id)

@step(r'range request state (.+)')
def request(w,state):
    w['state']=state;a,b=unit(w),unit(w,'B');w['ordinary']='C3i' not in state
    if not state.startswith('empty'):join(w,b,w['ordinary'])
    if 'destroyed' in state:a.crit_status|=C.C3_DESTROYED if w['ordinary'] else C.C3I_DESTROYED
    if 'owner-ECM' in state:a.status2|=4
    if state.startswith('hex'):
        a.targ_x,a.targ_y=map(int,re.findall(r'[XY](\d+)',state));a.targ_z=-1
        if 'height3' in state:w['map'].set_elevation(a.targ_x,a.targ_y,3)
        b.x,b.y=a.targ_x,a.targ_y;b.fx,b.fy=hex_to_float(b.x,b.y);b.z=4;b.fz=4*ZSCALE

@step(r'the source range function executes')
def request_run(w):
    w['result']=quiet(w,c3.range_query,unit(w),None,12,w['ordinary'],77)
    w['assert_observation']=request_result

def request_result(w,text):
    a,b=unit(w),unit(w,'B');distance,ref=w['result']
    if text=='targetZ3-and-elevated-NB-peer-range':
        eq(a.targ_z,3);eq(ref,b._id);assert math.isclose(distance,find_range(b.fx,b.fy,b.fz,b.fx,b.fy,3*ZSCALE)),distance
    else:
        eq(distance,12);eq(ref,77 if 'ref77' in text else 0)
        if text.endswith('stored-unchanged'):eq(c3.network_size(a,w['ordinary']),1);eq(c3.network_size(b,w['ordinary']),1)
        elif text.endswith('reciprocal-clear'):eq(c3.network_size(a,False),0);eq(c3.network_size(b,False),0)

@step(r'ordered peer LOS and NB results (.+)')
def views(w,text):
    t=unit(w,'T');w['target']=t
    if text=='none':return
    for i,kind in enumerate(text.split(',')):
        p=t if kind=='target-self' else unit(w,chr(66+i));join(w,p)
        if kind.startswith('unconscious'):p.status|=S.UNCONSCIOUS
        view(w,p,t,'clear' if kind in ('clear','unconscious-clear') else kind)

@step(r'network visibility is requested')
def views_run(w):w['result']=c3.seen_by_network(unit(w),w['target'])

@step(r'visibility code is (\d+)')
def views_result(w,code):eq(w['result'],int(code))

@step(r'combat condition (.+)')
def combat_fixture(w,condition):
    from tools.combat_resolution import CombatSession
    weapon='IS.LRM-5' if 'LRM' in condition else 'IS.MediumLaser'
    s=CombatSession({'config':{'periodic_updates':False},'actions':[],'units':[
        {'name':'u','at':[3,3,0],'weapons':[{'name':weapon,'section':'LA'}],'ammo':[{'weapon':weapon,'rounds':10}] if 'LRM' in condition else []},
        {'name':'v','at':[3,2,0],'team':2},{'name':'b','at':[3,3,0]},{'name':'c','at':[3,3,0]}]})
    a,t,b,d=[s.units[n] for n in ('u','v','b','c')]
    s.map._id=1000;s.engine.register_entity(s.map)
    for p in s.units.values():p.mapindex=1000
    s.acquire_contacts()
    for p in (a,b,d):p.specials|=Specials.C3_SLAVE_TECH;p.specials2|=32;p.working_c3_masters=1 if p is a else 0
    joined=c3.command(b,b.pilot,'join',a.contact_id);assert joined['ok'],joined
    real=12 if 'real12' in condition else 5.5 if 'LRM' in condition else 8
    peer=4 if 'peer4' in condition else 2
    if condition.startswith('both'):
        assert c3.command(d,d.pilot,'join',a.contact_id,False)['ok'];peer=4
    # North of the shooter, within the real forward weapon arc.
    for p,distance in ((t,real),(b,real-peer),(d,real-2)):
        p.fx=a.fx;p.fy=a.fy-distance*SCALEMAP;p.fz=a.fz
    from systems.los import MECHLOSFLAG_SEESP,MECHLOSFLAG_SEESS
    for observer in (a,b,d):s.map.losinfo[observer._id,t._id]=MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS
    if 'shutdown' in condition:
        from systems.startup import shutdown
        s.invoke(shutdown,s.engine,b,caller=b.pilot)
    if 'owner-ECM' in condition:a.status2|=4
    w.update(session=s,condition=condition)

@step(r'ordinary sight and fire consume the formed network')
def combat_run(w):
    from systems.combat import fire_weapon_number
    s=w['session'];a,t=s.units['u'],s.units['v']
    w['result']=[s.invoke(fire_weapon_number,s.engine,a,0,t,sight=sight,to_hit_roll=2) for sight in (True,False)]
    w['assert_observation']=combat_result

def combat_result(w,expected):
    s=w['session'];a,b=s.units['u'],s.units['b']
    bracket='TOFAR' if expected.startswith('TOFAR') or 'minimum' in expected else 'MED' if expected.startswith(('MED','C3-peer4')) else 'LONG' if expected.startswith('LONG') else 'SHORT'
    for result in w['result']:
        assert result.bth_breakdown is not None,result.messages
        eq(result.bth_breakdown.range_bracket,bracket)
        if bracket in ('SHORT','MED','TOFAR'):eq(result.bth_breakdown.c3_ref,-1 if 'minimum' in expected else b._id)
        if 'minimum' in expected:eq(result.bth_breakdown.range_mod,1)
    if 'membership-retained' in expected:eq(c3.network_size(a),1)
