# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.tech.commands.c
#   btech/mech.tech.damages.c

"""Ordered damage/scrap plans and numbered dispatch into ordinary repair commands."""
import re
from entities.mech import UnitType as U,FireMode as F,SectionConfig as C,Specials as S
from entities.crittypes import is_ammo,is_weapon,weapon2i
from entities.weapon import get_weapon_by_index
from systems.combat import part_is_nonfunctional
from systems.combat_ammunition import full_ammo
from systems.damage import unit_is_fixable
from systems.damage_commands import short_section
from systems.economic_inventory import is_crap
from systems.enhanced_crits import part_temp_nuke
from systems.weapon_inventory import weapon_crits
from systems.technician import weapon_difficulty,atoi
from systems.repair_work import invalid_scrap_path,require
from data.construction_catalog import source_id

REATTACH,REPAIRP,REPAIRP_T,ENHCRIT_MISC,ENHCRIT_FOCUS,ENHCRIT_CRYSTAL,ENHCRIT_BARREL,ENHCRIT_AMMOB,ENHCRIT_RANGING,ENHCRIT_AMMOM,REPAIRG,RELOAD,FIXARMOR,FIXARMOR_R,FIXINTERNAL,DETACH,SCRAPP,SCRAPG,UNLOAD,RESEAL,REPLACESUIT=range(21)
DESCRIPTIONS=('Reattachment','Repairs on %s','Repairs on %s','Repairs on %s',
    'Realign focus on %s','Charging crystal repairs on %s','Barrel repairs on %s',
    'Ammo feed repairs on %s','Ranging system repairs on %s','Ammo feed repairs on %s',
    'Replacement of %s','Reload of %s','Repairs on armor','Repairs on rear armor',
    'Repairs on internals','Removal of section','Removal of %s','Removal of %s','Unload of %s','Reseal','Replace suit')
COMMANDS=('reattach','replacepart','repairgun',*(['fixenhcrit']*7),'replacegun','reload',
    'fixarmor','fixarmor','fixinternal','removesection','removepart','removegun','unload','reseal','replacesuit')
PART_ROWS=set(range(1,12))|{16,17,18}


