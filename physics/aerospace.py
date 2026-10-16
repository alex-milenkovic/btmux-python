# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.events.c
#   btech/mech.move.c
# Historical Aerospace sources:
#   btech/aero.move.c
#   btech/ds.bay.c

"""Aircraft controls, source vector physics and dropship launch effects."""
import math
from core.events import EventType
from core.randomness import float32 as f32, draw, number
from entities.mech import UnitType as U, MoveType as M, MechStatus as S, MechStatus2 as S2, CritStatus, VehicleLocation
from entities.map import GRASSLAND, ROAD, BUILDING, LIGHT_FOREST, HEAVY_FOREST, ROUGH, MAPFLAG_UNDERGROUND
from physics.heights import AERO_TYPES, aero_free_fuel, ZSCALE
from physics.cargo import cargo_max_speed
from physics.collision import mech_elevation, mech_rterrain
from physics.hexmath import find_components, hex_to_float, find_range, my_hex_dist, TWOPIOVER360
from systems.movement_commands import c_number, notify, maybe_move
from systems.communications import common_checks, MECH_USUAL
from systems.sensors import los_broadcast

# min/max horizontal, min/max vertical, launch countdown, source notices
LAND_DATA = {
    U.VTOL: (-15, 15, -60, 10, 0, 'You bring your VTOL to a safe landing.', 'lands.', 'The rotor whines overhead as you lift off into the sky.', 'takes off!'),
    U.AERO: (32, 999, -30, 10, 10, 'You land your AeroFighter safely.', 'lands safely.', 'The Aerofighter launches into the air!', 'launches into the air!'),
    U.DS: (32, 999, -25, 10, 300, 'The DropShip lands safely.', 'lands safely.', "The DropShip's nose lurches upward, and it starts climbing to the sky!", 'starts climbing to the sky!'),
    U.SPHEROID_DS: (-40, 40, -40, 15, 300, 'The DropShip touches down safely.', 'touches down, and settles.', 'The DropShip slowly lurches upwards as engines battle the gravity..', 'starts climbing up to the sky!'),
}
DIRS = ((0,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0))
REASONS = ('Improper terrain', 'Uneven ground', 'Blocked landing zone')


def flying(unit):
    return unit.unit_type in AERO_TYPES or unit.move_type == M.VTOL


def is_ds(unit):
    return unit.unit_type in (U.DS, U.SPHEROID_DS)


def adjacent(x, y, direction):
    dx, dy = DIRS[direction % 6]
    nx = x + dx
    return nx, y + dy - int(bool(x % 2 and not nx % 2))


def continue_flying(unit):
    if flying(unit):
        unit.clear_status(S.LANDED)
        unit.z += 1
        unit.fz = ZSCALE * unit.z
        unit._engine.cancel_events_of_type(EventType.MOVE, unit)


def ds_info(unit, action):
    from systems.damage import external_effect
    external_effect(unit, 'DS information channel', f'DS #{unit._id} {action} at {unit.x} {unit.y} on map #{unit.mapindex}')


