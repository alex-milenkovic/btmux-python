"""APS bindings for the sensor completion card; captures supply fixture values."""
import re
from core.events import EventType
from core.game_loop import wire_standard_systems
from entities.mech import MechStatus as S,MechStatus2 as S2,CritStatus as C,UnitType,MoveType,Specials,SectionConfig,WeaponState,AmmoMode
from entities.weapon import get_weapon,WEAPON_INDEX,WeaponType,get_weapons_by_type
from entities.map import FIRE,SMOKE,LIGHT_FOREST,HEAVY_FOREST,WATER,MOUNTAINS
from physics.hexmath import SCALEMAP,ZSCALE,float_to_hex
from systems import sensors,targeting,ecm,observation
from systems.los import *
from entities.mech import MechStatus as S, CritStatus as C
from tools.sensors_los import SensorSession,LETTERS,EQUIPMENT,set_flag

BINDINGS=[]
N=r'(-?\d+(?:\.\d+)?)'
B=r'(True|False)'

def step(pattern):
    def decorate(fn): BINDINGS.append((pattern,fn));return fn
    return decorate

def eq(actual,expected):
    assert actual==expected,f'{actual!r} != {expected!r}'

def truth(value): return value=='True'
def session(w): return w['sensor_session']
def unit(w): return session(w).units['u']
def target(w): return session(w).units['t']
def event(w,kind,u=None): return session(w).engine.has_event(kind,u or unit(w))
def advance(w,seconds): return session(w).invoke(session(w).engine.run_ticks,int(seconds))
def call(w,fn,*a,**k): return session(w).invoke(fn,*a,**k)
def command(w,name,args='',u=None):
    ss=session(w);u=u or unit(w)
    w['result']=ss.invoke(ss.engine.inject_command,u,lambda:ss.command(u,name,args.split()),name)
    return w['result']
def pair(u,text): u.sensor=[LETTERS.index(c) for c in text]
def cached(w,a=None,b=None,flags=None):
    a=a or unit(w);b=b or target(w)
    session(w).map.losinfo[a._id,b._id]=flags if flags is not None else MECHLOSFLAG_SEEN|MECHLOSFLAG_SEESP|MECHLOSFLAG_SEESS|MECHLOSFLAG_SEEC2

def distance(w,d,a=None,b=None):
    a=a or unit(w);b=b or target(w)
    fx,fy,fz=a.fx,a.fy+float(d)*SCALEMAP,a.fz
    x,y=float_to_hex(fx,fy)
    session(w).place(b,[x,y,a.z],[fx,fy,fz])

def equip(u,name):
    word,bit,_=EQUIPMENT[name];setattr(u,word,getattr(u,word,0)|bit)

def mount(u,artillery=False):
    weapon=get_weapons_by_type(WeaponType.TARTILLERY)[0] if artillery else get_weapon('IS.LRM-10')
    wi=next(i for i,v in enumerate(WEAPON_INDEX) if v is weapon)
    from entities.crittypes import i2weapon
    u.weapons=[WeaponState(section=4,critical=0,weapon_idx=wi)]
    for crit in range(min(12,weapon.crits)):
        u.sections[4].criticals[crit].type=i2weapon(wi)
    return weapon

@step(r'a fresh sensor session with ready units and event time zero')
def fresh(w):
    w['sensor_session']=SensorSession(dict(map={'size':[100,100]},config={'periodic_updates':False},units=[dict(name='u',contact_id='AA',team=1,at=[2,1,0],facing=180),dict(name='t',contact_id='TT',team=2,at=[2,2,0])],actions=[]))

@step(r'the engine advances (\d+) seconds')
def advances(w,n): advance(w,n)
@step(r'the engine advances to time (\d+)')
def to_time(w,n): advance(w,int(n)-session(w).engine.muxevent_tick)
@step(r'visual sensors and a unit target lock with retained hex coordinates')
def locked(w):
    u=unit(w);cached(w);targeting.set_target(session(w).engine,u,target(w));u.targ_x,u.targ_y=4,5
    w['lockstate']=(u.targ_x,u.targ_y,int(u.status&S.LOCK_MODES))
@step(r'the pilot requests sensors (.+)')
def select(w,text): command(w,'sensor',text)
@step(r'current sensors are (\w+) wanted sensors are (\w+) and the unit target is (\w+)')
def selected(w,current,wanted,t):
    eq(''.join(LETTERS[i] for i in unit(w).sensor),current)
    p=targeting.sensor_check(session(w).engine,unit(w))
    eq(''.join(LETTERS[i] for i in p) if p else 'none',wanted)
    eq(unit(w).target,-1 if t=='cleared' else target(w)._id)
