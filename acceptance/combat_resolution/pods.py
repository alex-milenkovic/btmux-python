"""Pod removal uses real arm actuators and the full event clock."""
from . import step,unit,session,call,dice,eq,armor
from .equipment import advance
from entities.mech import Location as L,FireMode as F,UnitType as U
from entities.crittypes import i2special,Special
from systems import combat_equipment as e


def arms(w):
    for loc in (L.LARM,L.RARM):
        for pos,kind in enumerate((Special.SHOULDER_OR_HIP,Special.UPPER_ACTUATOR,
                                   Special.LOWER_ACTUATOR,Special.HAND_OR_FOOT_ACTUATOR)):
            unit(w).sections[loc].criticals[pos].type=i2special(kind)


@step(r'matching homing pods on (CT|LARM|RARM) and available arms with left modifier (\d+) right modifier (\d+)')
def ready(w,loc,left,right):
    arms(w)
    w['pod_loc']={'CT':L.CTORSO,'LARM':L.LARM,'RARM':L.RARM}[loc]
    unit(w).sections[w['pod_loc']].specials|=2
    for arm,modifier in ((L.LARM,int(left)),(L.RARM,int(right))):
        if modifier:unit(w).sections[arm].criticals[1].firemode|=F.DESTROYED_MODE


@step(r'pod removal succeeds')
def remove(w):
    dice(w,'pod_rolls',[12])
    w['pod_result']=call(w,e.remove_pods_mech,unit(w),L(w['pod_loc']).name+' H')
    eq(w['pod_result']['removed'],True)


@step(r'selected arm is (LARM|RARM) and its recycle is 30 and selected pod is cleared')
def removed(w,arm):
    eq(w['pod_result']['arm'],int(L[arm]))
    eq(unit(w).sections[L[arm]].recycle,30)
    eq(bool(unit(w).sections[w['pod_loc']].specials&2),False)


@step(r'a 55-ton MECH with a CT homing pod and (\d+) broken arm actuators')
def miss_fixture(w,broken):
    arms(w)
    u=unit(w);u.tonnage=55;u.sections[L.CTORSO].specials|=2
    # Only the chosen arm is available.
    u.sections[L.RARM].recycle=1
    for pos in range(1,int(broken)+1):u.sections[L.LARM].criticals[pos].firemode|=F.DESTROYED_MODE
    w['pod_armor']=u.sections[L.CTORSO].armor


@step(r'pod removal misses using that arm')
def miss(w):
    dice(w,'pod_rolls',[2])
    w['pod_result']=call(w,e.remove_pods_mech,unit(w),'CT H')
    eq(w['pod_result']['removed'],False)


@step(r'direct CT self damage is (\d+) and the pod remains')
def missed(w,damage):
    eq(w['pod_result']['self_damage'],int(damage))
    eq(w['pod_armor']-unit(w).sections[L.CTORSO].armor,int(damage))
    eq(bool(unit(w).sections[L.CTORSO].specials&2),True)


@step(r'a tank carrying ordinary NARC and all four iNARC pod kinds')
def tank(w):
    unit(w).unit_type=U.VEH_GROUND
    unit(w).sections[0].specials|=0x1f


@step(r'removal starts at signed speed (-?\d+) and completes at tick 60')
def tank_remove(w,speed):
    unit(w).speed=unit(w).desired_speed=int(speed)
    eq(call(w,e.remove_pods_tank,unit(w))['accepted'],True)
    advance(w,60)


@step(r'ordinary NARC remains and all iNARC kinds are removed')
def tank_done(w):eq(unit(w).sections[0].specials&0x1f,1)
