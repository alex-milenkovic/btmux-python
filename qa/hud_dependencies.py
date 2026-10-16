"""Independent CLI checks of the remaining explicitly unavailable display effects."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from hud_displays_common import *
from hud_displays_contacts import pair,building
from hud_displays_integration import entry


def _dependencies():
    doc=document([unit(at=[50,50,0],brief=1)]);building(doc)
    doc['maps'][1]['bay']=dict(enter_lock='[unsupported()]')
    doc['actions']=[hud('key=test'),hud('cb'),command('contacts')]
    case=Case('supplement/building-displays-missing-lock',doc)
    for index in (1,2):case.expect(f'results.{index}.blocked',['MUX LENTER lock for building #2000']).expect(f'results.{index}.effects_complete',False)
    case.expect('results.1.records',[dict(type='D',payload='Done',**{'class':'CB'})]).expect('results.2.contacts',[]);yield case
    doc,u,t=pair();t['communications']=dict(autopilot=99,freq=[123]+[0]*15)
    doc['actions']=[hud('key=test'),hud('asc TT'),hud('wsc TT')]
    case=Case('supplement/hud-scans-missing-autopilot',doc)
    for index in (1,2):case.expect(f'results.{index}.blocked','autopilot-scan-reply','contains').expect(f'results.{index}.effects_complete',False).expect(f'results.{index}.records.-1.type','D')
    yield case
    doc=document(actions=[command('status','A'),action('inspect')]);doc['units'][0].update(formed('AERO'));doc['units'][0]['display']=dict(status_template='7 &:0')
    yield Case('supplement/legacy-si-missing-input',doc).expect('results.0.ok',False).expect('results.0.blocked',['legacy-SI-display-input']).expect('state.units.u.si',0)
    doc=entry();doc['maps'][1]['bay']=dict(enter_lock='false');doc['actions']=[command('enterbase'),action('inspect')]
    yield Case('supplement/entry-missing-fail-afail',doc).expect('results.0.ok',False).expect('results.0.blocked',['MUX-FAIL/AFAIL']).expect('state.units.u.external_effects',dict(service='MUX FAIL/AFAIL',operation='building entry refused',applied=False),'has_fields')


def dependencies():
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for case in _dependencies():
        case.meta['dependency_driver_sha256']=source_hash
        yield case


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,choices=range(1,5),default=4);args=parser.parse_args()
    driver_hashes();production_hashes()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results=list(pool.map(lambda case:case.run(),dependencies()))
    for result in results:print(result['case'],result['passed'],result['errors'])
    print(f'{sum(result["passed"] for result in results)}/{len(results)} PASS')
    return int(any(not result['passed'] for result in results))


if __name__=='__main__':raise SystemExit(main())