@step(r'the hex coordinates and lock mode bits are unchanged')
def lock_kept(w):
    u=unit(w);eq((u.targ_x,u.targ_y,int(u.status&S.LOCK_MODES)),w['lockstate'])
@step(r'a sensor change from VV to IE requested at time zero')
def change_pending(w): command(w,'sensor','I E')
@step(r'current sensors are (\w+) wanted sensors are (\w+) and the sensor deadline is (\w+)')
def selected_deadline(w,current,wanted,deadline):
    eq(''.join(LETTERS[i] for i in unit(w).sensor),current)
    p=targeting.sensor_check(session(w).engine,unit(w));eq(''.join(LETTERS[i] for i in p) if p else 'none',wanted)
    events=[e.tick for e in session(w).engine.events._events.values() if e.data is unit(w) and e.event_type==EventType.SCHANGE and not e.zombie]
    eq(str(min(events)) if events else 'none',deadline)
@step(r'current sensors (\w+) and map light (\d+)')
def current(w,p,light): pair(unit(w),p);session(w).map.maplight=int(light)
@step(r'configured map light (\d+) is read by the normal time 25 map update')
def light_refresh(w,light):
    from core.game_loop import register_special_objects
    register_special_objects(session(w).engine)
    session(w).map.visibility_config=f'30 {light} 0 0 0'
    advance(w,25)
@step(r'current sensors are (\w+) with no sensor change event created')
def current_no_event(w,p): eq(unit(w).sensor,[LETTERS.index(c) for c in p]);eq(event(w,EventType.SCHANGE),False)
@step(r'all equipment required by that sensor pair is installed')
def pair_equipment(w):
    for sn in unit(w).sensor:
        row=sensors.sensors[sn]
        if row.required_special>0:
            word='specials' if row.specials_set==1 else 'specials2';setattr(unit(w),word,getattr(unit(w),word)|row.required_special)
@step(r'the pilot requests sensor readout (\w+)')
def readout(w,style): command(w,'sensor','info' if style=='verbose' else '')
@step(r'the sensor name includes (.+) and scanning description is (\w+)')
def sensor_text(w,name,arc):
    text=w['result']['message'];assert name in text,text
    eq('degree scanning' not in text,arc=='fullvision')
    if arc!='fullvision': assert arc+' degree scanning' in text,text
@step(r'blocker details are (\w+)')
def blockers(w,present): eq('Blocked by:' in w['result']['message'],present=='present')

@step(r'a started observer and an enemy one hex ahead with no cached contact')
def lifecycle(w):
    wire_standard_systems(session(w).engine)
    # Source map membership allocates zeroed directed LOS slots up front.
    assert not any(session(w).map.losinfo.values())
@step(r'the visibility workflow is (.+)')
def workflow(w,flow):
    ss=session(w);u=unit(w)
    if flow=='map-maintenance-only': sensors.update_los_info(ss.map);return
    if flow=='repeated-live-registration-and-advance': ss.engine.register_entity(u);ss.engine.register_entity(u)
    advance(w,2)
    if flow=='acquire-then-shutdown-and-advance': command(w,'shutdown');advance(w,2)
    elif flow=='acquire-lock-disable-visual-and-advance': command(w,'target','TT');ss.map.sensorflags=1;advance(w,2)
@step(r'the enemy contact is '+B+r' and enemy count is (\d+)')
def contact_state(w,seen,count):
    eq(bool(session(w).map.losinfo.get((unit(w)._id,target(w)._id),0)&MECHLOSFLAG_SEEN),truth(seen));eq(unit(w).num_seen,int(count))
@step(r'the observer has (\d+) pending acquisition chains')
def chains(w,count): eq(sum(e.data is unit(w) and e.event_type==EventType.PLOS and not e.zombie for e in session(w).engine.events._events.values()),int(count))
@step(r'autocontact mode (\d+) and a new (\w+) contact with clear NB visibility')
def notices(w,mode,relation):
    unit(w).brief=int(mode)*4;target(w).team=1 if relation=='friend' else 2;sensors.update_los_info(session(w).map)
@step(r'an ordinary acquisition sweep notices the contact')
def acquire(w): advance(w,1)
@step(r'the acquisition notification style is (\w+) and warning is '+B)
def notice_style(w,style,warn):
    texts=[m for m in unit(w).movement_messages if 'Seen:' in m or 'You notice' in m]
    eq('short' if texts and 'Seen:' in texts[0] else 'long' if texts else 'none',style);eq(any('%cr' in t for t in texts),truth(warn))
