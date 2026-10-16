"""Validated gameplay fixtures for the movement command-line interface."""
import math
from entities.map import GameMap
from entities.mech import (Mech, MechStatus as S, MechStatus2 as S2, UnitType,
                           MoveType, Location, Specials, FireMode, SectionConfig,
                           WeaponState, CritStatus)
from entities.pilot import Pilot
from physics.hexmath import ZSCALE, SCALEMAP, find_components, float_to_hex
from tools.path_cost_inputs import TERRAINS, terrain_value


def fields(value, allowed, required=()):
    if not isinstance(value, dict):
        raise ValueError('expected a JSON object')
    unknown, missing = set(value) - set(allowed), set(required) - set(value)
    if unknown or missing:
        raise ValueError(f'unknown fields {sorted(unknown)}; missing fields {sorted(missing)}')
    return value


def number(value, low=None, high=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'expected finite number, got {value!r}')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError('number is outside the finite machine range')
    if integer and not isinstance(value, int):
        raise ValueError('expected integer')
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f'number {value} outside {low}..{high}')
    return value


def boolean(value):
    if not isinstance(value, bool):
        raise ValueError('expected boolean')
    return value


def string(value):
    if not isinstance(value, str) or not value:
        raise ValueError('expected nonempty string')
    return value


def array(value, size=None):
    if not isinstance(value, list) or (size is not None and len(value) != size):
        raise ValueError(f'expected array of length {size}')
    return value


def coordinates(value, board, altitude=False):
    values = array(value, 3 if altitude else 2)
    x, y = [number(v, integer=True) for v in values[:2]]
    if not board.valid(x, y):
        raise ValueError(f'off-map coordinates {x},{y}')
    return (x, y, number(values[2], integer=True)) if altitude else (x, y)


def make_map(value):
    fields(value, ('size', 'default', 'hexes', 'gravity', 'special_rules', 'bridge_protection', 'visibility', 'light'))
    width, height = [number(v, 1, 100, True) for v in array(value.get('size', [7, 7]), 2)]
    board = GameMap(width, height)
    default = array(value.get('default', ['GRASSLAND', 0]), 2)
    terrain, elevation = terrain_value(string(default[0])), number(default[1], 0, 9, True)
    for x in range(width):
        for y in range(height):
            board.set_terrain(x, y, terrain)
            board.set_elevation(x, y, elevation)
    seen = set()
    for hexagon in array(value.get('hexes', [])):
        fields(hexagon, ('at', 'terrain', 'elevation'), ('at', 'terrain', 'elevation'))
        xy = coordinates(hexagon['at'], board)
        if xy in seen:
            raise ValueError('duplicate hex fixture')
        seen.add(xy)
        board.set_terrain(*xy, terrain_value(string(hexagon['terrain'])))
        board.set_elevation(*xy, number(hexagon['elevation'], 0, 9, True))
    board.grav = number(value.get('gravity', 100), 1, integer=True)
    if boolean(value.get('special_rules',False)): board.flags |= 2
    board.bridges_cs = boolean(value.get('bridge_protection', False))
    board.mapvis = number(value.get('visibility', 30), 0, 60, True)
    board.maxvis = 60
    board.maplight = number(value.get('light', 2), 0, 2, True)
    board.cloudbase = 200
    return board


UNIT_FIELDS = '''id class movement at tons actual_tons max_speed speed desired_speed
vertical_speed facing desired_facing jump_mp pilot_skill pilot_skill_base pilot_id
caller_id advantages states lateral cocoon target_hex target_id team fuel sections load
relative_position altitude heat stagger_level turret'''.split()
STATE_FLAGS = {name.lower(): flag for name, flag in S.__members__.items()
               if name in ('STARTED', 'FALLEN', 'JUMPING', 'HULLDOWN', 'BLINDED',
                           'UNCONSCIOUS', 'DESTROYED', 'LANDED', 'COMBAT_SAFE')}
