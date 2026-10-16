"""APS persistent runner adapter: python3 -m tools.acceptance_runner."""
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time


def evaluate(job):
    start = time.monotonic_ns()
    result = dict(id=job.get('id'), outcome='infrastructure_error', output='', error='')
    try:
        ir_path = Path(job['feature_json']).resolve()
        ir = json.loads(ir_path.read_text())
        candidates = [path for path in Path(job['generated_dir']).glob('*_acceptance.py')
                      if runpy.run_path(str(path))['IR']['name'] == ir['name']]
        if len(candidates) != 1:
            raise ValueError('expected one generated entrypoint for feature')
        timeout = re.fullmatch(r'(\d+(?:\.\d+)?)(ms|s|m)', job.get('timeout', '30s'))
        if timeout is None:
            raise ValueError('invalid runner timeout')
        seconds = float(timeout[1]) * {'ms': .001, 's': 1, 'm': 60}[timeout[2]]
        root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, PYTHONPATH=str(root), PYTHONDONTWRITEBYTECODE='1',
                           TMPDIR=str(root / 'tmp'))
        process = subprocess.run([sys.executable, str(candidates[0].resolve()), str(ir_path)],
                                 capture_output=True, text=True, timeout=seconds, env=environment)
        result['output'] = process.stdout + process.stderr
        if process.returncode == 0:
            result['outcome'] = 'test_success'
        elif 'AssertionError:' in process.stderr:
            result['outcome'] = 'test_failure'
        else:
            result['error'] = f'generated runner exited {process.returncode}'
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        result['error'] = str(error)
    result['duration'] = time.monotonic_ns() - start
    return result


def main():
    for line in sys.stdin:
        try:
            result = evaluate(json.loads(line))
        except (ValueError, TypeError, AttributeError) as error:
            result = dict(id=None, outcome='infrastructure_error', output='', error=str(error), duration=0)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
