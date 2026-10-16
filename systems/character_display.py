# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/btechstats.c
#   btech/src/coolmenu.c

"""Character coolmenu entries and ordered local player delivery."""
import re


def menu(entries):
    """mycool addmenu/addempty/addline, including partial two-column rows."""
    lines=[];position=0
    while position<len(entries):
        _,columns=entries[position];width=78//columns;fields=[]
        while position<len(entries) and len(fields)<columns and entries[position][1]>=columns:
            text,_=entries[position];position+=1
            if text is None:fields.append('%cb'+'-'*width+'%c');continue
            overhead=len(text)-len(re.sub(r'%c[A-Za-z]?','',text))
            clipped=text[:width-1+overhead]
            fields.append(clipped+' '*max(0,width-len(clipped)+overhead))
        lines.append(''.join(fields))
    return lines


def notify_character(store,ident,lines):
    from systems.notifications import personal_notify
    actor=store.actors.get(ident)
    if actor is None and ident in store.records:actor=store.actor(ident)
    for line in lines:personal_notify(actor,line)


def status_lines(result):
    entries=[]
    def add(text):entries.append((text,2))
    def line():entries.append((None,1))
    def empty():entries.append((' ',1))
    if result.get('id'):
        add(f"%cgName     %c: {result['name']} (#{result['id']})")
        if result.get('faction'):add(f"%cgFaction  %c: {result['faction']}")
        line()
        add(f"%cgBruise   %c: {result['bruise']} of {result['maximum']}")
        add(f"%cgLethal   %c: {result['lethal']} of {result['maximum']}")
    add(f"%cgLives    %c: {result['lives']}");empty()
    add('%cgAttributes');add('Characteristics');line()
    for name,label,characteristic in zip(result['attributes'],('BLD','REF','INT','LRN','CHA'),('Athletic','Physical','Mental','Social',None)):
        value=result['attributes'][name]
        add(f'  {label:<8}{value:1d} ({18-2*value}+)'+(' '*30 if label in ('INT','LRN') else ''))
        if characteristic:add(f"  {characteristic:<15}{result['characteristics'][characteristic]:2d}+")
    empty()
    if result['advantage_groups']:
        add('%cgAdvantages');line()
        # Each original advantage is followed by a full-width empty entry.
        for group in result['advantage_groups']:
            for text in group:add('  '+text)
            empty()
    add('%cgSkills');line()
    for skill in result['skills']:
        add('  None' if skill=='None' else f"  {skill['name'][:25]:<25} : {skill['level']} ({skill['target']}+)")
    return menu(entries)
