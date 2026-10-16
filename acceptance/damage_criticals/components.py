from . import *
from systems import criticals as cr, damage as dmg, vehicle_combat as vc
from core.events import EventType

@step(r'a MECH with LRS (\d+) tactical (\d+) scan (\d+) and base to hit (\d+)')
def sensors(w,lrs,tac,scan,bth):setup(w,lrs_range=int(lrs),tac_range=int(tac),scan_range=int(scan),base_to_hit=int(bth))

@step(r'(\d+) distinct functional sensor criticals occur')
def sensor_hits(w,count):
    for i in range(int(count)):
        unit(w).sections[4].criticals[i].type=i2special(Special.SENSORS);call(w,cr.apply_critical_to_slot,unit(w),4,i)

@step(r'LRS is (\d+) tactical is (\d+) scan is (\d+) and base to hit is (\d+)')
def sensor_result(w,lrs,tac,scan,bth):eq((unit(w).lrs_range,unit(w).tac_range,unit(w).scan_range,unit(w).base_to_hit),tuple(map(int,(lrs,tac,scan,bth))))

@step(r'a started repairable MECH with engine heat (\d+) and no other destroyed sections')
def engine_fixture(w,heat):unit(w).engine_heat=int(heat);unit(w).sections[4].criticals[0].type=i2special(Special.ENGINE)

@step(r'one functional engine critical occurs')
def engine_hit(w):call(w,cr.apply_critical_to_slot,unit(w),4,0)

@step(r'engine heat is (\d+) unit destroyed is (True|False) and no reactor explosion is triggered')
def engine_result(w,heat,dead):eq(unit(w).engine_heat,int(heat));eq(unit(w).is_destroyed,truth(dead));eq(bool(getattr(unit(w),'reactor_exploded',False)),False)

@step(r'a special engine slot with condition (\w+) brand (\d+) temporary failure (\d+) effect flags (\d+) and data (\d+)')
def broken_engine(w,condition,brand,temp,flags,data):
    from systems.enhanced_crits import set_part_temp_nuke
    s=unit(w).sections[4].criticals[0];s.type=i2special(Special.ENGINE);s.brand=int(brand);set_part_temp_nuke(s,int(temp));s.weap_damage_flags=int(flags);s.data=int(data)
    s.firemode={'functional':0,'broken':F.BROKEN_MODE,'disabled':F.DISABLED_MODE}[condition]

@step(r'engine heat is zero')
def noheat(w):unit(w).engine_heat=0

@step(r'that slot receives a critical')
def slot_hit(w):call(w,cr.apply_critical_to_slot,unit(w),4,0)

@step(r'it is destroyed with brand (\d+) temporary failure zero effect flags zero data (\d+) and engine heat (\d+)')
def slot_result(w,brand,data,heat):
    s=unit(w).sections[4].criticals[0];eq(bool(s.firemode&F.DESTROYED_MODE),True);eq((s.brand,s.weap_damage_flags,s.data,unit(w).engine_heat),tuple(map(int,(brand,'0',data,heat))))

@step(r'a MECH with ten dissipation capacity and a complete (\S+) heat sink group')
def sinks(w,kind):
    u=unit(w);w['sink']=kind
    u.specials|={'single':0,'IS-double':Specials.DOUBLE_HEAT_TECH,'Clan-double':Specials.CLAN_TECH}[kind]
    u.num_sinks=10 if kind=='single' else 5
    for i in range({'single':1,'IS-double':3,'Clan-double':2}[kind]):u.sections[0].criticals[i].type=i2special(Special.HEAT_SINK)

@step(r'sink loss occurs through (\S+)')
def sink_hit(w,path):
    w['sinkpath']=path
    if path=='direct-critical':call(w,cr.apply_critical_to_slot,unit(w),0,0)
    elif path=='hit-location':call(w,dmg.destroy_heat_sink,unit(w),0)
    elif path=='section-destruction':call(w,dmg.destroy_section,unit(w),None,0)
    else:raise AssertionError(path)

@step(r'remaining dissipation capacity is (\d+) and no second hit on its nonfunctional run repeats that loss')
def sink_result(w,capacity):
    eq(unit(w).effective_heat_sinks,int(capacity))
    if w['sinkpath']=='hit-location':call(w,dmg.destroy_heat_sink,unit(w),0)
    else:call(w,cr.apply_critical_to_slot,unit(w),0,0)
    eq(unit(w).effective_heat_sinks,int(capacity))

@step(r'a jumping MECH with (\d+) jump MP and one improved two-slot jet group at the hit location')
def jets(w,count):
    u=unit(w);u.specials2|=0x80;u.jump_mp=int(count);u.jump_speed=int(count)*10.75;u.status|=S.JUMPING
    for s in u.sections[0].criticals[:2]:s.type=i2special(Special.JUMP_JET)

