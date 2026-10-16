"""Damage/salvage ordering, displays, and numbered command dispatch."""
from . import check,attempt,stock,gun,U,F,C,Special,i2special,i2ammo,get_weapon,source_id
from .structure import destroy
from systems.repair_reports import *
from systems.enhanced_crits import set_part_temp_nuke
from systems.technician import pack


def run(w,initial,operation):
    if operation not in ('damages','build damage table diagnostic','scrap table','damage report','damage report CT','machine report','human report') and not operation.startswith('fix '):return False
    u=w['u'];sec=u.sections[4];slot=sec.criticals[0];jobs=w['jobs'];reports=w['reports'];inv=w['inventory']
    if 'CT destroyed' in initial:destroy(u,4);u.sections[0].armor=5
    if 'CT flooded' in initial:sec.config|=C.SECTION_FLOODED;u.sections[0].armor=5
    if 'LT destroyed' in initial:destroy(u,2);u.sections[0].armor=u.sections[3].armor=5
    if initial.startswith('Mech CT internal'):
        sec.internal=8 if 'internal8' in initial else 10;sec.armor=5;sec.rear=3;sec.rear_orig=5
    if initial.startswith('BA'):u.unit_type=U.BSUIT;destroy(u,0)
    if initial.startswith('pristine ground'):u.unit_type=U.VEH_GROUND
    if 'ammo' in initial:
        loc=1 if initial.startswith('unfixable') else 4;slot=u.sections[loc].criticals[0];slot.type=i2ammo(get_weapon('CL.ATM-6').index);slot.data=8
        if 'partial broken' in initial:slot.firemode=F.BROKEN_MODE
    if initial.startswith('gun enhanced'):
        gun(w,2);slot.firemode=F.DAMAGED_MODE;slot.weap_damage_flags=2|4 if 'focus' in initial else 4|8
    if initial.startswith(('undestroyed gun','destroyed gun')):
        gun(w,2)
        if initial.startswith('destroyed'):slot.firemode=F.DESTROYED_MODE
        else:set_part_temp_nuke(slot,1)
    if initial.startswith('weapon width'):
        first,second=(1,6) if initial.startswith('weapon width1') else (6,1)
        gun(w,first);gun(w,second,pos=first)
        set_part_temp_nuke(slot,1);set_part_temp_nuke(sec.criticals[first],1)
    if initial=='three snapshot rows':
        for loc in (4,2,3):u.sections[loc].armor=8
        stock(w,547,6)
    if initial.startswith('three damage rows'):
        sec.armor=8;stock(w,547,2)
        for pos,kind in ((0,Special.SHOULDER_OR_HIP),(1,Special.HEAT_SINK)):
            sec.criticals[pos].type=i2special(kind);sec.criticals[pos].firemode=F.BROKEN_MODE
        stock(w,i2special(Special.HEAT_SINK),1)
    if initial.startswith('unfixable') or 'on scrap list' in initial:
        destroy(u,4)
        if initial.startswith('unfixable'):
            slot=u.sections[1].criticals[0]
            if 'removable part' in initial or 'broken part' in initial:slot.type=i2special(Special.CASE)
            if 'broken part' in initial:slot.firemode=F.BROKEN_MODE
            if 'pending section' in initial:
                jobs.schedule(49,u,pack(7,1,0,2),60);u.sections[3].criticals[0].type=i2special(Special.CASE)
            if 'queued reload' in initial:jobs.schedule(46,u,pack(7,1),60)
        else:
            # Keep the ammo in a live limb that the source scrap traversal visits.
            u.sections[1].criticals[0].type=slot.type;u.sections[1].criticals[0].data=8;slot.type=0
    if initial.startswith(('front armor repair','rear armor repair')):
        sec.armor=8;sec.rear=3;sec.rear_orig=5
        jobs.schedule(47,u,7*65536+(12 if initial.startswith('rear') else 4)+2*16,180)
    if initial.startswith('fake part'):
        slot.type=i2special(Special.CASE);slot.firemode=F.BROKEN_MODE;jobs.schedule(43,u,pack(7,4),60,fake=True)
    w['streams']['tech_rolls']=[12]*3
    if operation.startswith('fix '):
        result=attempt(w,reports.fix,w['actor'],u,operation[4:]);err=w['error'];events=jobs.events()
        check(w,'no dispatch and no work',result==[] and not events and not w['draws'])
        check(w,'invalid low and no work','low' in err and not events and not w['draws'])
        check(w,'invalid high and no work','high' in err and not events and not w['draws'])
        check(w,'dispatch second row once',len(result or [])==1 and result[0]['number']==2 and len(events)==1 and events[0].data2%16==2)
        check(w,'first and third jobs queued second refuses stock with original indices',len(result or [])==3 and [r['number'] for r in result]==[1,2,3] and 'stock' in result[1]['error'] and result[0]['error']==result[2]['error']==None and len(events)==2);return True
    rows=reports.damage_table(u) if operation=='build damage table diagnostic' else reports.scrap_table(u) if operation=='scrap table' else reports.table(u)
    human=reports.human(w['actor'],u);machine=reports.machine(u);w['result']=dict(rows=rows,human=human,machine=machine)
    check(w,'CT reattach only',rows==[(0,4,0)])
    check(w,'scrap plan instead of CT reattachment',rows==reports.scrap_table(u) and rows and (0,4,0) not in rows)
    check(w,'CT reseal only',rows==[(19,4,0)])
    check(w,'LT reattach then RT work with LA suppressed',rows==[(0,2,0),(12,3,5)])
    check(w,'internal2 only before part rows',rows==[(14,4,2)])
    check(w,'front5 then rear2 before part rows',rows==[(12,4,5),(13,4,2)])
    check(w,'replace-suit row',rows==[(20,0,0)])
    check(w,'reload row before part replacement row',rows==[(11,4,0),(1,4,0)])
    check(w,'focus row only for that critical',rows==[(4,4,0)])
    check(w,'crystal row only for that critical',rows==[(5,4,0)])
    check(w,'temporary gun repair row and skip second slot',rows==[(2,4,0)])
    check(w,'gun replacement row and skip second slot',rows==[(10,4,0)])
    for noun in ('mech','unit'):check(w,'pristine '+noun+' message and empty machine list',not rows and machine=='' and bool(w['tech'].messages) and 'pristine '+noun in w['tech'].messages[-1]['text'].lower())
    check(w,'RA part removal before any RT traversal',bool(rows) and rows[0]==(16,1,0) and not any(r[1]==3 for r in rows))
    check(w,'RA detach row then RT traversal',rows[:2]==[(15,1,0),(16,3,0)])
    check(w,'skip broken part and offer detach',bool(rows) and rows[0]==(15,1,0) and not any(r[0]==16 for r in rows))
    check(w,'unload row and no detach',bool(rows) and rows[0]==(18,1,0) and (15,1,0) not in rows)
    check(w,'unload row and detach when path clear',rows[:2]==[(18,1,0),(15,1,0)])
    check(w,'front row in-progress with N/A time and BTH',bool(human) and human[0]['in_progress']==1 and human[0]['minutes']==human[0]['bth']==None)
    check(w,'rear row in-progress front row not marked',len(human)==2 and not human[0]['in_progress'] and human[1]['in_progress']==1)
    check(w,'part row in-progress despite no eventual repair',len(human)==1 and human[0]['in_progress']==1)
    check(w,'reload data name:2 and in-progress0',len(rows)==1 and rows[0][0]==11 and machine.endswith(':2|0'))
    check(w,'unload data name:8 and in-progress0',any(r[0]==18 for r in rows) and any('|18|' in s and s.endswith(':8|0') for s in machine.split(',')))
    check(w,'second temporary BTH retains extra_hard0 from first',len(human)==2 and [r['bth'] for r in human]==[9,11])
    check(w,'first temporary BTH uses extra_hard1 then second0',len(human)==2 and [r['bth'] for r in human]==[12,9])
    return True
