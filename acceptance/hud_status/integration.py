from . import *
from .observation import building,sight_state
from core.events import EventType

@step(r'a ready grounded mech at a real building entrance with an unlocked destination and one towed unit')
def entry_fixture(w):
    building(w,u(w).x,u(w).y);u(w).carrying=t(w)._id;u(w).map.name='outside';w['s'].maps['outside']=u(w).map
@step(r'enterbase is issued and (\d+) engine ticks elapse')
def entry(w,ticks):eq(command(w,'enterbase')['ok'],True);w['s'].action(dict(op='advance',seconds=int(ticks)))
@step(r'both units are on (\S+) and entry completion count is (\d+)')
def entered(w,name,count):
    board=w['building'] if name=='inside' else w['s'].maps['outside'];eq(u(w).map,board);eq(t(w).map,board);eq(getattr(u(w),'building_entries',0),int(count))
@step(r'a locked building with maximum CF 100 current CF (\d+) and safe (\S+)')
def locked(w,cf,safe):b=building(w,u(w).x,u(w).y);b.cf=int(cf);b.cfmax=100;b.enter_lock='false';b.buildflag=8 if truth(safe) else 0
@step(r'a ready mech issues enterbase at its entrance')
def enter(w):command(w,'enterbase')
@step(r'entry scheduling is (\S+)')
def scheduled(w,expected):eq(w['s'].engine.has_event(EventType.ENTER_HANGAR,u(w)),truth(expected));eq(w['result']['ok'],truth(expected))
@step(r'building entry was scheduled and the unit changes to (\S+) before tick 18')
def changed(w,state):
    entry_fixture(w);eq(command(w,'enterbase')['ok'],True)
    if state=='shutdown':command(w,'shutdown')
    if state=='jumping':u(w).status|=S.JUMPING
    if state=='moved-off-entrance':u(w).set_hex_position(3,3,0)
    if state=='locked-safe-destination':w['building'].enter_lock='false';w['building'].buildflag|=8
@step(r'the engine reaches tick 18')
def eighteen(w):w['s'].action(dict(op='advance',seconds=18))
@step(r'the unit stays outside with no completed entry')
def cancelled(w):eq(u(w).map,w['s'].maps['outside']);eq(getattr(u(w),'building_entries',0),0)
@step(r'a unit display fixture with an actual mounted weapon and armor')
def live(w):mount(u(w));u(w).facing=180;u(w).target=t(w)._id;w['original_armor']=[s.armor for s in u(w).sections]
@step(r'normal workflow (\S+) changes the unit and display commands are repeated')
def workflow(w,name):
    if name=='weapon-fire-and-recycle':
        w['fire']=command(w,'fire','0');w['before']=command(w,'status','W');w['s'].action(dict(op='advance',seconds=40));w['after']=command(w,'status','W')
    elif name=='real-section-armor-repair':
        u(w).sections[0].armor=u(w).sections[0].armor_orig-1
        w['s'].repair_jobs.schedule(47,u(w),u(w).command_actor._id*65536+16,1)
        w['before']=command(w,'status','A');w['s'].action(dict(op='advance',seconds=1));w['after']=command(w,'status','A')
    elif name=='timed-fire-overlay-expiry':
        w['s'].hexagon(dict(at=[4,4],terrain='ROAD',elevation=0,overlay='FIRE',duration=120));w['before']=command(w,'tactical','u');w['s'].action(dict(op='advance',seconds=120));w['after']=command(w,'tactical','u')
    elif name=='target-leaves-LOS':
        w['before']=command(w,'contacts');u(w).map.losinfo[u(w)._id,t(w)._id]=0;w['after']=command(w,'contacts');w['target_status']=command(w,'status','S')
    else:raise AssertionError(name)
@step(r'the new display shows (\S+) and unrelated state is preserved')
def refreshed(w,observable):
    if observable=='busy-then-ready':
        assert w['fire'].get('accepted',w['fire'].get('ok'));assert w['before']['weapons'][0]['status']!='Ready';eq(w['after']['weapons'][0]['status'],'Ready')
    elif observable=='repairing-then-current-value':
        assert '%ch%cb'in w['before']['armor']['text'];assert '%ch%cb'not in w['after']['armor']['text'];eq(u(w).sections[0].armor,u(w).sections[0].armor_orig)
    elif observable=='underlay-restored':eq(u(w).map.terrain(4,4),'#');assert '&'in w['before']['message'];assert '&'not in w['after']['message']
    elif observable=='contact-removed-target-not-in-LOS':eq(len(w['before']['contacts']),1);eq(w['after']['contacts'],[]);assert 'NOT in line of sight' in w['target_status']['message']
    eq([s.armor for s in u(w).sections][1:],w['original_armor'][1:])
@step(r'a local display workflow requires unavailable external service (\S+)')
def unavailable(w,service):
    w['service']=service
    if service=='MUX-expression-lock':entry_fixture(w);w['building'].enter_lock='owner(me)'
    if service=='MUX-custom-template-expression':u(w).status_expression=True
    if service=='autopilot-scan-reply':t(w).autopilot=999;t(w).freq=[100]
@step(r'the workflow reaches that service')
def missing(w):
    name=w['service']
    if name=='MUX-expression-lock':command(w,'enterbase')
    elif name=='MUX-custom-template-expression':command(w,'status')
    else:command(w,'scan','TT')
@step(r'the missing effect is explicitly reported and not counted as implemented behavior')
def explicit(w):assert w['result']['blocked'];eq(w['result']['effects_complete'],False)
@step(r'an unchanged six-location fighter template (\S+) is loaded with distinct section armor')
def fighter(w,reference):
    from data.template_dependency import resolve_catalog
    from data.template_files import load_stream
    with (resolve_catalog(True)/reference).open() as stream:load_stream(u(w),stream,reference)
    for i,section in enumerate(u(w).sections[:6]):section.armor=section.armor_orig=10+i
    u(w).status|=S.STARTED
@step(r'armor status critical status HUD oas and as are requested')
def fighter_displays(w):
    w['armor']=command(w,'status','A');w['crits']=command(w,'critstatus','Cockpit');w['s'].sessions['main'].request('key=fighter');w['oas']=hud(w,'oas');w['as']=hud(w,'as')
@step(r'all six named sections and five Cockpit slots are preserved and no gameplay SI pool is created')
def fighter_result(w):
    from systems.damage_commands import section_names
    eq(list(section_names(u(w))),['Nose','Left Wing','Right Wing','Fuselage','Cockpit','Engine'])
    eq(sorted(r['number'] for r in w['crits']['slots']),[1,2,3,4,5]);eq(len(records(w,result=w['oas'])),6);eq(len(records(w,result=w['as'])),6)
    for name in ('Nose','Left Wing','Right Wing','Fuselage','Cockpit','Engine'):assert name in w['armor']['armor']['plain']
    eq(getattr(u(w),'si',0),0)