@step(r'a functional slot in that group takes a critical from an attacker')
def jet_hit(w):call(w,cr.apply_critical_to_slot,unit(w),0,0,session(w).units['enemy'])

@step(r'jump MP is (\d+) the paired slot is nonfunctional and a real fall occurs (True|False)')
def jet_result(w,count,fall):eq(unit(w).jump_mp,int(count));eq(bool(unit(w).sections[0].criticals[1].firemode & (F.BROKEN_MODE|F.DESTROYED_MODE)),True);eq(unit(w).is_fallen,truth(fall))

@step(r'active equipment (\S+) with its linked consumer configured')
def equipment(w,name):
    w['equipment']=name
    kind={'C3-slave':Special.C3_SLAVE,'C3i':Special.C3I,'TAG':Special.TAG,'ECM':Special.ECM,'Angel-ECM':Special.ANGELECM,'Artemis':Special.ARTEMIS_IV,'null-signature':Special.NULL_SIGNATURE_SYSTEM,'DS-mechdoor':Special.DS_MECHDOOR}[name]
    u=unit(w);u.sections[4].criticals[0].type=i2special(kind);u.sections[4].criticals[0].data=1
    u.status2|=0x3C3
    from entities.mech import AmmoMode
    u.sections[4].criticals[1].ammomode|=AmmoMode.ARTEMIS_MODE
    u.c3i_network=[session(w).units['enemy']];session(w).units['enemy'].c3i_network=[u]

@step(r'a functional equipment critical occurs')
def equip_hit(w):call(w,cr.apply_critical_to_slot,unit(w),4,0,session(w).units['enemy'])

@step(r'the observable consequence is (\S+)')
def equip_result(w,consequence):
    u=unit(w)
    if consequence=='C3-destroyed':eq(bool(u.crit_status&C.C3_DESTROYED),True)
    elif consequence=='network-cleared':eq(u.c3i_network,[]);eq(session(w).units['enemy'].c3i_network,[])
    elif consequence=='TAG-destroyed-and-source-caller-validated':eq(bool(u.crit_status&C.TAG_DESTROYED),True)
    elif consequence=='ECM-ECCM-and-stealth-off':eq(u.status2&0x43,0)
    elif consequence=='Angel-ECM-ECCM-off':eq(u.status2&0x300,0)
    elif consequence=='linked-ammo-mode-cleared':eq(u.sections[4].criticals[1].ammomode&2,0)
    elif consequence in ('off-and-destroyed','door-and-null-signature-destroyed'):eq(u.status2&0x80,0);eq(bool(u.crit_status&C.NSS_DESTROYED),True)
    else:raise AssertionError(consequence)

ACTUATORS={'hand':Special.HAND_OR_FOOT_ACTUATOR,'upper':Special.UPPER_ACTUATOR,'lower':Special.LOWER_ACTUATOR,'shoulder':Special.SHOULDER_OR_HIP,'hip':Special.SHOULDER_OR_HIP}
def actuator(unit,location,kind,index=0):
    s=unit.sections[location].criticals[index];s.type=i2special(ACTUATORS[kind]);s.firemode=F.DESTROYED_MODE

@step(r'an intact biped arm with destroyed actuator set ([\w,]+)')
def arm(w,kinds):
    for i,kind in enumerate(kinds.split(',')):actuator(unit(w),0,kind,i)

@step(r'damaged-location normalization runs twice')
def normalize_arm(w):
    w['normalizations']=[]
    for _ in range(2):cr.normalize_location_actuators(unit(w),0);w['normalizations'].append(unit(w).sections[0].basetohit)

@step(r'arm weapon BTH is (\d+) after each run')
def arm_result(w,bth):eq(w['normalizations'],[int(bth)]*2)

@step(r'a (biped|quad) with template max speed ([\d.]+) and (\d+) destroyed legs without other criticals')
def legs(w,chassis,speed,lost):
    u=unit(w);u.template_max_speed=u.max_speed=float(speed);u.move_type=M.QUAD if chassis=='quad' else M.BIPED
    for loc in ((0,1,5,6) if chassis=='quad' else (5,6))[:int(lost)]:u.sections[loc].armor=u.sections[loc].internal=0

@step(r'a biped with template max speed ([\d.]+) a destroyed left hip and right leg actuator state (\S+)')
def hips(w,speed,right):
    u=unit(w);u.template_max_speed=u.max_speed=float(speed);actuator(u,5,'hip');u.crit_status|=C.HIP_DAMAGED
    if right!='intact':actuator(u,6,right.split('-')[0])
    if right=='hip-destroyed':u.crit_status|=C.HIP_DESTROYED

@step(r'complete actuator normalization runs twice')
def normalize_all(w):
    w['normalizations']=[]
    for _ in range(2):call(w,cr.recalculate_mech_stats,unit(w));w['normalizations'].append((unit(w).max_speed,unit(w).pilot_skill_base,unit(w).is_fallen))

