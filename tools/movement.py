"""Run ordered movement commands on a real map and production event engine."""
import argparse
from contextlib import contextmanager, redirect_stdout
from dataclasses import asdict
from io import StringIO
import json
from pathlib import Path
import random
import sys

from core.game_loop import GameEngine, register_special_objects
from core.events import EventType
from core.randomness import use_source, use_simulation
from entities.mech import MechStatus as S, MechStatus2 as S2, Location, SectionConfig, FireMode
from systems import movement_commands as commands, maneuver
from physics import movement, orbital, ice
from physics.cargo import cargo_max_speed
from systems.heat import calculate_movement_heat
from tools.movement_inputs import fields, number, boolean, string, array, coordinates, make_map, setup_units
from tools.path_cost_inputs import TERRAINS, COST_FUNCTIONS

STREAMS = {'pilot_rolls': (2, 12), 'percentage_draws': (1, 100), 'neighbor_d6': (1, 6),
           'neighbor_d3': (1, 3), 'surface_draws': (1, 100), 'ice_d6': (1, 6),
           'fall_directions': (1, 6), 'interception_rolls': (2, 12), 'suit_d4': (1, 4),
           'suit_members': (0, 7), 'hit_location_rolls': (2, 12),
           'critical_rolls': (2, 12), 'attack_rolls': (2, 12), 'fire_rolls': (2, 12),
           'fuel_check':(0,1), 'sideslip_rotation':(0,5), 'visibility_change':(-40,40),
           'domino_target':(0,2**31-1), 'suit_fall_location':(0,5), 'rolls':(2,12),
           'damage_entry':(2,12),'tow_rolls':(2,12),'sensor.random':(0,2**31-1),
           'map_contact_id':(0,25),'failure_generic_chance':(1,5000)}


class Dice:
    def __init__(self, values, deterministic):
        fields(values, (*STREAMS, 'seed'))
        self.queues, self.consumed, self.draws = {}, {}, []
        self.deterministic = deterministic
        self.specified = set(values)
        random.seed(number(values.get('seed', 0), integer=True))
        for name, bounds in STREAMS.items():
            self.queues[name] = [number(v, *bounds, integer=True) for v in array(values.get(name, []))]
            self.consumed[name] = 0

    def __call__(self, name, low, high, fallback):
        self.queues.setdefault(name,[])
        self.consumed.setdefault(name,0)
        index = self.consumed[name]
        if index < len(self.queues[name]):
            value = number(self.queues[name][index], low, high, True)
        elif name in ('suit_members', 'suit_d4', 'hit_location_rolls',
                      'critical_rolls', 'attack_rolls', 'fire_rolls') and name not in self.specified:
            value = fallback()  # Seeded damage-location dice unless explicitly supplied.
        elif self.deterministic:
            raise ValueError(f'deterministic dice exhausted: {name}')
        else:
            value = fallback()
        self.consumed[name] += 1
        self.draws.append({'name': name, 'value': value, 'range': [low, high]})
        return value


@contextmanager
def observe(session):
    """Collect production notifications and actual resolved rolls/damage."""
    from systems import piloting, combat, damage as damage_system, sensors
    originals = movement.NOTIFY_HOOK, piloting.make_piloting_roll, combat.apply_damage_with_transfer
    old_hooks = damage_system.NOTIFY_HOOK, sensors.NOTIFY_HOOK
    def notify(unit, text):
        session.messages.append({'unit': unit.name, 'text': text})
    def pilot(*args, **kwargs):
        result = originals[1](*args, **kwargs)
        session.rolls.append({'unit': args[0].name, 'target': result.target,
                              'roll': result.roll, 'success': result.success,
                              'modifier': args[1] if len(args) > 1 else kwargs.get('modifier', 0)})
        return result
    def damage(*args, **kwargs):
        amount = originals[2](*args, **kwargs)
        session.hits.append({'unit': args[0].name, 'section': int(args[1]),
                             'requested': args[2], 'resolved': amount})
        return amount
    movement.NOTIFY_HOOK, piloting.make_piloting_roll, combat.apply_damage_with_transfer = notify, pilot, damage
    damage_system.NOTIFY_HOOK = sensors.NOTIFY_HOOK = notify
    try:
        yield
    finally:
        damage_system.NOTIFY_HOOK, sensors.NOTIFY_HOOK = old_hooks
        movement.NOTIFY_HOOK, piloting.make_piloting_roll, combat.apply_damage_with_transfer = originals