def takeoff(engine, unit, argument='', caller=None):
    caller = caller or unit.pilot
    count = c_number(argument, True)
    if count and not getattr(caller, 'wizard', False):
        return False, 'Insufficient access!'
    if engine.has_event(EventType.TAKEOFF, unit):
        return False, 'The launch sequence has already been initiated!'
    if unit.unit_type not in LAND_DATA:
        return False, 'This vehicle type cannot takeoff!'
    error = common_checks(unit, caller, MECH_USUAL)
    if error is not None: return False, error
    if unit.unit_type not in AERO_TYPES and unit.has_status2(S2.FORTIFIED):
        return False, 'Your fortified state prevents you from moving.'
    if not flying(unit): return False, 'Only VTOL, Aerospace fighters and Dropships can take off.'
    if not unit.has_status(S.LANDED): return False, "You haven't landed!"
    vtol = unit.unit_type == U.VTOL
    if unit.is_fallen or cargo_max_speed(unit) <= 10.75 or unit.is_section_destroyed(VehicleLocation.ROTOR):
        return False, "The rotor's dead!" if vtol else 'The engines are dead!'
    if not aero_free_fuel(unit) and unit.fuel < 1:
        return False, "Your VTOL's out of fuel!" if vtol else "Your craft's out of fuel! No taking off until it's refueled."
    if unit.unit_type == U.AERO and unit.speed < 32.25:
        return False, "You're moving too slowly to take off!"
    if unit.map.flags & MAPFLAG_UNDERGROUND:
        return False, 'Realize the ceiling in this grotto is a bit to low for that!'
    unit._engine = engine
    if LAND_DATA[unit.unit_type][4] > 0:
        notify(unit, "Launch sequence initiated.. type 'land' to abort it.")
    if is_ds(unit):
        from physics.heights import dropship_notice
        if dropship_notice(unit, engine.tick):
            los_broadcast(unit, 'starts warming engines for liftoff!')
        ds_info(unit, 'has started takeoff')
    if unit.has_crit_status(CritStatus.HIDDEN):
        notify(unit, 'You break your cover to takeoff!')
        los_broadcast(unit, 'breaks its cover as it begins takeoff.')
        unit.clear_crit_status(CritStatus.HIDDEN)
    from systems.swarm import stop_hiding
    stop_hiding(unit)
    engine.schedule_event(1, EventType.TAKEOFF, takeoff_event, data=unit, data2=count or LAND_DATA[unit.unit_type][4])
    return True, 'Takeoff scheduled.'


def takeoff_event(event):
    unit, count = event.data, event.data2
    engine = unit._engine
    data = LAND_DATA[unit.unit_type]
    if count > 0:
        if count <= 5 or count % 10 == 0: notify(unit, f'Launch countdown: {count}.')
        if is_ds(unit):
            if count == data[4] // 4:
                los_broadcast(unit, "'s engines start to glow with unbearable intensity..")
            if count == 10: los_broadcast(unit, "'s engines are almost ready to lift off!")
            if count in (6, 2):
                from systems.sensors import scramble_infra_and_liteamp
                if count == 6:
                    los_broadcast(unit, "'s engines generate a tremendous heat wave!")
                    message = 'The blinding flash of light momentarily blinds you!'
                else:
                    notify(unit, 'The engines pulse out a stream of superheated plasma!')
                    los_broadcast(unit, "'s engines send forth a tremendous stream of superheated plasma!")
                    message = 'The blinding flash of light blinds you!'
                scramble_infra_and_liteamp(unit, 2 if count == 6 else 4, 0, message, message)
            if count == 1: exhaust(unit, 400)
        engine.schedule_event(1, EventType.TAKEOFF, takeoff_event, data=unit, data2=count-1)
        return
    if not is_ds(unit) and unit.unit_type == U.AERO and unit.speed < 32.25:
        notify(unit, "You're moving too slowly to lift off!")
        return
    unit.clear_crit_status(CritStatus.SPINNING)
    notify(unit, data[7]); los_broadcast(unit, data[8])
    unit.start_fx = unit.start_fy = unit.start_fz = 0
    if is_ds(unit): ds_info(unit, 'has lifted off')
    if unit.has_crit_status(CritStatus.HIDDEN):
        notify(unit, 'You move too much and break your cover!')
        los_broadcast(unit, 'breaks its cover in the brush.')
        unit.clear_crit_status(CritStatus.HIDDEN)
    if unit.unit_type == U.VTOL:
        unit.speed = unit.desired_speed = 0
        unit.vertical_speed = 60
    else:
        unit.desired_angle = 90
        unit.desired_speed = unit.max_speed * 2 / 3
    continue_flying(unit)
    maybe_move(engine, unit)


def improper_lz(unit, x=None, y=None):
    from systems.map_links import blocked_lz
    board = unit.map
    x, y = unit.x if x is None else x, unit.y if y is None else y
    if board is None or not board.valid(x, y): raise ValueError('Landing zone coordinates out of map bounds')
    mode = 0 if unit.unit_type in AERO_TYPES else getattr(unit._engine, 'blzmapmode', 0)
    if not mode and board.rterrain(x, y) not in (GRASSLAND, ROAD): return 1
    count = 0
    for direction in range(6):
        nx, ny = adjacent(x, y, direction)
        if board.valid(nx, ny):
            count = count + 1 if board.base_elevation(nx, ny) == board.base_elevation(x, y) else 0
    if not mode and count != 6: return 2
    return 3 if blocked_lz(unit, board, x, y) else 0


