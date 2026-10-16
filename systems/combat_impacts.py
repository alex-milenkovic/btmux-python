# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.combat.c

"""Damage shaping in determineDamageFromHit, before armor and critical routing."""
from entities.mech import UnitType as U,AmmoMode as A
from entities.weapon import WeaponFlags as W,WeaponType as T
from entities.map import GRASSLAND,LIGHT_FOREST,HEAVY_FOREST
from systems.combat_ranges import config,underwater


def determine_damage(unit,target,weapon,distance,section=None,critical=None,*,
                     gattling_shots=0,ammo_mode=0,failure_type=None,
                     failure_modifier=0,temporary=False,hit_x=None,hit_y=None):
    from systems.targeting import fa_mech_range
    if target is not None:distance=fa_mech_range(unit,target)
    elif hit_x is not None and hit_y is not None:
        from physics.hexmath import hex_to_float,find_range
        fx,fy=hex_to_float(hit_x,hit_y)
        distance=find_range(unit.fx,unit.fy,fx,fy)
    damage=gattling_shots if gattling_shots>0 else weapon.damage
    if weapon.special&W.HVYGAUSS:
        if distance>weapon.range_medium:damage=10
        elif distance>weapon.range_short:damage=20
    if weapon.special&W.SNUBPPC:
        if distance>weapon.range_medium:damage=5
        elif distance>weapon.range_short:damage=8
    if section is not None and critical is not None:
        from systems.enhanced_crits import get_crit_sub_damage
        damage-=get_crit_sub_damage(unit,section,critical)
    if target is not None:
        if ammo_mode&A.AC_FLECHETTE_MODE:
            if target.unit_type==U.MW:
                damage*=4 if target.map and target.map.rterrain(target.x,target.y)==GRASSLAND else 2
            elif target.unit_type!=U.BSUIT:damage=int(damage/2)
        if ammo_mode&A.AC_INCENDIARY_MODE and target.unit_type==U.MW:damage+=2
    if config(unit,'moddamagewithrange',0) and weapon.weapon_type==T.TBEAM:
        if distance<=1:damage+=1
        else:
            wet=underwater(unit,section)
            if distance>(weapon.range_long_water if wet else weapon.range_long):damage=int(damage/2)
            elif distance>(weapon.range_medium_water if wet else weapon.range_medium):damage-=1
    if failure_type=='DAMAGE':damage-=failure_modifier
    if target is not None and not temporary and config(unit,'moddamagewithwoods',0) and unit.map:
        terrain=unit.map.rterrain(target.x,target.y)
        if terrain in (LIGHT_FOREST,HEAVY_FOREST) and target.z-2<=unit.map.base_elevation(target.x,target.y):
            from systems.movement_commands import notify
            from systems.combat import possibly_ignite_or_clear
            clear_damage=damage
            damage-=2 if terrain==LIGHT_FOREST else 4
            notify(unit,'The woods absorb some of your shot!')
            notify(target,'The woods absorb some of the damage!')
            possibly_ignite_or_clear(unit,weapon.index,ammo_mode,clear_damage,target.x,target.y,1)
    return max(1,damage)
