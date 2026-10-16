"""Run independent catalog QA sequentially, preserving all raw CLI evidence."""
import argparse,importlib,json
from qa.template_catalog_common import OUT,initialize
FAMILIES=('inventory','workflows','boundaries')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',choices=FAMILIES)
    args=parser.parse_args();initialize();failed=False
    for family in (args.only,) if args.only else FAMILIES:
        importlib.import_module('qa.template_catalog_'+family).run()
        failed|=bool(json.loads((OUT/(family+'.json')).read_text())['failures'])
    return int(failed)
if __name__=='__main__':raise SystemExit(main())
