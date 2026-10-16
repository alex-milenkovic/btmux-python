"""APS generator: python3 -m tools.acceptance_entrypoint_generator IR OUTPUT."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def generate(ir_path, output):
    ir_path, output = Path(ir_path), Path(output)
    ir = json.loads(ir_path.read_text())
    if not ir['scenarios']:
        raise ValueError('feature has no scenarios')
    # Normal scripts attach the source path; APS itself need not include it.
    feature_path = ir.get('feature_path', str(ir_path.with_suffix('.feature')))
    name = re.sub(r'[^a-z0-9]+', '-', feature_path.lower()).strip('-')
    output.mkdir(parents=True, exist_ok=True)
    generated = output / (name + '_acceptance.py')
    source = ('# Generated from APS IR; do not edit.\n'
              'import json\nimport sys\nfrom pathlib import Path\nfrom acceptance.runtime import run_feature\n'
              f'IR = json.loads({json.dumps(ir, sort_keys=True)!r})\n'
              'if __name__ == "__main__":\n'
              '    supplied = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else IR\n'
              '    print(f"Passed {run_feature(supplied)} acceptance executions")\n')
    # Hash exactly the emitted bytes on Windows as well as POSIX.
    generated.write_bytes(source.encode('utf-8'))
    metadata_dir = output / 'metadata'
    metadata_dir.mkdir(exist_ok=True)
    metadata = dict(schema_version=1, feature_path=feature_path, ir_path=str(ir_path),
                    implementation_hash='sha256:' + hashlib.sha256(source.encode()).hexdigest(),
                    hash_scope='generated_files', generated_files=[str(generated)])
    (metadata_dir / (name + '.json')).write_text(json.dumps(metadata, indent=2) + '\n')
    return generated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ir')
    parser.add_argument('output')
    args = parser.parse_args(argv)
    try:
        generate(args.ir, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
