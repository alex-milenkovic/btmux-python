# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.build.c
#   btech/mech.mechref_ident.c
#   btech/mech.partnames.c
#   btech/mech.tech.c
#   btech/mechrep.c
#   btech/src/btech/weapons.h
#   btech/template.c

"""Source part IDs and ordered branded names for construction interfaces.

Live criticals retain Python catalog IDs. Conversion occurs only at file/readout
boundaries; the original weapons.h order is never imposed on existing units.
"""
from dataclasses import dataclass
import re
from data.construction_tables import MECH_REFERENCES
from data.templates import short_form
from entities.construction_weapon_data import WEAPON_ROWS
from entities.part_catalog import INTERNALS,CARGO,BOMBS
from entities.weapon import get_weapon_by_index,WeaponType as T,WeaponFlags as W
from systems.failures import get_part_brand_name

INVALID='#-1 INVALID PART NUMBER'
SOURCE_WEAPON_NAMES=tuple(row[0] for row in WEAPON_ROWS)


def source_weapon(index):
    from entities.weapon import get_weapon
    if not 0<=index<len(SOURCE_WEAPON_NAMES):raise ValueError('undefined source weapon index')
    return get_weapon(SOURCE_WEAPON_NAMES[index])


def weapon_id(name):
    return next((i+1 for i,value in enumerate(SOURCE_WEAPON_NAMES) if name.lower()==value.lower()),-1)


def legacy_ammo_id(name):
    index=weapon_id(name.partition('_')[2])
    return index+100 if index>0 else -1


def identify(reference):
    return next((name for prefix,name in MECH_REFERENCES if name is not None and reference.startswith(prefix)),None)


def valid_source_part(part):
    """Literal unable_to_find_proper_type predicate, without name dereferences."""
    if 1<=part<193:return part<=len(SOURCE_WEAPON_NAMES)
    if 193<=part<385:return part-193+1<=len(SOURCE_WEAPON_NAMES)
    if 394<=part<512:return part-394<len(INTERNALS)
    return True


def runtime_part(part):
    if 1<=part<193:return source_weapon(part-1).index+1
    if 193<=part<385:return source_weapon(part-193).index+193
    if part==0 or 385<=part<394+len(INTERNALS) or 512<=part<=65535:return part
    raise ValueError('undefined source part ID')


def source_id(part):
    if 1<=part<385:
        base=1 if part<193 else 193
        weapon=get_weapon_by_index(part-base)
        if weapon is None or weapon.name not in SOURCE_WEAPON_NAMES:raise ValueError('undefined runtime part ID')
        return SOURCE_WEAPON_NAMES.index(weapon.name)+base
    runtime_part(part)
    return part


def source_part(name):
    if not name or name.lower()=='empty':return 0
    for base,names,prefix in ((1,SOURCE_WEAPON_NAMES,''),(193,SOURCE_WEAPON_NAMES,'Ammo_'),
                              (385,BOMBS,'Bomb_'),(394,INTERNALS,''),(512,CARGO,'')):
        match=next((i for i,value in enumerate(names) if (prefix+value).lower()==name.lower()),None)
        if match is not None:return base+match
    return -1


def quick_wild(pattern,text):
    result=[];i=0
    while i<len(pattern):
        char=pattern[i];i+=1
        if char=='\\':
            if i==len(pattern):return not text if not result else re.fullmatch(''.join(result),text,re.I|re.S) is not None
            result.append(re.escape(pattern[i]));i+=1
        else:result.append('.*' if char=='*' else '.' if char=='?' else re.escape(char))
    return re.fullmatch(''.join(result),text,re.I|re.S) is not None


@dataclass(frozen=True)
class PartName:
    source_part_id:int
    brand:int
    short:str
    long:str
    vlong:str

    @property
    def packed(self):return self.source_part_id+1024*self.brand


