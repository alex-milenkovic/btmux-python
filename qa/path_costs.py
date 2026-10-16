#!/usr/bin/env python3
"""Check path-cost behavior through the documented CLI, without project imports.

Run from any directory: python3 qa/path_costs.py
APS supplies example data; expected results are the feature's literal costs.
Inputs, stdout, stderr and status are saved under the worktree's tmp/.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'tmp/qa-path-costs'
MODES = ('mech', 'hover', 'tracked')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def capture(records, label, command):
    result = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=30,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                 TMPDIR=str(ROOT / 'tmp')))
    records.append(dict(label=label, command=command, status=result.returncode,
                        stdout=result.stdout, stderr=result.stderr))
    return result


def query_options(**changes):
    options = {'mode': ['mech'], 'size': ['4', '4'],
               'from': ['0', '0'], 'to': ['1', '0'],
               'source': ['GRASSLAND', '0'],
               'destination': ['HEAVY_FOREST', '0']}
    options.update(changes)
    return [part for flag, values in options.items() if values is not None
            for part in ['--' + flag, *values]]


def query(records, label, expected, **changes):
    result = capture(records, label, [sys.executable, '-m', 'tools.path_cost',
                                     *query_options(**changes)])
    if expected is None:
        require(result.returncode != 0 and result.stdout == ''
                and 'error:' in result.stderr and 'Traceback' not in result.stderr,
                f'{label}: expected an input diagnostic without a result')
    else:
        require((result.returncode, result.stdout, result.stderr)
                == (0, f'cost={expected}\n', ''), f'{label}: unexpected command result')


def check_fixture(ir, mode, index):
    """Fail on fixture drift instead of silently applying outdated QA setup."""
    if mode == 'coordinates':
        background = 'all map hexes are GRASSLAND with stored elevation 0'
        source = '0 0' if index == 0 else '<fx> <fy>'
        steps = ['map dimensions <width> by <height>',
                 f'source coordinates {source} and destination coordinates <tx> <ty>',
                 'all three path costs are requested', 'each path cost is <cost>']
    else:
        background = 'a fresh 4 by 4 path-cost map with source at 0 0 and destination at 1 0'
        source = 'GRASSLAND with stored elevation 0' if index == 0 else '<source> with stored elevation <source_elevation>'
        steps = [f'source terrain {source}',
                 'destination terrain <terrain> with stored elevation <elevation>',
                 f'the {mode} path cost is requested', 'the path cost is <cost>']
    require([step['text'] for step in ir['background']] == [background],
            f'{mode}: update QA for changed background')
    require([step['text'] for step in ir['scenarios'][index]['steps']] == steps,
            f'{mode}/{index}: update QA for changed steps')


def feature_suite(records, mode):
    feature = f'features/path_costs/{mode}.feature'
    ir_file = f'./tmp/qa-path-costs/{mode}.json'
    parsed = capture(records, f'parse/{mode}', ['gherkin-parser', feature, ir_file])
    require(parsed.returncode == 0, f'{mode}: APS parsing failed')
    ir = json.loads((ROOT / ir_file).read_text())
    require(len(ir['scenarios']) == 2, f'{mode}: update QA for changed scenarios')
    count = 0
    for index, scenario in enumerate(ir['scenarios']):
        check_fixture(ir, mode, index)
        require(scenario['examples'], f'{mode}/{index}: missing examples')
        for number, row in enumerate(scenario['examples'], 1):
            if mode == 'coordinates':
                options = {'size': [row['width'], row['height']],
                           'from': [row.get('fx', '0'), row.get('fy', '0')],
                           'to': [row['tx'], row['ty']],
                           'destination': ['GRASSLAND', '0']}
                modes = MODES
            else:
                options = {'source': [row.get('source', 'GRASSLAND'), row.get('source_elevation', '0')],
                           'destination': [row['terrain'], row['elevation']]}
                modes = (mode,)
            for selected in modes:
                query(records, f'{mode}/{index + 1}/{number}/{selected}',
                      int(row['cost']), mode=[selected], **options)
                count += 1
    return count


def interface_suite(records):
    result = capture(records, 'help', [sys.executable, '-m', 'tools.path_cost', '--help'])
    require(result.returncode == 0 and result.stderr == '', 'help failed')
    help_text = ' '.join(result.stdout.lower().split())
    for phrase in (*MODES, '--size', '--from', '--to', '--source', '--destination',
                   'terrain', 'elevation', 'width', 'height', 'signed', 'depth',
                   'destination row', 'beyond map width', 'decorated', 'deferred'):
        require(phrase in help_text, f'help missing {phrase}')
    query(records, 'reference', 3)


def error_and_repeatability_suite(records):
    errors = {'invalid mode': {'mode': ['wheeled']},
              'invalid terrain': {'destination': ['BOG', '0']},
              'invalid dimension': {'size': ['0', '4']},
              'invalid elevation': {'destination': ['HEAVY_FOREST', '10']},
              'missing destination': {'destination': None},
              'same-hex conflict': {'to': ['0', '0']}}
    for label, changes in errors.items():
        query(records, label, None, **changes)
    query(records, 'same-hex agreement', 1, **{'to': ['0', '0'],
          'destination': ['GRASSLAND', '0']})
    query(records, 'reference after errors', 3)
    query(records, 'blocked hover', 0, mode=['hover'], destination=['WATER', '2'])
    query(records, 'reference after blocked hover', 3)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records, counts = [], {}
    report = {'procedure_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'feature_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted((ROOT / 'features/path_costs').glob('*.feature'))},
              'python': sys.version, 'passed': False, 'suites': counts, 'commands': records}
    try:
        interface_suite(records)
        for mode in (*MODES, 'coordinates'):
            counts[mode] = feature_suite(records, mode)
        error_and_repeatability_suite(records)
        report['passed'] = True
    except (AssertionError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        report['error'] = str(error)
        print(f'QA failed: {error}; see {OUTPUT}/results.json', file=sys.stderr)
        return 1
    finally:
        (OUTPUT / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    queries = sum(record['command'][1:3] == ['-m', 'tools.path_cost'] for record in records)
    print(f'Passed {queries} CLI checks: {counts}; evidence: {OUTPUT}/results.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
