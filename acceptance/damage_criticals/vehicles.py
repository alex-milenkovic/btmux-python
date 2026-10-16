from . import *
from .recovery import slot,ammunition,temp
from .armor import hit
from systems import vehicle_combat as vc, criticals as cr, damage as dmg, enhanced_crits as ec
from entities.mech import VehicleLocation as V
from entities.vehicle import TankCritStatus as T
from entities.crittypes import i2ammo
from core.events import EventType
from core.game_loop import wire_standard_systems

def events(w,kind):return [e for e in session(w).engine.events._events.values() if not e.zombie and e.data is unit(w) and e.event_type==kind]
def airborne(w,height=20):
    u=setup(w,'VTOL');u.status&=~S.LANDED;u.set_hex_position(u.x,u.y,height);u.fuel=100
    return u

def fire(w):
    from systems.combat import fire_weapon
    return call(w,fire_weapon,unit(w),session(w).units['enemy'],0,1,to_hit_roll=12,location_roll=7,engine=session(w).engine)

@step(r'a ground vehicle with one working (\w+) weapon and ten rounds of ammunition where applicable')
def jam_fixture(w,kind):setup(w,'GROUND');mount(w,kind,0);ammunition(w) if kind!='energy' else None

@step(r'a weapon-jam critical draws recycle duration (\d+)')
def jam(w,duration):draw(w,'vehicle_weapon_slot',[0]);draw(w,'vehicle_jam_recycle',[int(duration)]);call(w,vc.handle_weapon_jam,unit(w),0)

@step(r'its temporary failure is (\w+) firing is refused and recycle remaining is (\d+)')
def jam_result(w,failure,duration):
    eq(ec.part_temp_nuke(slot(w)),temp(failure));eq(slot(w).data,int(duration));eq(fire(w).hit,False)

@step(r'the normal started engine advances (\d+) ticks')
def normal_advance(w,duration):wire_standard_systems(session(w).engine);call(w,session(w).engine.run_ticks,int(duration))

@step(r'the weapon becomes operational and its ammunition has not been consumed by the critical')
def unjam(w):eq(ec.part_temp_nuke(slot(w)),0);eq(slot(w).data,0);eq(w['bin'].data if 'bin' in w else 10,10)

@step(r'an intact ground turret with jammed (True|False) and locked (True|False)')
def turret_fixture(w,jammed,locked):setup(w,'GROUND',tank_crit_status=(2 if truth(jammed) else 0)|(1 if truth(locked) else 0))

@step(r'a turret jam critical occurs')
def turret_hit(w):call(w,vc.handle_turret_jam,unit(w))

@step(r'turret jammed is (True|False) locked is (True|False) and turning is refused')
def turret_result(w,jammed,locked):
    eq((bool(unit(w).tank_crit_status&T.TURRET_JAMMED),bool(unit(w).tank_crit_status&T.TURRET_LOCKED)),(truth(jammed),truth(locked)))
    from systems.maneuver import set_turret
    eq(call(w,set_turret,session(w).engine,unit(w),90)[0],False)

@step(r'a ground vehicle rear section with (\d+) internal and bins containing (\d+) rounds at five damage each plus a Gauss bin')
def ammo_fixture(w,internal,rounds):
    setup(w,'GROUND');mount(w,'autocannon',3);unit(w).sections[3].internal=int(internal);ammunition(w,int(rounds))
    s=unit(w).sections[2].criticals[9];s.type=i2ammo(get_weapon('IS.GaussRifle').index);s.data=10;w['gauss']=s

@step(r'the ammunition critical occurs with critical rolls below eight')
def ammo_hit(w):call(w,vc.handle_ammo_explosion,unit(w),3,session(w).units['enemy'])

@step(r'rear internal is (\d+) eligible bin rounds are zero Gauss rounds are unchanged and fallback weapon destruction is (True|False)')
def ammo_result(w,internal,fallback):
    eq(unit(w).sections[3].internal,int(internal));eq(w['bin'].data,0);eq(w['gauss'].data,10);eq(bool(slot(w).firemode&F.DESTROYED_MODE),truth(fallback))

@step(r'an airborne VTOL with maximum speed ([\d.]+) and intact rotors')
def rotor_fixture(w,speed):airborne(w).max_speed=float(speed)

@step(r'one rotor-damage critical occurs')
def rotor_hit(w):call(w,vc.handle_rotor_damaged,unit(w))

@step(r'maximum speed is ([\d.]+) rotor destroyed is (True|False) and pending FALL events number (\d+)')
def rotor_result(w,speed,dead,count):eq(unit(w).max_speed,float(speed));eq(unit(w).is_section_destroyed(5),truth(dead));eq(len(events(w,EventType.FALL)),int(count))

