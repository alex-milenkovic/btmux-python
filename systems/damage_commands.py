# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.build.c
#   btech/mech.damage.c
#   btech/mech.utils.c
# Historical Aerospace sources:
#   btech/mech.damage.c
#   btech/mech.utils.c

"""Administrative damage commands and location weapon queries."""
import re
from entities.mech import Location, VehicleLocation, AeroLocation, UnitType, FireMode
from entities.crittypes import i2weapon
from entities.weapon import get_weapon_by_index
from systems.movement_commands import notify


def section_index(unit, name):
    names = Location if unit.unit_type in (UnitType.MECH, UnitType.MW) else (
        AeroLocation if unit.unit_type == UnitType.AERO else VehicleLocation)
    aliases = dict(LA='LARM', RA='RARM', LL='LLEG', RL='RLEG', LT='LTORSO', RT='RTORSO', CT='CTORSO', HD='HEAD')
    key = aliases.get(str(name).upper(), str(name).upper())
    if key.isdigit() and 0 <= int(key) < 8:
        return int(key)
    if unit.unit_type in (UnitType.DS, UnitType.SPHEROID_DS):
        return armor_section_from_string(unit,name)
    return int(names[key]) if key in names.__members__ else armor_section_from_string(unit,name)


def atoi(text):
    match = re.match(r'\s*([+-]?\d+)', str(text))
    return int(match[1]) if match else 0


def set_armor_status(unit, section, kind, value):
    location = armor_section_from_string(unit, section)
    if location < 0 or not unit.sections[location].internal_orig:
        return '#-1 INVALID SECTION'
    value = atoi(value)
    if not 0 <= value <= 255:
        return '#-1 INVALID ARMORVALUE'
    kind = atoi(kind)
    if kind not in (0, 1, 2):
        return '#-1 INVALID ARMORTYPE'
    setattr(unit.sections[location], ('armor', 'internal', 'rear')[kind], value)
    return '1'


def dodamage(unit, total, cluster, direction, critical=0, message='', broadcast=''):
    from systems.combat import apply_damage_with_transfer, get_hit_location, HitGroup
    if total < 0 or (total > 0 and cluster <= 0) or not 0 <= direction <= 21:
        return dict(accepted=False, sizes=[], message='Invalid damage, cluster size or direction.')
    if message:
        notify(unit, message)
    if broadcast:
        from systems.sensors import los_broadcast
        los_broadcast(unit,broadcast)
    sizes = []
    while total > 0:
        location, rear = direction % 8, direction >= 8
        if direction > 15:
            # C directions 16..21 map through ((direction-1)&3)+1.
            group = ((direction-1)&3)+1
            location, _ = get_hit_location(unit, {1: HitGroup.LEFTSIDE, 2: HitGroup.RIGHTSIDE,
                                                    3: HitGroup.FRONT, 4: HitGroup.BACK}[group])
            rear = direction > 18
        amount = min(cluster, total)
        apply_damage_with_transfer(unit, location, amount, rear, unit,
            is_critical=bool(critical), engine=unit._engine, ignore_swarmers=True, cause=0, los=0, attack_pilot=-1)
        sizes.append(amount)
        total -= amount
    return dict(accepted=True, sizes=sizes, message='1')


