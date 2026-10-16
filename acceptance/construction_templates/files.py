import io
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from data import templates as t
from data.template_files import load_stream,load_critical,finish_load,dump_locations,dump_item,saved_specials,mode_masks
from data.template_directory import save_legacy,load_legacy_stream
from entities.mech import UnitType as U,FireMode as F,SectionConfig as C
from . import step,eq,text,unit,part,attempt


def fields(values):return ''.join(f'{name} {{ {value} }}\n' for name,value in values)


def load(w,content,name='TEMPLATE',**options):
    attempt(w,load_stream,w['unit'],io.StringIO(content),name,catalog=w['catalog'],**options)


@step(r'a zeroed unit loads a modern file named (.+) containing Reference (.+) Unit_Era (.+) and Unit_TRO (.+)')
def named(w,filename,reference,era,tro):
    w['filename']=filename;w['content']=fields((('Reference',reference),('Unit_Era',text(era)),('Unit_TRO',text(tro))))


@step(r'loading succeeds')
def loaded(w):load(w,w['content'],w['filename']);eq(w['error'],None)


@step(r'stored reference era and TRO are (.+) (.+) and (.+)')
def named_result(w,reference,era,tro):eq((w['unit'].template_ref,w['unit'].unit_era,w['unit'].unit_tro),(reference,era,tro))


@step(r'a zeroed unit loads a modern template containing (.+)')
def ordered(w,sequence):w['content']=fields([item.split(':') for item in sequence.split(',')])


@step(r'loading finishes')
def finished(w):load(w,w['content']);eq(w['error'],None)


@step(r'current and original fuel both equal (\d+)')
def fuels(w,value):eq((w['unit'].fuel,w['unit'].fuel_orig),(int(value),int(value)))


@step(r'a zeroed non-mech template has source Clan flag ([01]) and item (.+) with computer (\d+) radio (\d+) and scan (\d+)')
def electronics(w,clan,item,computer,radio,scan):
    w['content']=fields((('Type','Vehicle'),('Specials','Clan' if clan=='1' else '-'),('Computer',computer),('Radio',radio),('Scan_Range',scan)))+'Front_Side\n'+fields((('CRIT_1',item+' - -'),))


@step(r'modern load finalization runs')
def finalize(w):load(w,w['content']);eq(w['error'],None)


@step(r'computer radio scan tac lrs radio_range and radio_type are (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) and (\d+)')
def electronics_result(w,*values):
    eq(tuple(getattr(w['unit'],k) for k in ('computer','radio','scan_range','tac_range','lrs_range','radio_range','radio_type')),tuple(map(int,values)))


@step(r'a modern (.+) template has an AC5 ammo slot with quantity (\d+) and mode (.+)')
def ammo_setup(w,kind,quantity,mode):
    unit(w,kind);w['quantity']=quantity;w['mode']=mode


@step(r'that slot is loaded')
def ammo_load(w):attempt(w,load_critical,w['unit'],0,'CRIT_1',f'Ammo_IS.AC/5 {w["quantity"]} {w["mode"]} -',w['catalog']);eq(w['error'],None)


@step(r'rounds are (\d+) and halfton is ([01])')
def normalized(w,rounds,half):
    s=w['unit'].sections[0].criticals[0];eq((s.data,bool(s.firemode&F.HALFTON_MODE)),(int(rounds),bool(int(half))))


@step(r'a zeroed unit loads modern field (.+) with value (.+)')
def field(w,name,value):
    w['field']=name;w['content']=('Left_Arm\n' if name=='Config' or name.startswith('CRIT') else '')+fields(((name,text(value)),))


@step(r'that field is applied')
def apply(w):load(w,w['content'],finalize=False)


@step(r'the field outcome is (.+)')
def applied(w,outcome):
    u=w['unit']
    if outcome in ('error','safe-bounds-error'):
        assert w['error']
        if outcome=='safe-bounds-error':assert 'bounds' in w['error'];eq([s.type for s in u.sections[0].criticals],[0]*12)
    else:
        eq(w['error'],None)
        if outcome=='both-flags-set':eq((u.specials,u.specials2),(32,4096))
        elif outcome=='unchanged-no-error':eq((u.specials,u.specials2,u.infantry_specials),(0,0,0))
        elif outcome=='zero':eq(u.sections[0].config,0)
        else:eq(u.tonnage,int(outcome))


@step(r'a modern file defines (CRIT_[\d-]+) as HeatSink data7 brand3 with parts enabled')
def range_setup(w,command):w['content']='Left_Arm\n'+fields(((command,'HeatSink 7 - 3'),))


@step(r'the critical range loads')
def range_load(w):load(w,w['content']);eq(w['error'],None)


@step(r'one-based slots holding HeatSink data7 brand3 are (.+)')
def copied(w,slots):
    values=w['unit'].sections[0].criticals
    eq([str(i+1) for i,s in enumerate(values) if s.type],slots.split(','))
    for s in values:
        if s.type:eq((s.type,s.data,s.brand),(part('HeatSink'),7,3))