@step(r'a vehicle stunned at tick zero and again at tick 30 with standard event dispatch')
def stuns(w):
    setup(w,'GROUND');mount(w);call(w,vc.handle_crew_stunned,unit(w));wire_standard_systems(session(w).engine)
    call(w,session(w).engine.run_ticks,30);call(w,vc.handle_crew_stunned,unit(w))

@step(r'time advances to tick (\d+)')
def stun_advance(w,time):call(w,session(w).engine.run_ticks,int(time)-session(w).engine.muxevent_tick)

@step(r'crew stunned is (True|False) and ordinary firing is permitted (True|False)')
def stun_result(w,stunned,permitted):eq(bool(unit(w).tank_crit_status&T.CREW_STUNNED),truth(stunned));eq(fire(w).bth_breakdown is not None,truth(permitted))

@step(r'an airborne VTOL at height five over (\w+) and a piloting roll that (passes|fails)')
def engine_fixture(w,terrain,roll):
    u=airborne(w,5)
    from entities import map as maps
    session(w).map.set_terrain(u.x,u.y,getattr(maps,terrain));u.terrain=getattr(maps,terrain);draw(w,'pilot_rolls',[12 if roll=='passes' else 2]*30)

@step(r'the direct vehicle-engine critical occurs')
def engine_hit(w):call(w,vc.handle_engine_hit,unit(w),session(w).units['enemy'])

@step(r'safe landing is (True|False) and immediate MechFalls dispatch is (True|False)')
def engine_result(w,landed,falls):eq(unit(w).has_status(S.LANDED) and not unit(w).is_fallen,truth(landed));eq(unit(w).is_fallen,truth(falls))

@step(r'a ground vehicle with maximum speed ([\d.]+) current speed (\d+) and desired speed (-?\d+)')
def cruise_fixture(w,maximum,current,desired):setup(w,'GROUND',max_speed=float(maximum),speed=int(current),desired_speed=int(desired))

@step(r'the crew-stun critical applies its cruise limit')
def cruise(w):call(w,vc.handle_crew_stunned,unit(w))

@step(r'current speed remains (\d+) and desired speed is (-?[\d.]+)')
def cruise_result(w,current,desired):eq(unit(w).speed,int(current));eq(unit(w).desired_speed,float(desired))

@step(r'two functional weapons in different sections with enumeration weights ([\d,]+)')
def main_fixture(w,weights):setup(w,'GROUND');mount(w,'energy',0);mount(w,'energy',1);draw(w,'vehicle_weapon_weight',map(int,weights.split(',')))

@step(r'the main weapon jam operation executes')
def main_jam(w):call(w,vc.jam_main_weapon,unit(w))

@step(r'selected weapon ordinal is (\w+) and no recovery timer is scheduled')
def main_result(w,ordinal):
    eq([i+1 for i in (0,1) if ec.part_temp_nuke(unit(w).sections[i].criticals[0])==5],[] if ordinal=='none' else [int(ordinal)])
    eq(len(events(w,EventType.MRECOVERY)),0)

@step(r'a moving (\w+) vehicle with maximum speed ([\d.]+) and no motive damage')
def motive_fixture(w,kind,speed):setup(w,'GROUND',move_type=M[kind],max_speed=float(speed),speed=20,desired_speed=20)

@step(r'motive roll (\d+) is applied without an extra modifier')
def motive(w,roll):draw(w,'motive_rolls',[int(roll)]);call(w,vc.motive_system_hit,unit(w))

@step(r'maximum speed is ([\d.]+) piloting penalty is (\d+) and immobilized is (True|False)')
def motive_result(w,speed,psr,immobile):eq(unit(w).max_speed,float(speed));eq(unit(w).pilot_skill_base,int(psr));eq(unit(w).is_fallen,truth(immobile))

@step(r'a live (\S+) with populated section (\w+) containing a weapon and other live sections')
def destroy_fixture(w,kind,name):
    u=setup(w,kind);w['section']=loc(w,name)
    if kind=='airborne-VTOL':airborne(w)
    mount(w,'energy',w['section'])

@step(r'that section is destroyed by enemy damage')
def destroy(w):call(w,dmg.destroy_section,unit(w),session(w).units['enemy'],w['section'],session(w).engine)

@step(r'unit destroyed is (True|False) pending fall is (True|False) and the section weapon is unusable')
def destroy_result(w,dead,fall):eq(unit(w).is_destroyed,truth(dead));eq(bool(events(w,EventType.FALL)),truth(fall));eq(bool(slot(w).firemode&F.DESTROYED_MODE),True)

@step(r'a (\w+) with live right-side sections')
def recurse_fixture(w,kind):setup(w,kind)

@step(r'section index three is destroyed')
def recurse(w):call(w,dmg.destroy_section,unit(w),session(w).units['enemy'],3,session(w).engine)

