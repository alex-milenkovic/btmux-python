"""Original design load, editor bounds and design serialization."""
import io
from . import step,eq,loc,NAMES,U,M,F,Special,i2special
from data.template_files import clear_mech,load_stream,dump_locations
from data.template_dependency import resolve_catalog
from entities.crittypes import crits_in_loc
from entities.mech import Mech
from systems.damage_commands import section_names
from systems.construction_editor import Editor

def load(w):
    u=w['u'];clear_mech(u,True)
    with (resolve_catalog(True)/'CHP-W5').open() as stream:load_stream(u,stream,'CHP-W5')
    w['design']=[[(s.type,s.brand,s.firemode,s.ammomode) for s in sec.criticals] for sec in u.sections]

@step(r'unchanged CHP-W5 is loaded')
def loaded(w):load(w)

@step(r'section (\d+) is (\w+) with armor (\d+) internal bookkeeping 10 and slot limit (\d+)')
def section(w,index,name,armor,slots):
    u=w['u'];i=int(index);eq(section_names(u)[i].replace(' ','_'),name)
    eq((u.sections[i].armor,u.sections[i].internal,crits_in_loc(u,i)),(int(armor),10,int(slots)))

@step(r'the physical equipment observation is (.+)')
def equipment(w,text):
    u=w['u']
    if text.startswith('Nose'):eq([(s.section,s.critical) for s in u.weapons if s.section==0],[(0,i) for i in range(5)])
    elif text.startswith('each-wing'):
        from entities.weapon import get_weapon
        for i in (1,2):
            eq([(s.critical,s.weapon_idx) for s in u.weapons if s.section==i],[(0,get_weapon('IS.LargeLaser').index),(2,get_weapon('IS.LargeLaser').index)])
            eq(u.sections[i].criticals[1].type,0)
    elif text.startswith('Fuselage'):eq([s.data for s in u.sections[3].criticals[:5]],[8,8,8,8,15])
    elif text.startswith('Cockpit'):eq([s.type for s in u.sections[4].criticals[:5]],[i2special(k) for k in (Special.LIFE_SUPPORT,Special.SENSORS,Special.COCKPIT,Special.SENSORS,Special.LIFE_SUPPORT)])
    elif text.startswith('Engine'):
        eq(len([s for s in u.weapons if s.section==5]),2);assert all(not s.type for s in u.sections[5].criticals[2:])
    elif text.startswith('six-sections'):
        eq(sum(s.armor for s in u.sections),120);eq(sum(s.internal for s in u.sections),60);eq(u.si,0);assert not u.is_destroyed
    else:eq((M(u.move_type).name,u.tonnage,u.max_speed,u.fuel,u.real_num_sinks),('FLY',90,86,750,25))

@step(r'resetcrits is applied to a fighter')
def defaults(w):
    editor=Editor(1,{'u':w['u']});editor.execute('settarget','u')
    eq(editor.execute('resetcrits')['ok'],True)

@step(r'section (\w+) has default contents (.+)')
def default_contents(w,name,contents):
    slots=w['u'].sections[loc(name)].criticals
    if contents=='empty':assert all(not s.type for s in slots)
    elif name=='Cockpit':equipment(w,'Cockpit');assert all(not s.type for s in slots[5:])
    else:eq([s.type for s in slots],[i2special(Special.ENGINE if i in (2,10) else Special.HEAT_SINK) for i in range(12)])

@step(r'the fighter editor operation is (.+)')
def edit(w,operation):
    from dataclasses import asdict
    load(w);editor=Editor(1,{'u':w['u']});editor.execute('settarget','u');w['before']=[asdict(s) for s in w['u'].sections]
    if operation.startswith('display-'):command,args='displaysection',operation[8:]
    else:
        kind,name,slot=operation.removeprefix('add-').split('-')
        command='addspecial' if kind=='special' else 'addweap'
        args=(f'HeatSink {name} {slot[4:]}' if kind=='special' else f'IS.LargeLaser {name} {slot[4:]}')
    w['edit_operation']=operation;w['result']=editor.execute(command,args)

@step(r'the result is (.+)')
def edited(w,result):
    from dataclasses import asdict
    r=w['result'];u=w['u']
    if result.startswith('rejected'):eq(r['ok'],False);eq([asdict(s) for s in u.sections],w['before'])
    else:
        eq(r['ok'],True)
        if result.startswith('section'):
            i=int(result[7]);eq(len(r['result']),5 if i==4 else 12)
        elif result=='one-slot-accepted':
            from entities.crittypes import is_weapon
            assert is_weapon(u.sections[5].criticals[11].type)

@step(r'loaded CHP-W5 with modification (.+)')
def modification(w,text):
    load(w);u=w['u'];w['modification']=text
    if text=='Nose-current-armor19':u.sections[0].armor=19
    elif text=='Fuselage-current-armor0':u.sections[3].armor=0
    elif text=='LRM-bin-current-ammo3':u.sections[3].criticals[0].data=3
    elif text=='wing-slot3-rear-mounted':u.sections[1].criticals[2].firemode|=F.REAR_MOUNT

@step(r'modern save writes a new reference and a fresh unit loads that file')
def roundtrip(w):
    out=io.StringIO();dump_locations(out,w['u']);u=Mech();clear_mech(u,True);u.unit_type=U.AERO
    load_stream(u,io.StringIO(out.getvalue()),'new-reference');w['reloaded']=u

@step(r'the observation is (.+)')
def observation(w,text):
    if text in ('fire-accepted-recycle-started','recycle-remains5','recycle-finishes','fire-refused'):
        from .weapons import lifecycle_result
        return lifecycle_result(w,text)
    if 'reloaded' not in w:
        from .damage import observe
        return observe(w,text)
    u=w['reloaded'];eq([s.armor for s in u.sections[:6]],[24,15,15,30,16,20]);eq([s.internal for s in u.sections[:6]],[10]*6)
    eq([s.data for s in u.sections[3].criticals[:5]],[8,8,8,8,15])
    eq([(m.section,m.critical,m.weapon_idx) for m in u.weapons],[(m.section,m.critical,m.weapon_idx) for m in w['u'].weapons])
    if w['modification']=='wing-slot3-rear-mounted':assert u.sections[1].criticals[2].firemode&F.REAR_MOUNT;eq(u.sections[1].criticals[1].type,0)
