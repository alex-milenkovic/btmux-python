"""Independent JSON/subprocess assertions; no engine or acceptance imports."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'tmp/qa-heat-updates'


def action(op, **values):
    return dict(op=op, **values)


def command(name, *args, unit='u'):
    return action('command', unit=unit, name=name, args=list(args))


def maintain(kind):
    return action('maintain', unit='u', kind=kind)


def advance(seconds):
    return action('advance', seconds=seconds)


def hit(damage=1, section='CT', arc='FRONT', weapon=None, target='u', **more):
    return action('hit', target=target, section=section, arc=arc,
                  damage=damage, weapon=weapon, **more)


def external(inferno=True, unit='u', heat=1):
    return action('external_heat', unit=unit, heat=heat, inferno=inferno)


def weapon(name='A', damage=10, per_ton=30, section='RA', slot=5, **more):
    return dict(name=name, category='BALLISTIC', damage=damage,
                ammo_per_ton=per_ton, section=section, slot=slot, **more)


def bin_fixture(rounds=3, section='LT', slot=1, weapon=0, **more):
    return dict(weapon=weapon, section=section, slot=slot, rounds=rounds, **more)


def armed(rounds=3, **more):
    return dict(equipment=[weapon()], bins=[bin_fixture(rounds)], **more)


def vehicle(**more):
    return dict({'class':'VEH_GROUND', 'movement':'TRACK'}, **more)


def only_front():
    # Public section fixtures use the documented existing Location enumeration.
    # The shared state indices 0..7 are LARM,RARM,LTORSO,RTORSO,CTORSO,LLEG,RLEG,HEAD.
    return [dict(location=loc, internal=0) for loc in
            ('RARM','LTORSO','RTORSO','CTORSO','LLEG','RLEG','HEAD')]


def value_at(document, path):
    current = document
    for key in path.split('.'):
        current = current[int(key)] if isinstance(current, list) else current[key]
    return current


class Case:
    def __init__(self, label, unit=None, actions=None, integrated=False, **document):
        self.label, self.integrated = label, integrated
        self.document = dict(units=[dict(name='u', **(unit or {}))],
                             config={'periodic_updates': False},
                             actions=actions or [action('inspect')])
        self.document.update(document)
        self.assertions = []
        self.error = None

    def expect(self, path, expected, mode='equal'):
        self.assertions.append(dict(path=path, expected=expected, mode=mode))
        return self

    def final(self, **expected):
        for path, value in expected.items():
            self.expect('final.units.u.'+path, value)
        return self

    def count(self, path, expected):
        return self.expect(path, expected, 'length')

    def pending(self, field, expected):
        return self.expect('final.units.u.'+field, expected, 'pending')

    def accepted(self, expected):
        return self.expect('results', expected, 'accepted')

    def notice(self, fragment, count=1):
        return self.expect('results', [fragment,count], 'notice')

    def execute(self):
        folder = OUTPUT / self.label
        folder.mkdir(parents=True, exist_ok=True)
        request = folder / 'request.json'
        request.write_text(self.document if isinstance(self.document,str)
                           else json.dumps(self.document, indent=2)+'\n')
        cmd = [sys.executable,'-m','tools.heat_updates','--input',str(request)]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True,
                                timeout=45, env=dict(os.environ,
                                PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT/'tmp')))
        (folder/'stdout.json').write_text(result.stdout)
        (folder/'stderr.txt').write_text(result.stderr)
        evidence = dict(label=self.label, integrated=self.integrated, command=cmd,
                        status=result.returncode, assertions=[], failure=None)
        try:
            if self.error is not None:
                assert result.returncode and not result.stdout and self.error in result.stderr, result.stderr
                assert 'Traceback' not in result.stderr, result.stderr
                evidence['assertions'].append(dict(diagnostic=self.error, passed=True))
            else:
                assert result.returncode == 0 and not result.stderr, result.stderr
                data = json.loads(result.stdout)
                assert self.assertions, 'case has no oracle'
                for assertion in self.assertions:
                    actual = value_at(data, assertion['path'])
                    mode, expected = assertion['mode'], assertion['expected']
                    if mode == 'length': actual = len(actual)
                    elif mode == 'pending': actual = actual is not None
                    elif mode == 'accepted': actual = sum(r.get('accepted',False) for r in actual)
                    elif mode == 'notice':
                        fragment, expected = expected
                        actual = sum(fragment in m['text'] for r in actual for m in r['messages'])
                    elif mode == 'contains': actual = expected in actual; expected = True
                    elif mode == 'primary_rolls': actual = sum(r['source'] != 'fall' for r in actual)
                    elif mode == 'damage_deltas':
                        initial = data['initial']['units']['u']['sections']
                        actual = [old['internal']-new['internal'] for old,new in zip(initial,actual)
                                  if old['internal'] != new['internal']]
                    passed = (abs(actual-expected) <= 1e-6 if isinstance(expected,float)
                              and isinstance(actual,(int,float)) else actual == expected)
                    evidence['assertions'].append(dict(**assertion, actual=actual, passed=passed))
                    assert passed, f"{assertion['path']}: expected {expected!r}, got {actual!r}"
        except (AssertionError, ValueError, KeyError, IndexError, TypeError) as error:
            evidence['failure'] = str(error)
        (folder/'result.json').write_text(json.dumps(evidence,indent=2)+'\n')
        return evidence
