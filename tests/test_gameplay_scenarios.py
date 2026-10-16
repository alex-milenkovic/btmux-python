"""Command-driven gameplay encounters, with public stdio replay parity.

Run: python -B -m tests.test_gameplay_scenarios
Record: python -B -m tests.test_gameplay_scenarios --record tmp/gameplay-results
One encounter: python -B -m tests.test_gameplay_scenarios --replay dfa_miss

Only fixture construction establishes state. After that, this driver sends
ordinary commands and advances the existing clock. Observations never call
collision, damage, landing, critical, flooding, or explosion helpers.
"""
from copy import deepcopy
import argparse
import importlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
REPLAYS = ROOT / 'examples' / 'gameplay_scenarios'
MANIFEST = json.loads((REPLAYS / 'manifest.json').read_text())
CLASSES = {'core_simulation': 'CoreSession', 'communications': 'CommunicationsSession',
           'maps_environment': 'MapsSession', 'aerospace': 'AerospaceSession'}


def document(name, directory):
    doc = json.loads((REPLAYS / (name + '.json')).read_text())
    interface = MANIFEST[name]['interface']
    if interface != 'core_simulation': doc['file_root'] = str(directory / 'maps')
    if interface in ('communications', 'aerospace'):
        doc['pilots'] = dict(doc.get('pilots', {}), root=str(directory / 'people'))
        doc['construction'] = {'root': str(directory / 'templates')}
    # No diagnostic action can accidentally masquerade as gameplay.
    assert all(a['op'] in ('command', 'advance', 'inspect') for a in doc['actions'])
    allowed = {'lock', 'sight', 'fire', 'speed', 'heading', 'stand', 'jump', 'c3',
               'spot', 'addtic', 'firetic', 'explode', 'contacts', 'sensor', 'slite',
               'hide', 'startup', 'shutdown', 'prone', 'safety'}
    assert all(a['name'] in allowed for a in doc['actions'] if a['op'] == 'command')
    return doc


def observation(session):
    """Read-only, small enough for a tick trace and independent assertions."""
    from entities.crittypes import is_ammo
    from entities.mech import FireMode, SectionConfig
    units = {}
    for name, u in session.units.items():
        units[name] = dict(at=[u.x, u.y, u.z], real=[round(u.fx, 5), round(u.fy, 5), round(u.fz, 5)],
            map=u.map.name if u.map else None, speed=round(u.speed, 4), facing=u.facing,
            started=u.is_started, jumping=u.is_jumping, fallen=u.is_fallen,
            destroyed=u.is_destroyed, unconscious=u.is_unconscious,
            damage=u.damage_taken, heat=round(u.heat, 4), pilot_hits=u.pilot_hits,
            target=u.target, crit_status=int(u.crit_status), masters=getattr(u, 'working_c3_masters', 0),
            sections=[[s.armor, s.rear, s.internal] for s in u.sections],
            flooded=[i for i, s in enumerate(u.sections) if s.config & SectionConfig.SECTION_FLOODED],
            disabled=[[i, j] for i, s in enumerate(u.sections) for j, c in enumerate(s.criticals)
                      if c.type and c.firemode & (FireMode.DISABLED_MODE | FireMode.DESTROYED_MODE)],
            recycle=[s.recycle for s in u.sections],
            ammo=sum(c.data for s in u.sections for c in s.criticals if is_ammo(c.type)))
        dfa = getattr(u, 'last_dfa_result', None)
        if dfa:
            units[name]['dfa'] = {k: getattr(dfa, k) for k in
                ('hit', 'roll', 'bth', 'damage_dealt', 'attacker_damage', 'attacker_fell', 'target_fell')}
    maps = {}
    for name, b in session.maps.items():
        maps[name] = dict(projectiles=[{k: getattr(p, k) for k in ('from_x', 'from_y', 'to_x', 'to_y', 'is_hit')}
                                      for p in b.projectiles], impacts=deepcopy(b.artillery_impacts),
            decorations=[dict(at=[o.x, o.y], terrain=b.terrain(o.x, o.y)) for o in b.decorations.values()],
            terrain=[[x, y, b.terrain(x, y), b.elevation(x, y)]
                     for x, y in getattr(session, '_scenario_cells', {}).get(name, [])])
    events = [dict(kind=e.event_type.name, unit=next((n for n, u in session.units.items() if e.data is u), None),
                   deadline=e.tick) for e in session.engine.events.pending_events()
              ]
    state = dict(tick=session.engine.tick, units=units, maps=maps, events=events)
    if getattr(session, '_scenario_los', False):
        from tests.gameplay_los_support import observe
        observe(session, state)
    return state


