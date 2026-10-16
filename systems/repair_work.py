# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.tech.commands.c
#   btech/mech.tech.do.c
#   btech/mech.tech.repairs.c

"""Repair commands and resource/failure helpers against live units and stores."""
from core.randomness import draw,number
from entities.mech import UnitType as U,FireMode as F,AmmoMode as A,SectionConfig as C,Specials as S,Location as L
from entities.crittypes import is_weapon,is_ammo,weapon2i
from entities.weapon import get_weapon_by_index
from data.construction_catalog import source_id
from systems import repairs
from systems.damage import unit_is_fixable
from systems.combat import part_is_nonfunctional
from systems.combat_ammunition import full_ammo
from systems.enhanced_crits import part_temp_nuke
from systems.parts import proper_armor,proper_internal
from systems.economic_inventory import is_crap
from systems.technician import parse_part,parse_gun,valid_gun_position,weapon_difficulty,variable_minutes,pack,divide
from systems.repair_materials import valid_ammo_mode,find_ammo_type,repair_alias
from systems.repair_jobs import destroy_part
from systems.weapon_inventory import weapon_crits


def require(condition,message):
    if not condition:raise ValueError(message)


def invalid_repair_path(unit,loc):
    if unit.unit_type!=U.MECH:return False
    parent={L.HEAD:L.CTORSO,L.LTORSO:L.CTORSO,L.RTORSO:L.CTORSO,L.LARM:L.LTORSO,L.RARM:L.RTORSO,L.LLEG:L.CTORSO,L.RLEG:L.CTORSO}.get(loc)
    return parent is not None and unit.is_section_destroyed(parent)


def invalid_scrap_path(unit,loc):
    if loc<0 or unit.unit_type!=U.MECH:return False
    children={L.CTORSO:(L.HEAD,L.LTORSO,L.RTORSO),L.LTORSO:(L.LARM,),L.RTORSO:(L.RARM,)}.get(loc,())
    return any(not unit.is_section_destroyed(child) or invalid_scrap_path(unit,child) for child in children)