@step(r'equal sensors (\w) with valid equipment and an eligible target at range 1')
def eligible_setup(w,sn): pair(unit(w),sn*2);pair_equipment(w);cached(w)
@step(r'the configured sensor disable mask is (\d+)')
def mask(w,n): session(w).map.sensorflags=int(n)
@step(r'sensor eligibility is inspected through the diagnostic command')
def eligibility(w): w['result']=session(w).diagnose(unit(w),'eligibility','t')
@step(r'the eligible sensor mask is (\d+)')
def eligible(w,n): eq(w['result']['eligible'],int(n))
@step(r'an observer with primary sensor (\w) secondary V and clear LOS to a flash source')
def flash_setup(w,sn): pair(unit(w),sn+'V');session(w).map.maplight=0;cached(w)
@step(r'a guaranteed flash of duration (\d+) occurs')
def flash(w,n): call(w,sensors.scramble_infra_and_liteamp,target(w),int(n),0,'Infra flash','Light flash')
@step(r'the engine advances (\d+) seconds with recovery consciousness '+B)
def recovery(w,n,conscious): set_flag(unit(w),'status',S.UNCONSCIOUS,not truth(conscious));advance(w,n)
@step(r'blinded is '+B+r' and recovery message count is (\d+)')
def recovered(w,blinded,n): eq(unit(w).has_status(S.BLINDED),truth(blinded));eq(unit(w).movement_messages.count('Your sight recovers.'),int(n))

@step(r'a unit of class (\w+) posture ([\w-]+) movement (\w+) at Z (\d+)')
def height_setup(w,cls,posture,movement,z):
    u=unit(w);u.unit_type=UnitType[cls];u.move_type=MoveType[movement];u.z=int(z)
    set_flag(u,'status',S.FALLEN,posture=='fallen');u.tank_crit_status=4 if posture=='dug-in' else 0
@step(r'the LOS height diagnostic is requested')
def height_diag(w): w['height']=actual_elevation(session(w).map,unit(w).x,unit(w).y,unit(w))
@step(r'effective unit LOS elevation is '+N)
def height_eq(w,n): eq(w['height'],float(n))
@step(r'a target in (\w+) under (\w+) at height (\d+) above the floor')
def woods_setup(w,terrain,overlay,height):
    t=target(w);session(w).hexagon(dict(at=[t.x,t.y],terrain=terrain,elevation=0,**(dict(overlay=overlay) if overlay!='none' else {})));session(w).place(t,[t.x,t.y,int(height)])
@step(r'the observer has visual primary visibility at daylight with no intervening woods or partial cover')
def visual(w): pair(unit(w),'VV');cached(w,flags=MECHLOSFLAG_SEESP)
@step(r'the sensor terrain modifier is inspected')
def modifier(w): w['modifier']=add_terrain_mod(unit(w),target(w),session(w).map,targeting.fa_mech_range(unit(w),target(w)),0)
@step(r'the terrain modifier is '+N)
def modifier_eq(w,n): eq(w['modifier'],float(n))
@step(r'infrared profile (\w+) and a hulldown target with partial cover and no woods')
def ir(w,profile): session(w).map.infrared_profile=profile;target(w).set_status(S.HULLDOWN);cached(w,flags=MECHLOSFLAG_PARTIAL|MECHLOSFLAG_SEESP)
@step(r'target heat is '+N+r' plus heat '+N+r' and minus heat '+N)
def heats(w,heat,plus,minus): target(w).heat=float(heat);target(w).plus_heat=float(plus);target(w).minus_heat=float(minus)
@step(r'the observer has primary infrared visibility')
def infrared(w): pair(unit(w),'II')
@step(r'the diagnostic cached contact has primary '+B+r' secondary '+B+r' and terrain block '+B)
def cache(w,p,s,b): cached(w,flags=(MECHLOSFLAG_SEESP if truth(p) else 0)|(MECHLOSFLAG_SEESS if truth(s) else 0)|(MECHLOSFLAG_BLOCK if truth(b) else 0))
@step(r'normal and NB line of sight are requested')
def los_diag(w): w['result']=session(w).diagnose(unit(w),'los','t')
@step(r'detected is '+B+r' and identified is '+B)
def los_result(w,d,i): eq(w['result'],dict(detected=truth(d),identified=truth(i)))

@step(r'a hostile (\w+) ECM emitter at real 3D range '+N+r' from an otherwise unjammed observer')
def emitter(w,kind,d):
    distance(w,d);equip(target(w),kind);target(w).status2|={'Guardian':1,'Angel':0x100,'Personal':0x1000}[kind]
@step(r'the normal ECM update runs')
def update_ecm(w): call(w,ecm.check_ecm,unit(w))
@step(r'the observer is ECM disturbed '+B)
def disturbance(w,b): eq(ecm.any_ecm_disturbed(unit(w)),truth(b))
def emitters(w,count,team,bit):
    ss=session(w)
    for _ in range(int(count)):
        name='emitter'+str(len(ss.units));u=ss.add_unit(dict(name=name,team=team,at=[2,1,0]));u.status2|=bit
