# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/map.c
#   btech/map.obj.c
#   btech/mech.combat.c

"""Weapon ignition and clearing, including C draw order and exclusions."""
from core.randomness import roll as source_roll
import random
from core.randomness import draw
from entities.map import LIGHT_FOREST, HEAVY_FOREST, ROUGH, GRASSLAND
from entities.mech import AmmoMode as A, MechStatus as S
from entities.weapon import get_weapon_by_index, WeaponType as T, WeaponFlags as F
from systems.movement_commands import notify

SMALL_WEAPONS = {'ERSmallLaser','SmallLaser','SmallPulseLaser','X-SmallPulseLaser',
                 'ERSmallPulseLaser','HeavySmallLaser','MachineGun','LightMachineGun',
                 'HeavyMachineGun','StreakSRM-2','SRM-2'}
IGNITE_EXCLUDED = SMALL_WEAPONS | {'GaussRifle','LightGaussRifle','HeavyGaussRifle',
                                 'MagshotGaussRifle','NarcBeacon','iNarcBeacon'}
CLEAR_EXCLUDED = SMALL_WEAPONS | {f'{prefix}AC/{size}' for prefix in
                                 ('','Ultra','Caseless','Hyper','Light','Rotary') for size in (2,5)} | {'LB2-XAC','LB5-XAC'}
PERSONAL = F.PC_HEAT | F.PC_IMPA | F.PC_SHAR


def roll():
    return source_roll('terrain_rolls', lambda: random.randint(1,6)+random.randint(1,6))


def can_weapon_ignite(index):
    return get_weapon_by_index(index).name[3:] not in IGNITE_EXCLUDED


def can_weapon_clear(index):
    return get_weapon_by_index(index).name[3:] not in CLEAR_EXCLUDED


def possibly_ignite(unit,index,ammo_mode,x,y,intentional):
    result=roll()
    board=unit.map
    weapon=get_weapon_by_index(index)
    if weapon.special & PERSONAL or board is None or not board.valid(x,y):
        return False
    if board.terrain(x,y) not in (LIGHT_FOREST,HEAVY_FOREST):
        return False
    threshold=13
    if weapon.name[3:] in ('Flamer','HeavyFlamer'):
        threshold=4
    elif weapon.weapon_type==T.TMISSILE and ammo_mode & A.INFERNO_MODE:
        threshold=5
    elif weapon.weapon_type==T.TAMMO and ammo_mode & A.AC_FLECHETTE_MODE:
        threshold=5
    elif can_weapon_ignite(index):
        if weapon.weapon_type==T.TBEAM:
            threshold=5
        elif weapon.weapon_type in (T.TMISSILE,T.TAMMO):
            threshold=9
    if result < threshold:
        return False
    return fire_hex(unit,x,y,intentional)


def terrain_message(unit,x,y,verb,intentional):
    from systems.sensors import los_broadcast
    if intentional:
        los_broadcast(unit,f"'s shot {verb}s {x},{y}!")
        notify(unit,f'You {verb} {x},{y}.')
    else:
        los_broadcast(unit,f"'s stray shot {verb}s {x},{y}!")
        notify(unit,f'You accidentally {verb} {x},{y}!')


def fire_hex(unit,x,y,intentional):
    board=unit.map
    if board is None or not board.valid(x,y) or board.terrain(x,y) not in (LIGHT_FOREST,HEAVY_FOREST): return False
    terrain_message(unit,x,y,'ignite',intentional)
    from physics.decorations import add_fire
    add_fire(unit._engine,board,x,y)
    return True


def clear_hex(unit,x,y,intentional):
    board=unit.map
    if board is None or not board.valid(x,y):
        return False
    if board.terrain(x,y)==HEAVY_FOREST:
        replacement=LIGHT_FOREST
    elif board.terrain(x,y)==LIGHT_FOREST:
        replacement=ROUGH if draw('terrain_replacement',1,2,lambda: random.randint(1,2))==1 else GRASSLAND
    else:
        return False
    board.set_terrain(x,y,replacement)
    terrain_message(unit,x,y,'clear',intentional)
    return True


def possibly_clear(unit,index,ammo_mode,damage,x,y,intentional):
    ignite_roll,clear_roll=roll(),roll()
    if get_weapon_by_index(index).special & PERSONAL:
        return False
    if ignite_roll <= (5 if intentional else 3):
        return possibly_ignite(unit,index,ammo_mode,x,y,intentional)
    if not can_weapon_clear(index) or clear_roll>damage:
        return False
    result=clear_hex(unit,x,y,intentional)
    from systems.mines import possibly_remove_mines
    possibly_remove_mines(unit,x,y)
    return result


def possibly_ignite_or_clear(unit,index,ammo_mode,damage,x,y,intentional):
    roll()  # The unused C r is still a real draw before the map lookup.
    if unit.map is None:
        return False
    if unit.has_status(S.LOCK_HEX_IGN):
        return possibly_ignite(unit,index,ammo_mode,x,y,True)
    if unit.has_status(S.LOCK_HEX_CLR):
        intentional=True
    return possibly_clear(unit,index,ammo_mode,damage,x,y,intentional)