class RepairWork:
    def __init__(self,jobs):self.jobs=jobs;self.tech=jobs.tech;self.inventory=jobs.inventory

    def costs(self,name,unit,loc,pos=0,amount=0):
        slot=unit.sections[loc%8].criticals[pos];brand=slot.brand&15
        # Ordinary repair keeps unsized materials when core diagnostics are enabled.
        internal=source_id(proper_internal(unit, complexrepair=False));electric=545
        if name=='replace_econ':return [] if is_ammo(slot.type) else [(repair_alias(unit,source_id(slot.type)),brand,1)]
        if name=='reload_econ':return [(repair_alias(unit,find_ammo_type(unit,loc,pos)),brand,1)]
        if name=='fixarmor_econ':return [(source_id(proper_armor(unit)),0,amount)]
        if name=='fixinternal_econ':return [(internal,0,amount)]
        if name=='repair_econ':
            count=3 if slot.firemode&F.DESTROYED_MODE else 1
            return [] if is_ammo(slot.type) else [(electric,0,count),(internal,0,count)]
        if name=='repairenhcrit_econ':return [(electric,0,1)]
        if name in ('reattach_econ','reseal_econ'):
            count=unit.sections[loc].internal_orig
            return [(internal,0,count),(electric,0,count)]
        if name=='replacesuit_econ':return [(internal,0,10),(600,0,2),(601,0,2),(602,0,10)]
        raise ValueError('Unsupported repair resource helper')

    def check_stock(self,unit,costs,*,reattach=False):
        store=self.jobs.store_for(unit)
        require(store in self.inventory.records,'Repair store unavailable')
        for part,brand,count in costs:
            available=self.inventory.find(store,part,brand)
            label=self.inventory.part_name(part,brand)
            message=(f"Not enough {'Electrics' if part==545 else label+'s'} in stock. You need {count-available} more."
                     if reattach else f'Not enough units of {label} in store.')
            require(available>=count,message)

    def economy(self,name,unit,loc,pos=0,amount=0):
        self.inventory.consume(self.jobs.store_for(unit),self.costs(name,unit,loc,pos,amount));return 0

    def success(self,name):
        require(name in ('replacep_succ','replaceg_succ','reload_succ','fixinternal_succ','fixarmor_succ','reattach_succ','reseal_succ','replacesuit_succ','repairg_succ','repairenhcrit_succ','repairp_succ'),'Unknown repair success helper')
        return 0

    def failure(self,name,actor,unit,loc,pos=0,amount=0):
        if name=='replaceg_fail':
            label='weapon' if is_weapon(unit.sections[loc].criticals[pos].type) else 'part'
            if self.tech.roll(actor,unit,1)<0:
                self.tech.notice(actor,f'You muck around, wasting the {label} in the progress.')
            else:
                self.tech.notice(actor,f'Despite messing the repair, you manage not to waste the {label}.')
                self.jobs.credit_slot(unit,loc,pos)
            return -1
        if name in ('replacep_fail','reload_fail','repairenhcrit_fail'):
            message={'replacep_fail':'Your repair fails.. all the parts are wasted for good.',
                     'reload_fail':'You fumble around, wasting the ammo in the progress.',
                     'repairenhcrit_fail':"You don't manage to repair the damage."}[name]
            self.tech.notice(actor,message);return -1
        if name in ('repairg_fail','repairp_fail'):
            slot=unit.sections[loc].criticals[pos]
            if slot.firemode&F.DESTROYED_MODE and is_weapon(slot.type) and weapon_crits(unit,weapon2i(slot.type))>4:
                require(pos+1<12,'Invalid adjacent weapon critical');destroy_part(unit.sections[loc].criticals[pos+1])
                self.tech.notice(actor,'You muck around, trashing the gun in the process.')
            else:self.tech.notice(actor,'Your repair fails.. all the parts are wasted for good.')
            return -1
        if name in ('fixarmor_fail','fixinternal_fail'):
            recovery=50 if self.tech.roll(actor,unit,1)>=0 else 0
            percent=recovery+draw('repair_percent',5,44,lambda:number(5,44))
            actual=divide(percent*amount,100)
            if actual==0:actual=1
            if actual==amount:actual=amount-1
            label='armor' if name=='fixarmor_fail' else 'internal'
            self.tech.notice(actor,f"Your {label} patching isn't exactly perfect.. You managed to fix {actual} out of {amount}.")
            return actual
        require(name in ('reattach_fail','reseal_fail','replacesuit_fail'),'Unknown repair failure helper')
        if self.tech.roll(actor,unit,0 if name=='reseal_fail' else 3)>=0:return 0
        percent=draw('repair_percent',5,94,lambda:number(5,94))
        message=(f"You don't manage to get all the water out and seal the section, though you recover {percent}% of the materials."
                 if name=='reseal_fail' else f'Despite your disastrous failure, you recover {percent}% of the materials.')
        self.tech.notice(actor,message)
        internal=source_id(proper_internal(unit, complexrepair=False));store=self.jobs.store_for(unit)
        if name=='replacesuit_fail':refunds=((600,max(2*percent//100,1)),(601,2*percent//100),(602,10*percent//100),(internal,max(10*percent//100,1)))
        else:
            original=unit.sections[loc].internal_orig;amount=divide(original*percent,100)
            if amount==0:amount=1
            if amount==original:amount=original-1
            refunds=((545,amount),(internal,amount))
        for part,count in refunds:self.inventory.change(store,part,0,count)
        return -1

    def start(self,actor,unit,kind,loc,pos=0,extra=0,*,minutes,fake=False,callback=None,explicit=False,amount=None):
        payload=pack(actor._id,loc,pos,extra) if amount is None else actor._id*65536+loc+amount*16
        seconds=self.tech.add_time(actor,minutes)
        if explicit:seconds=self.tech.pending(actor)*60
        if amount is not None and amount>0:seconds-=(amount-1)*(180 if kind==47 else 540)
        return self.jobs.schedule(kind,unit,payload,seconds,fake=fake,callback=callback)

    def variable(self,minutes,margin):
        config=self.tech.config
        return variable_minutes(minutes,margin,bool(config.variabletechtime),config.techtime_mod)

    def command(self,actor,unit,name,argument=''):
        name=name.lower().removeprefix('tech_')
        if name=='checkstatus':
            remaining=self.jobs.latest(unit)
            from systems.characters import duration
            self.tech.notice(actor,"The mech's ready to rock!" if not remaining else f"The 'mech has approximately {duration(self.tech.lagged(remaining))} until done.")
            return dict(ready=not remaining,seconds=remaining)
        if name in ('magic','fixextra'):
            require(getattr(actor,'wizard',False) or getattr(actor,'god',False) or actor._id==1,"Sorry, that command is restricted!")
        if name=='toggletype':require(getattr(actor,'wizard',False) or not unit.in_character,'This command only works in simpods!')
        else:self.tech.gate(actor,unit,'D' if name in ('reload','unload','fixarmor','repairs','checkstatus') else 'C')
        if name=='repairs':return self.jobs.show_report(actor,unit)
        if name=='fixextra':
            self.tech.notice(actor,'Fixed extra stuff - reseals, ammo feeds, etc.')
            return repairs.fixextra(unit)
        if name=='magic':
            from systems.construction_weight import internal_check
            self.tech.notice(actor,'Doing the magic..')
            result=repairs.magic(unit);internal_check(unit,True)
            self.tech.notice(actor,'Done!');return result
        if name in ('removegun','replacegun','repairgun','fixenhcrit'):
            error,loc,pos,extra=parse_gun(unit,argument,self.inventory.catalog,brand=name=='replacegun')
        else:
            position=name not in ('fixarmor','fixinternal','removesection','reattach','reseal','replacesuit')
            error,loc,pos,extra=parse_part(unit,argument,position=position,extra=name in ('reload','toggletype'),rear=name=='fixarmor')
        if error<0:
            messages={-1:'Invalid gun #!',-2:'Invalid object to replace with!',-3:'Invalid object type - not matching with original.',-4:'Invalid gun location - subscript out of range.'} if name in ('removegun','replacegun','repairgun','fixenhcrit') else {-1:'Invalid section!',-2:'Invalid part!'}
            raise ValueError(messages[error])
        if name in ('fixarmor','fixinternal'):return self.points(actor,unit,name,loc)
        if name in ('removesection','reattach','reseal','replacesuit'):return self.structure(actor,unit,name,loc)
        slot=unit.sections[loc].criticals[pos];kind=slot.type
        full=self.validate_slot(unit,name,loc,pos)
        if name=='toggletype':
            require(extra,'You need to give a type to toggle to (use - for normal)')
            mode=valid_ammo_mode(unit,loc,pos,extra);require(mode>=0,'That is invalid ammo type for this weapon!')
            slot.ammomode=(slot.ammomode&~int(A.AMMO_MODES))|mode;slot.data=full_ammo(unit,loc,pos)
            from systems.notifications import mech_notify,MECHALL
            mech_notify(unit,MECHALL,'Ammo toggled.');return
        if name=='reload' and extra:
            mode=valid_ammo_mode(unit,loc,pos,extra);require(mode>=0,'That is invalid ammo type for this weapon!')
            slot.data=0;slot.ammomode=(slot.ammomode&~int(A.AMMO_MODES))|mode
        self.tech.fatigue(actor)
        if name in ('replacegun','replacepart'):return self.replace(actor,unit,name,loc,pos,extra)
        if name in ('removegun','removepart'):
            gun=name=='removegun';label='gun' if gun else 'part';failure=False
            if not gun:self.tech.notice(actor,'You start removing the part..')
            if self.tech.roll(actor,unit,int(gun),weapons=gun)<0:
                self.tech.notice(actor,f'Ack! Your attempt is far from perfect, you try to recover the {label}..')
                failure=self.tech.roll(actor,unit,int(gun),weapons=gun)<0
                if failure:self.tech.notice(actor,'No good. Consider the part gone.')
            if gun and not failure:self.tech.notice(actor,'You start removing the gun..')
            width=weapon_crits(unit,weapon2i(kind)) if gun else 1
            width=max(1,width//2) if gun and unit.specials&S.CLAN_TECH else max(1,width)
            mod=3 if failure and not gun else 2
            return self.start(actor,unit,51 if gun else 50,loc,pos,mod,minutes=40*width*mod//2,fake=failure)
        if name=='unload':
            failed=self.tech.roll(actor,unit,2)<0
            self.tech.notice(actor,'You start unloading the ammo compartment..')
            return self.start(actor,unit,46,loc,pos,2 if slot.data==full else 1,minutes=15 if failed else 10)
        resources='reload_econ' if name=='reload' else 'repairenhcrit_econ' if name=='fixenhcrit' else 'repair_econ'
        self.economy(resources,unit,loc,pos)
        self.tech.notice(actor,{'reload':'You start reloading the ammo compartment..','repairpart':'You start repairing the part..','repairgun':'You start repairing the weapon..','fixenhcrit':'You start repairing the weapon...'}[name])
        difficulty=1 if name in ('reload','repairpart') else 0
        if name=='repairgun':difficulty=weapon_difficulty(get_weapon_by_index(weapon2i(kind)))+bool(slot.firemode&F.DESTROYED_MODE)
        failed=self.tech.roll(actor,unit,difficulty,weapons=name in ('repairgun','fixenhcrit'))<0
        if failed:self.failure({'reload':'reload_fail','repairpart':'repairp_fail','repairgun':'repairg_fail','fixenhcrit':'repairenhcrit_fail'}[name],actor,unit,loc,pos)
        duration={'reload':10,'repairpart':15,'repairgun':20,'fixenhcrit':15}[name]
        return self.start(actor,unit,46 if name=='reload' else 58 if name=='fixenhcrit' else 53,loc,pos,minutes=duration*(3 if failed else 2)//2,fake=failed,callback='repairgun' if name=='repairgun' else None)

    def validate_slot(self,unit,name,loc,pos):
        """Command-specific predicate order from the active C bodies."""
        slot=unit.sections[loc].criticals[pos];kind=slot.type
        checks={
            'empty':(lambda:bool(kind),'That location is empty!'),
            'section':(lambda:not unit.is_section_destroyed(loc),"That part's blown off! Use reattach first!"),
            'flood':(lambda:not unit.sections[loc].config&C.SECTION_FLOODED,"That location has been flooded! Use reseal first!"),
            'weapon':(lambda:is_weapon(kind),"That's no gun!"),
            'nonweapon':(lambda:not is_weapon(kind),'Use weapon maintenance command'),
            'ammo':(lambda:is_ammo(kind),"That's no ammo!"),
            'intact':(lambda:not slot.firemode&F.DESTROYED_MODE,'That part is destroyed!'),
            'enabled':(lambda:not slot.firemode&F.DISABLED_MODE,'That part is disabled!'),
            'functional':(lambda:not part_is_nonfunctional(unit,loc,pos),'Ammo compartment is nonfunctional!'),
            'replacement':(lambda:part_is_nonfunctional(unit,loc,pos),'That part is functional!'),
            'material':(lambda:not is_crap(source_id(kind)),'Structural material cannot be repaired or removed'),
            'first':(lambda:valid_gun_position(unit,loc,pos),'Select the mount first critical'),
            'repair':(lambda:not self.jobs.repairing(unit,loc,pos),'Someone is repairing that part'),
            'scrap':(lambda:not self.jobs.scrapping_part(unit,loc,pos),'Someone is scrapping that part'),
            'scrapsection':(lambda:not self.jobs.count(unit,49,loc),"Someone's scrapping that section - no repairs are possible!"),
            'temporary':(lambda:bool(part_temp_nuke(slot)),'No applicable temporary damage'),
            'enhanced':(lambda:bool(slot.firemode&F.DAMAGED_MODE),'No enhanced damage'),
            'notfull':(lambda:slot.data!=full_ammo(unit,loc,pos),'Ammo compartment is full'),
            'notempty':(lambda:bool(slot.data),'Ammo compartment is empty'),
        }
        orders={
            'removegun':'section weapon intact first scrap repair scrapsection',
            'removepart':'empty section nonweapon intact material scrap scrapsection repair',
            'replacegun':'section flood repair weapon first replacement scrapsection',
            'repairgun':'section flood repair weapon first scrap scrapsection enabled',
            'fixenhcrit':'section flood repair weapon scrap scrapsection enabled enhanced',
            'replacepart':'empty replacement material nonweapon section flood repair scrapsection',
            'repairpart':'empty intact enabled temporary material nonweapon section flood repair scrapsection',
            'toggletype':'ammo functional enabled',
            'reload':'ammo functional enabled notfull repair section flood scrapsection',
            'unload':'ammo functional enabled notempty repair section flood scrapsection',
        }
        require(name in orders,'Unknown repair command')
        for key in orders[name].split():
            condition,message=checks[key]
            defaults={
                'section':"That part's blown off! Use reattach first!",
                'flood':"That location has been flooded! Use reseal first!",
                'repair':"Someone's repairing that part already!",
                'scrap':"Someone's scrapping it already!",
                'scrapsection':"Someone's scrapping that section - no repairs are possible!",
                'replacement':"That gun isn't hurtin'!" if name=='replacegun' else "That part looks ok to me..",
                'material':"That part isn't hurtin'!",
                'temporary':"That part isn't hurtin'!",
                'enabled':"That gun can't be fixed yet!" if name in ('repairgun','fixenhcrit') else "That part can't be repaired yet!",
                'intact':"That part is gone for good!",
                'enhanced':"That gun isn't damaged!",
                'first':f"You can't {name.removesuffix('gun')} middle of a gun!",
                'nonweapon':f"That's a weapon! Use {'replacegun' if name=='replacepart' else 'repairgun'} instead.",
            }
            if name in ('removegun','removepart'):
                defaults.update(section=f"That part's blown off! You can assume the {'gun' if name=='removegun' else 'part'}'s gone too!",
                    intact=f"That {'gun' if name=='removegun' else 'part'}'s gone already!",
                    material="That type isn't scrappable!",nonweapon="That's a gun - use removegun instead!",
                    repair="Someone's tinkering with it already!",
                    scrapsection="Someone's scrapping that section - no additional removals are possible!")
            if name in ('reload','unload','toggletype'):
                defaults.update(functional="The ammo compartment is destroyed ; repair/replacepart it first.",
                    enabled="The ammo compartment is disabled ; repair/replacepart it first.",
                    notfull="That particular ammo compartment doesn't need reloading.",
                    notempty="That particular ammo compartment is empty already.",
                    repair="Someone's playing with that part already!")
                if name=='toggletype':defaults.update(functional="The ammo compartment is nonfunctional!",enabled="The ammo compartment is nonfunctional!")
            require(condition(),defaults.get(key,message))
        if name=='repairgun':
            if slot.firemode&F.DESTROYED_MODE:
                require(weapon_crits(unit,weapon2i(kind))>=5 and pos+1<12 and not unit.sections[loc].criticals[pos+1].firemode&F.DESTROYED_MODE,'That gun is gone for good!')
            else:require(part_temp_nuke(slot),"That gun isn't hurtin'!")
        return full_ammo(unit,loc,pos) if name in ('reload','unload','toggletype') else None

    def saving_notice(self,actor,base,minutes):
        saved=base-minutes
        if saved:self.tech.notice(actor,f"Your skill manages to save {saved} minute"+('!' if saved==1 else 's!'))

    def replace(self,actor,unit,name,loc,pos,brand):
        slot=unit.sections[loc].criticals[pos];gun=name=='replacegun';old=slot.brand&15
        if gun and brand:slot.brand=(slot.brand&~15)|(brand&15)
        part=source_id(slot.type) if gun else repair_alias(unit,source_id(slot.type));store=self.jobs.store_for(unit)
        if not is_ammo(slot.type):self.check_stock(unit,[(part,slot.brand&15,1)])
        label='gun' if gun else 'part'
        self.tech.notice(actor,f'You start replacing the {label}...')
        difficulty=1+weapon_difficulty(get_weapon_by_index(weapon2i(slot.type))) if gun else 2
        margin=self.tech.roll(actor,unit,difficulty,weapons=gun);failed=margin<0
        width=weapon_crits(unit,weapon2i(slot.type)) if gun else 1
        width=max(1,width//2) if gun and unit.specials&S.CLAN_TECH else max(1,width)
        base=60*width if gun else 45
        if failed:
            self.tech.notice(actor,f'Your attempt is unsuccessful, but you try to save the {label}...')
            margin=self.tech.roll(actor,unit,1 if gun else 3);base=base*3//2
            self.tech.notice(actor,f'You muck around, wasting the {label} for good...' if margin<0 else f'You manage to save the {label}...')
        minutes=base if margin<0 else self.variable(base,margin)
        if margin>=0:self.saving_notice(actor,base,minutes)
        if not failed or margin<0:self.inventory.change(store,part,slot.brand&15,-1)
        event=self.start(actor,unit,44 if gun else 43,loc,pos,brand if gun else 0,minutes=minutes,fake=failed,explicit=True)
        if gun and brand:slot.brand=(slot.brand&~15)|old
        return event

    def points(self,actor,unit,name,loc):
        armor=name=='fixarmor';sec=unit.sections[loc%8]
        field='rear' if armor and loc>=8 else 'armor' if armor else 'internal'
        actual=getattr(sec,field);original=getattr(sec,field+'_orig')
        if not armor:require(actual!=original,"The location doesn't need internals' repair!")
        require(not unit.is_section_destroyed(loc%8),"That part's blown off! Use reattach first!")
        require(not sec.config&C.SECTION_FLOODED,"That location has been flooded! Use reseal first!")
        require(not self.jobs.count(unit,47,loc) and not self.jobs.count(unit,48,loc%8),"Someone's repairing that section already!")
        if armor:require(sec.internal==sec.internal_orig,'The internals need to be fixed first!')
        require(not self.jobs.count(unit,49,loc),"Someone's scrapping that section - no repairs are possible!")
        amount=original-min(original,actual) if armor else original-actual
        if armor:require(amount>0,"The location doesn't need armor repair!")
        self.tech.fatigue(actor)
        self.economy(name+'_econ',unit,loc,amount=amount)
        self.tech.notice(actor,'You start fixing the '+('armor' if armor else 'internals')+'..')
        failed=self.tech.roll(actor,unit,1 if armor else 2)<0
        if failed:amount=self.failure(name+'_fail',actor,unit,loc,amount=amount)
        period=3 if armor else 9
        return self.start(actor,unit,47 if armor else 48,loc,minutes=divide(period*amount*(3 if failed else 2),2),amount=amount)

    def structure(self,actor,unit,name,loc):
        dead=unit.is_section_destroyed(loc);sec=unit.sections[loc]
        if name=='removesection':
            require(not dead,"That section's gone already!");require(not invalid_scrap_path(unit,loc),'You need to remove the outer sections first!')
            require(not self.jobs.count(unit,49,loc),"Someone's scrapping it already!")
            require(self.jobs.can_scrap_location(unit,loc),"Someone's tinkering with it already!")
        elif name=='reattach':
            require(unit.unit_type!=U.BSUIT,"You can't reattach a Battlesuit! Use 'replacesuit'!");require(dead,"That section isn't destroyed!")
            require(not invalid_repair_path(unit,loc),'You need to reattach adjacent locations first!')
            require(not self.jobs.count(unit,45,loc),"Someone's attaching that section already!");require(unit_is_fixable(unit),'You see nothing to reattach it to (read:unit is cored).')
        elif name=='reseal':
            require(not dead,'That section is destroyed!');require(sec.config&C.SECTION_FLOODED,'That has not been flooded!')
            require(not invalid_repair_path(unit,loc),'You need to reattach adjacent locations first!');require(not self.jobs.count(unit,56,loc),"Someone's sealing that section already!")
        else:
            require(unit.unit_type==U.BSUIT,"You can only use 'replacesuit' on a battlesuit unit!")
            members=sum(bool(section.internal) for section in unit.sections)
            maximum=getattr(unit,'max_suits',0)
            from systems.swarm import suit_name
            designation=suit_name(unit,True)
            require(members<maximum,f'This {designation} is already full! This {designation} only consists of {maximum} suits!')
            require(0<=loc<maximum,f'Invalid suit! This {designation} only consists of {maximum} suits!')
            require(dead,"That suit isn't destroyed!");require(not self.jobs.count(unit,57,loc),"Someone's already rebuilding that suit!")
            require(members>0,'You are unable to replace the suits here! None of the buggers are still alive!')
        self.tech.fatigue(actor)
        if name=='removesection':
            failed=self.tech.roll(actor,unit,2)<0
            self.tech.notice(actor,'You start removing the section..')
            return self.start(actor,unit,49,loc,extra=3 if failed else 2,minutes=180 if failed else 120)
        costs=self.costs(name+'_econ',unit,loc)
        if name=='reattach':self.check_stock(unit,costs,reattach=True)
        else:self.inventory.consume(self.jobs.store_for(unit),costs)
        self.tech.notice(actor,{'reattach':'You start replacing the section...','reseal':'You start resealing the section.','replacesuit':'You start replacing the missing suit.'}[name])
        margin=self.tech.roll(actor,unit,0 if name=='reseal' else 3);failed=margin<0;fake=False
        base={'reattach':240,'reseal':60,'replacesuit':120}[name]
        if name=='reattach':
            if failed:
                self.tech.notice(actor,'Your attempt is unsuccessful, but you try to save the section...')
                margin=self.tech.roll(actor,unit,3);base=base*3//2;fake=margin<0
                self.tech.notice(actor,'You muck around, wasting the section for good...' if fake else 'You manage to replace the section...')
            minutes=base if margin<0 else self.variable(base,margin)
            if margin>=0:self.saving_notice(actor,base,minutes)
            self.inventory.consume(self.jobs.store_for(unit),costs)
        else:
            if failed:fake=self.failure(name+'_fail',actor,unit,loc)<0
            minutes=base*(3 if failed else 2)//2
        return self.start(actor,unit,{'reattach':45,'reseal':56,'replacesuit':57}[name],loc,minutes=minutes,fake=fake,explicit=name=='reattach')