class RepairReports:
    def __init__(self,work):self.work=work;self.jobs=work.jobs

    def check_damage(self,unit,loc,rows):
        if unit.is_section_destroyed(loc):rows.append((REPLACESUIT if unit.unit_type==U.BSUIT else REATTACH,loc,0));return False
        sec=unit.sections[loc]
        if sec.config&C.SECTION_FLOODED:rows.append((RESEAL,loc,0));return False
        if sec.internal!=sec.internal_orig:rows.append((FIXINTERNAL,loc,sec.internal_orig-sec.internal))
        else:
            for kind,field in ((FIXARMOR,'armor'),(FIXARMOR_R,'rear')):
                amount=getattr(sec,field+'_orig')-getattr(sec,field)
                if amount:rows.append((kind,loc,amount))
        pos=0
        while pos<12:
            slot=sec.criticals[pos];part=slot.type
            if not part:pos+=1;continue
            if is_ammo(part) and not slot.firemode&F.DESTROYED_MODE and slot.data!=full_ammo(unit,loc,pos):rows.append((RELOAD,loc,pos))
            if (not part_is_nonfunctional(unit,loc,pos) and not part_temp_nuke(slot) and not slot.firemode&F.DAMAGED_MODE) or is_crap(source_id(part)):pos+=1;continue
            if slot.firemode&F.DAMAGED_MODE:kind=next((value for mask,value in ((2,4),(4,5),(8,6),(16,7),(32,8),(64,9)) if slot.weap_damage_flags&mask),ENHCRIT_MISC)
            elif is_weapon(part):kind=REPAIRG if slot.firemode&F.DESTROYED_MODE else REPAIRP_T
            else:kind=REPAIRP
            rows.append((kind,loc,pos))
            pos+=weapon_crits(unit,weapon2i(part)) if is_weapon(part) else 1
        return True

    def damage_table(self,unit):
        rows=[]
        if unit.unit_type==U.MECH:
            if self.check_damage(unit,4,rows):
                for torso,arm in ((2,0),(3,1)):
                    if self.check_damage(unit,torso,rows):self.check_damage(unit,arm,rows)
                for loc in (5,6,7):self.check_damage(unit,loc,rows)
        else:
            for loc,sec in enumerate(unit.sections):
                if sec.internal_orig:self.check_damage(unit,loc,rows)
        return rows

    def check_scrap(self,unit,loc,rows):
        if unit.is_section_destroyed(loc):return True
        if self.jobs.count(unit,49,loc):rows.append((DETACH,loc,0));return True
        ready=True;pos=0
        while pos<12:
            slot=unit.sections[loc].criticals[pos];part=slot.type
            if not part or slot.firemode&(F.DESTROYED_MODE|F.BROKEN_MODE) or is_crap(source_id(part)):pos+=1;continue
            if is_ammo(part) and slot.data:
                rows.append((UNLOAD,loc,pos));ready=ready and self.jobs.repairing(unit,loc,pos);pos+=1;continue
            rows.append((SCRAPG if is_weapon(part) else SCRAPP,loc,pos))
            ready=ready and self.jobs.scrapping_part(unit,loc,pos)
            pos+=weapon_crits(unit,weapon2i(part)) if is_weapon(part) else 1
        if ready and not invalid_scrap_path(unit,loc):rows.append((DETACH,loc,0))
        return False

    def scrap_table(self,unit):
        rows=[]
        if unit.unit_type==U.MECH:
            remaining=4
            for arm,torso in ((1,3),(0,2)):
                if self.check_scrap(unit,arm,rows):remaining-=self.check_scrap(unit,torso,rows)
            for loc in (6,5):remaining-=self.check_scrap(unit,loc,rows)
            if not remaining:self.check_scrap(unit,4,rows)
            self.check_scrap(unit,7,rows)
        else:
            for loc,sec in enumerate(unit.sections):
                if sec.internal_orig:self.check_scrap(unit,loc,rows)
        return rows

    def table(self,unit):return self.damage_table(unit) if unit_is_fixable(unit) else self.scrap_table(unit)

    def under_repair(self,unit,row):
        kind,loc,pos=row
        if kind in PART_ROWS-{SCRAPP,SCRAPG}:return int(self.jobs.repairing(unit,loc,pos))
        if kind in (SCRAPP,SCRAPG):return int(self.jobs.scrapping_part(unit,loc,pos))
        if kind in (FIXARMOR,FIXINTERNAL,FIXARMOR_R):return int(self.jobs.fixing(unit,loc+8 if kind==FIXARMOR_R else loc))
        return self.jobs.count(unit,{REATTACH:45,RESEAL:56,DETACH:49,REPLACESUIT:57}[kind],loc)

    def part_name(self,unit,loc,pos):
        from systems.status_display import part_name
        return part_name(unit,loc,pos)

    def machine(self,unit):
        result=[]
        for number,row in enumerate(self.table(unit),1):
            kind,loc,pos=row
            data=self.part_name(unit,loc,pos) if kind in PART_ROWS else str(pos) if kind in (FIXARMOR,FIXARMOR_R,FIXINTERNAL) else '-'
            if kind in (RELOAD,UNLOAD):
                current=unit.sections[loc].criticals[pos].data
                data+=':'+str(full_ammo(unit,loc,pos)-current if kind==RELOAD else current)
            result.append(f'{number}|{short_section(unit,loc)}|{kind}|{data}|{self.under_repair(unit,row)}')
        return ','.join(result)

    def human(self,actor,unit):
        from systems.piloting import find_tech_skill,skill_target
        self.work.tech.gate(actor,unit,'D');result=[];extra_hard=1
        general=find_tech_skill(actor,unit);weapons=skill_target(actor,'Technician-Weapons','technician_weapons',18)
        for number,row in enumerate(self.table(unit),1):
            kind,loc,pos=row;description=DESCRIPTIONS[kind];base=general
            if kind in PART_ROWS:description=description%self.part_name(unit,loc,pos)
            if kind==REATTACH:minutes,diff=240,3
            elif kind==DETACH:minutes,diff=120,2
            elif kind==RESEAL:minutes,diff=60,0
            elif kind==REPLACESUIT:minutes,diff=120,3
            elif kind==REPAIRP:minutes,diff=45,2
            elif kind in (REPAIRP_T,REPAIRG,SCRAPG):
                slot=unit.sections[loc].criticals[pos];width=weapon_crits(unit,weapon2i(slot.type));base=weapons
                difficulty=weapon_difficulty(get_weapon_by_index(weapon2i(slot.type)))
                if kind==REPAIRP_T:
                    if width<5:extra_hard=0
                    minutes,diff=20,1+difficulty+extra_hard
                else:minutes,diff=(60 if kind==REPAIRG else 40)*max(1,width//(2 if unit.specials&S.CLAN_TECH else 1)),1+(difficulty if kind==REPAIRG else 0)
            elif 3<=kind<=9:minutes,diff,base=15,0,weapons
            elif kind==SCRAPP:minutes,diff=40,0
            elif kind in (RELOAD,UNLOAD):
                minutes,diff=10,1 if kind==RELOAD else 2
                rounds=unit.sections[loc].criticals[pos].data
                if kind==RELOAD:rounds=full_ammo(unit,loc,pos)-rounds
                from systems.network_reports import ammo_description
                from entities.crittypes import ammo2weapon_i
                slot=unit.sections[loc].criticals[pos]
                description+=ammo_description(get_weapon_by_index(ammo2weapon_i(slot.type)),slot.ammomode)+(' ' if kind==RELOAD else '')+f'({rounds} rounds)'
            else:
                minutes,diff=(9 if kind==FIXINTERNAL else 3)*pos,2 if kind==FIXINTERNAL else 1
                if kind==FIXINTERNAL:
                    material=next((label for flag,label in ((S.ES_TECH,'Endosteel'),(S.REINFI_TECH,'Reinforced'),(S.COMPI_TECH,'Composite')) if unit.specials&flag),'')
                else:
                    material=next((label for yes,label in ((unit.specials&S.FF_TECH,'Ferrofibrous'),(unit.specials&S.HARDA_TECH,'Hardened'),(unit.specials2&1,'Stealth'),(unit.specials2&2,'Heavy Ferrofibrous'),(unit.specials2&0x4000,'Light Ferrofibrous'),(unit.infantry_specials&8,'Purifier Stealth')) if yes),'')
                description='Repairs on'+(' rear' if kind==FIXARMOR_R else '')+(' '+material if material else '')+(' internals' if kind==FIXINTERNAL else ' armor')+f' ({pos} points)'
            busy=self.under_repair(unit,row)
            result.append(dict(number=number,type=kind,location=short_section(unit,loc),value=pos,description=description,
                minutes=None if busy else minutes,bth=None if busy else base+diff,in_progress=busy))
        if not result:self.work.tech.notice(actor,self.pristine(unit))
        else:
            from systems.status_display import menu_lines
            from systems.character_display import menu
            from systems.notifications import unit_identity
            lines=[]
            for row in result:
                busy=row['in_progress']
                numbers=f"{'N/A':>4} {'N/A':>4}" if busy else f"{row['minutes']:4d} {row['bth']:4d}"
                row['text']=(f"%ch{'%cg' if busy else '%cy'}{'(*)' if busy else '':>3} {row['number']:3d} {numbers:>9} "
                             f"{row['location']:>3} {row['description']}%cn"+(' (*)' if busy else ''))
                lines.append(row['text'])
            lines=menu_lines(f'Damage for {unit_identity(unit)}',['   Fix# Time  BTH Loc Description']+lines)
            lines+=menu([('(*) / %ch%cgGreen%cn = Job already done. %ch%cyYellow%cn = To be done.',1),
                         ('Time = Normal Time (in minutes) to complete fix. BTH = Your BTH to fix.',1),(None,1)])
            for line in lines:self.work.tech.notice(actor,line)
        return result

    @staticmethod
    def pristine(unit):
        return "The 'mech is in pristine condition!" if unit.unit_type==U.MECH else "It's in pristine condition!"

    def fix(self,actor,unit,argument):
        self.work.tech.gate(actor,unit,'C');rows=self.table(unit)
        require(bool(rows),self.pristine(unit))
        match=re.match(r'\s*([+-]?[0-9]+)-\s*([+-]?[0-9]+)',argument,re.ASCII)
        if match:
            low,high=map(atoi,match.groups())
            require(1<=low<=len(rows),'Invalid low #!');require(1<=high<=len(rows),'Invalid high #!')
        else:
            low=high=atoi(argument);require(1<=low<=len(rows),'Invalid #!')
        results=[]
        for number in range(low,high+1):
            kind,loc,pos=rows[number-1];name=COMMANDS[kind];text=short_section(unit,loc)
            if kind in PART_ROWS:text+=' '+str(pos+1)
            if kind==FIXARMOR_R:text+=' r'
            try:self.work.command(actor,unit,name,text);results.append(dict(number=number,command=name,error=None))
            except ValueError as error:
                self.work.tech.notice(actor,str(error));results.append(dict(number=number,command=name,error=str(error)))
        return results
