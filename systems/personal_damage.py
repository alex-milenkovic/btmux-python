# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btechstats.c
#   btech/mech.startup.c
#   btech/pcombat.c

"""Bounded personal damage conversion and armor metadata from pcombat.c."""
import random
from core.randomness import draw, float32
from data.characters import divide, remainder
from entities.weapon import WeaponFlags as W
from entities.mech import UnitType

PCOMBAT = W.PC_IMPA | W.PC_HEAT | W.PC_SHAR
# location, armor ID, defended weapon flags, minimum, percentage, maximum
ARMORS = (
 (7,1,W.PC_IMPA|W.PC_HEAT,10,30,30),
 (7,2,PCOMBAT,20,50,60),
 (1,1,W.PC_SHAR|W.PC_HEAT,10,30,20),
 (1,2,PCOMBAT,20,50,60),
 (6,1,W.PC_SHAR|W.PC_IMPA,20,40,50),
 (6,2,PCOMBAT,40,50,100),
 (4,1,W.PC_SHAR,20,30,60),
 (4,2,W.PC_IMPA|W.PC_HEAT,30,40,80),
 (4,3,PCOMBAT,40,50,100),
 (4,4,W.PC_SHAR,40,50,80),
 (4,5,W.PC_IMPA|W.PC_HEAT,40,50,80),
 (4,6,PCOMBAT,50,50,120),
 (4,7,PCOMBAT,50,70,120),
 (4,8,PCOMBAT,60,80,140),
)


def number(name, low, high):
    return draw('personal_'+name,low,high,lambda:random.randint(low,high))


def damage_to_personal(unit, weapon, amount):
    if unit.unit_type != UnitType.MW or weapon and weapon.special & PCOMBAT:
        return amount
    return sum(number('conversion',80,130) for _ in range(amount))


def personal_to_damage(unit, weapon, amount):
    if unit.unit_type == UnitType.MW or weapon is None or not weapon.special & PCOMBAT:
        return amount
    return divide(amount,100) + (number('to_normal',1,100) <= remainder(amount,100))


def personal_location(location):
    return {2:4,3:4,0:1,5:6}.get(location,location)


def personal_armor_effect(unit, weapon, location, amount, id=-1):
    from systems.movement_commands import notify
    if id != -2: amount = divide(amount * number('variation',75,125),100)
    if unit.unit_type != UnitType.MW: return amount
    location = personal_location(location)
    armor_id = unit.sections[location].armor
    if not armor_id: return amount
    armor = next((row for row in ARMORS if row[:2] == (location,armor_id)),None)
    bypass = False
    if number('weak_point',1,5) == 1:
        if number('double_or_bypass',1,2) == 1: amount *= 2
        else: bypass = True
    elif number('half',1,10) == 2:
        amount = divide(amount,2)
    if armor is None: return amount
    _,_,defends,minimum,percentage,maximum = armor
    if weapon and weapon.special & PCOMBAT and not defends & weapon.special & PCOMBAT:
        return amount
    block = min(maximum//2,max(number('block',1,minimum//2),abs(divide(amount*percentage,100))))
    if bypass: block = 0
    if abs(amount)<block:
        notify(unit,'Your armor blocks all of the damage!')
        return 0
    if block: notify(unit,f'Armor blocks {block} points of the damage!')
    return divide((abs(amount)-block)*amount,abs(amount))


def initialize_pc(actor, unit, catalog=None):
    """Initialize the real MW body once, preserving equipment fallthrough order."""
    from entities.mech import CritStatus, Location as L
    from systems.characters import attached
    from data.characters import HEALTH, ATTRS, SKILLS
    from data.construction_catalog import Catalog, runtime_part, source_weapon
    from systems.weapon_inventory import sync_weapon_states
    import re
    if unit.unit_type != UnitType.MW or unit.has_crit_status(CritStatus.PC_INITIALIZED):
        return
    from systems.characters import character_store_for, source_stats
    from core.attributes import attributes_for
    store = character_store_for(unit, actor)
    ident = getattr(actor, '_character_id', getattr(actor, '_id', actor))
    stats = source_stats(unit, actor, HEALTH|ATTRS|SKILLS)
    unit.set_crit_status(CritStatus.PC_INITIALIZED)
    build=stats.get('Build'); remaining=build*20-stats.get('Bruise')-stats.get('Lethal')
    unit.max_speed=float32((build+stats.get('Reflexes')+stats.get('Running'))*10.75/9)
    for section,percent in zip(unit.sections,(30,30,35,35,50,35,35,15)):
        section.armor=section.armor_orig=0
        section.internal=section.internal_orig=(divide(percent*remaining,100)+1) & 0xff
    unit.clear_crit_status(CritStatus.OWEIGHT_OK)
    fallback = store.record(ident).get('pcequip', '') if store is not None else getattr(actor, 'pcequip', '')
    text = attributes_for(actor, attributes_for(unit)).get(ident, 'A_PCEQUIP', fallback)
    # sscanf reads three whitespace-delimited strings then two signed integers.
    match=re.match(r'\s*(\S+)(?:\s+(\S+))?(?:\s+(\S+))?',text)
    if match is None:return
    fields=[v for v in match.groups() if v is not None]
    tail=text[match.end():]
    for _ in range(2):
        number_match=re.match(r'\s*([+-]?\d+)',tail)
        if number_match is None:break
        from data.characters import integer
        token = number_match[1]
        sign = -1 if token.startswith('-') else 1
        digits = token.lstrip('+-').lstrip('0') or '0'
        if len(digits) > 10:
            raise ValueError('Unsupported signed PC equipment integer overflow')
        fields.append(integer(sign * int(digits)));tail=tail[number_match.end():]
    catalog=catalog or Catalog()
    try:
        for position,loc,ammo_position in ((2,L.LARM,4),(1,L.RARM,3)):
            if len(fields)<=position or fields[position]=='-':continue
            found=catalog.match('vlong',fields[position])
            if found is None:raise ValueError(f'Invalid PC weapon #1 for {actor.name}(#{ident}): {fields[position]}')
            part=found['source_part_id']
            if not 1<=part<193:continue
            section=unit.sections[loc];slot=section.criticals[0]
            slot.type=runtime_part(part);slot.data=slot.firemode=slot.ammomode=0
            weapon=source_weapon(part-1)
            if weapon.ammo_per_ton:
                slot=section.criticals[1];slot.type=weapon.index+193
                slot.data=(fields[ammo_position] if len(fields)>ammo_position else weapon.ammo_per_ton) & 0xff
                slot.firemode=slot.ammomode=0
        armor=fields[0]
        if len(armor)!=4:raise ValueError(f'Invalid armor string for {actor.name}(#{ident}): {armor}')
        for position,char in enumerate(armor,1):
            if char not in '0123456789':
                raise ValueError(f'Invalid armor char for {actor.name}(#{ident}) in {armor} (pos {position},{char})')
        for loc,value in zip((L.HEAD,L.CTORSO,L.RARM,L.RLEG),armor):unit.sections[loc].armor=int(value)
    except ValueError as error:
        from core.effects import send_error
        send_error(unit,str(error))
        return str(error)
    finally:
        sync_weapon_states(unit)
