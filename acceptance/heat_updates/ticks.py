"""Per-turn, turret, recycle and height integration bindings."""
from .context import *
from entities.mech import UnitType,MoveType,VehicleLocation,WeaponState
from systems import stability
from physics import heights
from core.game_loop import mech_heartbeat
from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke


@step(r'a running mech with gyro damage and posture (UPRIGHT|FALLEN|JUMPING|OOD)')
def posture(w,value):
    u=w['unit'];u.speed=u.desired_speed=60;u.set_crit_status(C.GYRO_DAMAGED)
    if value=='FALLEN':u.set_status(S.FALLEN)
    elif value=='JUMPING':u.set_status(S.JUMPING)
    elif value=='OOD':u.cocoon=10


@step(r'pilot maintenance runs at event tick (\d+) with a successful piloting roll')
def maintenance(w,tick):
    w['engine'].events.set_tick(int(tick));w['dice']['pilot_rolls']=12
    invoke(w,stability.update_pilot_skill_rolls,w['engine'],w['unit'])


@step(r'stability roll count is (\d+)')
def checks(w,count):
    equal(len(w['rolls']),int(count))


@step(r'an upright mech in special gravity with movement (BIPED|QUAD) actual speed '+N+r' and base maximum speed 64.5 KPH')
def gravity(w,movement,speed):
    u=w['unit'];u.move_type=MoveType[movement];u.speed=float(speed);u.set_status(S.UNDERSPECIAL | S.UNDERGRAVITY);w['map'].grav=150
    for section in u.sections:section.internal=1000
    w['internal_before']=[s.internal for s in u.sections]


@step(r'the turn-boundary gravity piloting check fails')
def gravity_check(w):
    w['engine'].events.set_tick(30);w['dice']['pilot_rolls']=2
    invoke(w,stability.update_pilot_skill_rolls,w['engine'],w['unit'])


@step(r'each intact leg takes (\d+) internal damage and injured limbs number (\d+)')
def injured(w,damage,limbs):
    differences=[n-s.internal for n,s in zip(w['internal_before'],w['unit'].sections)]
    equal([v for v in differences if v],[int(damage)]*int(limbs))


@step(r'no gravity-induced fall occurs')
def not_fallen(w):equal(w['unit'].is_fallen,False)


@step(r'a stationary vehicle with automatic turret flag enabled hull facing (\d+) turret facing 17 and a target at absolute bearing (\d+)')
def turret(w,hull,bearing):
    import math
    u=w['unit'];u.unit_type=UnitType.VEH_GROUND;u.move_type=MoveType.TRACK;u.set_status2(S2.AUTOTURN_TURRET)
    u.facing=int(hull);u.turret_facing=17;u.sections[VehicleLocation.TURRET].internal=100
    # The fixture specifies the source's reported bearing. Negative atan2
    # rounding biases non-cardinal bearings by one degree; use the interval midpoint.
    angle=int(bearing)-1.0 if int(bearing) else 0
    target=Mech.create_test_mech();target.fx=u.fx+math.sin(math.radians(angle))*100;target.fy=u.fy-math.cos(math.radians(angle))*100
    from physics.hexmath import find_bearing
    equal(find_bearing(u.fx,u.fy,target.fx,target.fy),int(bearing))
    w['map'].mechs_on_map.append(target);u.target=target._id;u.mapflag=0


@step(r'its turret eligibility state is (READY|JAMMED|LOCKED|DESTROYED_TURRET|STOPPED|UNCONSCIOUS|BLINDED)')
def turret_state(w,state):
    u=w['unit']
    if state=='JAMMED':u.turret_jammed=True
    elif state=='LOCKED':u.turret_locked=True
    elif state=='DESTROYED_TURRET':u.sections[VehicleLocation.TURRET].internal=0
    elif state=='STOPPED':u.clear_status(S.STARTED)
    elif state=='UNCONSCIOUS':u.set_status(S.UNCONSCIOUS)
    elif state=='BLINDED':u.set_status(S.BLINDED)


@step(r'relative turret facing is (\d+) and turret tracking marks LOS '+B)
def turret_result(w,facing,los):
    equal(w['unit'].turret_facing,int(facing));equal(bool(w['unit'].mapflag&1),boolean(los))


@step(r'a functional weapon with recycle 4 and temporary failure (NONE|TEMPORARY)')
def recycle(w,failure):
    from entities.weapon import get_weapon
    from entities.crittypes import i2weapon
    weapon=get_weapon('IS.MediumLaser');u=w['unit']
    u.weapons=[WeaponState(weapon_idx=weapon.index,section=Location.LARM,critical=4,recycle=4)]
    slot=u.sections[Location.LARM].criticals[4];slot.type=i2weapon(weapon.index);slot.data=4;set_part_temp_nuke(slot,0 if failure=='NONE' else 1)
    w['slot']=slot


@step(r'event time advances (\d+) seconds and one heartbeat runs')
def recycle_tick(w,seconds):
    w['engine'].events.set_tick(int(seconds));invoke(w,mech_heartbeat,w['engine'],w['unit'])