@step(r'friendly Guardian ECM count (\d+) Angel ECM count (\d+) and hostile Guardian ECCM count (\d+)')
def ecm_counts(w,fg,fa,hc): emitters(w,fg,1,1);emitters(w,fa,1,0x100);emitters(w,hc,2,2)
@step(r'friendly Guardian ECCM count (\d+) and hostile Angel ECM count (\d+)')
def eccm_counts(w,fc,ha): emitters(w,fc,1,2);emitters(w,ha,2,0x100)
@step(r'ECM countered is '+B)
def countered(w,b): eq(bool(ecm.ecm_countered(unit(w))),truth(b))
@step(r'a hostile Guardian emitter initially in range of the observer')
def guardian(w): emitter(w,'Guardian',1)
@step(r'the observer has functional Beagle equipment and BB sensors with a separate unprotected nonstealth target at range 1')
def probe(w):
    equip(unit(w),'Beagle');pair(unit(w),'BB');session(w).add_unit(dict(name='probe_target',team=2,at=[2,2,0]))
@step(r'the engine performs (\d+) ECM updates followed by emitter removal and one update')
def transition(w,n):
    for _ in range(int(n)): update_ecm(w)
    session(w).map.remove_mech(target(w));update_ecm(w)
@step(r'static notification count is (\d+) and normal-again notification count is (\d+)')
def static_count(w,static,normal): eq(sum('static!' in m for m in unit(w).movement_messages),int(static));eq(sum('back to normal' in m for m in unit(w).movement_messages),int(normal))
@step(r'ECM disturbed is False and the probe can detect an eligible target')
def probe_recovers(w): eq(ecm.any_ecm_disturbed(unit(w)),False);eq(sensors.bap_csee(unit(w),session(w).units['probe_target'],session(w).map,1,MECHLOSFLAG_SEEC2),1)
@step(r'one iNARC ECM pod on a MECH section with armor (\d+) internal (\d+) and destroyed config bit '+B)
def pod(w,armor,internal,config):
    section=unit(w).sections[0];section.armor=int(armor);section.internal=int(internal);section.specials|=8;section.config=SectionConfig.SECTION_DESTROYED if truth(config) else 0
@step(r'there are no other ECM or ECCM fields')
def no_fields(w):
    for u in session(w).units.values(): eq(int(u.status2)&0x3303,0)

@step(r'a functional searchlight initially '+B)
def initial_light(w,on): equip(unit(w),'searchlight');set_flag(unit(w),'status2',S2.SLITE_ON,truth(on))
@step(r'the pilot requests slite twice and the engine advances (\d+) seconds')
def twice(w,n): w['accepted']=int(command(w,'slite')['ok'])+int(command(w,'slite')['ok']);advance(w,n)
@step(r'searchlight on is '+B+r' with transition pending '+B)
def light_state(w,on,p): eq(bool(unit(w).status2&S2.SLITE_ON),truth(on));eq(event(w,EventType.SLITE_CHANGE),truth(p))
@step(r'exactly one slite request was accepted')
def one_request(w): eq(w['accepted'],1)
@step(r'an on searchlight at range '+N+r' and target arc ([\w-]+)')
def light_pred(w,d,arc):
    distance(w,d);unit(w).status2|=0x20
    if arc=='turret-only': unit(w).unit_type=UnitType.VEH_GROUND;unit(w).move_type=MoveType.TRACK;unit(w).facing=0;unit(w).turret_facing=180
@step(r'cached intervening woods are (\d+) water hexes (\d+) and terrain blocked '+B)
def terrain_cache(w,woods,water,block): cached(w,flags=int(woods)*MECHLOSFLAG_WOOD+int(water)*MECHLOSFLAG_WATER+(MECHLOSFLAG_BLOCK if truth(block) else 0))
@step(r'the unit illumination diagnostic evaluates the source')
def light_eval(w): w['qualifies']=sensors.mech_lites_target(unit(w),target(w))
@step(r'the source qualifies '+B)
def qualifies(w,b): eq(bool(w['qualifies']),truth(b))
@step(r'an already illuminated target with warning preference '+B)
def already_lit(w,warn): target(w).crit_status|=C.SLITE_LIT;target(w).sl_warn=truth(warn)
@step(r'(\d+) qualifying other light sources remain at range 30')
def remaining_lights(w,n): distance(w,30);unit(w).status2|=0x20 if int(n) else 0;cached(w)
@step(r'the normal end-light update runs twice')
def end_light(w): sensors.end_lite_check(target(w));sensors.end_lite_check(target(w))
@step(r'the target illuminated flag is '+B+r' and loss notification count is (\d+)')
def lit_retained(w,lit,count): eq(bool(target(w).crit_status&C.SLITE_LIT),truth(lit));eq(target(w).movement_messages.count('You are no longer being illuminated.'),int(count))

