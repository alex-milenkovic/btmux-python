"""Point repair, structural recovery, and technology selection examples."""
import re
from . import check,command,stock,advance,U,M,F,C,Specials,i2special,Special,source_id,source_part
from systems.damage import unit_is_fixable
from systems.parts import proper_armor,proper_internal
from systems.repair_materials import repair_alias
from systems.technician import pack


def destroy(u,loc):
    sec=u.sections[loc];sec.armor=sec.internal=0;sec.config|=C.SECTION_DESTROYED


def run(w,initial,operation):
    u=w['u'];inv=w['inventory'];name=operation.split()[0]
    if operation=='unit fixability':
        loc=4
        if initial.startswith('VTOL'):u.unit_type=U.VTOL;u.move_type=M.VTOL;loc=5 if 'rotor' in initial else 0
        elif initial.startswith('ground'):u.unit_type=U.VEH_GROUND;loc=4 if 'turret' in initial else 0
        elif initial.startswith('AERO'):u.unit_type=U.AERO;loc=3
        elif 'LA destroyed' in initial:loc=0
        if 'unpopulated' in initial:u.sections[loc].internal_orig=0
        destroy(u,loc);result=unit_is_fixable(u);check(w,'true',result);check(w,'false',not result);return True
    if operation in ('proper armor','proper internal','alias part'):
        for label,flag in [('FF and',Specials.FF_TECH),('Hardened',Specials.HARDA_TECH),('Endosteel',Specials.ES_TECH),('Reinforced',Specials.REINFI_TECH),('Composite',Specials.COMPI_TECH),('XL and',Specials.XL_TECH),('ICE',Specials.ICE_TECH),('XXL',Specials.XXL_TECH),('Compact',Specials.CE_TECH),('Light technology',Specials.LE_TECH),('double',Specials.DOUBLE_HEAT_TECH)]:
            if re.search(r'\b'+re.escape(label),initial):u.specials|=flag
        if 'Stealth' in initial:u.specials2|=1
        if 'HeavyFF' in initial:u.specials2|=2
        if 'LightFF' in initial:u.specials2|=0x4000
        if 'Purifier' in initial:u.infantry_specials|=8
        result=source_id(proper_armor(u)) if operation=='proper armor' else source_id(proper_internal(u)) if operation=='proper internal' else repair_alias(u,i2special(Special.ENGINE if 'Engine' in initial else Special.HEAT_SINK if 'HeatSink' in initial else Special.SHOULDER_OR_HIP))
        aliases={'FF cargo':source_part('FF_Armor'),'Stealth cargo':source_part('STH_Armor'),'HeavyFF cargo':source_part('HVY_FF_Armor'),'Purifier cargo':553,'Endosteel cargo':source_part('ES_Internal'),'Reinforced cargo':558,'Composite cargo':559,'standard actuator cargo':548,'XL engine cargo':542,'ICE engine cargo':544,'XXL engine cargo':555,'Compact engine cargo':556,'Light engine cargo':561,'double heat sink cargo':543}
        for label,expected in aliases.items():check(w,label,result==expected)
        return True
    if name not in ('fixarmor','fixinternal','reattach','reseal','replacesuit'):return False
    w['streams']['tech_rolls']=[2,2] if 'both fail' in initial or 'recovery fail' in initial else [2,12] if 'recovery pass' in initial else [12]
    match=re.search(r'percent(?:draw)?(\d+)',initial)
    if match:w['streams']['repair_percent']=[int(match[1])]
    loc=0 if any(x in initial for x in ('LA','AERO','BA','nonBA')) else 4;sec=u.sections[loc];arg='LA' if loc==0 else 'CT'
    if initial.startswith('AERO'):u.unit_type=U.AERO;u.move_type=M.FLY;arg='Nose';u.structural_integrity=17
    if initial.startswith('BA'):
        u.unit_type=U.BSUIT;arg='S1';u.max_suits=4
        for i,s in enumerate(u.sections):s.internal_orig=s.internal=10 if i<4 else 0;s.armor_orig=s.armor=10 if i<4 else 0
    if 'destroyed' in initial or 'armor0 internal0' in initial:destroy(u,loc)
    if 'no live members' in initial:
        for i in range(4):destroy(u,i)
    if 'LT destroyed' in initial:destroy(u,2)
    if 'flooded' in initial and 'not flooded' not in initial:sec.config|=C.SECTION_FLOODED;sec.criticals[0].type=i2special(Special.CASE);sec.criticals[0].firemode=F.DISABLED_MODE
    if name in ('fixarmor','fixinternal'):
        field='internal' if name=='fixinternal' else 'rear' if initial.startswith('rear') else 'armor'
        m=re.search(r'(?:armor|internal)(\d+) original(\d+)',initial)
        setattr(sec,field,int(m[1]));setattr(sec,field+'_orig',int(m[2]))
        if 'internal9 original10' in initial and name=='fixarmor':sec.internal=9
        if field=='rear':arg+=' r'
        m=re.search(r'stock(\d+)',initial);resource=547 if name=='fixarmor' else 546;stock(w,resource,int(m[1]) if m else 0)
    else:
        for part,count in ((546,10),(545,9 if 'electronics9' in initial else 10),(600,2),(601,2),(602,9 if 'fourth resource9' in initial else 10)):stock(w,part,count)
    before=inv.raw(1000)
    if operation=='reattach event':w['result']=w['jobs'].schedule(45,u,pack(7,loc),1);w['error']=''
    else:command(w,name,arg)
    event=w['result'];err=w['error'];deadline=event.tick if event else 0
    checks={'refuse path without dice or debit':'adjacent','refuse unfixable':'unfixable','refuse not flooded':'not flooded','refuse and retain both full stocks':'stock','refuse all dead without debit':'live','refuse and retain every resource':'stock','refuse wrong unit type':'Wrong','refuse suits need replacement':'Suits','refuse no repair need after source clamp':'No repair','refuse internals first':'internals'}
    for label,fragment in checks.items():check(w,label,fragment.lower() in err.lower() and not w['draws'] and inv.raw(1000)==before)
    observations=[]
    if operation=='reattach event':advance(w,1)
    elif 'advance' in operation and event:
        for number in re.findall(r'(?:advance|then)(\d+)',operation):advance(w,int(number));observations.append(getattr(sec,field) if name.startswith('fix') else sec.internal)
    if name.startswith('fix'):
        check(w,'armor7 then8 then9 then10 and stock0',observations==[7,8,9,10] and inv.find(1000,547)==0)
        check(w,'internal7 then8 then9 then10 and stock0',observations==[7,8,9,10] and inv.find(1000,546)==0)
        check(w,'rear5 then6 front unchanged encodedloc12',observations==[5,6] and sec.armor==10 and event.data2%16==12)
        for label,first,last,minutes in [('amount2 time9 minutes first due360 then540 total and stock0',360,540,9),('amount2 time27 minutes first due1080 then1620 total and stock0',1080,1620,27)]:
            valid=bool(event) and deadline==first and event.data2%65536//16==2 and w['tech'].pending(w['actor'])==minutes and inv.find(1000,resource)==0
            if valid:advance(w,first);one=getattr(sec,field);advance(w,last-first);valid=one==6 and getattr(sec,field)==7 and not w['jobs'].events()
            check(w,label,valid)
        for label,attr in [('armor10 no finish message and no remaining event','armor'),('internal10 no finish message and no remaining event','internal')]:check(w,label,getattr(sec,attr)==10 and observations==[10] and not w['jobs'].messages and not w['jobs'].events())
        check(w,'armor10 with internals10 and SI unchanged',sec.armor==sec.internal==10 and u.structural_integrity==17 if initial.startswith('AERO') else False)
    counts=[inv.find(1000,k) for k in (546,545,600,601,602)]
    check(w,'LA internal10 unflooded and both stocks0',sec.internal==10 and not sec.config&C.SECTION_FLOODED and counts[:2]==[0,0] and deadline==14400)
    check(w,'unflooded disabled parts repaired and both stocks0',not sec.config&C.SECTION_FLOODED and not sec.criticals[0].firemode&F.DISABLED_MODE and counts[:2]==[0,0] and deadline==3600)
    check(w,'real reseal and stocks0',not sec.config&C.SECTION_FLOODED and counts[:2]==[0,0] and deadline==5400)
    check(w,'still flooded and refund5 each',bool(sec.config&C.SECTION_FLOODED) and counts[:2]==[5,5])
    check(w,'member restored and all four resources0',sec.internal==10 and [counts[i] for i in (0,2,3,4)]==[0]*4 and deadline==7200)
    check(w,'member stays destroyed refunds5 internal1 sensor1 life5 electronics',sec.internal==0 and [counts[i] for i in (0,2,3,4)]==[5,1,1,5])
    check(w,'restored and stocks0',sec.internal==10 and counts[:2]==[0,0] and deadline==21600)
    check(w,'not restored and stocks0',sec.internal==0 and counts[:2]==[0,0] and deadline==21600)
    check(w,'internal1 armor0 and still armor-destroyed',sec.internal==1 and sec.armor==0 and u.is_section_destroyed(0))
    return True