@step(r'weapon and first-slot recycle are (\d+) temporary failure is (NONE|TEMPORARY) and completion notice is (NONE|READY|OPERATIONAL)')
def recycled(w,remaining,failure,notice):
    equal((w['unit'].weapons[0].recycle,w['slot'].data),(int(remaining),int(remaining)))
    equal(part_temp_nuke(w['slot']),0 if failure=='NONE' else 1)
    messages=w['unit'].movement_messages
    actual='OPERATIONAL' if any('operational' in s for s in messages) else 'READY' if any('finished recycling' in s for s in messages) else 'NONE'
    equal(actual,notice)


@step(r'a live unit of class (MW|MECH|VEH_GROUND|VTOL) movement (BIPED|TRACK|VTOL) enters cached FIRE terrain')
def fiery(w,kind,movement):
    w['unit'].unit_type=UnitType[kind];w['unit'].move_type=MoveType[movement];terrain(w,'FIRE')


@step(r'movement reaches the fiery-death check')
def death(w):invoke(w,heights.fiery_death,w['unit'])


@step(r'the unit is destroyed '+B+r' with reason (HEAT|NONE)')
def destroyed(w,value,reason):
    equal(w['unit'].is_destroyed,boolean(value));equal(getattr(w['unit'],'kill_reason','') or 'NONE',reason)


@step(r'a dropship last announced at event tick (\d+)')
def last_notice(w,last):w['unit'].last_dropship_notice=int(last)


@step(r'a throttled dropship descent notice is requested at event tick (\d+)')
def notice(w,now):w['notice']=heights.dropship_notice(w['unit'],int(now))


@step(r'the notice is emitted '+B+r' and last notice tick is (\d+)')
def noticed(w,emitted,last):equal(w['notice'],boolean(emitted));equal(w['unit'].last_dropship_notice,int(last))


@step(r'a submarine in water with lower elevation (-?\d+) at Z (-?\d+) and FZ '+N+r' diving at 10.75 KPH')
def submarine(w,bottom,z,fz):
    u=w['unit'];u.unit_type=UnitType.VEH_NAVAL;u.move_type=MoveType.SUB;terrain(w,'WATER',bottom)
    u.z=int(z);u.fz=float(fz);u.vertical_speed=-10.75;w['previous_z']=u.z


@step(r'the movement height-maintenance boundary is reached')
def height(w):invoke(w,heights.maintain_height,w['unit'],w.get('previous_z',w['unit'].z))


@step(r'submarine Z is (-?\d+) FZ is '+N+r' and vertical speed is '+N)
def sub_result(w,z,fz,vertical):
    equal(w['unit'].z,int(z));near(w['unit'].fz,fz);near(w['unit'].vertical_speed,vertical)


@step(r'a naval unit on (WATER|ICE|BRIDGE|GRASSLAND|HIGHWATER) with previous Z -1 current Z 0 FZ 1 vertical speed 10.75 speed 21.5 desired speed 32.25 and both facings 90')
def naval(w,name):
    u=w['unit'];u.unit_type=UnitType.VEH_NAVAL;u.move_type=MoveType.SUB;terrain(w,name,2)
    u.z=0;u.fz=1;u.vertical_speed=10.75;u.speed=21.5;u.desired_speed=32.25;u.facing=u.desired_facing=90;w['previous_z']=-1


@step(r'vertical speed is zero')
def vertical_zero(w):near(w['unit'].vertical_speed,0)


@step(r'FZ is '+N+r' actual speed is '+N+r' desired speed is '+N+r' and both facings are (\d+)')
def grounded(w,fz,speed,desired,facing):
    u=w['unit'];near(u.fz,fz);near(u.speed,speed);near(u.desired_speed,desired);equal((u.facing,u.desired_facing),(int(facing),int(facing)))


@step(r'an airborne VTOL on (WATER|GRASSLAND) at Z (-?\d+) with FZ equal to Z times 64.5 and vertical speed '+N)
def vtol(w,name,z,vertical):
    u=w['unit'];u.unit_type=UnitType.VTOL;u.move_type=MoveType.VTOL;terrain(w,name,2 if name=='WATER' else 0)
    u.z=int(z);u.fz=u.z*64.5;u.vertical_speed=float(vertical);u.fuel=100


@step(r'destroyed is '+B+r' final Z is (-?\d+) and final vertical speed is '+N)
def vtol_result(w,destroyed,z,vertical):
    equal(w['unit'].is_destroyed,boolean(destroyed));equal(w['unit'].z,int(z));near(w['unit'].vertical_speed,vertical)


@step(r'an airborne VTOL at Z (-?\d+) over (MOUNTAINS|BRIDGE) with signed elevation 3 vertical speed -21.5 desired speed 21.5 and a landing site that the real landing rules reject')
def landing(w,z,name):
    vtol(w,'GRASSLAND',z,-21.5);terrain(w,name,3);w['unit'].desired_speed=21.5
    w['dice']['pilot_rolls']=12


@step(r'a crash occurred '+B+r' landed is '+B+r' and final Z is (-?\d+)')
def landed(w,crash,landed,z):
    equal(hasattr(w['unit'],'last_fall_levels'),boolean(crash));equal(w['unit'].has_status(S.LANDED),boolean(landed));equal(w['unit'].z,int(z))
