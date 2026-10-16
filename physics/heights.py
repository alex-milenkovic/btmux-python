# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.update.c
# Historical Aerospace sources:
#   btech/aero.move.c
#   btech/mech.update.c

"""Naval and VTOL height maintenance at the movement tail."""
import math
from entities.mech import UnitType,MoveType,MechStatus as S
from entities.map import WATER,ICE,BRIDGE,FIRE,GRASSLAND,ROAD,BUILDING
from physics.collision import mech_rterrain,mech_elevation
from systems.movement_commands import in_water
from systems.movement_commands import notify
from systems.sensors import los_broadcast
from core.randomness import float32
from systems.ecm import mark_for_los_update

AERO_TYPES=(UnitType.AERO,UnitType.DS,UnitType.SPHEROID_DS)
ZSCALE=64.5


def aero_free_fuel(unit):
    """AeroFreeFuel: only configured fusion VTOLs are exempt."""
    from entities.mech import Specials
    return (unit.unit_type == UnitType.VTOL and
        getattr(unit._engine,'nofusion_vtol_fuel',False) and not unit.specials & Specials.ICE_TECH)


def fuel_check(unit):
    """aero.move.c FuelCheck, including its delayed zero-fuel consequence."""
    from core.randomness import draw, number
    from core.events import EventType
    from physics.cargo import cargo_max_speed
    from physics.orbital import fall_event
    from systems.sensors import los_broadcast
    if not unit.is_started or aero_free_fuel(unit):
        return False
    cost = 1
    maximum = cargo_max_speed(unit)
    if abs(unit.speed) > maximum:
        if unit.z < 100:
            if maximum <= 0:
                raise ValueError('unsupported FuelCheck division by nonpositive maximum speed')
            cost = int(abs(unit.speed / maximum))
    elif abs(unit.speed) < 10.75 and abs(unit.vertical_speed) < 21.5:
        if draw('fuel_check', 0, 1, lambda: number(0, 1)) == 0:
            return False
    if unit.fuel > 0:
        unit.fuel = max(0, unit.fuel - cost)
        return False
    if unit.unit_type in (UnitType.DS, UnitType.SPHEROID_DS):
        if unit.fuel == 0:
            unit.fuel = -1
            notify(unit, 'As the fuel runs out, the engines switch to backup power.')
        return False
    if unit.fuel < 0:
        return True
    unit.fuel -= 1
    if unit.unit_type == UnitType.VTOL:
        los_broadcast(unit, "'s rotors suddenly stop!")
        notify(unit, 'The sound of rotors slowly stops..')
    else:
        los_broadcast(unit, "'s engines die suddenly..")
        notify(unit, 'Your engines die suddenly..')
    unit.speed = unit.desired_speed = 0
    if not unit.has_status(S.LANDED):
        notify(unit, 'You ponder F = ma, S = F/m, S = at^2 => S=agt^2 in relation to the ground..')
        unit.vertical_speed = 0
        notify(unit, 'You start free-fall.. Enjoy the ride!')
        unit._engine.schedule_event(3, EventType.FALL, fall_event, data=unit, data2=-1)
    return True


def check_naval_height(unit,previous_z):
    terrain=mech_rterrain(unit)
    if terrain not in (WATER,ICE,BRIDGE):
        unit.speed=unit.desired_speed=unit.vertical_speed=0
        unit.facing=unit.desired_facing=0
        return
    if previous_z==0 and unit.z!=0 and unit.elev>1:
        mark_for_los_update(unit)
        unit.z=0
        los_broadcast(unit,'dives!')
        unit.z=-1
    if unit.fz>0:
        if unit.vertical_speed>0 and unit.z==0 and previous_z<0:
            notify(unit,'Your sub has reached surface and stops rising.')
            los_broadcast(unit, f'surfaces at {unit.x},{unit.y}!')
        unit.z=unit.fz=0
        if unit.vertical_speed>0:
            unit.vertical_speed=0
        return
    lower=-1 if terrain==BRIDGE else mech_elevation(unit)
    if unit.z<=lower:
        unit.z=min(0,lower+1)
        if mech_elevation(unit)>0:
            from core.effects import send_error
            send_error(unit, f"Oddity: #{unit._id} managed to wind up on '{unit.terrain}' ({unit.elev} elev.)")
        unit.fz=float32(((5.0*unit.z-4)*ZSCALE)/5.0)
        if unit.move_type==MoveType.SUB and unit.vertical_speed<0:
            unit.vertical_speed=0
            notify(unit,'The sub has reached bottom and stops diving.')


