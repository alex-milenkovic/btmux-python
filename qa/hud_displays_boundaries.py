"""Remaining visual/event boundaries in the supplemental procedures."""
from hud_displays_common import *
from hud_displays_contacts import pair,f32
from hud_displays_tactical import cell


def boundaries():
    for surplus in (0,6,7,12,13,15,16,17,18,23,24,39,40):
        doc=document(actions=[command('status','H')]);doc['units'][0].update(plus_heat=5+surplus+.9,minus_heat=5.9)
        # C uses integer heat, seven intervals, and identical lit glyphs in all bands.
        expected='Temp:%cx%ch %cx%ch';start=0
        for end,prefix in [(5,''),(12,'%cg%ch|%c%cg'),(18,'%ch'),(21,'%c%cy%ch|%c%cy'),(23,'%ch'),(29,'%c%cr%ch|%c%cr'),(45,'%ch')]:
            expected+=prefix+''.join(':' if column<5+surplus else '.' for column in range(start,end));start=end
        expected+='%cw%ch|%c'
        yield Case('supplement/heat-band-'+str(surplus),doc).expect('results.0.heat_scale.text',expected)
    for terrain,expected in [('GRASSLAND','O'),('LIGHT_FOREST','X')]:
        doc=document([unit(at=[50,50,0])],[command('tactical','b')]);doc['map']['hexes']=[dict(at=[50,49],terrain=terrain,elevation=0)]
        case=Case('supplement/landing-zone-'+terrain,doc);cell(case,0,50,49,lower=expected+('`' if terrain=='LIGHT_FOREST' else '_'));yield case
    doc=document([unit(at=[50,50,0])],[command('tactical','u'),action('advance',seconds=3),command('tactical','u')]);doc['map']['hexes']=[dict(at=[50,49],terrain='ROAD',elevation=0,overlay='SMOKE',duration=2)]
    case=Case('supplement/timed-smoke-expiry',doc);cell(case,0,50,49,'::','##');cell(case,2,50,49,'##','##');yield case
    for x,heading,damaged,carrier in [(50,0,False,False),(51,0,False,False),(50,60,False,False),(51,120,True,False),(50,0,False,True),(0,0,False,False)]:
        doc,u,t=pair();t.update(formed('DS'));t.pop('real');t.update(at=[x,47,0],facing=heading,sections=[dict(index=5,slots=[dict(index=0,special='DS_MECHDOOR',firemode=1 if damaged else 0)])],aerospace=dict(landed=True),specials2=0x80000 if carrier else 0)
        if x==0:u['at']=[0,50,0]
        doc['actions']=[command('tactical')];sx=max(0,x-10) if x==0 else 40;sy=43
        direction=int((heading+30)/60)%6;dx,dy=[(0,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0)][direction]
        tx=x+dx;ty=47+dy-int(x%2 and tx%2==0)
        case=Case(f'supplement/dropship-{x}-{heading}-{damaged}-{carrier}',doc)
        if carrier:case.expect('results.0.plain','@','excludes')
        elif tx>=0:cell(case,0,tx,ty,'@@',window=(sx,sy,21,14))
        yield case
    for friend,offset in [(True,30),(False,30),(False,0)]:
        doc,u,t=pair(0);t['team']=0 if friend else 2;t['real'][0]+=offset;doc['actions']=[command('navigate')]
        # Source NAV column=(2*ALPHA+offset)/(4*ALPHA/21)+4, row=6.
        column=int((2*93.097730906827152+offset)/(4*93.097730906827152/21)+4)
        glyph='*' if not offset else 'x' if friend else 'X'
        yield Case(f'supplement/navigate-subhex-{friend}-{offset}',doc).expect('results.0.rows.6',r'^.{'+str(column)+'}'+re.escape(glyph),'regex')
    for mode in ('t','l','h','s','m','e','c'):
        doc=document([unit(at=[50,50,0],lrs_range=0)],[command('lrs',mode)])
        yield Case('supplement/lrs-zero-scanner-'+mode,doc).expect('results.0.ok',False)
    doc=document([unit(at=[50,50,0])],[hud('key=test'),action('inspect'),hud('t 1 0 0 l'),action('inspect')])
    yield Case('supplement/hud-height-one-no-los-change',doc).expect('results.2.records',2,'length').expect('results.3.maps','results.1.maps','same')
    for observer in (False,True):
        doc,u,t=pair(21);u.update(lrs_range=20,observer=observer);doc['actions']=[command('lrs','t TT'),command('lrs','t 180 21')]
        yield Case('supplement/lrs-center-observer-'+str(observer),doc).expect('results.0.ok',False).expect('results.1.ok',observer)
    # Read scan/info and pending-event status from real registered queues.
    doc,u,t=pair();t.update(formed('VEHICLE-TRACK'));u['brief']=1;doc['actions']=[action('schedule',unit='target',callback='vehicle_burn_event',delay=30,data=2),command('contacts')]
    yield Case('supplement/pending-burn-status',doc).expect('results.1.contacts.0.status','   B ')
    doc,u,t=pair(21);u['observer']=True;doc['actions']=[command('scan','50 71 H')]
    yield Case('supplement/observer-three-arg-range',doc).expect('results.0.ok',False).expect('results.0.message','Those coordinates are out of scanner range.')
    for command_name in ('scan','report'):
        doc,u,t=pair();u['target']=20;doc['actions']=[command(command_name)]
        yield Case('supplement/default-unit-'+command_name,doc).expect('results.0.report.name','target')
    doc,u,t=pair();t['at']=[0,0,0];t.pop('real');u['target']=-1;doc['actions']=[action('configure',unit='u',values=dict(targ_x=50,targ_y=52)),command('report')]
    yield Case('supplement/default-hex-report-quirk',doc).expect('results.1.report.position',[0,0,0]).expect('results.1.report.range',0)
    # Literal C steel thresholds count destroyed physical parts for display.
    for special,tons,count,present in [('MACE',60,3,False),('MACE',60,4,True),('SWORD',45,2,False),('SWORD',45,3,True)]:
        doc=document(actions=[command('status','W'),action('inspect')]);doc['units'][0].update(tonnage=tons,real_mass=tons,sections=[dict(index=0,slots=[dict(index=4+i,special=special,firemode=1) for i in range(count)])])
        yield Case(f'supplement/physical-display-{special}-{tons}-{count}',doc).expect('results.0.physical.*.name',special.title()+'[LA]','contains' if present else 'excludes').expect('state.units.u.shots_fired',0)
    from hud_displays_catalog import definitions
    defs=definitions()
    for destroyed,active,text in [(False,False,'ECM(Off)'),(False,True,'ECM(ECM)'),(True,True,'ECM(XX)')]:
        doc=document(actions=[command('status','W')]);u=doc['units'][0];u.update(equipment=['Guardian'],status2=1 if active else 0,crit_status=defs['ECM_DESTROYED'] if destroyed else 0)
        yield Case(f'supplement/ecm-readiness-{destroyed}-{active}',doc).expect('results.0.plain',text,'contains')
    for heat,text in [(8.9,'TSM(Off)'),(9,'TSM(On)')]:
        doc=document(actions=[command('status','W')]);doc['units'][0].update(specials=defs['TRIPLE_MYOMER_TECH'],heat=heat)
        yield Case('supplement/tsm-status-'+str(heat),doc).expect('results.0.plain',text,'contains')
    doc,u,t=pair();u.update(status=8|64|defs['DFA_ATTACK'],dfa_target=20,core=dict(going_x=49,going_y=48),carrying=20);doc['actions']=[command('status','I')]
    yield Case('supplement/jump-dfa-and-tow',doc).expect('results.0.plain','JUMPING -->  49, 48','contains').expect('results.0.plain','Death From Above Target: target','contains').expect('results.0.plain','Towing target','contains')
    doc,u,t=pair();t.update(status=8|2,carrying=10);doc['actions']=[command('scan','TT I')]
    yield Case('supplement/scan-torso-tow',doc).expect('results.0.info',dict(torso=2,carrying=10)).expect('results.0.plain','Torso is 60 degrees right','contains').expect('results.0.plain','Towing u','contains')
