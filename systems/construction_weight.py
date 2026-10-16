# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.consistency.c
#   btech/mech.tech.commands.c
#   btech/template.c

"""Construction and remaining mass from mech.consistency.c (1/1024 ton).

Terms retain C integer operation order and rounding, including defined quirks.
Managed file-template units detect changed weight inputs before cached readout.
"""
import math
from collections import defaultdict
from data.construction_tables import INTERNAL_TABLE,ENGINE_TABLE
from entities.mech import UnitType as U,MoveType as M,Specials as S,FireMode as F,AmmoMode as A,CritStatus
from entities.crittypes import is_weapon,is_ammo,is_special,weapon2i,ammo2weapon_i,special2i,i2special,Special as P,crits_in_loc
from entities.weapon import get_weapon_by_index
from systems.parts import round_to_halfton as half,round_to_quarterton as quarter,reverse_split_crit_loc
from systems.damage import heat_sink_size
from core.randomness import float32 as f32


def div(a,b):
    if not b:raise ValueError('undefined construction denominator')
    return (abs(a)//abs(b))*(-1 if (a<0)!=(b<0) else 1)


def diagnostics(unit,message):
    if not hasattr(unit,'construction_messages'):unit.construction_messages=[]
    unit.construction_messages.append(message)


def server_error(unit,message):
    from core.effects import send_error
    diagnostics(unit,message)
    send_error(unit,message)


def internal_value(unit,location,row):
    if location==7:return 3
    column={4:1,2:2,3:2,0:4 if unit.move_type==M.QUAD else 3,
            1:4 if unit.move_type==M.QUAD else 3,5:4,6:4}.get(location)
    return row[column] if column is not None else 0


def internal_check(unit,noisy=False):
    row=next((r for r in INTERNAL_TABLE if r[0]==unit.tonnage),None)
    if unit.unit_type==U.MECH and row is None:
        if noisy:server_error(unit,f'VERY odd tonnage for #{unit._id}: {unit.tonnage}.')
        return
    if unit.unit_type not in (U.MECH,U.VEH_GROUND,U.VTOL,U.VEH_NAVAL):return
    for loc,section in enumerate(unit.sections):
        if unit.unit_type!=U.MECH and not section.internal_orig:continue
        value=internal_value(unit,loc,row) if unit.unit_type==U.MECH else max(div(unit.tonnage+5,10),1)
        if section.internal_orig!=value:
            if noisy:server_error(unit,f'Template {getattr(unit,"template_ref","")} / mech #{unit._id}: Invalid internals in loc {loc} (should be {value}, are {section.internal_orig})')
            section.internal_orig=section.internal=value
            invalidate(unit)


def suspension(unit):
    if unit.move_type==M.WHEEL:return 20
    if unit.move_type in (M.HULL,M.SUB):return 30
    bands={M.FOIL:((10,60),(20,105),(30,150),(40,195),(50,255),(60,300),(70,345),(80,390),(90,435)),
           M.HOVER:((10,40),(20,85),(30,130),(40,175)),M.VTOL:((10,50),(20,95))}
    if unit.move_type not in bands:return 0
    return next((value for bound,value in bands[unit.move_type] if unit.tonnage<=bound),
                {M.FOIL:480,M.HOVER:235,M.VTOL:140}[unit.move_type])


def engine_weight(unit):
    rating=unit.engine_size()-(suspension(unit) if unit.unit_type!=U.MECH else 0)
    value=dict(ENGINE_TABLE).get(rating)
    if value is None:
        if unit.move_type!=M.HOVER:server_error(unit,f'Error in #{unit._id} ({unit.name}) : No engine found!')
        return 0
    value*=512
    if unit.specials&S.ICE_TECH:return value*2
    if unit.unit_type in (U.VEH_GROUND,U.VTOL,U.VEH_NAVAL):value=half(value+div(value,2))
    for flag,numerator,denominator in ((S.XL_TECH,1,2),(S.XXL_TECH,1,3),(S.LE_TECH,3,4),(S.CE_TECH,3,2)):
        if unit.specials&flag:return half(div(value*numerator,denominator))
    return value


def crit_weight(unit,part):
    from systems.weapon_inventory import weapon_crits
    if is_weapon(part):
        weapon=get_weapon_by_index(weapon2i(part))
        if weapon is None:raise ValueError('undefined weapon weight')
        return div(div(round(weapon.tonnage*100)*1024,100),weapon_crits(unit,weapon.index))
    if is_ammo(part):return 512
    if not is_special(part):return 1024
    item=special2i(part);mech=unit.unit_type==U.MECH
    if item==P.HEAT_SINK:return div(1024,heat_sink_size(unit))
    if item in (P.TARGETING_COMPUTER,P.AXE,P.CLAW,P.MACE,P.DUAL_SAW,P.ARTEMIS_IV,P.MASC,P.C3_SLAVE,P.TAG,P.LAMEQUIP):return 1024
    if item==P.C3I:return 1280*(1 if mech else 2)
    if item==P.ANGELECM:return 1024*(1 if mech else 2)
    if item==P.BLOODHOUND_PROBE:return div(1024*(2 if mech else 6),3)
    if item==P.C3_MASTER:return 1024*(1 if mech else 5)
    if item==P.SWORD:return div(math.ceil(unit.tonnage/10)*512,math.ceil(unit.tonnage/15))
    if item==P.BEAGLE_PROBE:return div(3072,4 if mech else 2)
    if item==P.ECM:return div(1024*(4 if unit.specials&S.CLAN_TECH else 3 if mech else 6),4)
    if item in (P.CASE,P.LIGHT_BAP):return 512
    if item==P.JUMP_JET:return 512 if unit.tonnage<=55 else 1024 if unit.tonnage<=85 else 2048
    return 0


def ammo_weight(unit):
    value=0
    for loc,section in enumerate(unit.sections):
        if unit.is_section_destroyed(loc):continue
        for slot in section.criticals[:crits_in_loc(unit,loc)]:
            if is_ammo(slot.type):
                weapon=get_weapon_by_index(ammo2weapon_i(slot.type))
                if weapon is None:raise ValueError('undefined ammunition weight')
                value+=div(slot.data*1024,weapon.ammo_per_ton)
    return value


def ammo_mod(slot):
    if not is_ammo(slot.type) or slot.firemode&F.HALFTON_MODE or slot.ammomode&(A.AC_AP_MODE|A.AC_PRECISION_MODE):return 1
    return .5 if slot.ammomode&A.AC_CASELESS_MODE else 2


def weight(unit,interactive=0,notify=None):
    if unit.unit_type not in (U.MECH,U.VEH_GROUND,U.VTOL,U.VEH_NAVAL):
        if interactive>0:(notify or (lambda text: diagnostics(unit,text)))('Invalid vehicle type!')
        return dict(total=1,terms={})
    mech=unit.unit_type==U.MECH;design=interactive>=0;pile=defaultdict(int);armor=0;turret=0
    for loc,section in enumerate(unit.sections):
        if not section.internal_orig:continue
        armor+=(section.armor_orig+section.rear_orig) if design else (section.armor+section.rear)
        if not design and unit.is_section_destroyed(loc):continue
        for pos,slot in enumerate(section.criticals[:12 if mech else crits_in_loc(unit,loc)]):
            if design or not is_ammo(slot.type):
                selected=slot
                if mech and slot.type in (i2special(P.SPLIT_CRIT_LEFT),i2special(P.SPLIT_CRIT_RIGHT)):
                    other=reverse_split_crit_loc(unit,loc,pos)
                    if other<0:continue
                    if not 0<=slot.data<12:raise ValueError('split critical slot outside allocated range')
                    selected=unit.sections[other].criticals[slot.data]
                pile[selected.type]=int(pile[selected.type]+ammo_mod(selected))
            if not mech and loc==4 and unit.unit_type in (U.VEH_GROUND,U.VEH_NAVAL) and is_weapon(slot.type):
                turret+=crit_weight(unit,slot.type)
    terms={}
    def put(name,value):terms[name]=int(value)
    if mech:
        if design or not unit.is_section_destroyed(4):put('engine',engine_weight(unit))
        if design or not unit.is_section_destroyed(7):put('cockpit',2048 if unit.specials2&(1<<25) else 3072)
        gyro=f32(unit.engine_size()/100) if design or not unit.is_section_destroyed(4) else -1
        factor=.5 if unit.specials2&(1<<21) else 2 if unit.specials2&(1<<22) else 1.5 if unit.specials2&(1<<23) else 1
        put('gyro',math.ceil(gyro)*1024*factor)
    else:
        if any(s.internal for s in unit.sections):
            engine=engine_weight(unit);put('engine',engine)
            if unit.move_type==M.HOVER:put('hover_engine',max(0,div(unit.tonnage*1024,5)-engine))
            put('cockpit',quarter(div(unit.tonnage*1024,20)))
            if unit.unit_type==U.VTOL or unit.move_type in (M.HOVER,M.HULL,M.SUB):put('components',half(div(unit.tonnage*1024,10)))
        if design or not unit.is_section_destroyed(4):put('turret',quarter(div(turret,10)))
    total_int=max(1,sum(s.internal_orig for s in unit.sections));current_int=sum(s.internal for s in unit.sections)
    structure=1 if unit.specials&S.REINFI_TECH else 4 if unit.specials&(S.ES_TECH|S.COMPI_TECH) else 2
    put('internals',half(div(div(div(unit.tonnage*1024*(total_int if design else current_int),5),total_int),structure)))
    armor_count=armor
    if unit.specials&S.FF_TECH:armor=div(armor*50,60 if unit.specials&S.CLAN_TECH else 56)
    elif unit.specials2&2:armor=div(armor*50,62)
    elif unit.specials2&(1<<14):armor=div(armor*50,53)
    elif not mech and unit.specials&S.HARDA_TECH:armor*=2
    put('armor',half(div(armor*1024,8 if mech and unit.specials&S.HARDA_TECH else 16)))
    sinks=getattr(unit,'original_sinks',unit.real_num_sinks) if mech and design else unit.real_num_sinks
    size=heat_sink_size(unit);efficiency=2 if unit.specials&(S.CLAN_TECH|S.DOUBLE_HEAT_TECH) else 1
    if sinks or not mech:pile[i2special(P.HEAT_SINK)]=max(0,div(sinks*size,efficiency)-(0 if unit.specials&S.ICE_TECH else 10)*size)
    put('equipment',sum(crit_weight(unit,part)*count for part,count in pile.items() if part and count))
    cargo=getattr(unit,'cargo_space',0)
    if cargo:put('cargo',f32(f32(f32(cargo)/(1000 if unit.specials2&(1<<19) else 100 if unit.specials&S.CARGO_TECH else 500))*1024))
    if not design:put('ammunition',ammo_weight(unit))
    result=dict(total=max(1,sum(terms.values())),terms=terms)
    if interactive>0:
        result['messages']=weight_report(unit,terms,pile,armor_count,sinks)
        for line in result['messages']:(notify or (lambda text: diagnostics(unit,text)))(line)
    return result



def weight_report(unit,terms,pile,armor,sinks):
    """Source-ordered coolmenu, retaining labels and integer count semantics."""
    from data.construction_catalog import Catalog,source_id
    from systems.notifications import unit_identity
    from systems.status_display import menu_lines
    from systems.weapon_inventory import weapon_crits
    mech=unit.unit_type==U.MECH
    flags=((S.XL_TECH,'XL'),(S.XXL_TECH,'XXL'),(S.CE_TECH,'Compact'),(S.LE_TECH,'Light')) if mech else (
        (S.LE_TECH,'Light'),(S.CE_TECH,'Compact'),(S.XXL_TECH,'XXL'),(S.XL_TECH,'XL'),(S.ICE_TECH,'ICE'))
    engine=next(('Engine ('+name+')' for flag,name in flags if unit.specials&flag),'Engine')
    rating=unit.engine_size();susp=suspension(unit) if not mech else 0
    labels={'engine':f'{engine:<12}({rating}->{rating-susp} eff/wt rat)' if susp else f'{engine:<12}({rating} rating)',
        'hover_engine':'Engine size fix (-> 1/5 hover wt.)',
        'cockpit':'Cockpit (Small)' if mech and unit.specials2&(1<<25) else 'Cockpit',
        'gyro':next((f'Gyro ({name})' for bit,name in ((21,'XL'),(22,'Hardened'),(23,'Compact')) if unit.specials2&(1<<bit)),'Gyro'),
        'components':'SpecialComponents','turret':'Turret',
        'internals':next((f'Internals ({name})' for flag,name in ((S.REINFI_TECH,'Reinforced'),(S.COMPI_TECH,'Composite'),(S.ES_TECH,'ES')) if unit.specials&flag),'Internals'),
        'armor':next((f'Armor ({name})' for active,name in ((unit.specials2&1,'Stealth'),(unit.specials2&2,'Hvy FF'),(unit.specials2&(1<<14),'Lt FF'),(unit.specials&S.HARDA_TECH,'Hardened'),(unit.specials&S.FF_TECH,'FF')) if active),'Armor')}
    lines=menu_lines('Weight totals for '+unit_identity(unit),[])[:-1]
    def entry(label,value,count=None):
        if not value:return
        number=f'{count:5d} {value/1024:6.2f}' if count is not None else f'      {value/1024:6.2f}'
        lines.extend(menu_lines('',[label,number],2)[3:-1])
    for key in ('engine','hover_engine','cockpit','gyro','components','turret','internals','armor'):
        entry(labels[key],terms.get(key,0),armor if key=='armor' else None)
    if mech and not sinks:
        lines.append(menu_lines('WARNING: HS count may be off, due to certain odd things.',[])[1])
    catalog=Catalog(diagnostic=lambda text:server_error(unit,text))
    for part,count in sorted(pile.items(),key=lambda item:source_id(item[0])):
        if not part or not count:continue
        value=crit_weight(unit,part)*count
        if not value:continue
        if is_weapon(part):
            weapon=get_weapon_by_index(weapon2i(part));label=weapon.name
            count=div(count,weapon_crits(unit,weapon.index))
        else:label=catalog.names(source_id(part))[1] or '(null)'
        entry(label,value,count)
    entry(f'CargoSpace ({getattr(unit,"cargo_space",0)/100:.2f}t)',terms.get('cargo',0))
    total=sum(terms.values());colour='%ch%cr' if div(total,1024)>unit.tonnage else ''
    rule=menu_lines('',[])[0]
    lines.extend((rule,f'%cgTotal: {colour}{total/1024:.1f} tons (offset: {unit.tonnage-total/1024:.1f})%cn',rule))
    return lines


def fingerprint(unit):
    return (unit.unit_type,unit.move_type,unit.tonnage,unit.engine_rating,unit.max_speed,unit.specials,unit.specials2,
            unit.real_num_sinks,getattr(unit,'cargo_space',0),unit.is_destroyed,
            tuple((s.internal_orig,s.internal,s.armor,s.rear,s.config,
                   tuple((c.type,c.data,c.firemode,c.ammomode) for c in s.criticals)) for s in unit.sections))


def invalidate(unit):unit.crit_status = int(unit.crit_status) & ~int(CritStatus.OWEIGHT_OK)


def get_weight(unit,dynspeed=None,compute=None):
    if dynspeed is None:dynspeed=getattr(unit,'construction_dynspeed',True)
    state=(dynspeed,fingerprint(unit)) if getattr(unit,'construction_managed',False) else None
    if state is not None and state!=getattr(unit,'_construction_weight_state',None):invalidate(unit)
    if unit.crit_status&CritStatus.OWEIGHT_OK:return unit.rtons
    value=(compute or (lambda:weight(unit,-1)['total']))()
    if not dynspeed or value==1 and not unit.is_destroyed:value=unit.tonnage*1024
    unit.rtons=value;unit.crit_status|=CritStatus.OWEIGHT_OK;unit._construction_weight_state=state
    return value