def damage_command(unit, arguments, section=False, *, caller=None):
    from systems.combat import apply_damage_with_transfer
    from systems.combat_commands import read_number
    from core.effects import notify_actor
    actor = unit.pilot if caller is None else caller
    def reject(message):
        for line in message.split('\n'):notify_actor(unit,actor,line)
        return dict(accepted=False,sizes=[],message=message)
    args = arguments.split()
    if len(args) != 4:
        return reject('Invalid Arguments: <SECTION> <DAMAGE> <ISREAR> <ISCRITICAL>' if section else 'Invalid arguments!')
    if section:
        location = armor_section_from_string(unit,args[0])
        if location < 0:
            from systems.construction_editor import invalid_section
            return reject('\n'.join(invalid_section(unit)))
        labels = ('Invalid damage (Arg 2) amount! (Must be a number!)','Isrear value (Arg 3) Invalid! (1 or 0)','Iscritical value (Arg 4) Invalid! (1 or 0)')
        tokens = args[1:]
    else:
        labels = ('Invalid damage!','Invalid cluster size!','Invalid isrear flag!','Invalid iscritical flag!')
        tokens = args
    values = []
    for token,label in zip(tokens,labels):
        try:values.append(read_number(token))
        except ValueError:return reject(label)
    if section:
        total,rear,critical = values
        if not 0 < total <= 1000:return reject('Invalid damage (Arg 2 amount! (Must be >0 or <1000)')
        apply_damage_with_transfer(unit,location,total,bool(rear),unit,is_critical=bool(critical),
                                   ignore_swarmers=True,cause=0,attack_pilot=-1,los=0)
        sizes = [total]
    else:
        total,cluster,rear,critical = values
        if not 0 < total <= 1000:return reject('Invalid damage!')
        if cluster <= 0:return reject('Invalid cluster size!')
        if cluster > total:return reject('Invalid cluster size! (must be smaller than damage amount, but > 0)')
        if unit.unit_type == UnitType.MW:return reject('No MW killings!')
        from systems.missile import missile_hit
        from systems.personal_damage import personal_to_damage
        from systems.piloting import valid_pilot
        weapon = get_weapon_by_index(0)
        pilot = valid_pilot(unit,True)
        def apply(location,amount,rear,critical):
            return apply_damage_with_transfer(unit,location,personal_to_damage(unit,weapon,amount),rear,unit,
                is_critical=critical,weapon=weapon,w_ammo_mode=-1,bth=0,los=0,attack_pilot=pilot,cause=0)
        result = missile_hit(unit,unit,weapon,cluster,total//cluster,1,fire_mode=-1,ammo_mode=-1,damage_func=apply)
        sizes = [group[1] for group in result.groups]
    return dict(accepted=True,sizes=sizes,message='1')


def location_weapons(unit, location):
    """Source enumeration starts at global weapon one and stops only at -1."""
    from systems.weapon_modes import find_weapon_number_on_mech
    result = []
    number = 1
    while True:
        code, section, critical = find_weapon_number_on_mech(unit, number)
        if code == -1:
            return result
        if section == location:
            result.append((code, section, critical))
        number += 1


def count_weapons_in_location(unit, location):
    return len(location_weapons(unit, location))


def find_weapon_type_num_in_location(unit, location, ordinal):
    weapons = location_weapons(unit, location)
    return weapons[ordinal-1][0] if 1 <= ordinal <= len(weapons) else -1


def lose_weapon(unit, location):
    from systems.vehicle_combat import vehicle_draw
    from systems.criticals import destroy_weapon, find_first_weapon_crit
    count = count_weapons_in_location(unit, location)
    if not count:
        return
    if unit.unit_type in (UnitType.AERO, UnitType.DS, UnitType.SPHEROID_DS):
        # Historical random()%count + 1; a single candidate is ordinal one.
        from core.randomness import draw
        import random
        ordinal=draw('fighter_weapon_choice',0,count-1,lambda:random.randrange(count))+1
    else:
        ordinal=vehicle_draw('lose_weapon',1,count)
    index = find_weapon_type_num_in_location(unit, location, ordinal)
    if index < 0:
        return
    weapon = get_weapon_by_index(index)
    size = weapon.crits if unit.unit_type == UnitType.MECH else 1
    first = find_first_weapon_crit(unit, location, -1, 0, i2weapon(index), size)
    destroy_weapon(unit, location, i2weapon(index), first, 1, size)
    notify(unit,f'%ch%crYour {weapon.name[3:]} is destroyed!%c')


def section_names(unit):
    """ProperSectionStringFromType tables in mech.utils.c."""
    from entities.mech import MoveType
    if unit.unit_type==UnitType.BSUIT:return tuple(f'Suit {i}' for i in range(1,9))
    if unit.unit_type in (UnitType.MECH,UnitType.MW):
        return ('Front Left Leg','Front Right Leg','Left Torso','Right Torso','Center Torso','Rear Left Leg','Rear Right Leg','Head') if unit.move_type==MoveType.QUAD else ('Left Arm','Right Arm','Left Torso','Right Torso','Center Torso','Left Leg','Right Leg','Head')
    if unit.unit_type==UnitType.AERO:return ('Nose','Left Wing','Right Wing','Fuselage','Cockpit','Engine')
    if unit.unit_type==UnitType.DS:return ('Right Wing','Left Wing','Left Rear Wing','Right Rear Wing','Aft','Nose')
    if unit.unit_type==UnitType.SPHEROID_DS:return ('Front Right Side','Front Left Side','Rear Left Side','Rear Right Side','Aft','Nose')
    if unit.unit_type in (UnitType.VEH_GROUND, UnitType.VEH_NAVAL, UnitType.VTOL):
        return ('Left Side','Right Side','Front Side','Aft Side','Turret','Rotor')
    return None


def short_section(unit,location):
    names=section_names(unit)
    if not names or not 0<=location<len(names):raise ValueError('Invalid section')
    return ''.join(char for char in names[location] if char.isupper() or char.isdigit())


def armor_section_from_string(unit,text):
    """Source's ordered first/second-initial disambiguation, including quirks."""
    names=section_names(unit)
    text=str(text).upper()
    if not text or not names:return -1
    for i,name in enumerate(names):
        if name.upper()==text:return i
    for i,name in enumerate(names):
        if text[0]!=name[0]:continue
        j=next((j for j in range(i+1,len(names)) if names[j][0]==text[0]),None)
        if j is None:return i
        left=name.partition(' ')[2];right=names[j].partition(' ')[2]
        if not left and len(text)==1 and right:return i
        if not left and not right:return -1
        if len(text)==1:continue
        if left and text[1]==left[0]:return i
        if right and text[1]==right[0]:return j
    return -1
