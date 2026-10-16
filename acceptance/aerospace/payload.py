"""Physical bomb payload, trajectory and impact acceptance bindings."""
import math,re
from . import step,eq,near,invoke,position,make_unit,events,messages,check,U,M,S,C
from .flight import fixture
from entities.crittypes import i2bomb
from entities.mech import FireMode as F
from core.events import EventType as E
from systems import bombing as b
from physics.hexmath import hex_to_float,float_to_hex
from unittest.mock import patch


def install(w,index=2,slot=0,destroyed=False):
    part=w['u'].sections[0].criticals[slot]
    part.type=i2bomb(index);part.firemode=F.DESTROYED_MODE if destroyed else F.NONE
    return part


@step(r'bomb index (\d+)')
def index(w,value):w['index']=int(value)


@step(r'the source payload properties are inspected')
def properties(w):w['result']=b.properties(w['index'])


@step(r'name weight type and power are (\S+) (\d+) (\d+) and (\d+)')
def property_assert(w,name,weight,kind,power):eq(w['result'],dict(name=name,weight=int(weight),type=int(kind),power=int(power)))


@step(r'bomb command fixture (.+)')
def command_fixture(w,text):
    fixture(w,text)
    if 'one-bomb' in text:install(w)
    if 'IC' in text:w['u'].in_character=True
    if 'nonpilot-caller' in text:w['caller']=make_unit(w,'B').pilot


@step(r'BOMB executes with (.+)')
def bomb_command(w,text):
    w['result']=invoke(w,b.command,w['u'],'' if text=='empty' else text,w.get('caller'))
    r=w['result'];message=r.get('error','')
    checks={'No-bombs-installed':'No bombs installed','craft-landed-refusal':'craft is landed','option-required':'one option required','which-bomb-refusal':'WHICH bomb','invalid-argument':'Invalid argument','too-many-arguments':'Too many arguments','invalid-bomb-number':'Invalid bomb number','negative-bomb-number':'Negative bomb number','no-bomb-with-number':'No bomb with such number','unconscious-refusal':'unconscious','pilot-only-refusal':'only the pilot'}
    for key,fragment in checks.items():check(w,key,fragment in message or any(fragment in v for v in r.get('lines',[])))
    check(w,'payload-listed',len(r.get('rows',[]))==1)
    check(w,'bomb-released',r.get('scheduled',False) and w['u'].sections[0].criticals[0].type==0)


@step(r'payload fixture (.+)')
def payload_fixture(w,text):
    w['fixture']=text
    if text.startswith('NOSE0'):install(w,0,0,True);install(w,5,2)
    else:install(w,7)
    from systems.parts import set_cargo_weight
    set_cargo_weight(w['u']);w['cargo']=w['u'].carried_cargo
    w['slots']=[(s.type,s.firemode,s.data) for sec in w['u'].sections for s in sec.criticals]