def land(engine, unit, caller=None):
    if unit.unit_type not in LAND_DATA: return False, "You can't land this type of vehicle."
    vtol = unit.unit_type == U.VTOL
    if vtol and unit.fuel <= 0 and not aero_free_fuel(unit): return False, 'You lack fuel to maneuver for landing!'
    if unit.is_fallen: return False, "The rotor's dead!" if vtol else 'The engines are dead!'
    if unit.has_status(S.LANDED):
        if engine.has_event(EventType.TAKEOFF, unit):
            message = f'Launch aborted by {getattr(caller or unit.pilot, "name", "pilot")}.'
            notify(unit, message)
            if is_ds(unit): ds_info(unit, 'aborted takeoff')
            engine.cancel_events_of_type(EventType.TAKEOFF, unit)
            return True, message
        return False, "You're already landed!"
    if unit.z > mech_elevation(unit) + 1: return False, 'You are too high to land here.'
    minimum, maximum, down, up, *unused = LAND_DATA[unit.unit_type]
    horizontal = math.sqrt(abs(unit.desired_speed**2 - unit.vertical_speed**2))
    if horizontal >= maximum + 1: return False, "You're moving too fast to land."
    if horizontal < minimum: return False, "You're moving too slowly to land."
    if int(unit.vertical_speed) > up or unit.vertical_speed < down: return False, 'You are moving too fast to land. '
    if unit.speed < minimum:
        return False, "You're falling, not landing! Pick up some horizontal speed first." if unit.start_fz <= 0 else "You're climbing not landing!"
    if mech_rterrain(unit) not in ((GRASSLAND, ROAD, BUILDING) if vtol else (GRASSLAND, ROAD)):
        return False, "You can't land on this type of terrain."
    if not vtol and improper_lz(unit):
        from systems.combat_commands import NotifiedError
        return False, NotifiedError(notify(unit, 'This location is no good for landing!'))
    if is_ds(unit): ds_info(unit, 'has landed')
    notify(unit, LAND_DATA[unit.unit_type][5])
    los_broadcast(unit, LAND_DATA[unit.unit_type][6])
    if vtol:
        # Keep the previously working scalar, terrain and mine consumer.
        from physics.heights import land_vtol
        land_vtol(unit, effects=False)
    else:
        unit.z = mech_elevation(unit)
        unit.fz = ZSCALE * unit.z
        unit.set_status(S.LANDED)
        unit.speed = unit.vertical_speed = unit.start_fx = unit.start_fy = unit.start_fz = 0
    if unit.unit_type not in AERO_TYPES:
        from systems.damage import external_effect
        external_effect(unit, 'MUX scripts', 'A_AAEROLAND')
    from systems.mines import possible_mine_poof
    possible_mine_poof(unit, 'land')
    return True, LAND_DATA[unit.unit_type][5]


def checklz(unit, argument='', caller=None):
    error = common_checks(unit, caller or unit.pilot, MECH_USUAL)
    if error is not None: return False, error
    args = str(argument).split()
    if len(args) not in (0,2): return False, 'Invalid number of parameters!'
    x,y = (map(lambda value:c_number(value, True), args) if args else (unit.x,unit.y))
    if args and not unit.has_crit_status(CritStatus.OBSERVATORIC):
        fx,fy = hex_to_float(x,y)
        if find_range(unit.fx,unit.fy,fx,fy) > unit.tac_range: return False, 'Out of range!'
    result = improper_lz(unit,x,y)
    message = f"The hex ({x},{y}) doesn't look good for landing: {REASONS[result-1]}." if result else f'The hex ({x},{y}) looks good enough for a landing.'
    return True, notify(unit,message)