class Catalog:
    def weapon_dump(self):
        from systems.status_display import menu_lines
        header='%cgWeapon Name             Heat  Damage  Range: Min Short Med Long VRT C  ApT'
        rows=[dict(source_part_id=i+1,name=r[0],heat=r[3],damage=r[4],minimum=r[5],short=r[6],medium=r[7],
            gun_range=r[8]*(20 if r[2]=='TARTILLERY' else 1),recycle=r[1],crits=r[13],ammo_per_ton=r[14]) for i,r in enumerate(WEAPON_ROWS)]
        entries=[f'{r["name"]:<24} {r["heat"]:2d}     {r["damage"]:2d}           {r["minimum"]:2d}  {r["short"]:2d}    {r["medium"]:2d}  {r["gun_range"]:3d}  {r["recycle"]:2d}  {r["crits"]:2d} {r["ammo_per_ton"]:d}' for r in rows]
        return dict(header=header,rows=rows,messages=menu_lines('MechWeapons available',entries,1,header))

    def special_dump(self):
        from systems.status_display import menu_lines
        columns=min(4,max(1,(len(INTERNALS)+17)//18))
        return dict(header='MechSpecials available',rows=list(INTERNALS),
                    messages=menu_lines('MechSpecials available',list(INTERNALS),columns))

    def __init__(self,parts=True,clan=True,diagnostic=None):
        self.parts=parts;self.clan=clan
        self.messages=[];self.diagnostic=diagnostic
        self.entries={}
        for brand in range(6):
            for part in range(1024):
                forms=self.generate(part,brand)
                if forms:self.entries[part,brand]=PartName(part,brand,*forms)
        self.sorted={form:sorted(self.entries.values(),key=lambda entry:getattr(entry,form)) for form in ('short','long','vlong')}
        self.hashes={'short':{},'vlong':{}}
        for index,entry in enumerate(self.sorted['short'],1):
            for form in self.hashes:self.hashes[form].setdefault(getattr(entry,form).lower(),(index,entry))

    def short_name(self,part):
        """Raw part_figure_out_shname, independent of catalog/brand eligibility."""
        if 1<=part<1+len(SOURCE_WEAPON_NAMES) or 193<=part<193+len(SOURCE_WEAPON_NAMES):
            ammo=part>=193;name=SOURCE_WEAPON_NAMES[part-(193 if ammo else 1)]
            return short_form(('Ammo_' if ammo else '')+(name if self.clan and name[:2].lower()=='cl' else name[3:]))
        for base,names,prefix in ((385,BOMBS,'Bomb_'),(394,INTERNALS,''),(512,CARGO,'')):
            if base<=part<base+len(names):return short_form(prefix+names[part-base])
        return None

    def list_forms(self,form='short'):
        entries=[vars(entry)|{'packed':entry.packed} for entry in self.sorted[form]]
        messages=['Listing of forms:']+[f'{i:3d} {entry.short:<20} {entry.long:<25} {entry.vlong}' for i,entry in enumerate(self.sorted[form])]
        return dict(entries=entries,messages=messages)

    def match_result(self,form,query,cursor=-1):
        """Explicit C in/out cursor adapter, including exhausted searches."""
        result=self.match(form,query,cursor)
        if result is not None:return dict(found=True,**result)
        return dict(found=False,cursor=max(cursor+1,len(self.sorted['long'])) if form=='long' else cursor)

    def generate(self,part,brand=0):
        if not 0<=brand<=5:return None
        prefix=None
        if 1<=part<1+len(SOURCE_WEAPON_NAMES) or 193<=part<193+len(SOURCE_WEAPON_NAMES):
            ammo=part>=193;weapon=source_weapon(part-(193 if ammo else 1))
            if not self.clan and weapon.special&W.CLAT:return None
            if brand:
                prefix=get_part_brand_name(runtime_part(part),brand)
                if not prefix or not self.parts or weapon.special&W.CLAT:return None
            if ammo and (weapon.weapon_type in (T.TBEAM,T.THAND) or weapon.special&(W.PC_IMPA|W.PC_SHAR|W.PC_HEAT)):return None
            start='Ammo_' if ammo else ''
            long=start+weapon.name[3:];vlong=start+weapon.name
            short=self.short_name(part)
        elif brand:return None
        elif 385<=part<394:long=vlong='Bomb_'+BOMBS[part-385];short=short_form(long)
        elif 394<=part<394+len(INTERNALS):long=vlong=INTERNALS[part-394];short=short_form(long)
        elif 512<=part<512+len(CARGO):long=vlong=CARGO[part-512];short=short_form(long)
        else:return None
        if prefix:return short_form(prefix)+'.'+short,prefix+'.'+long,prefix+'.'+vlong
        return short,long,vlong

    def names(self,part,brand=0):
        if not 0<=brand<=5:raise ValueError('brand level must be 0..5')
        entry=self.entries.get((part,brand)) or self.entries.get((part,0))
        if entry:return entry.short,entry.long,entry.vlong
        message=f'No index for {part}/0'
        self.messages.append(message)
        if self.diagnostic is not None:self.diagnostic(message)
        return None,None,None

    def match(self,form,query,cursor=-1):
        if form in self.hashes:
            if cursor>=0:return None
            found=self.hashes[form].get(query.lower())
            if found is None:return None
            cursor,entry=found
        elif form=='long':
            found=next(((i,e) for i,e in enumerate(self.sorted['long']) if i>cursor and quick_wild(query,e.long)),None)
            if found is None:return None
            cursor,entry=found
        else:raise ValueError('invalid name form')
        return dict(cursor=cursor,source_part_id=entry.source_part_id,brand=entry.brand,packed=entry.packed)

    def packed_name(self,packed,selector):
        if type(packed) is not int or packed<0 or packed>=6144:return INVALID
        entry=self.entries.get((packed%1024,packed//1024))
        if entry is None:return INVALID
        form={'s':'short','l':'long','v':'vlong'}.get(selector[:1].lower())
        return getattr(entry,form) if form else '#-1 INVALID NAME TYPE'

    def partmatch(self,text,wizard=True):
        if not wizard:return '#-1 PERMISSION DENIED'
        if text is None:return '#-1 NEED PARTNAME'
        if len(text)>=1024:return '#-1 PARTNAME TOO LONG'
        values=[]
        for form,cursor in (('short',-1),('long',0),('vlong',-1)):
            while (result:=self.match(form,text,cursor)) is not None:
                values.append(str(result['packed'])+' ');cursor=result['cursor']
        return ''.join(values) or '#-1 INVALID PARTNAME'

    def partname(self,text,selector,wizard=True):
        if not wizard:return '#-1 PERMISSION DENIED'
        if text is None:return '#-1 NEED PARTNAME'
        match=re.match(r'\s*([+-]?\d+)',str(text))
        return self.packed_name(int(match[1]),selector) if match else INVALID

    def weapon_index(self,text):
        match=self.match('vlong',text)
        return match['source_part_id']-1 if match and 1<=match['source_part_id']<193 else -1

    def special_index(self,text):
        match=self.match('vlong',text)
        return match['source_part_id']-394 if match and 394<=match['source_part_id']<512 else -1