@step(r'max speed is ([\d.]+) pilot skill base is (\d+) and fallen is (True|False) after each run')
def legs_result(w,speed,psr,fallen):eq(w['normalizations'],[(float(speed),int(psr),truth(fallen))]*2)

@step(r'max speed is ([\d.]+) and pilot skill base is (\d+) after each run')
def hips_result(w,speed,psr):eq([v[:2] for v in w['normalizations']],[(float(speed),int(psr))]*2)

@step(r'a standing MECH with gyro (\w+) and all requested piloting rolls passing')
def gyro(w,kind):
    if kind=='hardened':unit(w).specials2|=0x400000
    else:eq(kind,'standard')

@step(r'(\d+) distinct gyro slots take criticals from an attacker')
def gyros(w,count):
    for i in range(int(count)):
        unit(w).sections[4].criticals[i].type=i2special(Special.GYRO);call(w,cr.apply_critical_to_slot,unit(w),4,i,session(w).units['enemy'])

@step(r'hardened damage is (True|False) gyro damaged is (True|False) gyro destroyed is (True|False) and actual fallen state is (True|False)')
def gyro_result(w,hard,damaged,destroyed,fallen):
    u=unit(w);eq((bool(getattr(u,'crit_status2',0)&1),bool(u.crit_status&C.GYRO_DAMAGED),bool(u.crit_status&C.GYRO_DESTROYED),u.is_fallen),tuple(map(truth,(hard,damaged,destroyed,fallen))))

@step(r'cargo-adjusted maximum (\d+) current speed (-?\d+) and desired speed (-?\d+)')
def speeds(w,maximum,current,desired):setup(w,max_speed=int(maximum),speed=int(current),desired_speed=int(desired))

@step(r'damage speed correction runs')
def correct(w):vc.correct_speed(unit(w))

@step(r'current speed is (-?\d+) and desired speed is (-?\d+)')
def speed_result(w,current,desired):eq((unit(w).speed,unit(w).desired_speed),(int(current),int(desired)))

@step(r'class (\w+) with combat safe (True|False) critproof (True|False) and vehicle-critical setting (\d+)')
def dispatch_fixture(w,kind,safe,proof,vcrit):
    u=setup(w,kind);session(w).engine.vcrit=int(vcrit)
    if truth(safe):u.status|=S.COMBAT_SAFE
    if truth(proof):u.specials|=Specials.CRITPROOF_TECH

@step(r'one torso critical is requested with MW gate draw (\d+) and a functional special slot')
def dispatch(w,roll):
    unit(w).sections[4].criticals[0].type=i2special(Special.LIFE_SUPPORT);draw(w,'critical_mw_gate',[int(roll)])
    w['results']=call(w,cr.check_and_apply_criticals,unit(w),4,1)

@step(r'slot dispatch count is (\d+)')
def dispatch_result(w,count):eq(len(w['results']),int(count))

@step(r'a torso with candidate kinds ([\w,-]+) in that order and all remaining slots empty')
def candidates(w,kinds):
    for i,kind in enumerate(kinds.split(',')):
        s=unit(w).sections[4].criticals[i]
        if kind=='damaged-weapon':s.type=i2weapon(get_weapon('IS.MediumLaser').index);s.firemode=F.DAMAGED_MODE
        else:
            s.type=i2special(Special[kind.removeprefix('disabled-')]);s.firemode=F.DISABLED_MODE if kind.startswith('disabled-') else 0

@step(r'(\d+) criticals repeatedly select eligible index zero')
def candidate_hits(w,count):w['results']=call(w,cr.check_and_apply_criticals,unit(w),4,int(count))

@step(r'destroyed slot indices are ([\w,]+) and no critical transfers to another section')
def candidate_result(w,indices):
    eq([i for i,s in enumerate(unit(w).sections[4].criticals) if s.firemode&F.DESTROYED_MODE],[] if indices=='none' else list(map(int,indices.split(','))))
    eq(any(s.firemode&F.DESTROYED_MODE for i,section in enumerate(unit(w).sections) if i!=4 for s in section.criticals),False)

@step(r'an intact MECH head containing a cockpit and life support as the only eligible slots')
def head_dispatch(w):
    for i,kind in enumerate((Special.COCKPIT,Special.LIFE_SUPPORT)):unit(w).sections[7].criticals[i].type=i2special(kind)

@step(r'two criticals repeatedly select eligible index zero')
def head_hits(w):w['results']=call(w,cr.check_and_apply_criticals,unit(w),7,2)

@step(r'cockpit and life support slots are destroyed and both critical requests are consumed')
def head_dispatch_result(w):eq(len(w['results']),2);eq([bool(s.firemode&F.DESTROYED_MODE) for s in unit(w).sections[7].criticals[:2]],[True,True])
