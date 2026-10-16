"""Read-only LOS observations and source-derived encounter milestones.

The ordinary JSON sessions own all detection, targeting, movement and combat.
This helper reads their cached state; it never performs a sensor/LOS decision.
"""
from physics.hexmath import find_range3d
from entities.mech import CritStatus, MechStatus, MechStatus2
from systems.sensors import sensors


def terrain_label(value):
    return {' ': 'clear', '`': 'light woods', '"': 'heavy woods', '&': 'fire', ':': 'smoke'}.get(value, value)


def observe(session, state):
    pairs = {}
    for name, unit in session.units.items():
        state['units'][name].update(
            sensors=[sensors[i].matchletter for i in unit.sensor],
            hidden=bool(unit.crit_status & CritStatus.HIDDEN),
            lit=bool(unit.crit_status & CritStatus.SLITE_LIT),
            searchlight=bool(unit.status2 & MechStatus2.SLITE_ON),
            lock_mode=int(unit.status & (MechStatus.LOCK_TARGET | MechStatus.LOCK_HEX |
                MechStatus.LOCK_HEX_IGN | MechStatus.LOCK_HEX_CLR | MechStatus.LOCK_BUILDING)),
            target_hex=[unit.targ_x, unit.targ_y],
            weapon_recycle=[w.recycle for w in unit.weapons])
        for target_name, target in session.units.items():
            if unit is target or unit.map is not target.map:
                continue
            flag = (unit.map.losinfo or {}).get((unit._id, target._id), 0)
            pairs[name + '->' + target_name] = dict(
                range=round(find_range3d(unit.fx, unit.fy, unit.fz,
                                        target.fx, target.fy, target.fz), 5),
                flag=flag, seen=bool(flag & 1), primary=bool(flag & 2),
                secondary=bool(flag & 4), blocked=bool(flag & 0x8000),
                woods=(flag // 0x20) % 16, partial=bool(flag & 0x1000),
                smoke=bool(flag & 0x4000), fire=bool(flag & 0x2000),
                viewer_terrain=unit.map.terrain(unit.x, unit.y),
                target_terrain=target.map.terrain(target.x, target.y))
    state['los'] = pairs


def timeline(state, previous, command, result):
    lines = []
    for name, u in state['units'].items():
        old = previous['units'][name] if previous else {}
        fields = ('sensors', 'hidden', 'lit', 'searchlight', 'target', 'target_hex', 'lock_mode')
        changed = [f'{k}={u[k]}' for k in fields if u[k] != old.get(k)]
        if changed:
            lines.append(name + ': ' + ', '.join(changed))
    for pair, values in state['los'].items():
        old = previous.get('los', {}).get(pair, {}) if previous else {}
        if not old or any(values[k] != old[k] for k in values if k != 'range') or (command and pair.startswith(command['unit']+'->')):
            lines.append(f"{pair}: range {values['range']:.3f}, woods {values['woods']}, "
                         f"target terrain {terrain_label(values['target_terrain'])}, contact " +
                         ('yes' if values['primary'] or values['secondary'] else 'no') +
                         ''.join(', ' + k for k in ('blocked', 'partial', 'smoke', 'fire') if values[k]))
    if command and command['name'] in ('contacts', 'sensor'):
        # Retain the actual public display, not just the driver's interpretation.
        lines.append('Display: ' + (result.get('text') or result.get('message') or str(result)))
    attack = result.get('attack', {}) if command else {}
    if attack.get('bth_breakdown'):
        lines.append('Shot: ' + str({k: attack[k] for k in ('hit', 'roll', 'bth', 'location', 'damage_dealt')}))
        terms = attack['bth_breakdown']
        lines.append('BTH terms: ' + str({k: terms[k] for k in
            ('base', 'range_mod', 'attacker_move', 'target_move', 'terrain_mod',
             'unstable_lock_mod', 'other_mods') if terms.get(k)}))
    return lines


def check(run):
    """Independent source relationships, not snapshots generated from a replay."""
    name, frames, final = run['name'], run['frames'], run['final']
    states = [f['state'] for f in frames]
    checks = []
    def expect(condition, label): checks.append(dict(milestone=label, passed=bool(condition)))
    def actions(unit, command):
        return [f for f in frames if f.get('command', {}).get('unit') == unit
                and f['command']['name'] == command]
    def contact(state, a='Mech', b='Small'):
        v = state['los'][a+'->'+b]
        return v['primary'] or v['secondary']
    def notices(unit): return '\n'.join(m for f in frames for m in f['messages'].get(unit, []))
    def at(tick): return [s for s in states if s['tick'] == tick][-1]
    expect(not any('error' in c['result'] for c in run['commands']),
           'commands complete without fixture, interface or random-stream errors')
    if name.startswith('los_woods_'):
        clear = name.endswith('_clear')
        small_is_person = '_mw_' in name
        expect(contact(states[0]) == clear and contact(states[0], 'Small', 'Mech') == clear,
               'clear ground permits mutual seven-hex contacts; continuous woods initially prevent both')
        expect(all(not contact(s) and not contact(s,'Small','Mech') for s in states
                   if s['los']['Mech->Small']['woods'] >= 3), 'three intervening woods points prevent visual contacts')
        if not clear:
            first = next((s for s in states if contact(s)), None)
            expect(first is not None and first['los']['Mech->Small']['woods'] == 2 and
                   first['units']['Mech']['at'][1] == (6 if name.endswith('_light') else 5),
                   'movement acquires at the three-hex light / two-hex heavy geometry boundary')
        expect(contact(final) and contact(final,'Small','Mech'), 'both participants retain the final contact')
        shot = actions('Small','fire')[0]
        bth = shot['result'].get('attack', {}).get('bth_breakdown') or {}
        weights = {'`': 1, '"': 2}
        expected_terrain = shot['state']['los']['Small->Mech']['woods'] + weights.get(shot['state']['los']['Small->Mech']['target_terrain'], 0)
        expect(bth.get('terrain_mod') == expected_terrain,
               'real firing BTH adds intervening and target woods independently')
        expect(shot['result'].get('attack', {}).get('damage_dealt') == (1 if small_is_person else 5)
               and final['units']['Mech']['damage'] == (1 if small_is_person else 5),
               'small-unit weapon hits and causes real mech damage')
        if small_is_person:
            expect(not actions('Mech','fire')[0]['result']['accepted'] and
                   'safety' in actions('Mech','fire')[0]['result']['text'],
                   'MW safety is a separate refusal after contact and lock')
            expect(final['units']['Small']['ammo'] == 44, 'infantry shot spends one rifle round')
        else:
            expect(final['units']['Small']['damage'] == 5 and not final['units']['Small']['destroyed'],
                   'battle suits survive a real return hit')
        expect(final['units']['Small']['at'][:2] != [3,3] and
               not any(final['units']['Small']['weapon_recycle']),
               'surviving small unit moves after combat and its weapon recycles')
        expect(all(f['result']['accepted'] for f in actions('Mech','lock')[1:]),
               'later ordinary unit locks succeed')
    elif name in ('los_hidden_five', 'los_hidden_three'):
        hidden = [s for s in states if s['units']['Small']['hidden']]
        expect(not states[0]['units']['Small']['hidden'] and hidden and hidden[0]['tick'] == 21,
               'ordinary infantry hide completes after 21 ticks with no prior enemy contact')
        first = next((s for s in states if contact(s)), None)
        bound = 5 if name.endswith('five') else 3
        expect(first is not None and bound-.15 < first['los']['Mech->Small']['range'] < bound and
               first['units']['Small']['hidden'],
               'hidden acquisition obeys the five-hex gate or strict under-three guaranteed boundary')
        expect(any(not contact(s) and s['los']['Mech->Small']['range'] > bound for s in hidden),
               'approach includes an unacquired contact outside the selected boundary')
        if bound == 3:
            expect(any(not contact(s) and 3 <= s['los']['Mech->Small']['range'] <= 5 for s in hidden),
                   'high but valid detection draws fail the reduced chance between three and five')
        expect(any(contact(s) and s['los']['Mech->Small']['range'] > 5 for s in hidden),
               'a previously acquired hidden contact persists when the mech withdraws beyond five')
        expect(not contact(at(231)) and at(231)['units']['Small']['hidden'],
               'changing away and back to visual loses that persistence and requires reacquisition')
        expect(all(contact(s,'Small','Mech') for s in states),
               'infantry independently retains visual contact with the approaching mech')
        expect(actions('Small','fire')[0]['result']['attack']['damage_dealt'] == 1 and
               final['units']['Mech']['damage'] == 1 and final['units']['Small']['ammo'] == 44,
               'infantry fires through the real weapon, ammunition and damage pipeline')
        expect(not final['units']['Small']['hidden'] and final['units']['Small']['at'][:2] == [3,4],
               'firing breaks concealment and the infantry subsequently leaves its cover hex')
    elif name == 'los_hidden_probe':
        hidden = [s for s in states if s['units']['Small']['hidden']]
        expect(hidden and hidden[0]['tick'] == 61, 'ordinary battle-suit hiding completes after 61 ticks')
        expect(not contact(at(76)) and at(76)['los']['Mech->Small']['range'] == 6,
               'Beagle cannot acquire the hidden non-Purifier stealth suit even at its six-hex limit')
        expect(contact(at(91)) and at(91)['units']['Small']['hidden'],
               'equipped Bloodhound acquires the hidden suit at six hexes')
        expect(contact(at(106)) and actions('Mech','sight')[2]['state']['units']['Small']['hidden'],
               'returning to Beagle retains an existing contact without repeating hidden acquisition')
        expect(all(f['result']['attack']['bth_breakdown']['terrain_mod'] == 0
                   for f in actions('Mech','sight')[1:]), 'active probes ignore the target woods BTH term')
        expect(final['units']['Mech']['damage'] == 5 and not final['units']['Small']['hidden'],
               'suit fire breaks cover and damages the mech')
        expect(final['units']['Small']['at'][:2] == [3,4] and contact(final),
               'battle suits move out of their hiding hex while the probe contact continues')
    elif name == 'los_asymmetric_sensors':
        expect(all(not contact(states[0],'Mech',n) and contact(states[0],n,'Mech') for n in ('Small','Infantry')),
               'infrared excludes both small classes while their visual sensors acquire the mech')
        expect(at(0)['units']['Mech']['damage'] == 6 and at(0)['units']['Infantry']['ammo'] == 44,
               'both small units attack before the mech has a reciprocal contact')
        fires = actions('Mech','fire')
        expect(not fires[0]['result']['accepted'] and not fires[1]['result']['accepted'],
               'direct fire cannot bypass missing small-unit contacts')
        hex_sight = next(f for f in actions('Mech','sight') if f['command']['args'] == [0])
        expect(hex_sight['result']['accepted'] and not fires[2]['result']['accepted'],
               'plain coordinate sight succeeds but occupant substitution makes actual fire fail LOS')
        expect(fires[3]['result']['accepted'] and fires[3]['result']['attack']['damage_dealt'] == 0 and
               fires[3]['state']['units']['Small']['damage'] == 0 and
               any(fires[3]['state']['units']['Mech']['weapon_recycle']),
               'explicit H-mode hex fire expends the weapon without becoming a hit on the unseen occupant')
        expect(contact(at(50)) and not contact(at(50),'Mech','Infantry'),
               'EM acquires battle suits but still excludes infantry')
        expect(contact(at(65),'Mech','Infantry') and not contact(at(110),'Mech','Infantry'),
               'split visual/IR acquires infantry forward and loses it when heading puts it behind')
        expect(contact(at(125),'Mech','Infantry') and 'weapons arc' in actions('Mech','sight')[-2]['result']['text'],
               'identical visual sensors regain a rear contact while weapon arc remains a separate gate')
        expect(not actions('Infantry','sensor')[0]['result']['accepted'] and
               not actions('Small','sensor')[0]['result']['accepted'],
               'infantry cannot change its eyes and battle suits cannot select seismic')
        expect(final['units']['Small']['damage'] == 5 and all(final['units'][n]['at'][1] > y
               for n,y in [('Small',3),('Infantry',5)]), 'EM return fire damages the suits and both small units continue moving')
    elif name == 'los_cover_transitions':
        expect(contact(states[0]) and contact(states[0],'Small','Mech'), 'open-ground contact is mutual')
        sights = actions('Mech','sight')
        expect(sights[0]['result']['attack']['bth_breakdown']['unstable_lock_mod'] == 1 and
               sights[1]['result']['attack']['bth_breakdown']['unstable_lock_mod'] == 0,
               'the configured eight-tick lock delay removes the real unstable-lock modifier')
        expect('stable lock' in notices('Mech'), 'lock callback delivers its stable-lock announcement')
        expect(any(s['units']['Small']['at'][:2] == [3,7] and contact(s) for s in states),
               'entering target woods alone does not immediately lose contact')
        lost = [s for s in states if s['los']['Mech->Small']['woods'] >= 3]
        expect(lost and all(not contact(s) and not contact(s,'Small','Mech') for s in lost),
               'moving behind three or more woods points removes both visual contacts')
        expect(any(s['units']['Mech']['target'] == s['units']['Small']['target'] == -1 for s in lost)
               and 'lock has been lost' in notices('Mech'), 'contact loss clears locks and announces their loss')
        expect(not actions('Mech','fire')[0]['result']['accepted'], 'a later shot while obscured is refused')
        expect(any(s['tick'] > lost[-1]['tick'] and contact(s) and contact(s,'Small','Mech') for s in states),
               'eastward maneuver around the woods restores contacts through normal PLOS ticks')
        shot = actions('Mech','fire')[-1]
        expect(shot['result']['attack']['damage_dealt'] == 8 and final['units']['Mech']['damage'] == 5,
               'initial suit fire and later reacquired mech fire both cause real damage')
        expect(final['units']['Small']['real'] != shot['state']['units']['Small']['real'] and
               not final['units']['Small']['destroyed'], 'the damaged suit unit keeps moving after reacquisition combat')
    elif name == 'los_ridge_cover':
        expect(all(v['blocked'] and not v['seen'] for v in states[0]['los'].values()),
               'the two-level ridge initially blocks both directions')
        expect(any(s['units']['Mech']['at'] == [3,6,2] and contact(s,'Mech','Target') for s in states),
               'real movement onto the ridge restores the elevated sight line')
        shot = actions('Mech','fire')[0]
        expect(shot['state']['units']['Mech']['at'] == [3,5,0] and shot['state']['los']['Mech->Target']['partial'],
               'descent behind the one-level pre-target ridge creates partial cover')
        expect(shot['result']['attack']['bth_breakdown']['terrain_mod'] == 3 and
               shot['result']['attack']['damage_dealt'] == 5 and shot['result']['attack']['location'] not in (5,6),
               'partial cover adds three BTH and the real hit uses an upper-body location')
        prone_state = actions('Mech','sight')[2]['state']
        expect(actions('Target','prone')[0]['result']['accepted'] and
               prone_state['los']['Mech->Target']['blocked'] and not contact(prone_state,'Mech','Target'),
               'lowering the target eye height by going prone blocks the ridge line')
        expect(not at(141)['units']['Target']['fallen'] and contact(at(141),'Mech','Target'),
               'standing and normal sensor updates restore targeting')
        expect(not final['los']['Mech->Target']['partial'] and final['units']['Target']['at'][0] > 3,
               'later lateral movement removes partial cover')
        expect(final['units']['Mech']['damage'] == 5 and final['units']['Target']['damage'] == 10,
               'post-recovery return fire and a subsequent uncovered hit resolve')
    elif name == 'los_night_searchlight':
        expect(not contact(states[0],'Mech','Target') and not contact(states[0],'Target','Mech'),
               'unlit visual sensors cannot acquire at six with night condition range three')
        changed = next(s for s in states if s['units']['Mech']['sensors'] == ['L','L'])
        expect(changed['tick'] == 10 and contact(at(15),'Mech','Target') and not contact(at(15),'Target','Mech'),
               'ten-tick light-amp change permits the doubled night range while reverse visual detection still fails')
        expect(not actions('Target','slite')[0]['result']['accepted'], 'a unit without searchlight equipment cannot turn one on')
        expect(not at(19)['units']['Mech']['searchlight'] and at(20)['units']['Mech']['searchlight'],
               'searchlight warm-up requires five actual ticks')
        expect(at(25)['units']['Target']['lit'] and not contact(at(25),'Mech','Target') and contact(at(25),'Target','Mech'),
               'illumination disables light-amp target detection and enables reverse visual detection')
        sights = actions('Mech','sight')
        expect(sights[1]['result']['attack']['bth_breakdown']['terrain_mod'] == 4 and
               sights[3]['result']['attack']['bth_breakdown']['terrain_mod'] == 2,
               'switching to visual on the lit target changes woods/light BTH from four to two')
        expect(not contact(at(58),'Mech','Target') and not contact(at(58),'Target','Mech') and
               not at(58)['units']['Target']['lit'], 'cool-down and maintenance remove illumination and distant visual contacts')
        expect(contact(at(73),'Mech','Target') and not contact(at(73),'Target','Mech'),
               'infrared reacquires the mech through darkness while reverse visual remains out of range')
        expect(contact(at(176),'Target','Mech') and at(176)['los']['Target->Mech']['range'] < 3,
               'continuous approach enters ordinary visual range and restores reciprocal targeting')
        expect(all(final['units'][n]['damage'] == 10 for n in ('Mech','Target')),
               'both participants fire before and after the lighting and movement transitions')
    elif name == 'los_smoke_maneuver':
        a,b='Observer','Target'
        expect(contact(states[0],a,b) and contact(states[0],b,a), 'fight begins with mutual clear visual contact')
        expect(any(any(o['terrain'] == '&' for o in s['maps']['field']['decorations']) for s in states),
               'the ordinary flamer hex command starts a real timed fire')
        expect(at(60)['los'][a+'->'+b]['smoke'] and not contact(at(60),a,b) and not contact(at(60),b,a),
               'wind-driven smoke removes contacts in both directions')
        expect(all(not actions(n,'fire')[0]['result']['accepted'] for n in (a,b)),
               'both pilots receive firing refusals through the smoke')
        expect(at(75)['los'][a+'->'+b]['smoke'] and contact(at(75),a,b) and not contact(at(75),b,a),
               'infrared penetrates smoke and produces a one-way targeting opportunity')
        expect(actions(a,'fire')[1]['result']['accepted'] and any(actions(a,'fire')[1]['state']['units'][a]['weapon_recycle']),
               'the infrared shot actually fires and recycles, even though its seeded attack misses')
        expect(any(s['maps']['field']['decorations'] and s['units'][b]['at'][:2] != [4,2] for s in states) and
               final['units'][a]['at'][:2] != [4,8], 'both combatants maneuver as the concealment evolves')
        expect(not final['maps']['field']['decorations'] and contact(final,a,b) and contact(final,b,a),
               'fire and smoke expire and visual targeting works again')
        expect(final['units'][a]['damage'] == 5 and final['units'][b]['damage'] == 8,
               'later visual shots hit both units through real damage resolution')
        expect(final['units'][b]['real'] != actions(b,'fire')[-1]['state']['units'][b]['real'],
               'damaged target continues moving after the final exchange')
    else:
        raise AssertionError('LOS encounter milestones have not been defined: ' + name)
    return checks