@step(r'corresponding arm index one is destroyed (True|False)')
def recurse_result(w,dead):eq(unit(w).sections[1].internal==0,truth(dead))

@step(r'an airborne VTOL at height twenty with no usable thrust after rotor destruction')
def fall_fixture(w):airborne(w);call(w,vc.handle_rotor_destroyed,unit(w))

@step(r'time advances to (\d+) ticks after the critical')
def fall_advance(w,time):call(w,session(w).engine.run_ticks,int(time))

@step(r'height is (\d+) and the unit is not instantly destroyed')
def fall_result(w,height):eq(unit(w).z,int(height));eq(unit(w).is_destroyed,False)

@step(r'a started ICE ground vehicle with a target pending movement events active ECM and live original sections')
def fuel_fixture(w):
    u=setup(w,'GROUND');u.specials|=Specials.ICE_TECH;u.status2|=S2.ECM_ENABLED;u.target=session(w).units['enemy']._id
    u.speed=u.desired_speed=20
    from systems.movement_commands import maybe_move
    maybe_move(session(w).engine,u)

@step(r'a fuel explosion critical occurs')
def fuel(w):call(w,vc.handle_fuel_tank_hit,unit(w),session(w).units['enemy'])

@step(r'kill reason is (\w+) all original-live sections are destroyed and speeds are zero')
def fuel_result(w,reason):
    u=unit(w);eq(u.kill_reason,reason);eq(all(s.internal==0 for s in u.sections if s.internal_orig),True);eq((u.speed,u.desired_speed,u.vertical_speed),(0,0,0))

@step(r'target pilot active ECM and obsolete movement events are cleared')
def cleared(w):
    u=unit(w);eq(u.target,-1);eq(u.pilot,None);eq(u.status2&S2.ECM_ENABLED,0);eq(len(events(w,EventType.MOVE)),0)

@step(r'a ground turret with an engine special slot and engine heat zero')
def engine_turret(w):setup(w,'GROUND');unit(w).sections[4].criticals[0].type=i2special(Special.ENGINE)

@step(r'the turret section is destroyed')
def turret_destroy(w):call(w,dmg.destroy_section,unit(w),None,4,session(w).engine)

@step(r'its slot is destroyed engine heat remains zero and the vehicle survives')
def turret_destroy_result(w):eq(bool(unit(w).sections[4].criticals[0].firemode&F.DESTROYED_MODE),True);eq(unit(w).engine_heat,0);eq(unit(w).is_destroyed,False)

@step(r'a landed AERO wing with armor (\d+) and other surviving sections')
def wing(w,armor):setup(w,'AERO');mount(w,'energy',1);unit(w).sections[1].armor=int(armor)

@step(r'ordinary wing damage is (\d+)')
def wing_hit(w,amount):hit(w,amount)

@step(r'wing armor is (\d+) and wing weapon is unusable (True|False)')
def wing_result(w,armor,lost):eq(unit(w).sections[1].armor,int(armor));eq(bool(slot(w).firemode&F.DESTROYED_MODE),truth(lost))

@step(r'a movable (\w+) hit in (\w+) with advanced critical dispatch enabled')
def chart_fixture(w,kind,location):w['chart']=(kind,location)

@step(r'rolls six through twelve are independently requested through critical dispatch')
def chart(w):
    w['chart_results']=[]
    kind,name=w['chart']
    for roll in range(6,13):
        f={};fresh(f);u=setup(f,kind);location=loc(f,name)
        u.specials|=Specials.ICE_TECH;u.max_speed=64.5
        mount(f,'autocannon',location);ammunition(f,3)
        for s in u.sections:s.armor=s.armor_orig=100;s.internal=s.internal_orig=100
        draw(f,'vehicle_critical_roll',[roll]);draw(f,'vehicle_weapon_slot',[0]*10);draw(f,'vehicle_jam_recycle',[60]);draw(f,'vehicle_weapon_weight',[5]*10)
        e=session(f).engine;e.fasaadvvtolcrit=e.fasaadvvhlcrit=1
        before=session(f).snapshot()['units']['u']
        result=call(f,cr.check_and_apply_criticals,u,location,1,session(f).units['enemy'])
        after=session(f).snapshot()['units']['u']
        w['chart_results'].append((f,result,before,after))

