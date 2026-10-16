"""Run independent public CLI verification."""
import argparse,importlib,json
FAMILIES=('channels','displays','hardware','membership','notifications','ranges','routing','transmission','workflows','supplements','master_correction')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--family',choices=FAMILIES,action='append');args=p.parse_args();results=[]
 for name in args.family or FAMILIES:
  result=importlib.import_module('qa.communications.'+name).run();results.append({k:v for k,v in result.items() if k!='results'})
 print(json.dumps({'families':results,'cases':sum(r['cases'] for r in results),'failures':sum(r['failures'] for r in results)},indent=2))
 return int(any(r['failures'] for r in results))
if __name__=='__main__':raise SystemExit(main())
