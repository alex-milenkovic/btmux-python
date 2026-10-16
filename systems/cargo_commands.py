# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/econ_cmds.c

"""Room manifests and cargo operations using the shared ECONPARTS backend."""
import re
from entities.mech import Specials
from systems.combat_commands import command_guard
from systems.technician import atoi
from systems.notifications import personal_notify
from systems.vehicle_combat import correct_speed
from systems.repair_work import require


class CargoCommands:
    def __init__(self,inventory):self.inventory=inventory;self.messages=[]

    def notice(self,actor,text):
        self.messages.append(dict(actor=actor._id,text=text));personal_notify(actor,text)

    def loading_bay(self,room,unit):
        text=str(self.inventory.get(room,'MECHSKILLS',''))
        values=[]
        # Scan each %d separately so a greedy conversion cannot split one integer.
        for _ in range(3):
            match=re.match(r'\s*([+-]?[0-9]+)',text,re.ASCII)
            if not match:break
            token=match[1];sign=token[0] if token[0] in '+-' else ''
            digits=token[len(sign):].lstrip('0') or '0'
            # Normalize only the value; consume the full original decimal token.
            values.append(int(sign+digits));text=text[match.end():]
        if len(values)<2:return
        x,y=values[:2];reveal=values[2] if len(values)>2 else 0
        require((unit.x,unit.y)==(x,y),"You're not where the cargo is!"+(f' Try looking around {x},{y} instead.' if reveal else ''))

    def command(self,actor,unit,name,argument='',*,data=True):
        name=name.lower().removeprefix('mech_')
        if name in ('raddstuff','rremovestuff','rresetstuff') or name=='rfixstuff' and data:
            require(getattr(actor,'wizard',False) or getattr(actor,'god',False) or actor._id==1,'Sorry, that command is restricted!')
        def transferred(row):
            verb={'loadcargo':'load','unloadcargo':'unload','raddstuff':'add','rremovestuff':'remove'}[name]
            part=self.inventory.catalog.names(row['part'],row['brand'])[1];count=row['count']
            self.notice(actor,f'You {verb} {count} {part}'+('s' if count>1 else '')+'.')
        if name=='manifest':return self.inventory.listing(actor.location,argument.lstrip(' \t\r\n\v\f'))
        if name=='rfixstuff':
            result=self.inventory.cleanup(actor.location if data else atoi(argument))
            self.notice(actor,'Fixing done. Original length: {old_length}. New length: {new_length}. Items in new: {items}. Unique items in new: {kinds}.'.format(**result));return result
        if name=='rresetstuff':
            self.notice(actor,'Inventory cleaned!');self.inventory.set_raw(actor.location,'')
            self.inventory.external.append(dict(service='MUX economy log',delivered=False,actor=actor._id,object=actor.location,action='reset'));return
        if name in ('raddstuff','rremovestuff'):
            rows=self.inventory.transfer(actor,argument,actor.location,modifier=1 if name=='raddstuff' else -1,notice=transferred)
        else:
            require(name in ('stores','loadcargo','unloadcargo'),'Unknown cargo command')
            error=command_guard(unit,started=name!='unloadcargo',pilot_only=name!='stores',caller=actor,wizard=getattr(actor,'wizard',False))
            if error:raise ValueError(error)
            if name!='stores':require(unit.specials&Specials.CARGO_TECH,'This unit cannot haul cargo!')
            if name=='loadcargo':require(unit.speed==0,"You're moving too fast!")
            if name in ('stores','loadcargo'):
                require(unit.location==unit.mapindex and not self.inventory.get(unit.location,'in_character',False),"You aren't inside a hangar!" if name=='stores' else "You aren't inside hangar!")
                self.loading_bay(unit.location,unit)
            if name=='stores':return self.inventory.listing(unit.location,argument.lstrip(' \t\r\n\v\f'))
            try:rows=self.inventory.transfer(actor,argument,unit._id,unit.mapindex,modifier=1 if name=='loadcargo' else -1,mortal=True,notice=transferred)
            finally:correct_speed(unit)
        return rows
