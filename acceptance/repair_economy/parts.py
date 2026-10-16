"""Equipment maintenance through the real command and event queue."""
import re
from core.events import SOURCE_EVENT_IDS
from . import check,command,stock,gun,advance,F,C,Special,i2special,i2ammo,get_weapon,source_id
from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke


def run(w,initial,operation):
    name=operation.split()[0]
    if name not in ('replacepart','replacegun','repairpart','repairgun','fixenhcrit'):return False
    u=w['u'];sec=u.sections[4];slot=sec.criticals[0];width=2
    weapon=None;arg='CT 1'
    if 'nonweapon' in initial or 'broken part' in initial:slot.type=i2special(Special.CASE)
    elif 'broken ammo' in initial:slot.type=i2ammo(get_weapon('IS.LRM-15').index)
    else:
        match=re.search(r'width(\d+)',initial);width=int(match[1]) if match else 3 if 'middle' in initial else 2
        weapon=gun(w,width)
    if initial.startswith('broken') or 'broken part' in initial:slot.firemode=F.BROKEN_MODE
    if initial.startswith('selected destroyed') or 'nonweapon destroyed' in initial:slot.firemode=F.DESTROYED_MODE
    if 'second destroyed' in initial:sec.criticals[1].firemode=F.DESTROYED_MODE
    if 'BROKEN only' in initial:slot.firemode=F.BROKEN_MODE
    if 'disabled' in initial:slot.firemode|=F.DISABLED_MODE
    if 'tempnuke1' in initial:set_part_temp_nuke(slot,1)
    if 'middle' in initial:
        arg='CT 2'
        if 'damaged middle' in initial:
            for index in (1,2):sec.criticals[index].firemode=F.DAMAGED_MODE;sec.criticals[index].weap_damage_flags=1
            set_part_temp_nuke(slot,1)
    if 'second slot selected' in initial:arg='CT 2';sec.criticals[1].firemode=F.BROKEN_MODE
    if 'flooded' in initial:sec.config|=C.SECTION_FLOODED
    amount=0 if 'stock0' in initial else 2
    brand=0
    if 'oldbrand1' in initial:
        slot.brand=1;brand=2
        entry=w['inventory'].catalog.entries[source_id(slot.type),2];arg+=' '+entry.long
    stock(w,source_id(slot.type),amount,brand)
    electric=3 if 'stock3 each' in initial or 'electronics3' in initial else 1
    stock(w,545,electric);stock(w,546,0 if 'internal0' in initial else electric)
    rolls=[2,2] if 'both rolls fail' in initial else [2,12] if 'recovery success' in initial else [2] if re.search(r'\bfail\b',initial) else [12]
    w['streams']['tech_rolls']=rolls
    before=w['inventory'].raw(1000);command(w,name,arg);event=w['result'];err=w['error'];queued=w['jobs'].events()
    count=w['inventory'].find(1000,source_id(slot.type),brand)
    unchanged=bool(slot.firemode&F.BROKEN_MODE)
    deadline=event.tick if event else 0;callback=event.repair_callback if event else None
    check(w,'refuse stock but slot brand2 remains','stock' in err and slot.brand==2)
    check(w,'stock1 slot brand1 until event',count==1 and slot.brand==1 and unchanged and bool(event))
    for key,fragment in [('refuse functional without dice or stock change','functional'),('refuse not mount first','first'),('refuse flooded without resource debit','flooded'),('refuse no applicable temporary damage','temporary'),('refuse disabled','disabled'),('refuse short destroyed weapon','gone'),('refuse both destroyed','gone'),('refuse destroyed part','destroyed'),('refuse nonweapon','gun'),('refuse no enhanced damage','enhanced')]:
        check(w,key,fragment.lower() in err.lower() and not w['draws'] and w['inventory'].raw(1000)==before)
    check(w,'refuse missing internal and retain electronics1','stock' in err and w['inventory'].find(1000,545)==1)
    check(w,'debit3 each and queue extra-hard repair',bool(event) and not event.repair_fake and w['inventory'].find(1000,545)==w['inventory'].find(1000,546)==0 and w['tech'].rolls[-1]['difficulty']>=2)
    check(w,'debit3 each destroy second slot now and fake1800',bool(event) and event.repair_fake and deadline==1800 and bool(sec.criticals[1].firemode&F.DESTROYED_MODE) and w['inventory'].find(1000,545)==w['inventory'].find(1000,546)==0)
    before_due=False
    match=re.search(r'advance(\d+)',operation)
    if event and (match or operation.endswith('at due')):
        due=int(match[1]) if match else deadline
        advance(w,due-1);before_due=bool(slot.firemode&F.BROKEN_MODE) if name.startswith('replace') else part_temp_nuke(slot)>0
        advance(w,1)
    functional=not slot.firemode&(F.BROKEN_MODE|F.DESTROYED_MODE) and not part_temp_nuke(slot)
    both=functional and not sec.criticals[1].firemode&(F.BROKEN_MODE|F.DESTROYED_MODE)
    check(w,'stock1 part repaired at2700 not2699',deadline==2700 and before_due and functional and count==1)
    check(w,'stock2 part unchanged and fake consumed',count==2 and deadline==4020 and bool(slot.firemode&F.BROKEN_MODE) and not w['jobs'].events())
    check(w,'stock1 part unchanged and fake consumed',count==1 and deadline==4020 and bool(slot.firemode&F.BROKEN_MODE) and not w['jobs'].events())
    check(w,'ammo repaired data0 and no negative stored entry',functional and slot.data==0 and count==0)
    check(w,'stock1 both slots repaired only at7200',count==1 and before_due and deadline==7200 and both)
    check(w,'stock2 both slots unchanged',count==2 and deadline==10800 and unchanged and bool(slot.firemode&F.BROKEN_MODE))
    check(w,'stock1 both slots unchanged',count==1 and deadline==10800 and unchanged and bool(slot.firemode&F.BROKEN_MODE))
    check(w,'slot brand2 and repaired',slot.brand==2 and functional)
    check(w,'both slots repaired using live callback under source type53',bool(event) and SOURCE_EVENT_IDS[event.event_type]==53 and callback=='repairgun' and deadline==1200 and before_due and both)
    check(w,'selected slot repaired at900',deadline==900 and before_due and functional)
    check(w,'stock consumed and slot unchanged',deadline==1320 and part_temp_nuke(slot)==1 and w['inventory'].find(1000,545)==w['inventory'].find(1000,546)==0)
    check(w,'middle damage cleared first tempnuke0 other damage retained',not sec.criticals[1].firemode&F.DAMAGED_MODE and sec.criticals[1].weap_damage_flags==0 and part_temp_nuke(slot)==0 and bool(sec.criticals[2].firemode&F.DAMAGED_MODE))
    return True