MODE_FLAGS = {name.lower(): flag for name, flag in S2.__members__.items()
              if name in ('SPRINTING', 'EVADING', 'DODGING', 'FORTIFIED')}
EXTRA_STATES = ('waterproof', 'digging', 'dug_in', 'hip_disabled', 'no_move',
                'weapon_recycle', 'limb_recycle', 'charging', 'mounted', 'masc',
                'supercharger', 'hot_tsm', 'dumping', 'unjamming', 'crew_stunned',
                'tail_rotor_destroyed', 'in_character', 'gyro_damaged', 'gyro_destroyed')


def section_fixture(unit, value):
    fields(value, ('location', 'front', 'original_front', 'rear', 'original_rear',
                   'internal', 'original_internal', 'recycle', 'base_to_hit', 'components', 'flooded'), ('location',))
    loc = Location[string(value['location'])]
    section = unit.sections[loc]
    mapping = {'front': 'armor', 'original_front': 'armor_orig', 'rear': 'rear',
               'original_rear': 'rear_orig', 'internal': 'internal',
               'original_internal': 'internal_orig', 'recycle': 'recycle', 'base_to_hit': 'basetohit'}
    for key, attr in mapping.items():
        if key in value:
            setattr(section, attr, number(value[key], 0, integer=True))
    if section.armor > section.armor_orig or section.rear > section.rear_orig or section.internal > section.internal_orig:
        raise ValueError('current section values exceed original values')
    if loc not in (Location.CTORSO, Location.LTORSO, Location.RTORSO) and section.rear_orig:
        raise ValueError('only torsos have rear armor')
    if not section.internal:
        section.config |= SectionConfig.SECTION_DESTROYED
    if boolean(value.get('flooded', False)):
        section.config |= SectionConfig.SECTION_FLOODED
    from entities.crittypes import i2special, Special
    types = {'hip': Special.SHOULDER_OR_HIP, 'jump_jet': Special.JUMP_JET, 'heat_sink': Special.HEAT_SINK}
    seen = set()
    for part in array(value.get('components', [])):
        fields(part, ('slot', 'type', 'condition', 'weapon', 'rounds'), ('slot', 'type', 'condition'))
        slot = number(part['slot'], 0, 11, True)
        if slot in seen:
            raise ValueError('duplicate component slot')
        seen.add(slot)
        critical = section.criticals[slot]
        if part['type'] == 'ammo':
            from entities.crittypes import i2ammo
            from entities.weapon import get_weapon
            weapon = get_weapon(string(part['weapon']))
            if weapon is None or not weapon.uses_ammo:
                raise ValueError('ammo component requires a catalog ammunition weapon')
            critical.type = i2ammo(weapon.index)
            critical.data = number(part['rounds'], 0, integer=True)
        else:
            if 'weapon' in part or 'rounds' in part: raise ValueError('weapon/rounds require ammo component')
            critical.type = i2special(types[string(part['type'])])
        critical.firemode = {'working': FireMode.NONE, 'disabled': FireMode.DISABLED_MODE,
                             'destroyed': FireMode.DESTROYED_MODE}[string(part['condition'])]