def significant(state):
    """Do not emit every fractional step, cooling tick or recycle decrement."""
    value = deepcopy(state)
    value.pop('tick')
    value['events'] = [e for e in value['events'] if e['kind'] not in ('PLOS', 'MOVE')]
    for u in value['units'].values():
        for key in ('real', 'speed', 'heat', 'facing'): u.pop(key)
        u['recycle'] = [bool(v) for v in u['recycle']]
    for e in value['events']: e.pop('deadline')
    for pair in value.get('los', {}).values(): pair.pop('range')
    for u in value['units'].values():
        if 'weapon_recycle' in u: u['weapon_recycle'] = [bool(v) for v in u['weapon_recycle']]
    return value


def command_summary(result):
    result = deepcopy(result)
    attack = result.get('attack')
    if attack:
        result['attack'] = {k: attack[k] for k in ('hit', 'roll', 'bth', 'location', 'damage_dealt',
                                                  'criticals_rolled', 'bth_breakdown')}
    result.pop('result', None)
    return result


def play(name):
    """The existing session adapter supplies detailed timelines; CLI replays it."""
    interface = MANIFEST[name]['interface']
    with TemporaryDirectory(prefix='btmux-scenario-') as directory:
        doc = document(name, Path(directory) / 'local')
        session = getattr(importlib.import_module('tools.' + interface), CLASSES[interface])(doc)
        session._scenario_los = name.startswith('los_')
        session._scenario_cells = {b.get('name', 'main'): [tuple(h['at']) for h in b.get('hexes', [])]
                                   for b in doc.get('maps', [doc.get('map', {})])}
        frames, commands, results = [], [], []
        cursors, inbox_cursors = {}, {}

        def note(command=None, result=None, force=False):
            state = observation(session)
            messages, inboxes = {}, {}
            def meaningful(text):
                if text.startswith('Self-destruction in '):
                    return session.engine.tick in (1, 30, 60, 90, 117, 118, 119)
                return any(c.isalpha() for c in text)
            for n, u in session.units.items():
                new = u.movement_messages[cursors.get(n, 0):]
                cursors[n] = len(u.movement_messages)
                if new := [m for m in new if meaningful(m)]: messages[n] = new
            if hasattr(session, 'personnel'):
                for ident, actor in session.personnel.objects.items():
                    inbox = getattr(actor, 'inbox', [])
                    new = inbox[inbox_cursors.get(ident, 0):]
                    inbox_cursors[ident] = len(inbox)
                    if new := [m for m in new if meaningful(m)]: inboxes[str(ident)] = new
            elif session._scenario_los:
                for unit in session.units.values():
                    actor = unit.command_actor
                    ident = str(getattr(actor, '_id', unit._id))
                    inbox = getattr(actor, 'inbox', [])
                    new = inbox[inbox_cursors.get(ident, 0):]
                    inbox_cursors[ident] = len(inbox)
                    if new := [m for m in new if meaningful(m)]: inboxes[ident] = new
            if force or messages or inboxes or not frames or significant(state) != significant(frames[-1]['state']):
                frames.append(dict(state=state, messages=messages, delivered=inboxes,
                                   **({'command': command, 'result': command_summary(result)} if command else {})))

        note(force=True)
        for a in doc['actions']:
            if a['op'] == 'advance':
                for _ in range(a['seconds']):
                    result = session.action({'op': 'advance', 'seconds': 1})
                    assert not result.get('error'), result
                    note()
                result = {}
            else:
                result = session.action(a)
                if a['op'] == 'command':
                    commands.append(dict(tick=session.engine.tick, action=a, result=command_summary(result)))
                    note(a, result, force=True)
                else: note(force=True)
            results.append(result)
        state = session.snapshot()
        local = dict(name=name, interface=interface, commands=commands, frames=frames,
                     final=observation(session), draws=deepcopy(session.draws),
                     characters=state.get('characters', {}))
        public_doc = document(name, Path(directory) / 'public')
        process = subprocess.run([sys.executable, '-B', '-m', 'tools.' + interface],
            cwd=ROOT, input=json.dumps(public_doc), capture_output=True, text=True,
            encoding='utf-8', timeout=60, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8'))
        assert process.returncode == 0, process.stderr
        public = json.loads(process.stdout)
        # Public replay must agree on every command, named draw, and final unit.
        assert public['draws'] == json.loads(json.dumps(session.draws)), 'stdio random consumption differs'
        for a, expected, actual in zip(doc['actions'], results, public['results'], strict=True):
            if a['op'] == 'command': assert actual == json.loads(json.dumps(expected)), (a, expected, actual)
        for n, u in state['units'].items():
            assert public['state']['units'][n] == json.loads(json.dumps(u)), 'stdio unit differs: ' + n
        assert public['state'].get('characters', {}) == state.get('characters', {}), 'stdio occupants differ'
        assert public['state']['maps'] == json.loads(json.dumps(state['maps'])), 'stdio maps differ'
        assert public['state']['events'] == json.loads(json.dumps(state['events'])), 'stdio pending callbacks differ'
        local['stdio'] = dict(exit_status=process.returncode, command_results_match=True,
                              final_units_match=True, final_maps_match=True, pending_events_match=True, random_draws_match=True)
        return local


def check_scenario(run):
    """Milestones derived from the reviewed C callers, not generated goldens."""
    if run['name'].startswith('los_'):
        from tests.gameplay_los_support import check
        return check(run)
    from entities.mech import CritStatus
    from entities.map import ICE, WATER, FIRE, SMOKE, ROUGH, GRASSLAND
    name, final = run['name'], run['final']
    units = final['units']
    states = [f['state'] for f in run['frames']]
    commands = run['commands']
    checks = []
    def check(condition, label):
        checks.append(dict(milestone=label, passed=bool(condition)))
    def actions(unit, command):
        return [r for r in commands if r['action']['unit'] == unit and r['action']['name'] == command]
    def messages(unit):
        return '\n'.join(m for f in run['frames'] for m in f['messages'].get(unit, []))
    def observed(unit, predicate):
        return any(predicate(s['units'][unit]) for s in states)
    if name.startswith('dfa_'):
        a, t = units['Attacker'], units['Target']
        hit = name != 'dfa_miss'
        check(actions('Attacker', 'jump')[0]['result']['accepted'], 'jump command starts DFA')
        check(observed('Attacker', lambda u: u['jumping'] and u['at'][2] > 0), 'real airborne trajectory')
        check(a.get('dfa', {}).get('hit') == hit, 'hit/miss resolves at landing')
        check(t['damage'] >= 15 if hit else t['damage'] == 0, 'target receives hit damage only')
        check(a['damage'] >= 10 and a['dfa']['attacker_damage'] == 10, 'attacker receives DFA self damage')
        check(observed('Attacker', lambda u: any(u['recycle'])) and not any(a['recycle']), 'limbs recycle then become available')
        check('piloting skill' in messages('Attacker'), 'piloting consequences are exercised')
        if name != 'dfa_hit': check(observed('Attacker', lambda u: u['fallen']), 'failed attack or piloting causes a fall')
        check(not a['fallen'] and not a['jumping'] and a['at'][:2] != [3, 4], 'recovered attacker moves away')
        check(not any(e['kind'] == 'JUMP' for e in final['events']), 'jump callback cleans up')
    elif name.startswith('ice_'):
        broken = name == 'ice_break'
        u = units['Runner']
        terrain = final['maps']['main']['terrain'][0][2]
        check(terrain == (WATER if broken else ICE), 'ice transition follows actual entry draw')
        check(observed('Runner', lambda u: u['at'][:2] == [3, 4]), 'continuous movement crosses onto ice')
        fire = actions('Runner', 'fire')[0]['result']
        if broken:
            check(observed('Runner', lambda u: u['fallen'] and u['at'][2] == -2), 'fall reaches water floor')
            check(u['damage'] > 0 and 0 in u['flooded'] and [0, 4] in u['disabled'], 'exposed arm floods and disables laser')
            check(not fire['accepted'] and 'destroyed' in fire['text'], 'disabled laser refuses later fire')
            check(u['at'] == [3, 3, 0], 'damaged mech eventually walks out of the pond')
        else:
            check(u['damage'] == 0 and not u['flooded'] and fire['accepted'], 'intact ice preserves equipment and firing')
        check(not u['fallen'] and actions('Runner', 'speed')[-1]['result']['accepted'], 'standing pilot can request subsequent movement')
    elif name.startswith('ledge_'):
        u = units['Runner']
        check(observed('Runner', lambda u: u['at'] == [3, 5, 0]), 'actual boundary crossing reaches lower hex')
        if name == 'ledge_fall':
            check('run off the cliff' in messages('Runner') and u['damage'] >= 15, 'three-level edge causes failed-PSR fall')
        else:
            first_lower = next(s['units']['Runner'] for s in states if s['units']['Runner']['at'] == [3, 5, 0])
            check(first_lower['damage'] == 0 and not first_lower['fallen'], 'two-level descent causes no automatic fall')
            check('hill too steep' in messages('Runner'), 'next higher hex invokes wall collision')
            check((u['damage'] == 0) if name == 'ledge_stop' else (u['damage'] > 0 and 'run headlong' in messages('Runner')), 'wall PSR selects stop or damaging fall')
        check(observed('Runner', lambda u: u['speed'] == 0 and u['at'] == [3, 5, 0]), 'collision/fall stops at corrected position')
        check(not u['fallen'] and u['at'][0] > 3, 'pilot recovers and moves into open terrain')
    elif name.startswith('bay_'):
        check(all(units[n]['map'] == 'field' for n in ('Alpha', 'Bravo', 'Charlie')), 'three units cross real bay edge and transfer')
        check(all('You have left the bay.' in messages(n) for n in ('Alpha', 'Bravo', 'Charlie')), 'bay exit notifications delivered')
        check(any('bay' == s['units']['Alpha']['map'] for s in states), 'initial units are inside the valid bay')
        damage = sum(u['damage'] for u in units.values())
        check(damage == 0 if name == 'bay_orderly' else damage > 0, 'departure spacing selects clean exit or actual bump damage')
        check(len({tuple(units[n]['at']) for n in ('Alpha', 'Bravo', 'Charlie')}) == 3, 'landing zone is cleared after the encounter')
    elif name.startswith('stack_'):
        damage = sum(u['damage'] for u in units.values())
        check(damage == 0 if name == 'stack_2' else damage > 0, 'two eligible mechs are safe; third or weighted DropShip triggers stacking')
        if name == 'stack_dropship':
            check(units['Arriving']['damage'] > units['Ship']['damage'] > 0, 'DropShip target reverses collision damage split')
        elif name == 'stack_3':
            check(sum(units[n]['damage'] > 0 for n in ('Bravo', 'Charlie')) == 1, 'real random selection damages one standing target')
        check(units['Arriving']['at'][1] < (10 if name == 'stack_dropship' else 5), 'arriving mech continues beyond occupied hex')
    elif name.startswith('artillery_'):
        board = final['maps']['main']
        launch = next(s for s in states if s['maps']['main']['projectiles'])
        impact = next(s for s in states if s['maps']['main']['impacts'])
        check(impact['tick'] - launch['tick'] == 10, 'shell remains in flight for source minimum ten ticks')
        check(any(s['maps']['main']['projectiles'] and s['units']['Target']['at'][:2] != [3, 3] for s in states), 'target crosses a hex while shell is airborne')
        check(launch['units']['Target']['damage'] == 0 and units['Target']['damage'] > 0 and units['Neighbor']['damage'] > 0, 'damage occurs at impact and reaches neighboring hexes')
        actual = board['impacts'][0]
        check([actual['x'], actual['y']] == ([3, 3] if name == 'artillery_hit' else [4, 2]), 'seeded hit/scatter uses captured target coordinates')
        check(not board['projectiles'] and not any(e['kind'] == 'ARTILLERY_HIT' for e in final['events']), 'impact releases projectile and event')
        check(units['Gun']['ammo'] == 9 and units['Neighbor']['at'][:2] != [4, 3], 'ammunition is consumed and damaged neighbor resumes movement')
        if name == 'artillery_scatter': check('trajectory-correction data' in messages('Gun'), 'spotter observes miss and provides correction')
    elif name == 'reactor':
        check(not next(s for s in states if s['tick'] == 119)['units']['Reactor']['destroyed'], 'countdown has not detonated at tick 119')
        check(next(s for s in states if s['tick'] == 120)['units']['Reactor']['destroyed'], 'ordinary self-destruct detonates at tick 120')
        check(all(s[2] == 0 for s in units['Reactor']['sections']), 'reactor blast destroys all linked sections')
        check(units['Neighbor']['damage'] > 0 and units['Far']['damage'] == 0, 'nearby blast effect has bounded reach')
        check(not run['characters']['110']['alive'] and run['characters']['110']['location'] == 900, 'occupant dies and transfers to configured afterlife')
        check(run['characters']['111']['alive'] and units['Neighbor']['at'][:2] != [10, 9], 'surviving neighbor continues play')
        check(not any(e['unit'] == 'Reactor' or e['kind'] == 'EXPLODE' for e in final['events']), 'destruction removes reactor-owned callbacks')
        check(any(f['delivered'].get('110') for f in run['frames']), 'actual occupant inbox receives countdown/destruction')
    elif name == 'fire_smoke':
        check(any(any(c['terrain'] == FIRE for c in s['maps']['field']['decorations']) for s in states), 'weapon ignition starts timed fire')
        check(any(any(c['terrain'] == SMOKE for c in s['maps']['field']['decorations']) for s in states), 'wind-driven callbacks generate smoke')
        sights = actions('Observer', 'sight')
        check(sights[0]['result']['accepted'] and not sights[1]['result']['accepted'] and sights[-1]['result']['accepted'], 'clear visibility becomes obscured and returns after expiration')
        check(not final['maps']['field']['decorations'] and final['maps']['field']['terrain'][0][2] in (ROUGH, GRASSLAND), 'decorations expire and burned forest becomes source-defined terrain')
        check(actions('Observer', 'lock')[-1]['result']['accepted'] and actions('Observer', 'fire')[-1]['result']['accepted'], 'later lock and fire are legal')
    elif name == 'c3_maneuver_damage':
        sights = [r['result']['attack']['bth_breakdown'] for r in actions('Master', 'sight')]
        check([s['range_bracket'] for s in sights] == ['MED', 'SHORT', 'MED', 'LONG'], 'maneuver and hardware loss change real range brackets')
        check([s['c3_ref'] for s in sights] == [11, 11, 12, -1], 'closest eligible contributor falls back to backup then own range')
        check(units['Scout']['damage'] == 8 and units['Master']['damage'] == 8, 'ordinary hostile attacks damage both C3 units')
        check(all(r['result']['attack']['criticals_rolled'] == 1 for r in actions('Target', 'fire')), 'both hardware losses arise through critical resolution')
        check(units['Scout']['crit_status'] & CritStatus.C3_DESTROYED and units['Master']['masters'] == 0, 'slave and master hardware become unavailable')
        check(all(r['result']['accepted'] and r['result']['attack']['hit'] for r in actions('Master', 'fire')), 'master fires at every meaningful network stage')
        check(units['Scout']['at'][0] > 3 and not units['Scout']['destroyed'], 'damaged scout continues maneuvering')
    else: raise AssertionError('No milestone assertions for ' + name)
    return checks


RECORD = None
RESULTS = {}
class GameplayScenarios(unittest.TestCase):
    """One independently replayable test per purposeful encounter variant."""


def write_record(result, directory):
    """Full machine-readable evidence and a concise human-readable timeline."""
    name = result['name']
    input_link = quote(Path(os.path.relpath(REPLAYS / (name + '.json'), directory)).as_posix(), safe='/')
    directory.mkdir(parents=True, exist_ok=True)
    # Compact JSON preserves actual draws and fractional positions for inspection.
    (directory / (name + '.json')).write_text(json.dumps(result, separators=(',', ':')) + '\n', encoding='utf-8')
    rows = [f'# {name}', '', f"Replay: `python -B -m tests.test_gameplay_scenarios --replay {name}`",
            '', f"Inputs: [{name}.json]({input_link}). Detailed evidence: [{name}.json]({name}.json).",
            '', '| Tick | Command / meaningful change |', '|---:|---|']
    previous = None
    for frame in result['frames']:
        state, changes = frame['state'], []
        if 'command' in frame:
            a, r = frame['command'], frame['result']
            command = f"{a['unit']}: {a['name']} {' '.join(map(str, a.get('args', [])))}".rstrip()
            changes.append(f"`{command}` → " +
                           ('accepted' if r.get('accepted', r.get('ok')) else 'refused'))
            if not r.get('accepted', r.get('ok')):
                changes.append(r.get('text') or r.get('message') or r.get('error') or 'command unavailable')
            if attack := r.get('attack'):
                if bth := attack.get('bth_breakdown'):
                    changes.append(f"BTH {attack['bth']}, {bth['range_bracket']}, C3 reference {bth['c3_ref']}")
        for n, u in state['units'].items():
            old = previous['units'][n] if previous else {}
            parts = []
            for key in ('map', 'at', 'damage', 'fallen', 'jumping', 'destroyed', 'pilot_hits', 'flooded', 'disabled'):
                if u[key] != old.get(key) and (old or key in ('map', 'at')):
                    parts.append(f'{key}={u[key]}')
            if bool(any(u['recycle'])) != bool(any(old.get('recycle', []))):
                parts.append('physical recycle ' + ('active' if any(u['recycle']) else 'finished'))
            if u.get('dfa') != old.get('dfa'):
                parts.append('DFA ' + ('hit' if u['dfa']['hit'] else 'miss') + f" ({u['dfa']['roll']} vs {u['dfa']['bth']})")
            if parts: changes.append(n + ': ' + ', '.join(parts))
        for n, board in state['maps'].items():
            old = previous['maps'][n] if previous else {}
            for key in ('projectiles', 'impacts', 'decorations', 'terrain'):
                if board[key] != old.get(key, []) and board[key]:
                    value = board[key]
                    if key == 'terrain' and 'los' in state:
                        from tests.gameplay_los_support import terrain_label
                        value = [f'({x},{y}) {terrain_label(t)} z{z}' for x,y,t,z in value]
                    changes.append(n + ' ' + key + ': ' + str(value))
                elif old.get(key) and not board[key]: changes.append(n + ' ' + key + ': cleared')
        if 'los' in state:
            from tests.gameplay_los_support import timeline
            changes.extend(timeline(state, previous, frame.get('command'), frame.get('result', {})))
        # Messages retain source wording while collapsing repeated countdowns.
        excerpts = []
        for n, values in frame['messages'].items():
            for value in values:
                if any(term in value.lower() for term in ('break the ice', 'floods into', 'cliff', 'bump into',
                        'c3 system', 'miss your dfa', 'piloting skill fails', 'self-destruction in', 'smoke',
                        'trajectory-correction', 'have left the bay', 'finished standing', 'still recharg',
                        'destroyed', 'no line of sight', 'personal injury', 'stable lock',
                        'lock has been lost', 'now hidden', 'break out of', 'illuminated', 'lock clears')):
                    excerpts.append(n + ': ' + re.sub(r'%c[a-z]?', '', value))
        changes.extend(dict.fromkeys(excerpts))
        if changes:
            text = '; '.join(changes).replace('|', '\\|').replace('\n', ' / ')
            rows.append(f"| {state['tick']} | {text} |")
        previous = state
    rows.extend(['', 'Milestones:', ''])
    rows.extend('- ' + ('PASS' if c['passed'] else 'FAIL') + ': ' + c['milestone'] for c in result['checks'])
    rows.extend(['', 'Public stdio: command replies, final units/maps, pending events and all named random draws match.', ''])
    (directory / (name + '.md')).write_text('\n'.join(rows), encoding='utf-8')


def scenario_test(name):
    def test(self):
        result = play(name)
        result['checks'] = check_scenario(result)
        RESULTS[name] = result
        if RECORD:
            write_record(result, RECORD)
        failed = [c['milestone'] for c in result['checks'] if not c['passed']]
        self.assertEqual([], failed, name + ': ' + '; '.join(failed))
    return test


for _name in MANIFEST:
    setattr(GameplayScenarios, 'test_' + _name, scenario_test(_name))


def main():
    global RECORD
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, help='write compact timelines, input draws, and milestone results')
    parser.add_argument('--replay', choices=list(MANIFEST), help='run just this encounter')
    args = parser.parse_args()
    RECORD = args.record
    if RECORD: RECORD.mkdir(parents=True, exist_ok=True)
    suite = unittest.TestSuite(GameplayScenarios('test_' + n) for n in ([args.replay] if args.replay else MANIFEST))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if RECORD:
        summary = {name: dict(passed=all(c['passed'] for c in r['checks']), ticks=r['final']['tick'],
                             checks=len(r['checks']), stdio=r['stdio']) for name, r in RESULTS.items()}
        (RECORD / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    if args.replay and args.replay in RESULTS and not RECORD:
        print(json.dumps(RESULTS[args.replay], indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(main())