@step(r'a functional TAG unit and an identified enemy at range '+N)
def tag_setup(w,d): equip(unit(w),'TAG');distance(w,d);cached(w)
@step(r'the pilot tags that enemy and the engine advances (\d+) seconds')
def tag_time(w,n): w['accepted']=command(w,'tag','TT')['ok'];advance(w,n)
@step(r'the TAG command is '+B+r' reciprocal relationship is '+B+r' and stable message count is (\d+)')
def tag_result(w,ok,linked,count):
    eq(w['accepted'],truth(ok));eq(unit(w).tag_target==target(w)._id and target(w).tagged_by==unit(w)._id,truth(linked));eq(sum('stable lock' in m for m in unit(w).movement_messages),int(count))
@step(r'the TAG system is recycling '+B)
def recycling(w,b): eq(event(w,EventType.TAG_RECYCLE),truth(b))
@step(r'a TAG relationship started at time zero with its original target')
def initial_tag(w): tag_setup(w,10);command(w,'tag','TT')
@step(r'at time (\d+) the pilot requests tag cancellation')
def cancel_tag(w,n): advance(w,n);w['accepted']=command(w,'tag','-')['ok']
@step(r'cancellation is '+B+r' reciprocal relationship is '+B+r' and the TAG system is recycling '+B)
def cancelled(w,ok,linked,recycle): eq(w['accepted'],truth(ok));eq(unit(w).tag_target==target(w)._id and target(w).tagged_by==unit(w)._id,truth(linked));eq(event(w,EventType.TAG_RECYCLE),truth(recycle))
@step(r'ready message count is (\d+)')
def ready_count(w,n): eq(sum('finished recycling' in m for m in unit(w).movement_messages),int(n))
@step(r'a stable TAG relationship to target t and another tagger b')
def stable(w): initial_tag(w);advance(w,30);session(w).add_unit(dict(name='b',team=1,at=[2,1,0],equipment=['TAG']))
@step(r'the target change is (.+) and normal TAG validation runs')
def tag_change(w,change):
    if change.startswith('range-to-'): distance(w,float(change[len('range-to-'):]))
    elif change=='block-NB-LOS': cached(w,flags=MECHLOSFLAG_SEESP|MECHLOSFLAG_BLOCK)
    elif change=='b-overwrites-tag':
        b=session(w).units['b'];cached(w,b,target(w));targeting.tag(session(w).engine,b,target(w))
    elif change=='target-removed': session(w).map.remove_mech(target(w));session(w).engine.unregister_entity(target(w))
    else: raise ValueError(change)
    targeting.check_tag(unit(w))
@step(r'the original tagger remains linked '+B+r' and target tagged-by is (\w+)')
def ownership(w,linked,owner):
    eq(unit(w).tag_target>0,truth(linked));actual='absent' if target(w).map is None else 'original' if target(w).tagged_by==unit(w)._id else 'b' if target(w).tagged_by==session(w).units['b']._id else 'none';eq(actual,owner)
@step(r'the original tagger has a cooldown pending '+B)
def cooldown(w,b): eq(event(w,EventType.TAG_RECYCLE),truth(b))
@step(r'a target speed '+N+r' started '+B+r' and tagged-by relation ([\w-]+)')
def semiguided_target(w,speed,started,relation):
    t=target(w);t.speed=float(speed);set_flag(t,'status',S.STARTED,truth(started));cached(w)
    if relation in ('other-friendly','hostile'):
        b=session(w).add_unit(dict(name='b',team=1 if relation=='other-friendly' else 2,at=[3,1,0]));t.tagged_by=b._id
    elif relation=='self': t.tagged_by=unit(w)._id
    elif relation=='dangling-positive-ID': t.tagged_by=999999
    elif relation=='none': t.tagged_by=0
    else: raise ValueError(relation)
@step(r'the shooter sights with ammunition (\w+)')
def semiguided_sight(w,ammo):
    mount(unit(w));unit(w).sections[4].criticals[0].ammomode=AmmoMode.SGUIDED_MODE if ammo=='semiguided' else 0
    command(w,'target','TT')
    command(w,'sight','0 TT')
@step(r'the applied target movement modifier is '+N)
def applied_move(w,n): eq(w['result']['attack']['bth_breakdown']['target_move'],float(n))