class Session:
    def __init__(self, document):
        fields(document, ('map', 'units', 'config', 'random', 'actions'), ('actions',))
        self.actions = array(document['actions'])
        self.board = make_map(document.get('map', {}))
        self.board._id = 1_000_000  # Disjoint from the fixture unit IDs (1..255).
        self.engine = GameEngine()
        self.engine.register_entity(self.board)
        config = fields(document.get('config', {}), ('periodic_updates', 'movement_modes', 'damage_weight',
            'overspeeding', 'tsm_sprint_bonus', 'tsm_tow_bonus', 'sprint_bth', 'stand_careful', 'stacking', 'new_stagger'))
        # Unsupported alternate profiles must never be silently accepted.
        fixed = {'movement_modes': True, 'damage_weight': 'nominal', 'overspeeding': False,
                 'stacking': True}
        for name, default in fixed.items():
            if name in config and (type(config[name]) is not type(default) or config[name] != default):
                raise ValueError(f'unsupported configuration {name}; supported value is {default!r}')
        self.engine.standcareful = boolean(config.get('stand_careful', True))
        self.engine.new_stagger = int(boolean(config.get('new_stagger', False)))
        if boolean(config.get('periodic_updates', True)):
            register_special_objects(self.engine)
        self.units, self.callers = setup_units(document.get('units', [{}]), self.board, self.engine, document.get('map', {}))
        for unit in self.units.values():
            unit.tsm_sprint_bonus = boolean(config.get('tsm_sprint_bonus', True))
            unit.tsm_tow_bonus = boolean(config.get('tsm_tow_bonus', True))
            unit.btech_sprint_bth = number(config.get('sprint_bth', -4), integer=True)
        self.dice = Dice(document.get('random', {}), 'random' in document)
        if 'seed' in document.get('random',{}): self.engine.randomness.mt.seed(document['random']['seed'])
        self.messages, self.rolls, self.hits = [], [], []

    def unit(self, action, field='unit'):
        return self.units[string(action[field])]

    def snapshot(self):
        reverse = {value: name for name, value in TERRAINS.items()}
        board = {'size': [self.board.map_width, self.board.map_height], 'hexes': [
            {'at': [x, y], 'terrain': reverse.get(self.board.terrain(x, y), self.board.terrain(x, y)),
             'elevation': self.board.elevation(x, y)}
            for x in range(self.board.map_width) for y in range(self.board.map_height)]}
        units = {}
        for name, u in self.units.items():
            sections = {loc.name: {'front': s.armor, 'rear': s.rear, 'internal': s.internal,
                'flooded': bool(s.config & SectionConfig.SECTION_FLOODED), 'recycle': s.recycle,
                'components': [{'type': c.type, 'data': c.data,
                    'condition': 'disabled' if c.firemode & FireMode.DISABLED_MODE else
                        'destroyed' if c.firemode & FireMode.DESTROYED_MODE else 'working'} for c in s.criticals]}
                for loc, s in zip(Location, u.sections)}
            event = u._mode_event
            transition = 'NONE'
            if event is not None and not event.zombie:
                transition = {S2.SPRINTING: 'SPRINT', S2.EVADING: 'EVADE', S2.DODGING: 'DODGE'}[event.data2[0]]
                transition += '_ON' if event.data2[1] else '_OFF'
            units[name] = {'at': [u.x, u.y, u.z], 'fz': u.fz, 'speed': u.speed, 'desired_speed': u.desired_speed,
                'facing': u.facing, 'desired_facing': u.desired_facing, 'vertical_speed': u.vertical_speed,
                'class': u.unit_type.name, 'movement': u.move_type.name, 'terrain': reverse.get(u.terrain, u.terrain),
                'mode': next((label for flag, label in ((S2.SPRINTING, 'SPRINT'), (S2.EVADING, 'EVADE'), (S2.DODGING, 'DODGE')) if u.has_status2(flag)), 'NONE'),
                'pending_transition': transition, 'fallen': u.is_fallen, 'jumping': u.is_jumping,
                'hulldown': u.has_status(S.HULLDOWN), 'landed': u.has_status(S.LANDED), 'started': u.is_started, 'destroyed': u.is_destroyed,
                'cocoon': u.cocoon, 'lateral': u.lateral, 'lateral_description': maneuver.LATERAL_NAMES[u.lateral],
                'pilot_injuries': u.pilot_hits, 'jump_mp': u.jump_mp, 'heat': u.heat, 'sections': sections,
                'timers': {kind.name: self.engine.event_time_remaining(kind, u) for kind in EventType
                    if self.engine.events.has_event_type_data(kind, u)},
                'last_fall_levels': getattr(u, 'last_fall_levels', 0),
                'required_roll': getattr(u, 'last_ood_target', None),
                'piloting_modifier': getattr(u, 'last_piloting_modifier', None),
                'turn_mode': u.turn_mode, 'torso_left': u.has_status(S.TORSO_LEFT), 'torso_right': u.has_status(S.TORSO_RIGHT),
                'turret_facing': getattr(u, 'turret_facing', None), 'los_dirty': u.mapflag,
                'num_sinks': u.num_sinks, 'digging': u.digging, 'dug_in': u.dug_in}
        return {'tick': self.engine.tick, 'map': board, 'units': units}

    def command(self, action):
        fields(action, ('op', 'unit', 'name', 'args'), ('op', 'unit', 'name', 'args'))
        unit, name = self.unit(action), string(action['name'])
        args = array(action['args'])
        if any(not isinstance(v, str) for v in args): raise ValueError('command args must be strings')
        caller, engine = self.callers[unit.name], self.engine
        noargs = {'sprint', 'evade', 'dodge', 'prone', 'land', 'thrash', 'shutdown'}
        unary = {'hulldown', 'heading', 'speed', 'vertical', 'lateral', 'turnmode', 'torso', 'turret', 'bootlegger', 'stand'}
        if name not in noargs | unary | {'jump', 'ood', 'eta'}:
            raise ValueError(f'unknown command {name}')
        text = ' '.join(args)
        if name in ('sprint', 'evade', 'dodge'): result = commands.set_mode(engine, unit, name, caller)
        elif name == 'shutdown':
            from systems.startup import shutdown
            result = shutdown(engine, unit, caller=caller)
        elif name in ('prone', 'land', 'thrash'): result = getattr(commands, name)(engine, unit, caller)
        elif name == 'jump': result = commands.jump_command(engine, unit, text, caller)
        elif name == 'ood': result = orbital.initiate_ood(engine, unit, text)
        elif name in ('lateral', 'turnmode', 'torso'):
            function = {'lateral': maneuver.set_lateral, 'turnmode': maneuver.set_turnmode, 'torso': maneuver.rotate_torso}[name]
            result = function(engine, unit, text, caller=caller)
        elif name == 'turret': result = maneuver.set_turret(engine, unit, text if args else None, caller)
        else: result = getattr(commands, name)(engine, unit, text, caller)
        return {'accepted': result[0], 'message': result[1], **({'eta': result[1]} if name == 'eta' else {})}

    def action(self, action):
        if not isinstance(action, dict) or 'op' not in action: raise ValueError('action requires op')
        op = string(action['op'])
        if op == 'command': return self.command(action)
        if op == 'advance':
            fields(action, ('op', 'seconds'), ('seconds',))
            self.engine.run_ticks(number(action['seconds'], 0, 10000, True))
            return {}
        if op == 'inspect':
            fields(action, ('op', 'unit'))
            units = [self.unit(action)] if 'unit' in action else list(self.units.values())
            return {'queries': {u.name: {'effective_max_speed': cargo_max_speed(u),
                'movement_heat': calculate_movement_heat(u)} for u in units}}
        if op == 'ice':
            fields(action, ('op', 'name', 'args'), ('name', 'args'))
            functions = {'addice': ice.map_addice, 'delice': ice.map_delice}
            args = array(action['args'])
            if any(not isinstance(v, str) for v in args): raise ValueError('ice args must be strings')
            before = [self.board.terrain(x, y) for x in range(self.board.map_width) for y in range(self.board.map_height)]
            accepted, message = functions[string(action['name'])](self.board, ' '.join(args))
            after = [self.board.terrain(x, y) for x in range(self.board.map_width) for y in range(self.board.map_height)]
            return {'accepted': accepted, 'message': message, 'changed_hexes': sum(a != b for a, b in zip(before, after))}
        if op == 'path_cost':
            fields(action, ('op', 'mode', 'from', 'to'), ('mode', 'from', 'to'))
            points = [number(v, integer=True) for key in ('from', 'to') for v in array(action[key], 2)]
            return {'cost': COST_FUNCTIONS[string(action['mode'])](self.board, *points)}
        if op == 'hit_hex':
            fields(action, ('op', 'attacker', 'at', 'weapon_damage'), ('attacker', 'at', 'weapon_damage'))
            from entities.weapon import Weapon, register_weapon
            from systems.combat import hex_hit
            attacker = self.unit(action, 'attacker')
            weapon = register_weapon(Weapon(name='Scenario impact', damage=number(action['weapon_damage'], 0, integer=True)))
            xy = coordinates(action['at'], self.board)
            attacker.clear_status(S.LOCK_MODES)
            attacker.set_status(S.LOCK_HEX)
            hex_hit(attacker, *xy, weapon.index, 0, weapon.damage, 1)
            return {}
        if op == 'damage':
            fields(action, ('op', 'unit', 'attacker', 'section', 'external', 'internal'), ('unit', 'attacker', 'section', 'external', 'internal'))
            from systems.combat import apply_damage_with_transfer
            from systems.damage import cause_internal_damage
            unit, attacker = self.unit(action), self.unit(action, 'attacker')
            external, internal = [number(action[key], 0, integer=True) for key in ('external', 'internal')]
            loc = Location[string(action['section'])]
            if external and internal: raise ValueError('combined external/internal damage has no faithful entrypoint (D2)')
            if internal:
                overflow, _ = cause_internal_damage(unit, attacker, loc, internal, engine=self.engine)
                amount = internal - overflow
            else: amount = apply_damage_with_transfer(unit, loc, external, attacker=attacker, engine=self.engine)
            return {'resolved_damage': amount}
        if op == 'cocoon_hit':
            fields(action, ('op', 'unit', 'attacker', 'damage'), ('unit', 'attacker', 'damage'))
            orbital.cocoon_damage(self.unit(action), self.unit(action, 'attacker'), number(action['damage'], 0, integer=True))
            return {}
        if op == 'fall':
            fields(action, ('op', 'unit', 'levels', 'show_message'), ('unit', 'levels'))
            from physics.jump import mech_falls
            return {'fall': asdict(mech_falls(self.unit(action), number(action['levels'], 0, integer=True),
                                notify_fall=boolean(action.get('show_message', True))))}
        if op == 'surface':
            fields(action, ('op', 'unit', 'name'), ('unit', 'name'))
            function = {'break_up': movement.break_thru_ice, 'drop_down': movement.drop_thru_ice,
                        'drop_chance': movement.possibly_drop_thru_ice}[string(action['name'])]
            result = function(self.unit(action))
            return {'dropped': bool(result)} if action['name'] == 'drop_chance' else {}
        if op == 'flood':
            fields(action, ('op', 'unit'), ('unit',))
            from physics.flooding import flood_unit
            flood_unit(self.unit(action))
            return {}
        if op == 'scan':
            fields(action, ('op', 'unit'), ('unit',))
            from systems.targeting import start_plos_event
            start_plos_event(self.engine, self.unit(action))
            return {}
        if op == 'limb_use':
            fields(action, ('op', 'unit', 'location', 'seconds'), ('unit', 'location', 'seconds'))
            from systems.physical import set_recycle_limb
            unit = self.unit(action)
            event = unit._mode_event
            if event is None or event.zombie or event.data2 != (S2.DODGING, True):
                raise ValueError('limb_use requires a pending dodge activation')
            loc = Location[string(action['location'])]
            if loc not in (Location.LARM, Location.RARM, Location.LLEG, Location.RLEG):
                raise ValueError('limb_use requires an arm or leg')
            set_recycle_limb(unit, loc, number(action['seconds'], 1, 60, True))
            return {'recycle': unit.sections[loc].recycle}
        if op == 'fire':
            fields(action, ('op', 'unit', 'target', 'weapon', 'roll'), ('unit', 'target', 'weapon', 'roll'))
            from entities.weapon import get_weapon
            from entities.mech import WeaponState
            from entities.crittypes import i2weapon
            from systems.combat import fire_weapon_number
            unit, target = self.unit(action), self.unit(action, 'target')
            weapon = get_weapon(string(action['weapon']))
            if weapon is None or weapon.uses_ammo:
                raise ValueError('fire supports a named energy weapon only')
            matches = [i for i, w in enumerate(unit.weapons) if w.weapon_idx == weapon.index]
            if not matches:
                slot = unit.sections[Location.CTORSO].criticals[8]
                slot.type = i2weapon(weapon.index)
                unit.weapons.append(WeaponState(section=Location.CTORSO, critical=8, weapon_idx=weapon.index))
            self.engine.fire_unlocked_id = True
            result = fire_weapon_number(self.engine, unit, matches[0] if matches else len(unit.weapons)-1,
                target=target, to_hit_roll=number(action['roll'], 2, 12, True), location_roll=7)
            return {'attack': asdict(result), 'weapon_recycle': unit.weapons[-1].recycle}
        if op == 'punch':
            fields(action, ('op', 'unit', 'target', 'arm', 'roll', 'location_roll'), ('unit', 'target', 'arm', 'roll', 'location_roll'))
            from systems.physical import mech_punch
            results = mech_punch(self.unit(action), self.unit(action, 'target'), string(action['arm']),
                number(action['roll'], 2, 12, True), number(action['location_roll'], 1, 6, True))
            return {'attacks': [asdict(r) for r in results]}
        raise ValueError(f'unknown op {op}')

    def run(self):
        results = []
        with observe(self), use_simulation(self.engine.randomness), use_source(self.dice):
            for action in self.actions:
                self.messages, self.rolls, self.hits = [], [], []
                output = StringIO()
                with redirect_stdout(output): result = self.action(action)
                if output.getvalue():
                    raise ValueError(f'engine diagnostic during {action.get("op")}: {output.getvalue().strip()}')
                returned_messages = [result['message']] if result.get('message') else []
                for attack in result.get('attacks', []) + ([result['attack']] if 'attack' in result else []):
                    returned_messages.extend(attack['messages'])
                for message in returned_messages:
                    if not any(m['text'] == message for m in self.messages):
                        self.messages.append({'unit': action.get('unit'), 'text': message})
                results.append({'op': action['op'], **result, 'messages': self.messages,
                    'pilot_rolls': self.rolls, 'damage_clusters': self.hits,
                    'snapshot': self.snapshot(), 'consumed': dict(self.dice.consumed)})
        return {'results': results, 'draws': self.dice.draws, 'consumed': self.dice.consumed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=(
        'Run ordered movement workflows: python3 -m tools.movement --script FILE. '
        'JSON fields: map, units, config, random, actions. Distances use hex ranges, '
        'speed KPH (10.75 per MP), stored elevations 0..9, signed altitude, time seconds. '
        'Commands: sprint evade dodge hulldown heading speed vertical lateral turnmode torso turret '
        'eta bootlegger prone stand jump land ood thrash shutdown. Actions also include advance, '
        'ice addice/delice, hit_hex, damage, cocoon_hit, fall, surface, flood, inspect, path_cost, scan, fire, punch. '
        'limb_use supplies 1..60 seconds of real arm/leg recycle only during pending dodge activation. '
        'Output: JSON results, snapshots, notifications, actual damage clusters, rolls and timers. '
        'Named FIFO dice are strict when random is supplied; missing/exhausted draws fail. '
        'Damage-location and other ordinary dice use seed 0 by default. '
        'Fixtures and supported states/components/configuration are documented in tools/movement_inputs.py. '
        'Limits D1-D7: measured mass is not a live weight ledger; class damage, aircraft, mines, '
        'stagger, normalization, world broadcasts and decorated terrain remain partial. '
        'Full combined external/internal damage is unsupported.'))
    parser.add_argument('--script', type=Path, required=True, help='workflow JSON file (see tools/movement_inputs.py)')
    args = parser.parse_args(argv)
    try:
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result: raise ValueError(f'duplicate JSON field {key}')
                result[key] = value
            return result
        document = json.loads(args.script.read_text(), object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'nonfinite number {value}')))
        session = Session(document)
        result = session.run()
        serialized = json.dumps(result, sort_keys=True, allow_nan=False)
    except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        parser.error(str(error))
    print(serialized)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
