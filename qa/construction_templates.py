#!/usr/bin/env python3
"""Independent source/spec CLI QA; run selected families sequentially."""
import argparse,importlib,json,sys
from qa.construction_qa_common import Audit,OUT
MODULES={'workflows':'workflows','numeric':'numeric','catalog':'catalog','loading':'loading','editor':'editor','more-workflows':'more_workflows','saving':'saving','technology':'technology','c-oracle':'c_oracle','boundaries':'boundaries','shared':'shared','loader-edges':'loader_edges'}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--only',choices=MODULES);args=parser.parse_args()
    failed=False
    for name in [args.only] if args.only else MODULES:
        audit=Audit()
        try:importlib.import_module('qa.construction_qa_'+MODULES[name]).run(audit)
        finally:
            result=audit.save();(OUT/(name+'-results.json')).write_text(json.dumps(result,indent=2)+'\n');failed |= bool(result['failures'])
    return int(failed)
if __name__=='__main__':sys.exit(main())