def land_warning(unit, severity):
    result = improper_lz(unit)
    if not result: return None
    color = '%ch%cr' if severity == 1 else '%ch%cy' if severity == 0 else ''
    advice = 'CLIMB UP NOW!!!' if severity == 1 else 'No further descent is advisable.' if severity == 0 else 'Please do not even consider landing here.'
    return notify(unit, f'{color}WARNING: {REASONS[result-1]} - {advice}%cn')


def thrust(engine, unit, argument='', caller=None):
    if unit.has_status(S.LANDED): return False, "You're landed!"
    if unit.unit_type in AERO_TYPES and unit.has_crit_status(CritStatus.SPINNING):
        return False, 'You are unable to control your craft at the moment.'
    args = str(argument).split()
    if not args: return True, f'Your current thrust is {unit.desired_speed:.2f}.'
    speed = f32(c_number(args[0]))
    if unit.unit_type in (U.AERO,U.DS) and speed < 6.45:
        return False, 'Minimum thrust you stay in air with is 6.5 kph.'
    maximum = max(0, cargo_max_speed(unit))
    if unit.is_fallen: return False, "Your engine's dead, no way to thrust!"
    if speed < 0: return False, "Doh, thrust backwards.. where's your sense of adventure?"
    if speed > maximum: return False, f'Maximum thrust: {maximum:.2f} ({maximum/10:.2f} kb/sec2)'
    unit.desired_speed = speed
    message=notify(unit,f'Thrust set to {speed:.2f}.')
    maybe_move(engine,unit)
    return True, message


def vheading(unit, argument='', flag=1):
    args = str(argument).split()
    if not args: return True, f'Present angle: {unit.desired_angle} degrees.'
    angle = flag*c_number(args[0], True)
    if abs(angle) > 90: angle = flag*90
    if abs(angle) != 90 and unit.z < 100 and unit.unit_type == U.SPHEROID_DS:
        return False, 'You can go only up / down at <100 z!'
    message=notify(unit, f'Climbing angle set to {angle} degrees.' if angle >= 0 else f'Diving angle set to {-angle} degrees.')
    unit.desired_angle = angle
    return True, message


def update_heading(unit):
    if unit.unit_type == U.SPHEROID_DS:
        from physics.movement import update_heading as ground_heading
        ground_heading(unit)


def update_speed(unit):
    maximum = cargo_max_speed(unit)
    if unit.has_crit_status(CritStatus.SPINNING):
        unit.desired_speed = min(maximum,max(0,unit.desired_speed+draw('aero_spin_speed',1,10,lambda:number(1,10))))
        unit.desired_angle = max(-90,unit.desired_angle-draw('aero_spin_angle',1,15,lambda:number(1,15)))
        from physics.hexmath import acceptable_degree
        unit.desired_facing = acceptable_degree(unit.desired_facing+draw('aero_spin_heading',-3,3,lambda:number(-3,3)))
    angle = math.radians(unit.desired_angle)
    wz = f32(unit.desired_speed*math.sin(angle))
    horizontal = f32(unit.desired_speed*math.cos(angle))
    if unit.fuel < 0: wz,horizontal = f32(wz/5), f32(horizontal/5)
    wx,wy = find_components(f32(5*abs(horizontal)),unit.desired_facing)
    wz = f32(wz*5)
    dx,dy,dz = f32(wx-unit.start_fx),f32(wy-unit.start_fy),f32(wz-unit.start_fz)
    length = f32(math.hypot(dx,dy,dz))
    if not length > 0: return
    bonus = f32(2.5 if unit.unit_type == U.AERO else .7)
    if unit.z < 100: bonus = f32(bonus/2)
    cap = f32(f32(f32(bonus*5)*maximum)/30)
    if length > cap:
        mod = f32(cap/length)
        dx,dy,dz = f32(dx*mod),f32(dy*mod),f32(dz*mod)
    nx,ny,nz = f32(unit.start_fx+dx),f32(unit.start_fy+dy),f32(unit.start_fz+dz)
    if unit.unit_type != U.SPHEROID_DS:
        unit.facing = (int(f32(f32(math.atan2(ny,nx))/TWOPIOVER360))+90)%360
    unit.speed = f32(math.hypot(nx,ny))
    unit.vertical_speed = nz
    if unit.unit_type != U.SPHEROID_DS and abs(unit.speed)<10.75: unit.facing=unit.desired_facing
    unit.start_fx,unit.start_fy,unit.start_fz = nx,ny,nz


