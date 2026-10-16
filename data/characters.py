# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btechstats.c

"""Durable local character categories with btechstats.c retrieval/store semantics."""
from dataclasses import dataclass,field
import json
from pathlib import Path
import re
from data.character_values import VALUES,ATTRIBUTE,SKILL,ADVANTAGE,XP_MAX,code

HEALTH,SKILLS,ATTRS,ADVS,ALL=1,2,4,8,15


def integer(value):
    if not isinstance(value,int) or isinstance(value,bool) or not -(1<<31)<=value<(1<<31):
        raise ValueError('Unsupported signed character integer overflow/domain')
    return value


def divide(a,b):
    if not b:raise ValueError('Unsupported character division by zero')
    return (abs(a)//abs(b)) * (-1 if (a<0)!=(b<0) else 1)


def remainder(a,b):return a-divide(a,b)*b


@dataclass
class Stats:
    values: list=field(default_factory=lambda:[0]*len(VALUES))
    xp: list=field(default_factory=lambda:[0]*len(VALUES))
    last_use: list=field(default_factory=lambda:[0]*len(VALUES))
    dbref: int=0

    @classmethod
    def fresh(cls):
        result=cls(dbref=-1);result.clear();return result

    def clear(self):
        self.values=[int(row.type==ATTRIBUTE) for row in VALUES]
        self.xp=[0]*len(VALUES)
        self.set('Lives',1)  # Source does not clear existing last_use.

    def get(self,name):
        index=code(name)
        if index<0:return -1
        return self.values[index]+(divide(self.xp[index],XP_MAX) if VALUES[index].type==SKILL else 0)

    def set(self,name,value):
        index=code(name)
        if index<0:return
        integer(value)
        if index==11:self.values[5]=(self.values[5]+value-self.values[index])%256
        self.values[index]=value%256


def scan_ints(text,count):
    values=[];position=0
    for i in range(count):
        if i:
            if text[position:position+1]!=',':break
            position+=1
        match=re.match(r'\s*([+-]?\d+)',text[position:])
        if match is None:break
        values.append(integer(int(match[1])));position+=match.end()
    return values


def generic_retrieve(stats,text):
    for entry in text.split('/'):
        match=re.match(r'([A-Za-z_-]+):',entry)
        if match is None:return
        values=scan_ints(entry[match.end():],3)
        if not values:return
        index=code(match[1])
        if index<0:continue
        stats.values[index]=values[0]%256  # Generic retrieval bypasses code11 coupling.
        if len(values)>1 and values[1]:stats.xp[index]=values[1]
        if len(values)>2 and values[2]:stats.last_use[index]=values[2]


def generic_store(stats,skills):
    """Approved D1: safe string construction, retaining exact source format."""
    result=[]
    for i,row in enumerate(VALUES):
        if not stats.values[i] and not stats.xp[i]:continue
        if skills:
            if row.type!=SKILL:continue
        elif i!=5 and row.type!=ADVANTAGE:continue
        value=stats.values[i]
        if not isinstance(value,int) or not 0<=value<=255:raise ValueError('Character byte out of bounds')
        text=f'{row.short}:{value}'
        if stats.xp[i]:text+=f',{integer(stats.xp[i])},{integer(stats.last_use[i])}'
        result.append(text+'/')
    return ''.join(result)


class CharacterStore:
    """One engine's character records and single source BTH cache.

    JSON files hold identity metadata and the four exact source category strings.
    There is no gameplay serialization-size limit; source integer domains remain
    validated. Replacing one record is atomic and never truncates a category.
    """
    def __init__(self,root=None):
        from core.effects import LocalEffects
        self.effects=LocalEffects()
        self.root=Path(root).resolve() if root is not None else None
        self.records={};self.actors={};self.cache=None
        self.thresholds=[row.threshold for row in VALUES]
        if self.root is not None and self.root.exists():
            for path in sorted(self.root.glob('*.json')):
                if path.is_symlink():raise ValueError('Character record symlink is not supported')
                rec=json.loads(path.read_text());ident=integer(rec['id'])
                if ident<0 or path.stem!=str(ident):raise ValueError('Invalid character record identity')
                self.records[ident]=rec

    def create(self,ident,name,**metadata):
        integer(ident)
        if ident<0 or ident in self.records:raise ValueError('Invalid or duplicate character identity')
        rec={'id':ident,'name':name,'is_player':True,'valid':True,'alive':True,'connected':True,
             'wizard':False,'wiz_r':False,'god':False,'location':-1,'in_character':True,
             'categories':{},**metadata}
        self.records[ident]=rec;self.persist(ident)
        return rec

    def persist(self,ident):
        if self.root is None:return
        self.root.mkdir(parents=True,exist_ok=True)
        target=self.root/f'{ident}.json';pending=self.root/f'{ident}.new'
        if target.is_symlink() or pending.is_symlink():raise ValueError('Character record symlink is not supported')
        text=json.dumps(self.records[ident],sort_keys=True,indent=2)+'\n'
        pending.write_text(text);pending.replace(target)

    def record(self,ident):
        if ident not in self.records:return {'id':ident,'is_player':False,'categories':{}}
        return self.records[ident]

    def retrieve(self,ident,modes=ALL):
        stats=Stats();rec=self.record(ident)
        for mask,name in ((HEALTH,'health'),(ADVS,'advs'),(ATTRS,'attrs'),(SKILLS,'skills')):
            if not modes&mask:continue
            text=rec['categories'].get(name,'')
            if mask in (HEALTH,ATTRS):
                names=('Bruise','Lethal') if mask==HEALTH else ('Build','Reflexes','Intuition','Learn','Charisma')
                values=scan_ints(text,len(names))
                if len(values)!=len(names):
                    stats=Stats.fresh();self.store(ident,stats,ALL)
                else:
                    for key,value in zip(names,values):stats.set(key,value)
            else:generic_retrieve(stats,text)
        return stats

    def store(self,ident,stats,modes=ALL):
        rec=self.record(ident)
        if not rec['is_player']:return
        updates={}
        if modes&HEALTH:updates['health']=f"{stats.get('Bruise')},{stats.get('Lethal')}"
        if modes&ATTRS:updates['attrs']=','.join(str(stats.get(n)) for n in ('Build','Reflexes','Intuition','Learn','Charisma'))
        if modes&ADVS:updates['advs']=generic_store(stats,False)
        if modes&SKILLS:updates['skills']=generic_store(stats,True)
        if modes&(ADVS|SKILLS) and self.cache is not None and self.cache[0]==ident:self.cache=None
        rec['categories'].update(updates);self.persist(ident)

    def clear_record(self,ident):
        self.records[ident]['categories']={name:'' for name in ('attrs','skills','advs','health')}
        self.persist(ident)  # The command does not directly invalidate BTH.

    def lookup(self,caller,name):
        if name.lower()=='me':return caller
        if name.startswith('#'):
            if not re.fullmatch(r'[+-]?\d+',name[1:]):return -1
            ident=int(name[1:]);rec=self.records.get(ident)
            return ident if rec and rec.get('valid',True) and (rec['is_player'] or self.record(caller).get('god')) else -1
        return next((ident for ident,rec in self.records.items() if rec['is_player'] and rec.get('valid',True) and rec['name'].lower()==name.lower()),-1)

    def actor(self,ident):
        from entities.pilot import Pilot
        if ident not in self.records:raise ValueError('Unknown character identity')
        actor=self.actors.get(ident)
        if actor is None:
            actor=Pilot();actor._character_store=self;actor._character_id=ident
            self.actors[ident]=actor
        for key,val in self.records[ident].items():
            if key!='categories':setattr(actor,'_id' if key=='id' else key,val)
        return actor