@step(r'the payload operation executes')
def payload_operation(w):
    u=w['u'];text=w['fixture']
    if text.endswith('list'):
        result=b.list_payload(u);rows=result['rows'];raw='\n'.join(result['lines'])
        check(w,'two-rows',len(rows)==2);check(w,'weights1-and5',[v['weight']//10 for v in rows]==[1,5]);check(w,'Type-header','Type' in raw)
        check(w,'no-type-row-value',all(word not in '\n'.join(result['lines'][2:]) for word in ('Inferno','Standard','Cluster')))
    elif 'drop' in text:
        w['streams']['pilot_rolls']=[12]
        result=invoke(w,b.drop,u,2 if text.endswith('drop2') else 1)
        check(w,'NOSE2-cleared',u.sections[0].criticals[2].type==0);check(w,'NOSE0-retained',u.sections[0].criticals[0].type==i2bomb(0))
        check(w,'cargo-recomputed',u.carried_cargo==1020 and u.carried_cargo<w['cargo'])
        check(w,'number-refused',not result['ok']);check(w,'slots-retained',w['slots']==[(s.type,s.firemode,s.data) for sec in u.sections for s in sec.criticals])
    else:
        b.destroy_bomb(u,0)
        check(w,'no-change-or-damage',w['slots']==[(s.type,s.firemode,s.data) for sec in u.sections for s in sec.criticals] and not u.damage_taken and not events(w,E.ARTILLERY_HIT))


@step(r'bomb origin has elevation ([\d.]+) and vertical start speed ([\d.]+) with zero horizontal vector')
def origin(w,z,vz):w['u'].fz=float(z)*64.5;w['u'].start_fz=float(vz)


@step(r'aim computes the ballistic destination')
def aim(w):w['result']=invoke(w,b.aim,w['u'])


@step(r'time and displayed suffix are ([\d.]+) and (\w+) with the original hex retained')
def aim_assert(w,time,suffix):
    r=w['result'];near(r['time'],time);eq((r['x'],r['y']),(10,10));assert f"{float(time):.1f} second{'' if suffix=='empty' else suffix}," in r['message']


@step(r'drop fixture (.+)')
def drop_fixture(w,text):
    w['fixture']=text;u=w['u'];install(w)
    match=re.match(r't([\d.]+)',text);time=float(match[1]) if match else 2
    u.fz=(time*time/2)*64.5;u.z=int(u.fz/64.5)
    w['streams']['pilot_rolls']=[2 if 'PSR-fail' in text else 12]
    if 'scatter' in text:
        w['streams']['bomb_scatter_distance']=[int(re.search(r'scatter(\d+)',text)[1])]
        w['streams']['bomb_scatter_direction']=[int(re.search(r'direction(\d+)',text)[1])]
    if 'offmap' in text:u.start_fx=10000
    from systems.parts import set_cargo_weight
    set_cargo_weight(u);w['cargo']=u.carried_cargo
    w['recipient']=make_unit(w,'B')
    for sec in w['recipient'].sections:sec.armor=sec.armor_orig=1000;sec.internal=sec.internal_orig=1000


@step(r'a real drop and the impact clock execute')
def drop_run(w):
    from entities.map import GameMap
    from systems.map_transitions import transfer
    u=w['u'];text=w['fixture'];r=invoke(w,b.drop,u,1);w['result']=r
    for value in (4,5):check(w,'PSR-mod'+str(value),r['modifier']==value and any(name=='pilot_rolls' for name,*_ in w['draws']))
    check(w,'no-scatter-draw',not any(name.startswith('bomb_scatter') for name,*_ in w['draws']))
    check(w,'slot-cleared',u.sections[0].criticals[0].type==0)
    for value in (1,2,10):check(w,'impact-due'+str(value),r.get('due')==value)
    check(w,'miss6-hex-X',r['x']==16 and r['y']==10)
    check(w,'miss-minimum1',r['x']==9);check(w,'C-short-truncation',r['y']==9)
    check(w,'release-notices','detach a bomb' in messages(w));check(w,'payload-retained',u.sections[0].criticals[0].type==i2bomb(2));check(w,'no-cargo-change',u.carried_cargo==w['cargo'])
    check(w,'no-event',not w['engine'].events.pending_events(E.ARTILLERY_HIT))
    if 'another-map' in text:
        other=GameMap(30,30);other._id=1001;w['engine'].register_entity(other);invoke(w,transfer,u,other)
    if 'destroy-bomber' in text:u.set_status(S.DESTROYED)
    if r['scheduled']:
        invoke(w,w['engine'].run_ticks,r['due'])
        check(w,'impact-original-map-and-hex',w['recipient'].damage_taken>0 and w['recipient'].map is w['map'])
        damage=w['recipient'].damage_taken
        invoke(w,w['engine'].run_ticks,1)
        check(w,'impact-still-occurs-once',damage>0 and w['recipient'].damage_taken==damage and not w['engine'].events.pending_events(E.ARTILLERY_HIT))


@step(r'flight traversal fixture (.+)')
def traversal(w,text):
    w['fixture']=text;u=w['u'];w['time']=.5 if text.startswith('t0.5') else 4
    u.fz=8*64.5;w['dest']=(14,10)
    if 'out-of-map' in text:u.fx,u.fy=hex_to_float(-4,10);w['dest']=(4,10)
    fx,fy=hex_to_float(*w['dest']);samples=[]
    from core.randomness import float32
    dx,dy=float32((fx-u.fx)/w['time']),float32((fy-u.fy)/w['time']);x,y,z=u.fx,u.fy,u.fz
    for i in range(1,4):
        x,y,z=float32(x+dx),float32(y+dy),float32(z-1)
        samples.append(float_to_hex(x,y))
    w['samples']=samples
    if 'only-second' in text:w['map'].set_elevation(*samples[1],9)
    if 'second-and-third' in text:
        for xy in samples[1:]:w['map'].set_elevation(*xy,9)
    if 'out-of-map' in text:
        for xy in samples:
            if w['map'].valid(*xy):w['map'].set_elevation(*xy,9)
    if 'equals' in text:
        # Equality is tested with an exactly representable floor at the first sample.
        u.fz=8*64.5+1;w['map'].set_elevation(*samples[0],8)


@step(r'simulate flight examines the path')
def traversal_run(w):
    result=invoke(w,b.simulate_flight,w['u'],w['map'],*w['dest'],w['time']);w['result']=result
    check(w,'unchanged-destination',result==w['dest']);check(w,'second-sampled-hex',result==w['samples'][1]);check(w,'third-sampled-hex',result==w['samples'][2])
    check(w,'outside-samples-skipped',not w['map'].valid(*w['samples'][0]) and w['map'].valid(*result));check(w,'inbounds-obstacle-selected',result==w['samples'][-1])


@step(r'bomb (\S+) hits an occupied hex')
def impact_fixture(w,name):
    from entities.part_catalog import BOMBS
    install(w,BOMBS.index(name));w['recipient']=make_unit(w,'B')
    for sec in w['recipient'].sections:sec.armor=sec.armor_orig=3000;sec.internal=sec.internal_orig=3000
    w['u'].fz=2*64.5;w['u'].z=2;w['streams']['pilot_rolls']=[12]


@step(r'the real scheduled impact executes')
def impact_run(w):
    from systems import damage
    invoke(w,b.drop,w['u'],1)
    with patch.object(damage,'blast_hit_hexes',wraps=damage.blast_hit_hexes) as blast:
        invoke(w,w['engine'].run_ticks,2)
    eq(blast.call_count,1);w['blast_args']=blast.call_args.args


@step(r'blast damage heat and cluster size are (\d+) (\d+) and (\d+)')
def impact_assert(w,damage,heat,cluster):
    args=w['blast_args'];eq((args[1],args[3],args[2]),(int(damage),int(heat),int(cluster)))
    eq(w['recipient'].damage_taken,int(damage))
    if int(heat):
        assert w['recipient'].has_crit_status(C.JELLIED)
        eq(w['recipient']._burn_event.tick-w['engine'].muxevent_tick,int(heat)*6)
    else:assert not w['recipient'].has_crit_status(C.JELLIED)