def make_unit(value, index, board, special):
    fields(value, UNIT_FIELDS)
    unit = Mech(name=string(value.get('id', 'A')))
    unit._id = index + 1
    unit.unit_type = UnitType[string(value.get('class', 'MECH'))]
    unit.move_type = MoveType[string(value.get('movement', 'BIPED'))]
    unit.tonnage = number(value.get('tons', 50), 1, integer=True)
    mass = value.get('actual_tons', unit.tonnage)
    unit.measured_mass = None if mass is None else int(number(mass, 0.001) * 1024)
    for name, default in (('max_speed', 64.5), ('speed', 0), ('desired_speed', 0),
                          ('vertical_speed', 0), ('jump_mp', 3), ('heat', 0)):
        setattr(unit, name, number(value.get(name, default), 0 if name in ('max_speed', 'jump_mp', 'heat') else None))
    unit.jump_speed = unit.jump_mp * 10.75
    for name, default in (('facing', 0), ('desired_facing', value.get('facing', 0)),
                          ('pilot_skill_base', 0), ('team', 1), ('fuel', 1000), ('stagger_level', 0)):
        setattr(unit, name, number(value.get(name, default), integer=True))
    unit.stagger_damage = unit.stagger_level * 20
    unit.lateral = number(value.get('lateral', 0), integer=True)
    if unit.lateral not in (0, 60, 120, 240, 300):
        raise ValueError('unsupported lateral offset')
    unit.cocoon = number(value.get('cocoon', 0), -1, integer=True)
    pilot_id = value.get('pilot_id', 'P')
    unit.pilot = None if pilot_id is None else Pilot(name=string(pilot_id), piloting=number(value.get('pilot_skill', 5), 0, integer=True))
    for advantage in array(value.get('advantages', ['dodge_maneuver', 'maneuvering_ace'])):
        if advantage not in ('dodge_maneuver', 'maneuvering_ace', 'speed_demon') or unit.pilot is None:
            raise ValueError('unsupported pilot advantage')
        setattr(unit.pilot, advantage, True)
    for loc, section in enumerate(unit.sections):
        section.armor = section.armor_orig = 1000
        section.internal = section.internal_orig = 1000
        section.rear = section.rear_orig = 1000 if loc in (2, 3, 4) else 0
    from entities.crittypes import i2special, Special
    for loc in (Location.LARM, Location.RARM, Location.LLEG, Location.RLEG):
        for slot in range(4):
            unit.sections[loc].criticals[slot].type = i2special(slot)
    seen = set()
    for section in array(value.get('sections', [])):
        if not isinstance(section, dict): raise ValueError('expected a section object')
        if section.get('location') in seen:
            raise ValueError('duplicate section fixture')
        seen.add(section.get('location'))
        section_fixture(unit, section)
    unit.set_status(S.STARTED)
    for state in array(value.get('states', [])):
        if state in STATE_FLAGS:
            unit.set_status(STATE_FLAGS[state])
        elif state in MODE_FLAGS:
            unit.set_status2(MODE_FLAGS[state])
        elif state not in EXTRA_STATES:
            raise ValueError(f'unsupported state {state!r}; pending actions require commands')
        elif state == 'waterproof': unit.specials2 |= 0x100000
        elif state == 'hip_disabled': unit.sections[Location.LLEG].criticals[0].firemode |= FireMode.DISABLED_MODE
        elif state == 'no_move': unit.move_type = MoveType.NONE
        elif state == 'weapon_recycle': unit.weapons.append(WeaponState(recycle=60))
        elif state == 'limb_recycle': unit.sections[Location.LARM].recycle = 60
        elif state == 'charging': unit.charge_target = 2
        elif state == 'mounted': pass  # resolved against the registered units below
        elif state == 'masc': unit.set_status(S.MASC_ENABLED)
        elif state == 'supercharger': unit.set_status(S.SCHARGE_ENABLED)
        elif state == 'hot_tsm':
            unit.specials |= Specials.TRIPLE_MYOMER_TECH
            unit.heat = 9
        elif state in ('gyro_damaged', 'gyro_destroyed'): unit.set_crit_status(CritStatus[state.upper()])
        else: setattr(unit, state, True)
        if state in ('dug_in', 'digging', 'tail_rotor_destroyed'):
            unit.tank_crit_status = getattr(unit, 'tank_crit_status', 0) | {'dug_in': 4, 'digging': 8, 'tail_rotor_destroyed': 32}[state]
    if special:
        unit.set_status(S.UNDERSPECIAL | S.UNDERGRAVITY)
    return unit


