"""Run independent HUD CLI examples with at most four concurrent subprocesses."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from hud_displays_common import OUT,driver_hashes,production_hashes
from hud_displays_session import sessions,state
from hud_displays_equipment import equipment,queries
from hud_displays_armor import armor
from hud_displays_status import status
from hud_displays_maps import hud_maps,lrs

from hud_displays_contacts import contacts,hud_contacts

from hud_displays_scanning import scanning

from hud_displays_tactical import tactical

from hud_displays_integration import integration

from hud_displays_catalog import catalog

from hud_displays_extra import extra

from hud_displays_map_oracles import map_oracles

from hud_displays_procedures import procedures

from hud_displays_remaining import remaining

from hud_displays_boundaries import boundaries
from hud_displays_final_workflows import final_workflows

BUILDERS={'boundaries':boundaries,'remaining':remaining,'procedures':procedures,'map_oracles':map_oracles,'extra':extra,'catalog':catalog,'integration':integration,'tactical':tactical,'scanning':scanning,'contacts':contacts,'hud_contacts':hud_contacts,'session':sessions,'hud_state':state,'hud_equipment':equipment,'queries':queries,'armor':armor,'status':status,'hud_tactical':hud_maps,'lrs_navigation':lrs}
BUILDERS['final_workflows']=final_workflows


def main():
    driver_hashes();production_hashes()
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    parser.add_argument('families',nargs='*');parser.add_argument('--case');args=parser.parse_args()
    cases=[case for family in args.families or BUILDERS for case in BUILDERS[family]() if not args.case or args.case in case.name]
    names=[case.name.casefold() for case in cases]
    if len(names)!=len(set(names)):raise ValueError('Case paths collide on a case-insensitive filesystem')
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results=[]
        for result in pool.map(lambda case:case.run(),cases):
            results.append(result);print(result['case'],result['passed'],result['errors'][:3],flush=True)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'latest.json').write_text(json.dumps(results,indent=2)+'\n')
    print(f'{sum(r["passed"] for r in results)}/{len(results)} PASS')
    return int(any(not r['passed'] for r in results))


if __name__=='__main__':raise SystemExit(main())
