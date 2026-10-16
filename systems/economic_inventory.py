# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/econ.c
#   btech/econ_cmds.c
#   btech/mech.status.c
#   btech/mech.tech.do.c

"""Object ECONPARTS attributes shared by stores, repairs and cargo.

Source IDs belong in storage; sparse Python weapon IDs belong in live slots.
Local JSON persistence replaces the attribute backend, not its list semantics.
"""
from collections import defaultdict
import json
from pathlib import Path
import re
from data.construction_catalog import Catalog, runtime_part, source_part, quick_wild
from entities.crittypes import Special, i2special
from systems.damage_commands import atoi

RECORD=re.compile(r'\[\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\]')


def is_crap(part):
    return part in {0,*[i2special(k) for k in (Special.ENDO_STEEL,
        Special.FERRO_FIBROUS,Special.TRIPLE_STRENGTH_MYOMER,
        Special.STEALTH_ARMOR,Special.HVY_FERRO_FIBROUS,Special.LT_FERRO_FIBROUS)]}


class InventoryStore:
    def __init__(self,catalog=None,path=None):
        self.catalog=catalog or Catalog();self.path=Path(path) if path else None
        self.records={};self.objects={};self.writes=[];self.external=[]
        if self.path and self.path.exists():
            data=json.loads(self.path.read_text())
            if data.get('format')!='btmux-objects-1':raise ValueError('Invalid object inventory format')
            self.records={int(k):v for k,v in data['objects'].items()}

    def register(self,identity,obj=None,**attributes):
        if type(identity) is not int or identity<0:raise ValueError('Invalid object identity')
        self.records.setdefault(identity,{})
        if obj is not None:self.objects[identity]=obj;obj.inventory_store=self
        if attributes:self.records[identity].update(attributes)
        self.persist();return identity

    def persist(self):
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_suffix(self.path.suffix+'.new')
            temporary.write_text(json.dumps(dict(format='btmux-objects-1',objects=self.records),sort_keys=True))
            temporary.replace(self.path)

    def get(self,identity,attribute,default=None):
        return self.records.get(identity,{}).get(attribute,default)

    def put(self,identity,attribute,value):
        if identity not in self.records:return False
        self.records[identity][attribute]=value
        self.writes.append(dict(object=identity,attribute=attribute,value=value));self.persist();return True

    def raw(self,identity):return self.get(identity,'ECONPARTS','')

    def set_raw(self,identity,text):
        if not isinstance(text,str):raise ValueError('ECONPARTS must be text')
        return self.put(identity,'ECONPARTS',text)

    def normalize_brand(self,part,brand):
        if not 0<=brand<=5:raise ValueError('Invalid brand')
        if brand and self.catalog.names(part,brand)[0]==self.catalog.names(part,0)[0]:return 0
        return brand

    def entry(self,identity,part,brand):
        text=self.raw(identity);start=text.find(f'[{part},{brand},')
        if start<0:return None
        match=RECORD.match(text,start)
        return match

    def find(self,identity,part,brand=0):
        brand=self.normalize_brand(part,brand);entry=self.entry(identity,part,brand)
        return int(entry[3]) if entry else 0

    def remove(self,identity,part,brand=0):
        text=self.raw(identity);entry=self.entry(identity,part,brand)
        if entry is None:return False
        start,end=entry.span()
        result=text[:start]+text[end+1:] if end<len(text) else text[:max(0,start-1)]
        return self.set_raw(identity,result)

    def add(self,identity,part,brand,count):
        text=self.raw(identity)
        return self.set_raw(identity,text+(',' if text else '')+f'[{part},{brand},{count}]')

    def change(self,identity,part,brand,amount):
        if identity not in self.records:return
        if not self.catalog.names(part,0)[0]:raise ValueError('Invalid source inventory part')
        brand=self.normalize_brand(part,brand)
        text=self.raw(identity);entry=self.entry(identity,part,brand)
        if entry is None and f'[{part},{brand},' in text:return
        total=(int(entry[3]) if entry else 0)+amount
        if entry:
            start,end=entry.span()
            text=text[:start]+text[end+1:] if end<len(text) else text[:max(0,start-1)]
        if total<=0:
            if entry:self.set_raw(identity,text)
            return
        if i2special(Special.SHOULDER_OR_HIP)<=part<=i2special(Special.HAND_OR_FOOT_ACTUATOR):
            self.set_raw(identity,text)
            self.change(identity,source_part('Actuator'),brand,total)
        else:self.set_raw(identity,text+(',' if text else '')+f'[{part},{brand},{total}]')

    def set(self,identity,part,brand,count):
        old=self.find(identity,part,brand)
        if old!=count:self.change(identity,part,brand,count-old)

    def entries(self,identity):
        for match in RECORD.finditer(self.raw(identity)):
            part,brand,count=map(int,match.groups())
            if 0<=part<1024 and 0<=brand<=5 and self.catalog.names(part,brand)[0]:
                yield part,brand,count

    def aggregate(self,identity):
        pile=defaultdict(int)
        for part,brand,count in self.entries(identity):pile[part,brand]+=count
        return dict(pile)

    def runtime_entries(self,identity):
        return [(runtime_part(part),brand,count) for part,brand,count in self.entries(identity)]

    def part_name(self,part,brand=0):
        from systems.status_display import catalog_part_name
        return catalog_part_name(part,brand,part_catalog=self.catalog)

    def consume(self,identity,costs):
        if identity not in self.records:raise ValueError('Repair store is unavailable')
        merged=defaultdict(int)
        for part,brand,count in costs:merged[part,self.normalize_brand(part,brand)]+=count
        for (part,brand),count in merged.items():
            if self.find(identity,part,brand)<count:raise ValueError(f'Not enough units of {self.part_name(part,brand)} in store! You need to have at least {count}.')
        for (part,brand),count in merged.items():
            self.change(identity,part,brand,-count)

    def cleanup(self,identity):
        pile=self.aggregate(identity);old=len(self.raw(identity));self.set_raw(identity,'')
        kinds=items=0
        for (part,brand),count in sorted(pile.items()):
            if count<=0 or is_crap(part) or not self.catalog.names(part,brand)[1]:continue
            self.change(identity,part,brand,count);kinds+=1;items+=count
        return dict(old_length=old,new_length=len(self.raw(identity)),items=items,kinds=kinds)

    def matching(self,selector,forms=('short','vlong','long')):
        for form in forms:
            if form=='long':result=[entry for entry in self.catalog.sorted[form] if quick_wild(selector,entry.long)]
            else:
                result=self.catalog.match(form,selector)
                result=[self.catalog.entries[result['source_part_id'],result['brand']]] if result else []
            if result:return result
        return []

    def listing(self,identity,selector=''):
        from systems.parts import part_weight
        from systems.status_display import catalog_part_name
        pile=self.aggregate(identity);rows=[]
        # The C listing cursor starts at zero and advances before matching.
        matches={(e.source_part_id,e.brand) for e in self.catalog.sorted['long'][1:]
                 if quick_wild(selector,e.long)} if selector else None
        for entry in self.catalog.sorted['short']:
            key=entry.source_part_id,entry.brand;count=pile.get(key,0)
            if not count or matches is not None and key not in matches:continue
            rows.append(dict(part=key[0],brand=key[1],name=catalog_part_name(key[0],key[1],long=True,part_catalog=self.catalog),count=count,
                weight=part_weight(runtime_part(key[0]))*count))
        return dict(rows=rows,footer='None' if not rows else '')

    def transfer(self,actor,argument,first,second=-1,modifier=1,mortal=False,notice=None):
        from data.templates import parse_attributes
        from systems.technician import atoi
        args=parse_attributes(argument,2)
        if len(args)!=2:raise ValueError('Invalid number of arguments!')
        count=min(50000,atoi(args[1]))
        if count<=0:raise ValueError('Invalid amount!')
        matches=self.matching(args[0])
        if not matches:raise ValueError(f"Nothing matches '{args[0]}'!")
        if not mortal and len(matches)>20 and actor._id!=1:raise ValueError(f"Wizards can't add more than 20 different objtypes at a time. ('{args[0]}' matches: {len(matches)})")
        if mortal:
            if actor.location!=first:raise ValueError("You ain't in your 'mech!")
            obj=self.objects.get(first)
            if obj is None or getattr(obj,'location',None)!=second:raise ValueError("You ain't in hangar!")
        rows=[]
        for entry in matches:
            part,brand=entry.source_part_id,entry.brand
            amount=min(count,self.find(first if modifier<0 else second,part,brand)) if mortal else count
            if not amount:continue
            self.change(first,part,brand,modifier*amount)
            if mortal:self.change(second,part,brand,-modifier*amount)
            row=dict(part=part,brand=brand,count=amount,from_object=second if modifier>0 else first,
                to_object=first if modifier>0 else second)
            rows.append(row);self.external.append(dict(service='MUX economy log',delivered=False,actor=actor._id,**row))
            if notice is not None:notice(row)
        if not rows:raise ValueError('Nothing matching that criteria was found!')
        return rows