def land_vtol(unit, effects=True):
    """Preserved VTOL scalar landing; the aircraft command can own ordered effects."""
    if unit.unit_type!=UnitType.VTOL:
        return False
    if (unit.fuel<=0 and not aero_free_fuel(unit)) or unit.is_fallen or unit.has_status(S.LANDED):
        return False
    if unit.z>mech_elevation(unit)+1:
        return False
    # C my_sqrtm computes sqrt(max(x,y)^2-min(x,y)^2), not hypot.
    horiz=math.sqrt(abs(unit.desired_speed**2-unit.vertical_speed**2))
    if horiz>=16 or int(unit.vertical_speed)>10 or unit.vertical_speed < -60 or unit.speed < -15:
        return False
    if mech_rterrain(unit) not in (GRASSLAND,ROAD,BUILDING):
        return False
    unit.z=mech_elevation(unit)
    unit.fz=unit.z*ZSCALE
    unit.set_status(S.LANDED)
    unit.speed=unit.vertical_speed=0
    unit.start_fx=unit.start_fy=unit.start_fz=0
    if effects:
        notify(unit,'You bring your VTOL to a safe landing.')
        from systems.mines import possible_mine_poof
        possible_mine_poof(unit, 'land')
    return True


def check_vtol_height(unit):
    if in_water(unit) and unit.z<=0:
        from systems.damage import destroy_mech,KILL_TYPE_FLOOD
        notify(unit,'You crash your vehicle into the water!')
        notify(unit,'Water pours into the cockpit....glub glub!')
        los_broadcast(unit,'splashes into the water!')
        z, fz = unit.z, unit.fz
        destroy_mech(unit,unit,showboom=False,reason=KILL_TYPE_FLOOD,engine=unit._engine)
        unit.z, unit.fz = z, fz  # This C water-crash branch does not settle the craft.
        return
    if unit.z>=300 and unit.unit_type not in AERO_TYPES:
        notify(unit,'You cannot achieve orbit! Vertical movement halted!')
        unit.z=299
        unit.fz=299*ZSCALE
        unit.vertical_speed=0
        return
    elevation=mech_elevation(unit)
    if unit.z>=elevation or (mech_rterrain(unit)==BRIDGE and unit.z!=elevation-1):
        return
    from physics.aerospace import land
    if land(unit._engine, unit)[0]:
        return
    from physics.jump import mech_falls
    levels=int(1+abs(unit.vertical_speed/10.75))
    notify(unit,'CRASH!! You smash your toy into the ground!!' if unit.unit_type in AERO_TYPES
           else 'CRASH! You smash your toy into the ground!')
    los_broadcast(unit,'crashes into the ground!')
    mech_falls(unit,levels,notify_fall=False)
    unit.z=elevation
    unit.fz=elevation*ZSCALE
    unit.speed=unit.vertical_speed=0
    unit.set_status(S.LANDED)


def fiery_death(unit):
    if (unit.terrain!=FIRE or unit.unit_type in AERO_TYPES
            or unit.move_type==MoveType.VTOL or unit.is_destroyed):
        return False
    if unit.unit_type==UnitType.MW:
        from systems.damage import destroy_mech,KILL_TYPE_HEAT
        notify(unit,'You feel a tad bit too warm..')
        notify(unit,'You faint.')
        destroy_mech(unit,unit,showboom=False,reason=KILL_TYPE_HEAT,engine=unit._engine)
        return True
    return False


def dropship_notice(unit,now):
    last=getattr(unit,'last_dropship_notice',0)
    if last>now or now-last>=10:
        unit.last_dropship_notice=now
        return True
    return False


def maintain_height(unit, previous_z):
    if (unit.move_type == MoveType.VTOL or unit.unit_type in AERO_TYPES) and not unit.has_status(S.LANDED):
        check_vtol_height(unit)
    if unit.unit_type == UnitType.VEH_NAVAL:
        check_naval_height(unit, previous_z)
