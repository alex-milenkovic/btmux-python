"""Catalog expectations derived from read-only C tables and name bodies."""
from qa.construction_qa_common import *
from qa.construction_qa_numeric import table
import re

def uncomment(s):return re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
def source_weapons():
    source=uncomment((CROOT/'weapons.h').read_text()).split('MechWeapons[] = {')[1].split('};')[0]
    rows=[]
    for body in re.findall(r'\{\s*("[^"]+".*?)\}',source,re.S):
        cells=[s.strip() for s in body.split(',')];cells[0]=json.loads(cells[0]);rows.append(cells)
    assert len(rows)==178,len(rows)
    return rows

def short(s):
    if len(s)<=4 and '/' not in s:return s
    out=''.join(c for c in s if c.isupper() or c.isdigit() or c=='_')
    return out+s[1] if len(out)==1 else out

def entries(parts=True,clan=True):
    weapons=source_weapons();names={};kinds={}
    for i,r in enumerate(weapons):
        if not clan and 'CLAT' in r[17]:continue
        names[1+i]=r[0];kinds[1+i]=r
        if r[2] not in ('TBEAM','THAND') and not any(s in r[17] for s in ('PCOMBAT','PC_HEAT','PC_IMPA','PC_SHAR')):names[193+i]='Ammo_'+r[0]
    names.update({394+i:n for i,n in enumerate(table('internals'))});names.update({512+i:n for i,n in enumerate(table('cargo'))})
    bombs=re.findall(r'\{"([^"]+)"',uncomment((CROOT/'aero.bomb.c').read_text()).split('BOMBINFO bombs[] = {')[1].split('};')[0]);names.update({385+i:'Bomb_'+n for i,n in enumerate(bombs)})
    brands=re.findall(r'\{"([^"]+)"',uncomment((CROOT/'failures.h').read_text()).split('struct brand_data brands[] = {')[1].split('};')[0])
    result=[]
    for b in range(6):
        for part,name in sorted(names.items()):
            prefix=None;r=kinds.get(part)
            if b:
                if not r or not parts or 'CLAT' in r[17] or any(s in r[17] for s in ('PCOMBAT','PC_HEAT','PC_IMPA','PC_SHAR')):continue
                # GetBrandIndex: flamer first, energy, IsAutocannon, missile.
                group=3 if 'Flamer' in name else 0 if r[2]=='TBEAM' else 1 if r[2]=='TAMMO' else 2 if r[2]=='TMISSILE' else None
                if group is None:continue
                prefix=brands[group*5+b-1]
            if 1<=part<193 or 193<=part<385:
                ammo=part>=193;w=weapons[part-(193 if ammo else 1)][0];start='Ammo_' if ammo else ''
                long=start+w[3:];sh=short(start+(w if clan and w[:2].lower()=='cl' else w[3:]))
            else:long=name;sh=short(name)
            result.append(dict(source_part_id=part,brand=b,short=short(prefix)+'.'+sh if prefix else sh,long=prefix+'.'+long if prefix else long,vlong=prefix+'.'+name if prefix else name,packed=part+1024*b))
    return result

