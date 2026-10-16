"""Salvage commands and preserved legacy helper effects."""
import re
from . import check,command,attempt,stock,gun,advance,F,C,Special,i2special,source_id
from .structure import destroy
from systems.technician import pack


def run(w,initial,operation):
    name=operation.split()[0];u=w['u'];inv=w['inventory'];jobs=w['jobs'];loc=0;slot=u.sections[loc].criticals[0]
    if initial=='mounted bomb and cargo':
        from copy import deepcopy
        from entities.crittypes import BOMB_BASE_INDEX
        slot.type=BOMB_BASE_INDEX;stock(w,545,3)
        before=(deepcopy(u.sections),inv.raw(1000),list(jobs.messages))
        jobs.schedule(54 if name=='mountbomb' else 55,u,pack(7,loc),1);advance(w,1)
        check(w,'no state inventory or notification changes',before==(u.sections,inv.raw(1000),jobs.messages));return True
    if name.endswith('_succ'):
        stock(w,545,4);slot.firemode=F.DAMAGED_MODE;before=(inv.raw(1000),slot.firemode,slot.brand)
        result=attempt(w,w['work'].success,name)
        check(w,'return0 with no state dice or queue changes',result==0 and before==(inv.raw(1000),slot.firemode,slot.brand) and not jobs.events() and not w['draws']);return True
    if name.endswith('_fail'):
        width=5 if 'width5' in initial else 4
        if 'gun' in initial:gun(w,width,loc=loc);slot.firemode=F.DESTROYED_MODE
        else:slot.type=i2special(Special.CASE)
        if 'enhanced' in initial:slot.firemode=F.DAMAGED_MODE;slot.weap_damage_flags=7
        if 'bin' in initial:slot.data=8
        before=(slot.type,slot.data,slot.firemode,slot.weap_damage_flags)
        w['streams']['tech_rolls']=[12 if 'recovery pass' in initial else 2]
        match=re.search(r'percent(\d+)',initial)
        if match:w['streams']['repair_percent']=[int(match[1])]
        result=attempt(w,w['work'].failure,name,w['actor'],u,loc,0)
        check(w,'refund1 and return-1',result==-1 and inv.find(1000,source_id(slot.type))==1)
        check(w,'refund0 return-1 and no dice',result==-1 and not inv.raw(1000) and not w['draws'])
        check(w,'second destroyed and return-1',result==-1 and bool(u.sections[loc].criticals[1].firemode&F.DESTROYED_MODE))
        check(w,'second intact and return-1',result==-1 and not u.sections[loc].criticals[1].firemode&F.DESTROYED_MODE)
        check(w,'unchanged and return-1',result==-1 and before==(slot.type,slot.data,slot.firemode,slot.weap_damage_flags))
        check(w,'refund5 internal5 electronics return-1',result==-1 and inv.find(1000,546)==inv.find(1000,545)==5)
        check(w,'refund0 return0',result==0 and not inv.raw(1000))
        check(w,'refund1 internal1 sensor0 life0 electronics return-1',result==-1 and [inv.find(1000,p) for p in (546,600,601,602)]==[1,1,0,0]);return True
    if operation=='CanScrapLoc':
        kind=int(re.search(r'type(\d+)',initial)[1]);jobs.schedule(kind,u,pack(7,loc),60)
        result=jobs.can_scrap_location(u,loc);check(w,'true under narrow source filter',result);check(w,'false',not result);return True
    if name not in ('removegun','removepart','removesection') and initial!='scheduled normal remove-section now internal6 frontarmor8':return False
    if 'gun' in initial or initial=='weapon slot':gun(w,2,loc=loc)
    else:slot.type=i2special(Special.ENDO_STEEL if 'Endosteel' in initial else Special.CASE)
    if 'pending repair' in initial:jobs.schedule(53,u,pack(7,loc),60)
    if initial.startswith('Mech LT'):loc=2
    if initial.startswith('Mech CT'):
        loc=4
        for index in (0,1,2,3):destroy(u,index)
    sec=u.sections[loc]
    if 'frontarmor20' in initial:sec.armor=sec.armor_orig=20;sec.rear=sec.rear_orig=8
    w['streams']['tech_rolls']=[2,2] if 'both' in initial else [2,12] if 'first fail' in initial else [2] if initial.endswith('fail') else [12]
    if operation=='execute event':
        event=jobs.schedule(49,u,pack(7,loc,0,2),1);sec.internal=6;sec.armor=8;advance(w,1);w['error']=''
    else:
        command(w,name,{0:'LA',2:'LT',4:'CT'}[loc]+(' 1' if name!='removesection' else ''));event=w['result']
    err=w['error'];deadline=event.tick if event else 0;identity=source_id(slot.type)
    for label,fragment in [('refuse structural material','Structural'),('refuse use weapon removal','weapon'),('refuse outside-in path','outer'),('refuse head prerequisite','outer'),('refuse same part repair','repairing')]:check(w,label,fragment.lower() in err.lower() and not w['draws'] and not inv.raw(1000))
    match=re.search(r'advance(\d+)',operation)
    early=True
    if match and event:
        advance(w,int(match[1])-1);early=not slot.firemode&F.DESTROYED_MODE;advance(w,1)
    dead=bool(slot.firemode&F.DESTROYED_MODE);salvage=inv.find(1000,identity)
    check(w,'gun destroyed at4800 and salvage1',dead and salvage==1 and early and deadline==4800)
    check(w,'gun intact and salvage0 with normal-time fake',not dead and salvage==0 and bool(event) and event.repair_fake and deadline==4800)
    check(w,'part destroyed salvage1',dead and salvage==1 and deadline==2400)
    check(w,'part intact salvage0',not dead and salvage==0 and deadline==3600)
    counts=[inv.find(1000,p) for p in (546,547,545)]
    for label,values in [('detached salvage10 internal20 armor5 electronics',[10,20,5]),('detached salvage6 internal13 armor3 electronics',[6,13,3]),('salvage6 internal8 armor3 electronics from due state',[6,8,3])]:check(w,label,counts==values and u.is_section_destroyed(loc))
    return True
