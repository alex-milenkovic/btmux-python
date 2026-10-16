from pathlib import Path
from tempfile import TemporaryDirectory
from core.game_loop import GameEngine
from core.events import EventType
from entities.map import GameMap
from entities.mech import MechStatus as S
from data.template_directory import TemplateDirectory,load_legacy_stream
from . import step,eq,attempt


def directory(w):
    if 'directory' not in w:
        w['temp']=TemporaryDirectory(dir='./tmp');w['root']=Path(w['temp'].name)
        w['directory']=TemplateDirectory(w['root'])
    return w['directory']


@step(r'a unit reference is AS7-D with nonzero heat damage statuses targets TICs radio frequencies and channel titles')
def channels(w):
    u=w['unit'];u.template_ref='AS7-D';u.heat=40;u.damage_taken=7;u.status=S.STARTED;u.target=99
    u.tics[0].add(2);u.freq=[123]*16;u.chantitle=['alpha']*16
    b=GameMap(9,9);u.x=u.y=3;b.add_mech(u);w['board']=b;w['identity']=u._id


@step(r'mech_loadnew requests (.+) with a valid modern file')
def load(w,reference):
    d=directory(w);(w['root']/'AS7-D').write_text('Name { Atlas }\nTons { 50 }\n')
    (w['root']/'AS7-K').write_text('Name { Atlas }\nTons { 50 }\n')
    eq(d.loadnew(w['unit'],reference),True)


@step(r'TICs frequencies and titles are (retained|cleared) while runtime reset and live identity preservation succeed')
def reset(w,retention):
    u=w['unit'];keep=retention=='retained'
    eq((u.tics[0],u.freq[0],u.chantitle[0]),({2},123,'alpha') if keep else (set(),0,''))
    eq((u.heat,u.damage_taken,u.target,u.brief,u.aim,u.pilot),(0,0,-1,1,8,None))
    eq((u._id,u.x,u.y,u.map),(w['identity'],3,3,w['board']));eq(w['board'].mechs_on_map,[u])


@step(r'a unit with queued events and cached LOS requests (loadnew|restore) using a (.+) reference')
def wrapper(w,operation,file):
    u=w['unit'];u._engine=GameEngine();u.template_ref='' if file=='missing-reference' else 'A'
    w['operation']=operation;w['file']=file;d=directory(w)
    if file=='valid':(w['root']/'A').write_text('Tons { 50 }\n')
    b=GameMap(9,9);b.add_mech(u);w['board']=b;b.slot_los[0][0]=123
    for kind in (EventType.BLINDREC,EventType.VEHICLE_BURN):u._engine.events.schedule(100,kind,lambda e:None,u)


@step(r'the operation completes')
def wrapped(w):
    d=directory(w);u=w['unit']
    if w['operation']=='restore':attempt(w,d.restore,u)
    else:attempt(w,d.loadnew,u,'A',wrapper=True)


@step(r'its result and event policy are (.+) and (.+)')
def wrapper_result(w,result,events):
    u=w['unit']
    if result=='success':eq(w['error'],None);eq(w['result'],True)
    elif result=='failure-before-clear':assert w['error'];eq(u.template_ref,'')
    else:eq(w['result'],False);eq(u.tonnage,0)
    count={'all-unit-events-cancelled':0,'no-extra-wrapper-cancellation':1,'only-clear-mech-burning-cleanup':1,'unchanged':2}[events]
    eq(u._engine.events.count_data(u),count)
    eq(w['board'].slot_los[0][0],0 if events=='all-unit-events-cancelled' else 123)


@step(r'a template root contains (.+) and its cache is built')
def tree(w,name):
    d=directory(w);p=w['root']/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('')
    w['path']=p;d.scan()


@step(r'lookup (.+) uses (.+)')
def lookup(w,query,change):
    d=directory(w)
    if change=='add-AS7-K-after-scan':(w['root']/'AS7-K').write_text('')
    elif change=='save-AS7-K-invalidates-cache':d.save(w['unit'],'AS7-K')
    elif change=='delete-hit-and-retry':w['path'].unlink()
    elif change!='none':raise ValueError(change)
    w['result']=d.lookup(query)


@step(r'the outcome is (root-hit|subdir-hit|cache-miss|explicit-path-hit|not-found)')
def looked(w,outcome):
    if outcome in ('cache-miss','not-found'):eq(w['result'],None)
    else:
        assert w['result'].is_file()
        if outcome=='root-hit':eq(w['result'].parent,w['root'].resolve())
        elif outcome=='subdir-hit':eq(w['result'].parent.name,'Custom')
        else:eq(w['result'].parent.name,'nested')


@step(r'a complete numeric legacy template header has specials (\d+) and optional radio (.+)')
def legacy(w,specials,radio):
    w['content']=f'50 20 40 20 10 64.5 0 {specials}\n'+('20 5 0 0\n'+'0 0 0\n'*12)*8+'0 0\n'+('' if radio=='absent' else radio+'\n')


@step(r'legacy load is requested')
def legacy_load(w):
    import io
    load_legacy_stream(w['unit'],io.StringIO(w['content']),'old')


@step(r'specials and radio range are (\d+) and (\d+)')
def legacy_loaded(w,specials,radio):eq((w['unit'].specials,w['unit'].radio_range),(int(specials),int(radio)))
