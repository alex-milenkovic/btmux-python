"""Cargo commands and source weight/speed coupling on shared objects."""
from . import check,attempt,stock,U,M,S,F,Specials,Special,i2special,source_part
from entities.mech import CritStatus
from entities.crittypes import BOMB_BASE_INDEX
from systems.parts import set_cargo_weight,part_weight
from systems.vehicle_combat import correct_speed


def run(w,initial,operation):
    u=w['u'];inv=w['inventory'];actor=w['actor'];a=source_part('Ammo_IS.LRM-15')
    if operation.startswith(('loadcargo','unloadcargo')):
        u.status|=S.STARTED;u.specials|=Specials.CARGO_TECH;u.in_character=True;actor.location=u._id
        inv.put(1000,'MECHSKILLS','10 10 1');stock(w,546,5)
        if initial.startswith('shutdown'):u.status&=~S.STARTED
        if 'without CargoTech' in initial:u.specials&=~Specials.CARGO_TECH
        if 'speed0.1' in initial:u.speed=.1
        if 'speed-0.1' in initial:u.speed=-.1
        if 'moving IC' in initial:u.speed=5;stock(w,546,5,identity=10);stock(w,546,0)
        if 'wrong bay' in initial:inv.put(1000,'MECHSKILLS','5 5 '+('0' if 'flag0' in initial else '1'))
        if 'IC hangar' in initial:inv.put(1000,'in_character',True)
        if initial=='pilot outside unit':actor.location=1000
        if initial=='unit outside its map room':u.location=999
        selector='Internal';count=operation.split()[-1]
        b=source_part('Ammo_IS.SRM-6')
        if initial.startswith('store itemA'):
            selector='Ammo*';stock(w,a,2);stock(w,b,5)
        if initial.startswith('store21'):
            selector='R*'
            for entry in inv.matching(selector):stock(w,entry.source_part_id,1,entry.brand)
        if 'one numeric token' in initial:inv.put(1000,'MECHSKILLS','5')
        if 'matches no items' in initial:selector='Missing';u.carried_cargo=12345
        before=(inv.raw(10),inv.raw(1000));result=attempt(w,w['cargo'].command,actor,u,operation.split()[0],selector+' '+count);err=w['error']
        check(w,'unit plus3 store minus3',inv.find(10,546)==3 and inv.find(1000,546)==2)
        check(w,'unit minus3 store plus3',inv.find(10,546)==2 and inv.find(1000,546)==3)
        for label,fragment in [('refuse shared started gate','online'),('refuse CargoTech','cargo'),('refuse movement','moving'),('refuse IC hangar','hangar'),('refuse actor location',"ain't in your"),('refuse hangar relationship',"ain't in hangar")]:check(w,label,fragment.lower() in err.lower() and before==(inv.raw(10),inv.raw(1000)))
        check(w,'refuse and reveal required coordinates','5,5' in err and before==(inv.raw(10),inv.raw(1000)))
        check(w,'refuse without coordinates',bool(err) and '5,5' not in err and before==(inv.raw(10),inv.raw(1000)))
        check(w,'transfer A2 B4 independently',[inv.find(10,p) for p in (a,b)]==[2,4] and [inv.find(1000,p) for p in (a,b)]==[0,1])
        check(w,'all21 transfer without admin match cap',len(result or [])==21 and all(r['count']==1 for r in result))
        check(w,'no bay-coordinate restriction',not err and inv.find(10,546)==1)
        check(w,'nothing matching and correct-speed refresh still occurs',bool(err) and u.carried_cargo==0);return True
    if operation.startswith('correct speed'):
        u.max_speed=60;u.tonnage=20;u.measured_mass=20480;u.specials|=Specials.CARGO_TECH
        if 'desired-50' in initial:
            u.speed=u.desired_speed=-50;correct_speed(u);check(w,'actual-40 desired-40 using reverse two-thirds',u.speed==u.desired_speed==-40)
        else:
            u.speed=u.desired_speed=55;stock(w,a,10,identity=10);correct_speed(u);first=(u.speed,u.desired_speed);correct_speed(u)
            check(w,'first speeds55 second speeds40',first==(55,55) and (u.speed,u.desired_speed)==(40,40))
        return True
    if operation!='refresh cargo weight':return False
    u.fuel_orig=u.fuel=u.fuel_max=100
    flying=initial.startswith('flying');u.unit_type=U.AERO if flying else U.MECH
    tank=i2special(Special.FUELTANK);slot=u.sections[0].criticals[0]
    if 'mounted fuel tank1' in initial:slot.type=tank
    if 'destroyed mounted' in initial:slot.firemode=F.DESTROYED_MODE
    if 'stored tank2' in initial:stock(w,tank,2,identity=10)
    if 'brands1 and2' in initial:inv.set_raw(10,f'[{a},1,1],[{a},2,1]');u.crit_status|=CritStatus.LOAD_OK
    if 'backing section7' in initial:slot=u.sections[7].criticals[11];slot.type=BOMB_BASE_INDEX;slot.firemode=F.DESTROYED_MODE
    if initial.startswith('stored bomb'):stock(w,BOMB_BASE_INDEX,2,identity=10)
    if 'current150' in initial:u.fuel=150
    if 'current90' in initial:u.fuel=90
    mass=set_cargo_weight(u)
    check(w,'mass2 tons regardless brands and LOAD_OK cleared',mass==2048 and not u.crit_status&CritStatus.LOAD_OK)
    check(w,'max fuel original plus6000',u.fuel_max==6100)
    check(w,'max fuel original plus2000',u.fuel_max==2100)
    check(w,'no mounted tank capacity addition',mass==0 and u.fuel_max==100)
    check(w,'bomb mass included',mass==part_weight(BOMB_BASE_INDEX)>0)
    check(w,'source bomb weight times8 mass units',mass==part_weight(BOMB_BASE_INDEX)*8)
    check(w,'excess50 raw mass added',mass==50)
    check(w,'no excess-fuel mass',mass==0);return True