def run(a):
    for parts,clan in [(True,True),(False,True),(True,False)]:
        expected=entries(parts,clan);forms=('short','long','vlong');actions=[cat('list',form=f) for f in forms]
        d=a.run(f'catalog/all-{int(parts)}-{int(clan)}',document(actions,construction={'parts':parts,'clan':clan}),'ordinary')
        for f,rows in zip(forms,d['results']):a.eq('complete '+f+' table',rows,sorted(expected,key=lambda r:r[f]))
    # Full ordered reference table, including nulls and shadows.
    text=uncomment((CROOT/'mech.mechref_ident.c').read_text());refs=[(x,json.loads(y) if y!='NULL' else None) for x,y in re.findall(r'"([^"]+)",\s*("[^"]+"|NULL)',text)]
    inputs=[p+'QA' for p,n in refs]+['unknown','MAD-3R','Mad-Prime','Thor','HCT-3F','CHP-W5']
    want=[next((n for p,n in refs if n is not None and s.startswith(p)),None) for s in inputs]
    d=a.run('catalog/all-reference-prefixes',document([cat('identify',text=s) for s in inputs]),'ordinary');a.eq('all first-prefix results',d['results'],want)
    for outline in range(1,8):
        for line,r in examples('catalog',outline):
            kw={};text=r.get('text','');action=None
            if outline==1:action=cat('identify',text=r['reference']);expected=None if r['name']=='none' else r['name']
            elif outline in (2,3):
                action=cat('names',text=r['part'],brand=int(r.get('brand',0)));kw={'construction':{'parts':bool(int(r.get('parts',1)))}}
                expected=[None if r[k]=='none' else r[k] for k in ('short','long','vlong')] if outline==2 else r['name']
            elif outline==4:action=cat('match',form=r['form'],text=r['query'],cursor=int(r['cursor']));expected=bool(int(r['success']))
            elif outline==5:action=cat('partname',text=r['id'],form=r['selector']);expected='#-1 '+r['text'].replace('_',' ') if r['text'].startswith('INVALID') else r['text']
            elif outline==6:
                kind={'WeaponIFromString':'weapon_id','AmmoIFromString':'legacy_ammo_id','FindSpecialItemCodeFromString':'special_index','WeaponIndexFromString':'weapon_index'}[r['helper']];action=cat(kind,text=text);expected=int(r['value'])
            else:
                if r['command']=='btpartmatch':action=cat('partmatch',text=r['argument'],wizard=bool(int(r['wizard'])))
                else:
                    num,form=r['argument'].split('/');action=cat('partname',text=num,form=form,wizard=bool(int(r['wizard'])))
                expected=('#-1 '+r['result'].replace('_',' ')) if '_' in r['result'] else r['result']
            d=a.run(f'catalog/{outline}-{line}',document([action],**kw));actual=d['results'][0]
            if outline==2:actual=[actual[k] for k in ('short','long','vlong')]
            elif outline==3:actual=actual['vlong']
            elif outline==4:actual=actual is not None
            a.eq('accepted example',actual,expected)
    # Complete valid/invalid base/brand space and hash exhaustion. Expected names
    # come from the source reconstruction above, never from a CLI result.
    expected=entries();index={(e['source_part_id'],e['brand']):e for e in expected}
    actions=[];want=[]
    for brand in range(6):
        for part in range(1024):
            actions.append(cat('names',part=part,brand=brand));e=index.get((part,brand),index.get((part,0)));want.append([e[f] if e else None for f in ('short','long','vlong')])
    d=a.run('catalog/all-base-brand-requests',document(actions));a.eq('all6144 requests/fallbacks',[[r[f] for f in ('short','long','vlong')] for r in d['results']],want)
    ordered=sorted(expected,key=lambda e:e['short']);hashes={f:{} for f in ('short','vlong')}
    for cursor,e in enumerate(ordered,1):
        for f in hashes:hashes[f].setdefault(e[f].lower(),dict(cursor=cursor,source_part_id=e['source_part_id'],brand=e['brand'],packed=e['packed']))
    actions=[];want=[]
    for form,lookup in hashes.items():
        for name,e in lookup.items():actions += [cat('match',form=form,text=name,cursor=-1),cat('match',form=form,text=name,cursor=e['cursor'])];want += [e,None]
    d=a.run('catalog/all-exact-hashes-and-exhaustion',document(actions));a.eq('hash insertion/cursors',d['results'],want)
    ordered=sorted(expected,key=lambda e:e['long']);actions=[cat('match',form='long',text='*',cursor=i) for i in range(-1,len(ordered)+1)]
    want=[dict(cursor=i,source_part_id=e['source_part_id'],brand=e['brand'],packed=e['packed']) for i,e in enumerate(ordered)]+[None,None]
    d=a.run('catalog/all-long-cursors',document(actions));a.eq('long preincrement/exhaustion',d['results'],want)
    for query in ('HeatSink','Steel','*','MediumLas?r','no-such','',r'\*',r'\?',r'Heat\Sink'):
        pattern='';escape=False
        for c in query:
            if escape:pattern+=re.escape(c);escape=False
            elif c=='\\':escape=True
            elif c=='*':pattern+='.*'
            elif c=='?':pattern+='.'
            else:pattern+=re.escape(c)
        results=[]
        h=hashes['short'].get(query.lower())
        if h:results.append(h['packed'])
        results += [e['packed'] for e in ordered[1:] if re.fullmatch(pattern,e['long'],re.I|re.S)]
        h=hashes['vlong'].get(query.lower())
        if h:results.append(h['packed'])
        d=a.run('catalog/partmatch-'+str(len(a.rows)),document([cat('partmatch',text=query)]));a.eq('short/long1+/vlong duplicates and trailing spaces',d['results'][0],''.join(str(x)+' ' for x in results) or '#-1 INVALID PARTNAME')
    constants=dict(re.findall(r'#define\s+(VRT_\w+)\s+(\d+)',(CROOT/'weapons.vrt.h').read_text()))
    want=[]
    for i,r in enumerate(source_weapons()):
        want.append(dict(source_part_id=i+1,name=r[0],heat=int(r[3]),damage=int(r[4]),minimum=int(r[5]),short=int(r[6]),medium=int(r[7]),gun_range=int(r[8])*(20 if r[2]=='TARTILLERY' else 1),recycle=int(constants[r[1]]),crits=int(r[13]),ammo_per_ton=int(r[14])))
    d=a.run('catalog/all-dump-rows',document([cat('weapons'),cat('specials')]),'ordinary');a.eq('all178 source weapon numerical rows',d['results'][0]['rows'],want);a.eq('all52 special rows',d['results'][1]['rows'],table('internals'))
