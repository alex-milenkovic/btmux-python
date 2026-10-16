"""Setup, verify, or audit the optional pinned BTMux design catalog."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from data.template_dependency import resolve_catalog,setup,verify
from data.template_catalog_audit import audit


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('setup','verify','audit'))
    parser.add_argument('--path',help='explicit catalog directory (relative to invocation directory)')
    parser.add_argument('--output',help='JSON report outside the read-only catalog; stdout if omitted')
    parser.add_argument('--reverse',action='store_true',help='audit in reverse order; output remains sorted')
    args=parser.parse_args(argv)
    try:
        root=resolve_catalog(args.path if args.path else True)
        if args.output and Path(args.output).resolve().is_relative_to(root):raise ValueError('Cannot write an audit report into the read-only catalog')
        report=audit(root,reverse=args.reverse) if args.command=='audit' else {'setup':setup,'verify':verify}[args.command](root)
        output=json.dumps(report,indent=2,sort_keys=True)+'\n'
        if args.output:Path(args.output).write_text(output)
        else:print(output,end='')
        if args.command=='audit':return 2 if report['failures'] else 0
        return 0 if report['outcome'].startswith('verified') else 1
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print(json.dumps({'outcome':'incomplete','error':str(error)}),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