@step(r'a shooter with a mounted artillery weapon and no LOS to a friendly self-spotter')
def arty(w): mount(unit(w),True);target(w).team=1;target(w).spotter=target(w)._id;session(w).map.losinfo.clear()
@step(r'their real range is '+N+r' and observer radio range is (\d+)')
def radio(w,d,r): distance(w,d);target(w).radio_range=int(r)
@step(r'the shooter requests that spotter and the engine advances (\d+) seconds')
def request_spot(w,n): w['accepted']=command(w,'spot','TT')['ok'];advance(w,n)
@step(r'the spot request is '+B+r' and the datalink is '+B+r' with handshake pending '+B)
def spot_state(w,ok,linked,pending): eq(w['accepted'],truth(ok));eq(unit(w).spotter==target(w)._id,truth(linked));eq(event(w,EventType.SPOT_LOCK),truth(pending))
@step(r'an accepted artillery spot handshake at range (\d+)')
def handshake(w,d): arty(w);radio(w,d,80);eq(command(w,'spot','TT')['ok'],True)
@step(r'before expiry shooter X changes '+B+r' shooter Y changes '+B+r' observer X changes '+B+r' and observer Y changes '+B)
def movement_gate(w,sx,sy,ox,oy):
    for u,x,y in [(unit(w),sx,sy),(target(w),ox,oy)]:
        if truth(x): u.fx+=1
        if truth(y): u.fy+=1
@step(r'the engine advances to the handshake deadline')
def handshake_time(w):
    deadline=next(e.tick for e in session(w).engine.events._events.values() if e.event_type==EventType.SPOT_LOCK and not e.zombie);advance(w,deadline-session(w).engine.muxevent_tick)
@step(r'the datalink is '+B+r' and movement failure notifications total (\d+)')
def handshake_result(w,linked,messages): eq(unit(w).spotter==target(w)._id,truth(linked));eq(sum('not established due to movement' in m for u in session(w).units.values() for m in u.movement_messages),int(messages))
@step(r'a spot link established by ([\w-]+)')
def spot_method(w,method):
    target(w).radio_range=10
    if method=='artillery-handshake': handshake(w,10);handshake_time(w);target(w).radio_range=10
    else:
        target(w).team=1;target(w).spotter=target(w)._id;cached(w);command(w,'spot','TT')
@step(r'the observer state becomes ([\w-]+) and the engine advances (\d+) seconds')
def watchdog_change(w,state,n):
    if state=='at-radio-limit': distance(w,2*target(w).radio_range)
    elif state=='beyond-radio-range': target(w).radio_range=1;distance(w,3)
    elif state=='no-longer-spotting': target(w).spotter=-1
    elif state=='linked-to-another-spotter': target(w).spotter=999
    elif state=='different-map': session(w).map.remove_mech(target(w))
    else: raise ValueError(state)
    advance(w,n)
@step(r'the datalink is '+B+r' and a watchdog is pending '+B)
def watchdog_state(w,linked,p): eq(unit(w).spotter==target(w)._id,truth(linked));eq(event(w,EventType.SPOT_CHECK),truth(p))
@step(r'a self-spotter with two linked shooters at fire adjustments (\d+) and (\d+) and an unrelated shooter at (\d+)')
def adjustments(w,a,b,c):
    u=unit(w);u.spotter=u._id;target(w).spotter=u._id;target(w).fire_adjustment=int(a)
    extra=session(w).add_unit(dict(name='linked',at=[3,1,0]));extra.spotter=u._id;extra.fire_adjustment=int(b)
    extra=session(w).add_unit(dict(name='unrelated',at=[4,1,0]));extra.fire_adjustment=int(c)
@step(r'the self-spotter performs ([\w-]+)')
def adjust_action(w,action):
    if action=='spot-cancel': command(w,'spot','-')
    elif action=='clear-target': command(w,'target','-')
    elif action=='change-hex-target': command(w,'target','4 4')
    else: raise ValueError(action)
@step(r'both linked adjustments are zero and the unrelated adjustment remains (\d+)')
def adjusted(w,n): eq(target(w).fire_adjustment,0);eq(session(w).units['linked'].fire_adjustment,0);eq(session(w).units['unrelated'].fire_adjustment,int(n))
@step(r'a stationary conscious self-spotter with a visible ([\w-]+) target and no settling lock')
def indirect_setup(w,kind):
    t=target(w);t.team=1;t.spotter=t._id;unit(w).spotter=t._id
    enemy=session(w).add_unit(dict(name='enemy',team=2,at=[2,3,0]));cached(w,t,enemy)
    if kind in ('unit','clear-unit'): t.target=enemy._id
    else:
        t.targ_x,t.targ_y,t.targ_z=2,3,0
        if kind=='empty-hex': session(w).map.remove_mech(enemy)
    w['armor']=[s.armor for s in enemy.sections]