def control_effect(unit):
    if unit.has_crit_status(CritStatus.SPINNING) or unit.is_destroyed or unit.has_status(S.LANDED): return
    notify(unit,'You lose control of your craft!')
    los_broadcast(unit,'spins out of control!')
    unit.set_crit_status(CritStatus.SPINNING)
    unit.start_spin = unit._engine.sim_now


def update(engine,unit):
    if unit.is_destroyed: return
    from systems.stability import update_pilot_skill_rolls
    from systems.heat import update_from_environment
    if unit.is_started or unit.has_status(S.UNCONSCIOUS): update_pilot_skill_rolls(engine,unit)
    if unit.is_started or unit.plus_heat > 0: update_from_environment(unit,engine.muxevent_tick)
    if int(engine.sim_now/3)%5 == 0:
        if not unit.has_crit_status(CritStatus.SPINNING) or unit.is_destroyed or unit.has_status(S.LANDED): return
        from systems.piloting import make_piloting_roll
        modifier = int((unit.start_spin-engine.sim_now)/15)+8
        unit.last_piloting_modifier = modifier
        if make_piloting_roll(unit,modifier).success:
            notify(unit,'You recover control of your craft.')
            unit.clear_crit_status(CritStatus.SPINNING)
    if unit.is_started:
        unit.vis_mod = max(0,min(100,unit.vis_mod+draw('visibility_change',-40,40,lambda:number(-40,40))))
    from systems.ecm import check_ecm
    from systems.targeting import check_tag
    from systems.sensors import end_lite_check
    check_ecm(unit); check_tag(unit); end_lite_check(unit)


def descent(unit, old_z):
    if not is_ds(unit): return
    if unit.z < 10 <= old_z: land_warning(unit,1)
    elif unit.z < 50 <= old_z: land_warning(unit,0)
    elif unit.z < 100 <= old_z:
        if abs(unit.desired_angle) != 90:
            from physics.heights import dropship_notice
            if dropship_notice(unit,unit._engine.tick):
                notify(unit,"As the craft enters the lower atmosphere, it's nose rises up for a clean landing..")
                los_broadcast(unit,f'starts descending towards {unit.x}, {unit.y}..')
            else: notify(unit,'Due to low altitude, climbing angle set to 90 degrees.')
            unit.desired_angle=90
        unit.start_fx=unit.start_fy=0
        land_warning(unit,-1)


def exhaust(unit,damage):
    from physics.decorations import add_fire
    from systems.notifications import hex_broadcast
    from systems.damage import blast_hit_hexes_f
    board = unit.map
    radius = 5 if damage > 100 else 3
    for x in range(max(0,unit.x-radius),min(board.map_width,unit.x+radius+1)):
        for y in range(max(0,unit.y-radius),min(board.map_height,unit.y+radius+1)):
            distance=my_hex_dist(unit.x,unit.y,x,y,0)
            if distance > radius: continue
            if board.rterrain(x,y) in (LIGHT_FOREST,HEAVY_FOREST) and (x,y) not in board.decorations:
                ending = 'are instantly burned to ash!' if damage > 100 else 'light up and burn.'
                hex_broadcast(board,x,y,f'%ch%crThe trees in $h {ending}%cn')
                if damage//max(1,distance)>100: board.set_terrain(x,y,ROUGH)
                else: add_fire(unit._engine,board,x,y)
    messages = ('You receive a direct hit!','is caught in the middle of the inferno!','You are hit by the wave!','gets hit by the wave!') if damage > 100 else ("You are hit by the DropShip's plasma exhaust!","is hit directly by DropShip's exhaust!","You are hit by the DropShip's plasma exhaust!","is hit by DropShip's exhaust!")
    z=unit.z
    try:
        unit.z=z+6
        blast_hit_hexes_f(board,damage,5,damage//2,unit.fx,unit.fy,unit.fx,unit.fy,*messages,0,4,4,True,radius,engine=unit._engine)
    finally: unit.z=z