EFFECT_ENUM={'driver':vc.VehicleCritType.DRIVER_HIT,'weapon-jam':vc.VehicleCritType.WEAPON_JAM,'stabilizer':vc.VehicleCritType.STABILIZER_DESTROYED,'sensor':vc.VehicleCritType.SENSOR_HIT,'commander':vc.VehicleCritType.COMMANDER_HIT,'weapon-destroyed':vc.VehicleCritType.WEAPON_DESTROYED,'crew-killed':vc.VehicleCritType.CREW_KILLED,'cargo':vc.VehicleCritType.CARGO_HIT,'crew-stun':vc.VehicleCritType.CREW_STUNNED,'engine':vc.VehicleCritType.ENGINE_HIT,'fuel':vc.VehicleCritType.FUEL_TANK_HIT,'ammo':vc.VehicleCritType.AMMO_EXPLOSION,'turret-jam':vc.VehicleCritType.TURRET_JAM,'turret-lock':vc.VehicleCritType.TURRET_LOCK,'turret-off':vc.VehicleCritType.TURRET_BLOWN_OFF,'copilot':vc.VehicleCritType.COPILOT_HIT,'pilot':vc.VehicleCritType.PILOT_HIT,'rotor-damage':vc.VehicleCritType.ROTOR_DAMAGED,'tail-rotor':vc.VehicleCritType.TAIL_ROTOR_DAMAGED,'rotor-destroyed':vc.VehicleCritType.ROTOR_DESTROYED}

@step(r'the selected source effects are ([\w,-]+) and each selected effect executes its production consequence')
def chart_result(w,effects):
    for (f,result,before,after),effect in zip(w['chart_results'],effects.split(','),strict=True):
        eq(len(result),1)
        u=unit(f);s=u.sections[f['section']]
        if effect=='cargo':
            eq(after['messages'][len(before['messages']):],['The shot pierces your armor yet fails to hit a critical system!'])
            before['messages']=after['messages']
            eq(before,after)
        elif effect in ('weapon-jam',):eq(ec.part_temp_nuke(slot(f)),1)
        elif effect=='weapon-destroyed':eq(bool(slot(f).firemode&F.DESTROYED_MODE),True)
        elif effect=='stabilizer':eq(bool(s.config&__import__('entities.mech',fromlist=['SectionConfig']).SectionConfig.STABILIZERS_DESTROYED),True)
        elif effect=='driver' or effect=='pilot':eq(u.pilot_skill_base,2)
        elif effect=='sensor' or effect=='copilot':eq(u.base_to_hit,1)
        elif effect=='commander':eq((u.pilot_skill_base,u.base_to_hit),(1,1));eq(bool(u.tank_crit_status&T.CREW_STUNNED),True)
        elif effect=='crew-stun':eq(bool(u.tank_crit_status&T.CREW_STUNNED),True)
        elif effect in ('crew-killed','fuel'):eq(u.is_destroyed,True)
        elif effect=='ammo':eq(f['bin'].data,0);eq(s.internal,85)
        elif effect=='engine':eq(u.max_speed,0 if u.unit_type!=U.VTOL else 64.5)
        elif effect=='turret-jam':eq(bool(u.tank_crit_status&T.TURRET_JAMMED),True)
        elif effect=='turret-lock':eq(bool(u.tank_crit_status&T.TURRET_LOCKED),True)
        elif effect=='turret-off':eq(s.internal,0)
        elif effect=='rotor-damage':eq(u.max_speed,53.75)
        elif effect=='tail-rotor':eq(bool(u.tank_crit_status&T.TAIL_ROTOR_DESTROYED),True)
        elif effect=='rotor-destroyed':eq(u.sections[5].internal,0)
        else:raise AssertionError(effect)

@step(r'a movable (\w+) with advanced critical dispatch disabled and profile (\w+)')
def legacy_fixture(w,kind,profile):w['legacy']=(kind,profile)

@step(r'six independent critical resolutions choose legacy outcomes zero through five after any preliminary gate')
def legacy(w):
    w['legacy_results']=[]
    for roll in range(6):
        f={};fresh(f);kind,profile=w['legacy'];u=setup(f,kind);mount(f,'energy',3)
        draw(f,'vehicle_motive_gate',[6]);draw(f,'vehicle_legacy_critical',[roll]);draw(f,'vehicle_weapon_weight',[5])
        result=call(f,vc.legacy_vehicle_critical,u,3,session(f).units['enemy'],fasa=profile=='FASA',vtol=kind=='VTOL')
        w['legacy_results'].append((f,result))

@step(r'the selected source effects are ([\w,-]+)')
def legacy_result(w,effects):
    for (f,r),effect in zip(w['legacy_results'],effects.split(','),strict=True):
        u=unit(f)
        if effect=='head-injury':eq(u.pilot_hits,1)
        elif effect=='main-jam':eq(ec.part_temp_nuke(slot(f)),5)
        elif effect=='engine':eq(u.max_speed,0)
        elif effect in ('crew-killed','cockpit','fuel','powerplant'):
            eq(u.is_destroyed,True);eq(u.kill_reason,{'crew-killed':'PILOT','cockpit':'COCKPIT','fuel':'FUELTANK','powerplant':'POWERPLANT'}[effect])
        else:raise AssertionError(effect)