@step(r'the linked shooter sights with a mounted ([\w-]+) weapon')
def indirect_sight(w,weapon): mount(unit(w),weapon=='artillery');command(w,'sight','0')
@step(r'the indirect attempt is '+B+r' with observer modifier (\w+) and target selection (\w+)')
def indirect_result(w,ok,mod,selection):
    eq(w['result']['ok'],truth(ok));b=w['result']['attack']['bth_breakdown']
    if mod=='none': eq(b,None)
    else: eq(w['result']['attack']['observer_modifier'],int(mod))
    # Actual firing result carries the selected target identity when present.
    if selection!='none': eq(w['result']['attack']['target_id'] is not None,selection=='unit')
@step(r'ammunition and armor are unchanged')
def no_damage(w): eq([s.armor for s in session(w).units['enemy'].sections],w['armor']);eq(unit(w).weapons[0].recycle,0)

@step(r'contact brief value (\d+)')
def brief_initial(w,n): unit(w).brief=int(n)
@step(r'the pilot issues brief (.+)')
def brief_request(w,text): command(w,'brief',text)
@step(r'the command is '+B+r' and brief value is (\d+)')
def brief_result(w,ok,n): eq(w['result']['ok'],truth(ok));eq(unit(w).brief,int(n))
@step(r'identified contacts friend f enemy e shutdown enemy s destroyed enemy d and locked shutdown enemy t')
def contact_fixture(w):
    ss=session(w);ss.map.remove_mech(target(w));ss.engine.unregister_entity(target(w))
    for name,team in [('f',1),('e',2),('s',2),('d',2),('t',2)]:
        if name=='t': ss.units.pop('t')
        u=ss.add_unit(dict(name=name,contact_id=name*2,team=team,at=[3,3,0],started=name not in ('s','t'),destroyed=name=='d'));cached(w,unit(w),u)
    unit(w).target=ss.units['t']._id
@step(r'contact brevity is (\d+) with no buildings')
def brief_mode(w,n): unit(w).brief=int(n)
@step(r'the pilot requests contacts with filter (.+)')
def filter_contacts(w,text): command(w,'contacts','' if text=='no-argument' else text)
@step(r'the included unit IDs as an unordered set are ([\w,]+)')
def contact_ids(w,ids): eq(sorted(r['name'] for r in w['result']['contacts']),sorted(ids.split(',')))
@step(r'visible live contacts near at range (\d+) far at range (\d+) and destroyed wreck at range (\d+) in that roster order')
def order_fixture(w,near,far,wreck):
    ss=session(w);ss.map.remove_mech(target(w))
    for name,d in [('near',near),('far',far),('wreck',wreck)]:
        u=ss.add_unit(dict(name=name,team=2,at=[2,2,0],destroyed=name=='wreck'));distance(w,d,b=u);cached(w,b=u)
@step(r'the pilot requests contact brevity (\d+)')
def contact_brevity(w,n): unit(w).brief=int(n);command(w,'contacts')
@step(r'displayed contact order is ([\w,]+) and ordinary heading is '+B)
def contact_order(w,names,heading): eq([r['name'] for r in w['result']['contacts']],names.split(','));eq(w['result']['heading'],truth(heading))
@step(r'a same-team contact with primary visibility and terrain block '+B)
def hidden_name(w,block): target(w).team=1;cached(w,flags=MECHLOSFLAG_SEESP|(MECHLOSFLAG_BLOCK if truth(block) else 0))
@step(r'the contact is heated jellied burning and has active ECM and attached NARC')
def statuses(w):
    t=target(w);t.heat=5;t.crit_status|=C.JELLIED;t.status2|=1;t.sections[0].specials|=1;session(w).map.set_terrain(t.x,t.y,FIRE)
@step(r'a brief contact list is requested')
def brief_list(w): unit(w).brief=2;command(w,'contacts')
@step(r'the name is ([\w-]+) apparent friend is '+B+r' and five status characters are ([\w+]+)')
def status_result(w,name,friend,status):
    r=w['result']['contacts'][0];eq(r['name'],target(w).name if name=='real-name' else name);eq(r['friend'],truth(friend));eq(r['status'],status.replace('_',' '))

