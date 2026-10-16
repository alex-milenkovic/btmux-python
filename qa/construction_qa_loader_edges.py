"""Source ranges, bitfield storage, strings, and modern mode token boundaries."""
from qa.construction_qa_common import *

def run(a):
    for brand in (0,1,15,16,17,31,-1):
        for parts in (False,True):
            u={'name':'u','sections':[{'index':2,'slots':[{'index':i,'desired_ammo_loc':4} for i in range(12)]}]}
            content='Left_Torso\n'+field('CRIT_1-12',f'IS.MediumLaser 8 RearMount|Precision {brand}')+field('CRIT_6-7','HeatSink 9 - 3')
            doc=document([D('load_fields','RANGES'),R()],units=[u],construction={'parts':parts,'files':{'RANGES':content}})
            d=a.run(f'loading/range-brand-{brand}-{parts}',doc);slots=d['results'][1]['slots'][2]
            a.eq('range and overlap source IDs',[s['source_part_id'] for s in slots],[403 if i in (5,6) else 79 for i in range(12)])
            a.eq('bitfield brand and copy',[s['brand'] for s in slots],[3 if parts and i in (5,6) else (brand&15 if parts else 0) for i in range(12)])
            a.eq('weapon data normalized',[s['data'] for s in slots],[9 if i in (5,6) else 0 for i in range(12)])
            a.eq('first-only desired ammo reset',[s['desired_ammo_location'] for s in slots],[-1 if i in (0,5) else 4 for i in range(12)])
    for token,want in [('RearMount|RearMount|Precision',[32,65536]),('rearmount|pReCiSiOn',[32,65536]),('|RearMount',[32,0]),('RearMount||Precision',[32,65536]),('RearMount|',None),('Halfton|LBX/Cluster',[128,1]),('-', [0,0]),('unknown',None),('RearMount|unknown',None)]:
        d=a.run('modes/token-'+str(len(a.rows)),document([D('mode_masks',token)]));r=d['results'][0]
        if want is None:a.eq('unknown fails',r['ok'],False)
        else:a.eq('D1 source tokenization',r,want)
    for fieldname,attr,limit,letter in [('Name','name',30,'N'),('Unit_Era','unit_era',24,'E'),('Unit_TRO','unit_tro',24,'T')]:
        for size in (1,limit,limit+1):
            d=a.run(f'loading/strings-{fieldname}-{size}',document([D('load_fields','STRING'),R()],{'STRING':field(fieldname,letter*size)},units=[{'name':'u','construction':{'zeroed':True}}]));r=d['results'][1]
            if size<=limit:
                a.eq('source string bytes',r[attr],'Undefined' if size==1 and fieldname!='Name' else letter*size)
            else:a.eq('unsafe strings rejected',d['results'][0]['ok'],False)
    for size in (24,25,34,35):
        reference='R'*size
        d=a.run(f'loading/reference-limit-{size}',document([T('load',reference),R()],{reference:field('Name','Reference size')}))
        a.eq('reference truncates24',d['results'][1]['template_ref'],reference[:24])
    # Mutate a real saved ordinary rear/precision file, then use normal load.
    d=a.run('ordinary/13-invalid-source-save',document([T('load','QA50'),E('addweap','IS.AC/5 LT 1 2 3 4 R'),E('reload','IS.AC/5 RT 1 P'),dict(op='construction_pilot'),C('startup'),A(40),C('precision','1'),E('savetemp2','MODES')],{'QA50':modern()},ordinary=True),'ordinary')
    a.eq('ordinary mode source saved',d['results'][-1]['ok'],True)
    saved=(OUT/'ordinary/13-invalid-source-save/templates/MODES').read_text()
    for kind,loc,part in [('weapon',2,96),('ammo',3,288)]:
        for mixed in (False,True):
            lines=saved.splitlines(keepends=True)
            for i,line in enumerate(lines):
                if ('Ammo_IS.AC/5' in line) if kind=='ammo' else ('IS.AC/5' in line and 'Ammo_' not in line):
                    old='Precision' if kind=='ammo' else 'RearMount|Precision'
                    lines[i]=line.replace(old,('Precision|' if mixed else '')+'unknown');break
            else:raise AssertionError('saved mode line missing')
            d=a.run(f'ordinary/13-edited-unknown-{kind}-{mixed}',document([T('load','BAD'),R()],{'BAD':''.join(lines)}),'ordinary');slot=d['results'][1]['slots'][loc][0]
            a.eq('ordinary edited-file rejection',d['results'][0]['ok'],False);a.eq('earlier type write survives fallback',slot['source_part_id'],part);a.eq('failed masks unchanged after clear',[slot['fire'],slot['ammo']],[0,0])
