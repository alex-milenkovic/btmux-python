# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.advanced.c
#   btech/mech.combat.c
#   btech/mech.combat.misc.c
#   btech/mech.events.c
#   btech/mech.utils.c

"""Source ammunition checks, expenditure and warning thresholds."""
from core.randomness import roll as source_roll
from dataclasses import dataclass
from entities.mech import FireMode as F,AmmoMode as A,CritStatus
from entities.weapon import get_weapon_by_index,WeaponType as T,WeaponFlags as W
from entities.crittypes import i2ammo,crits_in_loc
from systems.movement_commands import notify


@dataclass
class AmmoPlan:
    accepted: bool=True
    message: str=''
    first: object=None
    second: object=None
    gattling_shots: int=0


def count_ammo(unit,index):
    from systems.combat import part_is_nonfunctional
    return sum(slot.data for loc,sec in enumerate(unit.sections) for pos,slot in enumerate(sec.criticals)
        if slot.type==i2ammo(index) and slot.data>0 and not part_is_nonfunctional(unit,loc,pos))


def find_and_check(unit,ws,gattling_shots=0):
    from systems.combat import find_ammo_for_weapon
    from systems.weapon_modes import ammo_mode_filters
    weapon=get_weapon_by_index(ws.weapon_idx)
    slot=unit.sections[ws.section].criticals[ws.critical]
    mode=slot.firemode
    plan=AmmoPlan(gattling_shots=gattling_shots)
    def reject(message):
        from systems.notifications import personal_notify
        actor = getattr(unit, 'gun_pilot', None) or unit.pilot
        personal_notify(actor, message)
        plan.accepted, plan.message = False, message
        return plan
    if weapon.weapon_type in (T.TBEAM,T.THAND):return plan
    if weapon.special==W.ROCKET or mode&F.OS_MODE:
        used=F.ROCKET_FIRED if weapon.special==W.ROCKET else F.OS_USED
        if mode&used:return reject('That weapon has already been used!')
        return plan
    if weapon.special&W.RAC:
        for bit,rounds in ((F.RAC_TWOSHOT_MODE,2),(F.RAC_FOURSHOT_MODE,4),(F.RAC_SIXSHOT_MODE,6)):
            if mode&bit and count_ammo(unit,ws.weapon_idx)<rounds:
                slot.firemode = F(int(slot.firemode) & ~int(bit))
                # C returns before filling ammoLoc. Decrement's RAC branch
                # searches its own bins, so it needs no first-bin pointer.
                return plan
    if mode&F.GATTLING_MODE:
        plan.gattling_shots=min(gattling_shots,max(count_ammo(unit,ws.weapon_idx)//3,1))
    nogof,gof=ammo_mode_filters(slot,weapon)
    first=find_ammo_for_weapon(unit,ws.weapon_idx,ws.section,nogof,gof,critical=ws.critical)
    if first is None:
        return reject("You don't have any ammo for that weapon stored on this mech!")
    loc,pos=first
    ws.ammo_section,ws.ammo_critical=int(loc),pos
    plan.first=unit.sections[loc].criticals[pos]
    if mode&(F.ULTRA_MODE|F.RFAC_MODE):
        plan.first.data-=1
        try:second=find_ammo_for_weapon(unit,ws.weapon_idx,ws.section,nogof,gof,critical=ws.critical)
        finally:plan.first.data+=1
        if second is None:slot.firemode &= ~mode
        else:plan.second=unit.sections[second[0]].criticals[second[1]]
    return plan


def expenditure_check(unit,index,offset):
    unit.clear_crit_status(CritStatus.OWEIGHT_OK)
    if unit.prefs&16:return None
    weapon=get_weapon_by_index(index)
    count=slots=0
    for loc,sec in enumerate(unit.sections):
        for slot in sec.criticals[:crits_in_loc(unit,loc)]:
            if slot.type!=i2ammo(index):continue
            count+=slot.data
            mod=1 if slot.firemode&F.HALFTON_MODE or slot.ammomode&(A.AC_AP_MODE|A.AC_PRECISION_MODE) else .5 if slot.ammomode&A.AC_CASELESS_MODE else 2
            slots=int(slots+mod)
    threshold=max(3,min(30,int(slots*weapon.ammo_per_ton/8)))
    severity=None
    for value,label in ((threshold,'red'),(threshold*2,'yellow')):
        if count==value+offset or offset and value<=count<value+offset:
            severity=label
            break
    if severity and unit.is_started and index%65536:
        from systems.notifications import mech_printf, MECHALL
        from data.construction_catalog import source_id
        from systems.status_display import catalog
        from entities.crittypes import i2weapon
        name = catalog().names(source_id(i2weapon(index)),0)[1]
        mech_printf(unit, MECHALL, '%sWARNING: Ammo for %s is running low.%%c', '%ch%cr' if severity == 'red' else '%ch%cy', name)
        return severity
    return None


def decrement(unit,index,ws,plan,*,source_number=False):
    from systems.combat import find_ammo_for_weapon
    if source_number:
        from entities.source_weapon_numbers import source_weapon
        weapon=source_weapon(index)
        index=weapon.index
    else:weapon=get_weapon_by_index(index)
    slot=unit.sections[ws.section].criticals[ws.critical]
    mode=slot.firemode
    if weapon.weapon_type in (T.TBEAM,T.THAND):return
    if weapon.special==W.ROCKET:
        from systems.enhanced_crits import get_weap_data
        _,size,first=get_weap_data(unit,ws.section,ws.critical)
        for part in unit.sections[ws.section].criticals[first:first+size]:part.firemode|=F.ROCKET_FIRED
        return
    if mode&F.OS_MODE:
        slot.firemode|=F.OS_USED
        return
    expenditure_check(unit,index,max(plan.gattling_shots,int(bool(mode&(F.ULTRA_MODE|F.RFAC_MODE)))))
    if mode&F.GATTLING_MODE or weapon.special&W.RAC:
        rounds=plan.gattling_shots*3 if mode&F.GATTLING_MODE else 2 if mode&F.RAC_TWOSHOT_MODE else 4 if mode&F.RAC_FOURSHOT_MODE else 6 if mode&F.RAC_SIXSHOT_MODE else 1
        for _ in range(rounds):
            found=find_ammo_for_weapon(unit,index,ws.section,int(A.AMMO_MODES),0,critical=ws.critical)
            if found is None:break
            unit.sections[found[0]].criticals[found[1]].data-=1
    else:
        if plan.first is not None and plan.first.data:plan.first.data-=1
        if mode&(F.ULTRA_MODE|F.RFAC_MODE) and plan.second is not None and plan.second.data:plan.second.data-=1


def usebin(unit,text,*,caller=None,wizard=False):
    from systems.combat_commands import command_guard,read_number,parse_attributes,command_message
    from systems.weapon_modes import find_weapon_number_on_mech
    from systems.damage_commands import armor_section_from_string
    from systems.parts import armor_string
    def reply(ok,text,audience=None):
        command_message(unit,text,caller=caller,audience=audience)
        return dict(accepted=ok,text=text)
    error=command_guard(unit,started=False,caller=caller,wizard=wizard)
    if error:return reply(False,error)
    args=parse_attributes(text,2)
    if len(args)!=2:return reply(False,'Invalid number of arguments!')
    try:index=read_number(args[0])
    except ValueError:return reply(False,f'Invalid value: {args[0]}')
    code,loc,pos=find_weapon_number_on_mech(unit,index)
    errors={-1:"The weapons system chirps: 'Illegal Weapon Number!'",
            -2:"The weapons system chirps: 'That Weapon has been destroyed!'",
            -3:"The weapon system chirps: 'That weapon is still reloading!'",
            -4:"The weapon system chirps: 'That weapon is still recharging!'"}
    if code in errors:return reply(False,errors[code])
    slot=unit.sections[loc].criticals[pos]
    from entities.crittypes import weapon2i
    weapon=get_weapon_by_index(weapon2i(slot.type))
    if weapon.weapon_type==T.TBEAM:return reply(False,'Energy weapons do not use ammo!')
    if args[1].startswith('-'):
        answer=reply(True,f'Prefered ammo source reset for weapon #{index}',2)
        slot.desired_ammo_loc=-1
        return answer
    chosen=armor_section_from_string(unit,args[1])
    if chosen<0 or not unit.sections[chosen].internal_orig:return reply(False,'Invalid section!')
    if not unit.sections[chosen].internal:return reply(False,'That section is destroyed!')
    name=armor_string(unit,chosen)
    if slot.desired_ammo_loc==chosen:return reply(False,f'Prefered ammo source already set to {name} for weapon #{index}')
    answer=reply(True,f'Prefered ammo source set to {name} for weapon #{index}',2)
    slot.desired_ammo_loc=chosen
    return answer


def risky_mode_failure(unit,ws,result,plan):
    """FireWeapon's mode checks, preserving notices and first-run destruction."""
    from systems.enhanced_crits import set_part_temp_nuke,FAIL_AMMOJAMMED
    from systems.criticals import destroy_weapon,find_first_weapon_crit
    from systems.combat import roll_2d6,apply_damage_with_transfer
    from systems.movement_commands import notify
    from systems.sensors import los_broadcast
    from entities.mech import UnitType
    weapon=get_weapon_by_index(ws.weapon_idx)
    slot=unit.sections[ws.section].criticals[ws.critical]
    mode,rolled,name=slot.firemode,result.roll,weapon.name[3:]
    def emit(text):
        notify(unit,text);result.messages.append(text)
    def jam(loading=False):
        emit(f'%ch%crThe ammo {"loading" if loading else "loader"} mechanism jams on your {name}!%cn')
        set_part_temp_nuke(slot,FAIL_AMMOJAMMED)
    def destroy(explode=False,critical=False):
        size=weapon.crits if unit.unit_type==UnitType.MECH else 1
        first=find_first_weapon_crit(unit,ws.section,-1,0,slot.type,size)
        destroy_weapon(unit,ws.section,slot.type,first,size,size)
        if explode:
            los_broadcast(unit,'shudders from an internal explosion!')
            apply_damage_with_transfer(unit,ws.section,0,is_rear=False,is_critical=critical,
                attacker=unit,engine=unit._engine,internal_damage=weapon.damage,
                ignore_swarmers=True,cause=-1,bth=0,attack_pilot=-1,los=0)
            decrement(unit,ws.weapon_idx,ws,plan)
    if mode&F.HOTLOAD_MODE and rolled in (2,3):jam(True)
    elif slot.ammomode&A.AC_CASELESS_MODE and rolled in (2,3):
        jam(True)
        if source_roll('caseless_rolls',roll_2d6)>7:
            emit(f'%ch%crPropellant from your {name} ignites and destroys it!%cn')
            destroy(True,True)
    elif mode&F.RFAC_MODE and rolled<5:
        if rolled==2:
            emit(f'%ch%crA catastrophic misload on your {name} destroys it and causes an internal explosion!%cn')
            destroy(True)
        else:jam()
    elif weapon.special&W.RAC and (mode&F.RAC_TWOSHOT_MODE and rolled==2 or mode&F.RAC_FOURSHOT_MODE and rolled<=3 or mode&F.RAC_SIXSHOT_MODE and rolled<=4):jam()
    elif mode&F.ULTRA_MODE and rolled==2:
        emit(f'The loader jams on your {name}, destroying it!')
        destroy()
    else:return False
    result.shot_aborted=True
    return True


def ammo_capacity(base, firemode=0, ammomode=0):
    """FullAmmo's priority and integer half-up conversion."""
    if ammomode & (A.AC_AP_MODE | A.AC_PRECISION_MODE) or firemode & F.HALFTON_MODE:
        return base >> 1
    if ammomode & A.AC_CASELESS_MODE: return base << 1
    if ammomode & A.MML_LRM_MODE: return (base * 1200 + 500) // 1000
    return base


def full_ammo(unit, loc, pos):
    from entities.crittypes import ammo2weapon_i, is_ammo
    slot = unit.sections[loc].criticals[pos]
    if not is_ammo(slot.type): raise ValueError('FullAmmo requires an ammunition slot')
    weapon = get_weapon_by_index(ammo2weapon_i(slot.type))
    if weapon is None: raise ValueError('Unsupported ammunition catalog index')
    return ammo_capacity(weapon.ammo_per_ton, slot.firemode, slot.ammomode)


@dataclass
class AmmunitionGroup:
    weapon_idx: int
    mode: int
    current: int = 0
    maximum: int = 0


def find_ammunition(unit, returnall=False):
    from entities.crittypes import is_ammo, ammo2weapon_i
    from systems.combat import part_is_nonfunctional
    groups = {}
    for loc, section in enumerate(unit.sections):
        for pos, slot in enumerate(section.criticals):
            if not is_ammo(slot.type): continue
            key = (ammo2weapon_i(slot.type), int(slot.ammomode & A.AMMO_MODES))
            group = groups.setdefault(key, AmmunitionGroup(*key))
            if not part_is_nonfunctional(unit, loc, pos): group.current = (group.current + slot.data) & 0xffff
            group.maximum = (group.maximum + full_ammo(unit, loc, pos)) & 0xffff
    return [group for group in groups.values() if returnall or group.current]


def find_rounds_for_weapon(unit, index):
    from systems.combat import part_is_nonfunctional
    return sum(slot.data for loc, sec in enumerate(unit.sections) for pos, slot in enumerate(sec.criticals)
               if slot.type == i2ammo(index) and not part_is_nonfunctional(unit, loc, pos))


def find_normal_ammo_for_weapon(unit, index, start):
    """FindAmmoForWeapon wrapper excludes special rounds and bin preferences."""
    from systems.combat import find_ammo_for_weapon
    return find_ammo_for_weapon(unit, index, -1, int(A.AMMO_MODES), 0,
                                critical=-1, start=start)