@step(r'a template section has original armor (\d+) internal (\d+) rear (\d+) and current values1 with config Case')
def save_setup(w,armor,internal,rear):
    s=w['unit'].sections[0];s.armor_orig=int(armor);s.internal_orig=int(internal);s.rear_orig=int(rear)
    s.armor=s.internal=s.rear=1;s.config=C.CASE_TECH


@step(r'modern locations are saved')
def save_locations(w):
    stream=io.StringIO();dump_locations(stream,w['unit'],catalog=w['catalog']);w['saved']=stream.getvalue()


@step(r'emitted armor internal rear and config are (.+) (.+) (.+) and (.+)')
def saved_locations(w,armor,internal,rear,config):
    for name,expected in zip(('Armor','Internals','Rear','Config'),(armor,internal,rear,config)):
        found=re.search(r'\b'+name+r'\s+\{ (.*?) \}',w['saved'])
        if expected in ('omitted','section-omitted'):eq(found,None)
        else:eq(found[1],expected)
    if armor=='section-omitted':eq(w['saved'],'')


@step(r'a source mech has (\d+) adjacent identical (.+) slots with data0 mode0 and brand0')
def group(w,count,name):
    for slot in w['unit'].sections[0].criticals[:int(count)]:slot.type=part(name)


@step(r'dump_item begins at one-based slot1')
def dump(w):
    stream=io.StringIO();w['result']=dump_item(stream,w['unit'],0,0,catalog=w['catalog']);w['saved']=stream.getvalue()


@step(r'its run length is (\d+)')
def grouped(w,value):eq(w['result'],int(value))


@step(r'a non-mech section contains part (.+)')
def nonmech(w,name):
    u=unit(w,'Vehicle');u.sections[0].internal_orig=1;u.sections[0].criticals[0].type=part(name)


@step(r'the item is (omitted|emitted)')
def excluded(w,value):eq('CRIT_' in w['saved'],value=='emitted')


@step(r'a unit has original front armor20 current front armor7 and an AC5 ammo slot with remaining (\d+) and halfton ([01])')
def capacity_setup(w,remaining,half):
    u=w['unit'];s=u.sections[0];s.armor_orig=20;s.armor=7;s.internal_orig=s.internal=8
    slot=s.criticals[0];slot.type=part('Ammo_IS.AC/5');slot.data=int(remaining);slot.firemode=128 if half=='1' else 0


@step(r'modern and legacy saves are read')
def capacity_save(w):
    save_locations(w)
    with TemporaryDirectory(dir='./tmp') as root:
        path=Path(root)/'old';save_legacy(w['unit'],path);w['legacy']=path.read_text().splitlines()


@step(r'modern armor and rounds are20 and (\d+) while legacy armor and rounds are7 and (\d+)')
def capacities(w,modern,legacy):
    eq(re.search(r'Armor\s+\{ (\d+)',w['saved'])[1],'20')
    eq(re.search(r'Ammo_IS.AC/5 (\d+)',w['saved'])[1],modern)
    eq(w['legacy'][1].split()[0],'7');eq(w['legacy'][2].split()[1],legacy)


@step(r'a Mech carries only special flag (.+)')
def flag(w,name):
    index=t.name_index(t.SPECIALS_NAMES,name)
    if index>=0:w['unit'].specials=1<<index
    else:w['unit'].specials2=1<<t.name_index(t.SPECIALS2_NAMES,name)
    w['flag']=name


@step(r'modern template specials are saved')
def filter_flags(w):
    a,b=saved_specials(w['unit']);w['saved']=t.bit_names2(t.SPECIALS_NAMES,t.SPECIALS2_NAMES,a,b)


@step(r'that flag is (emitted|omitted)')
def filtered(w,value):eq(w['flag'] in w['saved'].split(),value=='emitted')


@step(r'a modern template has (weapon|ammo) slot with mode field (.+)')
def modes_setup(w,kind,value):
    u=w['unit'];u.unit_type=U.VEH_GROUND;slot=u.sections[0].criticals[0];slot.firemode=32;slot.ammomode=8192
    w['slot']=slot;w['mode_content']=('IS.AC/5 - ' if kind=='weapon' else 'Ammo_IS.AC/5 20 ')+text(value)+' -'


@step(r'the approved union mode loader runs')
def union(w):attempt(w,load_critical,w['unit'],0,'CRIT_1',w['mode_content'],w['catalog'])


@step(r'fire mask is (.+) ammo mask is (.+) and outcome is (success|error)')
def union_result(w,fire,ammo,outcome):
    eq(w['error'] is None,outcome=='success')
    eq((w['slot'].firemode,w['slot'].ammomode),(32 if fire=='unchanged' else int(fire),8192 if ammo=='unchanged' else int(ammo)))


@step(r'the standalone (fire|ammo) mode parser receives (.+)')
def strict(w,kind,value):w['result']=t.parse_bit_vector_delim(t.CRIT_FIRE_MODES if kind=='fire' else t.CRIT_AMMO_MODES,text(value))
