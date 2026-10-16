"""Parse, generate, then execute the selected APS acceptance features."""
import json
import argparse
import os
from pathlib import Path
import subprocess
import sys

from tools.acceptance_entrypoint_generator import generate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', help='Feature directory to execute, e.g. sensors_los')
    parser.add_argument('--only', help='Feature stem within the selected suite')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    output = Path('tmp/acceptance')
    output.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                       TMPDIR=str(root / 'tmp'), PYTHONPATH=str(root))
    generated = []
    features = sorted(Path('features').glob('*/*.feature'))
    if args.suite:
        features = [f for f in features if f.parent.name == args.suite]
    if args.only:
        features = [f for f in features if f.stem == args.only]
    for feature in features:
        ir_path = output / (feature.parent.name + '-' + feature.stem + '.json')
        subprocess.run(['gherkin-parser', str(feature), './' + str(ir_path)],
                       check=True, env=environment)
        ir = json.loads(ir_path.read_text())
        ir['feature_path'] = feature.as_posix()
        ir_path.write_text(json.dumps(ir, indent=2) + '\n')
        generated.append(generate(ir_path, output / 'generated'))
    if not generated:
        raise RuntimeError('no acceptance features found')
    for entrypoint in generated:
        subprocess.run([sys.executable, str(entrypoint)], check=True, env=environment)


if __name__ == '__main__':
    main()
