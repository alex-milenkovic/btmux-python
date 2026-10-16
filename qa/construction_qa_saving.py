"""Source-defined file grouping, omission and original/current boundaries."""
from qa.construction_qa_common import *
from qa.construction_qa_numeric import blank,table,tech
from qa.construction_qa_catalog import source_weapons
import re

def run(a):
    parts=table('internals');weapons=source_weapons()
    def rawpart(name):
        if name=='empty':return 0
        if name.startswith('IS.'):
            # Runtime IDs are resolved by the public catalog, never used as an oracle.
            return None
        return 394+parts.index(name)
    for outline in range(1,6):
        for line,r in examples('saving',outline):
            u=blank('Vehicle','Track') if outline==3 else blank();sec=u['sections'][0];sec.update(internal=8,internal_orig=8);actions=[]
            if outline==1:sec.update(armor=1,armor_orig=int(r['armor']),internal=1,internal_orig=int(r['internal']),rear=1,rear_orig=int(r['rear']),config=1)
            elif outline==2:
                for j in range(int(r['count'])):
                    s=sec['slots'][j];part=r['part']
                    if part.startswith('IS.'):s.pop('type');s['weapon']=part
                    else:s['type']=rawpart(part)
            elif outline==3:
                if r['part'].startswith('IS.'):sec['slots'][0].pop('type');sec['slots'][0]['weapon']=r['part']
                else:sec['slots'][0]['type']=rawpart(r['part'])
            elif outline==4:sec.update(armor=7,armor_orig=20);sec['slots'][0].update(type=212,data=int(r['remaining']),firemode=128 if r['half']=='1' else 0)
            else:tech(u,r['tech'])
            actions+=[T('save','MODERN'),T('read','MODERN'),T('save','LEGACY',legacy=True),T('read','LEGACY')]
            d=a.run(f'saving/{outline}-{line}',document(actions,units=[u]));text=d['results'][1].get('text','');old=d['results'][3].get('text','')
            a.eq('save succeeded',d['results'][0]['ok'],True)
            if outline==1:
                if r['out_internal']=='section-omitted':a.eq('zero-original section omitted','Left_Arm' in text,False)
                else:
                    section=text.split('Left_Arm\n')[1]
                    for label,col in [('Armor','out_armor'),('Internals','out_internal'),('Rear','out_rear')]:
                        matches=re.findall(label+r'\s+\{\s*(.*?)\s*\}',section);a.eq('design '+label,matches,[] if r[col]=='omitted' else [r[col]])
                    a.eq('CASE omitted','Config' in section,False)
            elif outline==2:
                run=int(r['run']);want='CRIT_1'+('-'+str(run) if run>1 else '')
                a.eq('first grouped run',re.findall(r'CRIT_\d+(?:-\d+)?',text)[:1],[] if r['part']=='empty' else [want])
            elif outline==3:a.eq('vehicle exclusion',r['part'] in text,r['result']=='emitted')
            elif outline==4:
                a.eq('modern capacity',re.search(r'Ammo_IS.AC/5\s+(\d+)',text)[1],r['modern_rounds']);a.eq('legacy quantity',old.splitlines()[2].split()[1],r['legacy_rounds']);a.eq('legacy current armor',old.splitlines()[1].split()[0],'7');a.eq('modern design armor',re.search(r'Armor\s+\{ (\d+) \}',text)[1],'20')
            else:a.eq('source tech filter',r['tech'] in text,r['result']=='emitted')
    # Every grouping equality field, including data and otherwise-unserialized modes.
    for changed in ('type','data','firemode','ammomode','brand'):
        for enabled in (True,False):
            u=blank();s=u['sections'][2];s.update(internal=12,internal_orig=12)
            for j in range(3):s['slots'][j].update(type=403,data=7,brand=3)
            s['slots'][1][changed]={'type':404,'data':8,'firemode':32,'ammomode':1,'brand':4}[changed]
            d=a.run(f'saving/group-break-{changed}-{enabled}',document([T('save','S'),T('read','S')],units=[u],construction={'parts':enabled}))
            a.eq('group equality fields',re.findall(r'CRIT_\d+(?:-\d+)?',d['results'][1]['text']),['CRIT_1-3'] if changed=='brand' and not enabled else ['CRIT_1','CRIT_2','CRIT_3'])
