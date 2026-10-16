"""Cross-command ordering, stdin parity and actual missing-service branches."""
from hud_displays_common import *
from hud_displays_contacts import pair
from hud_displays_catalog import definitions
from hud_displays_integration import entry
from hud_displays_tactical import cell


def final_workflows():
    doc=document(actions=[hud(''),hud('key=test'),hud('gs'),command('status','A'),action('inspect')])
    yield Case('supplement/stdin-parity',doc,dict(stdin_parity=True)).expect('results.0.wire','#HUD hudinfo version 0.8\r\n').expect('results.1.wire','#HUD:test:KEY:R# Key set\r\n')
    doc,u,t=pair();u['brief']=1;t.update(speed=12.25,vertical_speed=-3.5,facing=345,heat=2,tonnage=70)
    far=unit('far',30,at=[50,58,0],contact_id='FF',team=2);doc['units'].append(far);doc['diagnostic_cache'].append(dict(viewer='u',target='far',flags=14))
    doc['actions']=[command('contacts'),command('contacts','h'),hud('key=test'),hud('c')]
    case=Case('supplement/contact-format-ordering',doc).expect('results.0.contacts.*.name',['far','target'])
    case.expect('results.1.lines.1|4','FF').expect('results.1.lines.2|4','TT')
    case.expect('results.3.records.0.payload','TT,v,PS,B,target,50,52,0,2.000,180,12.250,-3.500,345,-,0.000,180,70,2,+')
    case.expect('results.3.records.1.payload|4','far');yield case
    defs=definitions();names='SGUIDED SWARM1 ARTEMIS CLUSTER INARC_ECM AC_FLECHETTE INARC_HAYWIRE INFERNO LBX MINE NARC AC_PRECISION SWARM AC_AP INARC_EXPLO AC_INCENDIARY SMOKE STINGER AC_CASELESS ATM_ER ATM_HE'.split()
    doc=document(actions=[hud('key=test'),hud('we')]);doc['units'][0]['sections']=[dict(index=0,slots=[dict(index=4,weapon='IS.MediumLaser',ammomode=sum(defs[name+'_MODE'] for name in names))])]
    yield Case('supplement/combined-ammo-order',doc,dict(diagnostic=True)).expect('results.1.records.0.payload|6','G1ACEFHILMNPSaXesTURX')
    doc,u,t=pair();u['brief']=1;t.update(formed('quad'));t['fallen']=True;doc['actions']=[command('stand',unit='target'),command('contacts'),action('inspect')]
    yield Case('supplement/real-standing-contact',doc).expect('results.0.accepted',True).expect('results.1.contacts.0.status','  f  ').expect('state.events',dict(kind='STAND',unit='target'),'has_fields')
    for first in (1,5):
        doc=document([unit(at=[50,50,0])],[command('tactical','m')]);doc['map']['map_objects']=[dict(kind='MINE',x=50,y=48,datac=value,datas=20) for value in (6-first,first)]
        # Source map-object insertion prepends: the last inserted matching mine wins.
        case=Case('supplement/mine-first-object-'+str(first),doc);cell(case,0,50,48,lower='<>' if first==1 else '  ');yield case
    for order in ('before','after'):
        doc,u,t=pair();t.update(formed('DS'));t.pop('real');t.update(at=[50,47,0],aerospace=dict(landed=True))
        coloc=unit('coloc',30,at=[50,47,0],contact_id='CC',team=2)
        doc['units'].insert(1 if order=='before' else 2,coloc);doc['diagnostic_cache'].append(dict(viewer='u',target='coloc',flags=14));doc['actions']=[command('tactical')]
        case=Case('supplement/dropship-contact-precedence-'+order,doc);cell(case,0,50,47,upper='CC');yield case
    doc=entry();doc['units'][0]['communications']=dict(autopilot=99);doc['actions']=[command('enterbase'),action('advance',seconds=18),action('inspect')]
    yield Case('supplement/entry-missing-autopilot-refresh',doc).expect('state.units.u.mapindex',2000).expect('state.units.u.external_effects',dict(service='autonomous map-index recalculation',operation='building entry',applied=False),'has_fields')
