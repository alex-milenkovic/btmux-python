from . import step,eq,truth
from .personnel import fresh_personnel
from core.events import EventType as E
from core.randomness import use_source
from entities.mech import UnitType as U,MoveType as M,MechStatus as S,Location as L,FireMode as F
from systems import occupants as o
_DIRECTORY=None

@step(r'a valid source-backed local pilot in an IC map with a loadable MechWarrior template')
def fresh(w):
    global _DIRECTORY
    fresh_personnel(w);w['family']='ejection';w['radio']=[]
    from data.template_catalog import CatalogDirectory
    from data.template_dependency import resolve_catalog
    if _DIRECTORY is None:_DIRECTORY=CatalogDirectory(w['root']/'custom',resolve_catalog(True))
    w['engine'].template_directory=_DIRECTORY
    def radio():w['radio'].append(123456);return 123456
    w['world'].radio_source=radio;w['before']=set(w['world'].objects)

@step(r'a manual eject request with (\S+)')
def condition(w,condition):
    w['condition']=condition;u=w['unit']
    if condition=='MECH-started-owner':pass
    elif condition=='ground-landed-owner':u.unit_type=U.VEH_GROUND;u.status|=S.LANDED
    elif condition=='VTOL-airborne':u.unit_type=U.VTOL;u.move_type=M.VTOL;u.status&=~S.LANDED
    elif condition=='dropship':u.unit_type=U.DS
    elif condition=='BA':u.unit_type=U.BSUIT
    elif condition=='nonIC-unit':u.in_character=False
    elif condition=='nonIC-map':u.location_ic=False
    elif condition=='MUX-IC-off':w['world'].in_character=False
    elif condition=='started-other-pilot':u.pilot=w['store'].actor(102)
    elif condition=='stopped-wrong-owner':u.status&=~S.STARTED;u.official_pilot=999
    elif condition=='nonfunctional-cockpit':u.sections[L.HEAD].criticals[2].firemode|=F.DISABLED_MODE
    elif condition=='missing-template':w['store'].records[101]['mwtemplate']='not-present'
    else:raise AssertionError(condition)
@step(r'the ordinary eject command runs')
def eject(w):w['result']=o.eject(w['unit'],w['actor'])

@step(r'a disembark request with started (True|False) caller (pilot|passenger) and speed (-?[\d.]+)')
def disembark_condition(w,started,caller,speed):
    u=w['unit'];u.speed=float(speed)
    if not truth(started):u.status&=~S.STARTED
    if caller=='passenger':u.pilot=w['store'].actor(102)
@step(r'the ordinary disembark command runs')
def disembark(w):w['result']=o.disembark(w['unit'],w['actor'])
@step(r'it is (accepted|rejected-running|rejected-speed)')
def disembarked(w,expected):
    r=w['result'];eq(r['ok'],expected=='accepted');eq(w['unit'].is_destroyed,False)
    if expected=='accepted':eq(w['actor'].location,r['unit']);eq(w['world'].objects[r['unit']].official_pilot,101)
    else:assert ('running' if expected=='rejected-running' else 'too fast') in r['error'],r

@step(r'source Z (-?\d+) ground elevation (-?\d+) speed (-?[\d.]+) and vertical speed (-?[\d.]+)')
def airborne(w,z,ground,speed,vertical):
    u=w['unit'];u.status&=~S.STARTED;u.z=int(z);u.speed=float(speed);u.vertical_speed=float(vertical)
    w['board'].set_elevation(3,3,int(ground))
@step(r'the pilot disembarks')
def airborne_run(w):disembark(w)
@step(r'new MW Z is (-?\d+) and fall event data is (none|-?\d+) due after (\d+) seconds')
def airborne_result(w,z,data,delay):
    eq(w['result']['ok'],True);mw=w['world'].objects[w['result']['unit']];eq(mw.z,int(z));eq(mw.opaque,True)
    events=[e for e in w['engine'].events.pending_events() if e.event_type==E.FALL and e.data is mw]
    eq([(e.data2,e.tick) for e in events],[] if data=='none' else [(int(data),int(delay))])

@step(r'automatic ejection condition (\S+)')
def auto_condition(w,condition):
    w['condition']=condition
    if condition=='player-zero':
        w['store'].create(0,'Zero',location=10);w['actor']=w['store'].actor(0);w['world'].add(w['actor'],10);w['unit'].pilot=w['actor'];w['before'].add(0)
    elif condition=='location-nonIC':w['unit'].location_ic=False
    elif condition=='missing-template':w['store'].records[101]['mwtemplate']='not-present'
    elif condition.startswith('last-BA'):
        w['unit'].unit_type=U.BSUIT
        for s in w['unit'].sections:s.internal=s.internal_orig=0
        w['unit'].sections[7].internal=w['unit'].sections[7].internal_orig=1
@step(r'the ordinary destruction producer invokes autoejection')
def auto_run(w):
    from systems.damage import reactor_explosion,destroy_section
    condition=w['condition'];u=w['unit']
    def draw(name,lo,hi,fallback):return int(condition[-2:]) if condition.startswith('last-BA') else hi
    with use_source(draw):
        if condition.startswith('last-BA'):destroy_section(u,None,7);w['result']=getattr(u,'last_ejection',None)
        else:reactor_explosion(u,u);w['result']=getattr(u,'last_ejection',None)

def result(w,expected):
    r=w['result'];u=w['unit']
    errors={'landed-error':'landed','dropship-error':'Dropships','no-seat-error':'no ejection seat','unit-IC-error':"unit isn't in character",'location-IC-error':"location isn't in character",'MUX-IC-error':"MUX isn't in character",'seat-error':"pilot's seat",'official-pilot-error':'official pilot','used-cockpit-error':'already used'}
    if expected in errors:eq(r['ok'],False);assert errors[expected] in r['error'],r;eq(w['actor'].location,10);eq(w['radio'],[]);return
    created=[obj for ident,obj in w['world'].objects.items() if ident not in w['before']]
    if expected in ('creation-rolled-back-player-unmoved','error-no-orphan-no-fake-success','no-creation','no-MW-contents-death'):
        eq(created,[]);eq(w['radio'],[])
        if expected=='creation-rolled-back-player-unmoved':eq(r['ok'],False);eq(w['actor'].location,10);eq(u.is_destroyed,False)
        if expected=='no-MW-contents-death':eq(w['actor'].alive,False);eq(w['actor'].location,900)
        return
    eq(len(created),1);mw=created[0];eq(mw.unit_type,U.MW);eq(w['actor'].location,mw._id);eq(w['actor'].alive,True)
    eq(mw.freq[0],123456);eq(w['radio'],[123456]);eq(u.is_destroyed,True)
    if expected.startswith('success'):
        eq(r['ok'],True);eq(mw.official_pilot,101)
        if 'cockpit' in expected:eq(bool(u.sections[L.HEAD].criticals[2].firemode&F.DESTROYED_MODE),True)
    elif expected=='MW-before-head-destruction-OOD150':eq(mw.z,150);eq(w['engine'].has_event(E.OOD,mw),True);eq(u.sections[L.HEAD].internal,0)
    else:eq(expected,'MW-climbout-no-OOD');eq(w['engine'].has_event(E.OOD,mw),False)