def setup_units(values, board, engine, map_config):
    units, configs = {}, {}
    for index, value in enumerate(array(values)):
        unit = make_unit(value, index, board, boolean(map_config.get('special_rules', False)))
        if unit.name in units:
            raise ValueError('duplicate unit ID')
        units[unit.name], configs[unit.name] = unit, value
    placed = set()
    def place(name, visiting):
        if name in placed: return
        if name in visiting: raise ValueError('cyclic relative placement')
        unit, cfg = units[name], configs[name]
        if 'relative_position' in cfg:
            if 'at' in cfg: raise ValueError('relative_position and at are mutually exclusive')
            relative = fields(cfg['relative_position'], ('to', 'bearing', 'range'), ('to', 'bearing', 'range'))
            reference = string(relative['to'])
            place(reference, visiting | {name})
            origin = units[reference]
            dx, dy = find_components(number(relative['range'], 0) * SCALEMAP, number(relative['bearing']))
            fx, fy = origin.fx + dx, origin.fy + dy
            x, y = float_to_hex(fx, fy)
            z = number(cfg.get('altitude', 0), integer=True)
        else:
            if 'altitude' in cfg: raise ValueError('altitude requires relative_position')
            x, y, z = coordinates(cfg.get('at', [3, 3, 0]), board, True)
            fx = fy = None
        if not board.valid(x, y): raise ValueError('relative placement is off-map')
        unit.set_hex_position(x, y)
        if fx is not None: unit.fx, unit.fy = fx, fy
        unit.z, unit.fz = z, z * ZSCALE
        board.add_mech(unit)
        unit.terrain, unit.elev = board.terrain(x, y), board.elevation(x, y)
        if unit.terrain == TERRAINS['ICE'] and z < -unit.elev:
            raise ValueError('unit below ice floor')
        engine.register_entity(unit)
        unit._engine = engine
        placed.add(name)
    for name in units: place(name, set())
    callers = {}
    for name, unit in units.items():
        cfg = configs[name]
        caller_id = cfg.get('caller_id', cfg.get('pilot_id', 'P'))
        callers[name] = unit.pilot if caller_id == cfg.get('pilot_id', 'P') else Pilot(name=string(caller_id))
        if 'target_hex' in cfg: unit.targ_x, unit.targ_y = coordinates(cfg['target_hex'], board)
        if 'target_id' in cfg: unit.target = units[string(cfg['target_id'])]._id
        if 'mounted' in cfg.get('states', []):
            hosts = [u for u in units.values() if u is not unit]
            if not hosts: raise ValueError('mounted requires another unit as host')
            unit.swarm_target = hosts[0]
        load = fields(cfg.get('load', {}), ('cargo_tons', 'tow', 'salvage', 'cargo_tech', 'carrier', 'cache_valid'))
        unit.carried_cargo = int(number(load.get('cargo_tons', 0), 0) * 1024)
        if 'tow' in load:
            unit.towed_unit = units[string(load['tow'])]
            if unit.towed_unit is unit: raise ValueError('cannot tow self')
            unit.carrying = unit.towed_unit._id
        for key, flag in (('salvage', Specials.SALVAGE_TECH), ('cargo_tech', Specials.CARGO_TECH)):
            if boolean(load.get(key, False)): unit.specials |= flag
        if boolean(load.get('carrier', False)): unit.specials2 |= 0x80000
        if boolean(load.get('cache_valid', False)):
            from physics.cargo import cargo_max_speed
            cargo_max_speed(unit)
        if 'turret' in cfg:
            turret = fields(cfg['turret'], ('present', 'jammed', 'locked', 'facing'))
            unit.has_turret = boolean(turret.get('present', True))
            unit.turret_jammed = boolean(turret.get('jammed', False))
            unit.turret_locked = boolean(turret.get('locked', False))
            unit.tank_crit_status = (getattr(unit, 'tank_crit_status', 0) & ~3) | (2 if unit.turret_jammed else 0) | (1 if unit.turret_locked else 0)
            if not unit.has_turret: unit.sections[4].internal = 0
            unit.turret_facing = number(turret.get('facing', 0), integer=True)
    return units, callers