@step(r'a scanner range (\d+) and an identified ordinary unit at real range '+N)
def scanner(w,scan_range,d): unit(w).scan_range=int(scan_range);distance(w,d);cached(w)
@step(r'the pilot issues (\w+) for the target ID')
def scan_command(w,name): command(w,name,'TT')
@step(r'the command is '+B+r' and the target receives (\d+) scan notifications')
def scan_result(w,ok,n): eq(w['result']['ok'],truth(ok));eq(sum('being scanned' in m for m in target(w).movement_messages),int(n))
@step(r'an identified target with real armor and mounted weapon state within scanner range')
def scan_options_setup(w): cached(w);mount(target(w));unit(w).target=target(w)._id
@step(r'the pilot requests scan option (\w+)')
def scan_option(w,option): command(w,'scan','' if option=='all' else option)
@step(r'armor details are '+B+r' information extras are '+B+r' and weapon details are '+B)
def scan_fields(w,a,i,we): eq('armor' in w['result'],truth(a));eq('info' in w['result'],truth(i));eq('weapons' in w['result'],truth(we))
@step(r'the base position and movement report is present')
def report_fields(w): assert 'position' in w['result']['report'];assert 'movement' in w['result']['report']
@step(r'a target with markings ([\w-]+) and NB visibility '+B)
def markings(w,text,nb): target(w).markings='' if text=='empty' else text;cached(w,flags=MECHLOSFLAG_SEESP|(0 if truth(nb) else MECHLOSFLAG_BLOCK))
@step(r'the pilot views its contact ID')
def view_command(w): command(w,'view','TT')
@step(r'the view outcome is ([\w-]+)')
def view_result(w,outcome):
    if outcome=='not-seen-well-enough': eq(w['result']['ok'],False);assert 'seen well enough' in w['result']['message']
    else: eq(w['result']['message'],'That target has no markings.' if outcome=='no-markings' else outcome)
@step(r'an observer at hex (\d+) (\d+) Z (\d+) and destination hex (\d+) (\d+) at floor (\d+)')
def navigation_setup(w,x,y,z,tx,ty,tz): session(w).place(unit(w),[int(x),int(y),int(z)]);session(w).map.set_elevation(int(tx),int(ty),int(tz));w['destination']=tx+' '+ty
@step(r'the map is dark '+B)
def dark(w,b): session(w).map.dark=truth(b)
@step(r'the pilot requests coordinate range')
def range_command(w): command(w,'range',w['destination'])
@step(r'displayed 3D range rounded to one decimal is '+N+r' and displayed ground range is '+N)
def range_result(w,r,g): eq(f"{w['result']['range']:.1f}",r);eq(f"{w['result']['ground_range']:.1f}",g)

@step(r'an upright observer at hex (\d+) (\d+) Z (\d+) facing south on a clear map')
def map_observer(w,x,y,z): session(w).place(unit(w),[int(x),int(y),int(z)]);unit(w).facing=180
@step(r'selected sensors (\w+) map visibility (\d+) light (\d+) and clairvoyance '+B)
def map_sensors(w,p,v,l,c): pair(unit(w),p);session(w).map.mapvis=int(v);session(w).map.maplight=int(l);set_flag(unit(w),'crit_status',C.CLAIRVOYANT,truth(c))
@step(r'the pilot renders rectangle origin (\d+) (\d+) width (\d+) height (\d+)')
def render(w,x,y,width,height):
    try: w['map_result']=calculate_los_map(session(w).map,unit(w),int(x),int(y),int(width),int(height));w['render_ok']=True
    except ValueError: w['map_result']=None;w['render_ok']=False
@step(r'row-major visibility flags are ([\d,]+)')
def flags(w,text): eq(w['map_result'].cells,[int(v) for v in text.split(',')])
@step(r'visual sensors map visibility (\d+) and light (\d+)')
def visual_map(w,v,l): map_sensors(w,'VV',v,l,'False')
@step(r'a ([\w-]+) light source at hex (\d+) (\d+)')
def map_light(w,source,x,y):
    if source=='none': return
    if source=='fire-decoration': session(w).hexagon(dict(at=[int(x),int(y)],terrain='CLEAR',elevation=0,overlay='FIRE'))
    elif source=='jellied-unit': session(w).place(target(w),[int(x),int(y),0]);target(w).crit_status|=C.JELLIED
    else: raise ValueError(source)
@step(r'sensors (\w+) visibility (\d+) light (\d+) and hex (\d+) (\d+) containing (\w+) at floor '+N)
def map_terrain(w,p,v,l,x,y,t,floor): map_sensors(w,p,v,l,'False');session(w).hexagon(dict(at=[int(x),int(y)],terrain=t,elevation=int(float(floor))))
@step(r'a clear (\d+) by (\d+) map')
def size_map(w,width,height):
    board=session(w).map;board.map_width=int(width);board.map_height=int(height)
    board._terrain=[[' ']*int(width) for _ in range(int(height))];board._elev=[[0]*int(width) for _ in range(int(height))]
@step(r'the render is '+B+r' and cell count is (\d+)')
def rendered(w,ok,n): eq(w['render_ok'],truth(ok));eq(len(w['map_result'].cells) if w['map_result'] else 0,int(n))
