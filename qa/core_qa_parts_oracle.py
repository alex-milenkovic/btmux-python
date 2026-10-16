"""Source-table weights and compiled C material aliases through the public CLI."""
import re,subprocess,json
from core_simulation_qa import ROOT,OUT,D,case,check as q
from core_qa_oracles import function


def build():
    src=ROOT/'btmux/btmux/btech/src/btech'
    source=(src/'mech.utils.c').read_text();header=(src/'mech.h').read_text()
    template=(src/'template.c').read_text()
    for array,base in [('internalsweight',394),('cargoweight',512)]:
        body=re.search(r'int '+array+r'\[\]\s*=\s*\{(.*?)\};',template,re.S)[1]
        body=re.sub(r'/\*.*?\*/','',body,flags=re.S)
        body=subprocess.run(['cc','-E','-P','-DBT_COMPLEXREPAIRS','-x','c','-'],input=body,text=True,capture_output=True,check=True).stdout
        values=[int(v.strip()) for v in body.split(',') if v.strip()]
        case('parts','source-table-'+array,[D('GetPartWeight',base+i,True) for i in range(len(values))],[q('results',values)])
    names=('GetPartMod','ProperArmor','ProperInternal','alias_part','ProperMyomer')
    normalized=re.sub(r'^\s+(int '+r'(?:'+'|'.join(names)+r')\()',r'\1',source,flags=re.M)
    body=''.join(function(normalized,n) for n in names)
    definitions={m[1]:m[0] for m in re.finditer(r'^#define\s+([A-Z][A-Z0-9_]*)\s+[^\n]+',header,re.M)}
    needed=set(re.findall(r'\b[A-Z][A-Z0-9_]+\b',body))
    while True:
        expanded=needed|{v for n in needed if n in definitions for v in re.findall(r'\b[A-Z][A-Z0-9_]+\b',definitions[n])}
        if expanded==needed:break
        needed=expanded
    shim='''#include <stdio.h>
#define BOUNDED(lo,v,hi) ((v)<(lo)?(lo):(v)>(hi)?(hi):(v))
typedef struct{int tons,engine,quad;unsigned int specials,specials2;} MECH;
struct{int btech_complexrepair;}mudconf;
#define MechTons(m) ((m)->tons)
#define MechEngineSize(m) ((m)->engine)
#define MechSpecials(m) ((m)->specials)
#define MechSpecials2(m) ((m)->specials2)
#define MechIsQuad(m) ((m)->quad)
#define Special(n) ((n)+394)
#define Cargo(n) ((n)+512)
#define IsSpecial(n) ((n)>=394 && (n)<512)
#define IsActuator(n) ((n)>=394 && (n)<=397)
'''
    main='''int main(){MECH m;while(scanf("%d%d%d%u%u%d",&m.tons,&m.engine,&m.quad,&m.specials,&m.specials2,&mudconf.btech_complexrepair)==6){printf("%d %d %d",ProperArmor(&m),ProperInternal(&m),ProperMyomer(&m));for(int p=394;p<=419;p++)for(int loc=0;loc<8;loc++)printf(" %d",alias_part(&m,p,loc));puts("");}return 0;}'''
    path=OUT/'parts-oracle.c';exe=OUT/'parts-oracle'
    path.write_text(shim+'\n'.join(definitions[n] for n in sorted(needed) if n in definitions and n!='BOUNDED')+'\n'+body+main)
    subprocess.run(['cc','-O0',str(path),'-o',str(exe)],check=True,capture_output=True)
    def bit(name):return int(re.search(r'^#define\s+'+name+r'\s+(0x[0-9a-fA-F]+|\d+)\b',header,re.M)[1],0)
    s1=('FF_TECH','HARDA_TECH','ES_TECH','REINFI_TECH','COMPI_TECH','TRIPLE_MYOMER_TECH','XL_TECH','ICE_TECH','CE_TECH','XXL_TECH','LE_TECH','DOUBLE_HEAT_TECH','CLAN_TECH')
    s2=('HVY_FF_ARMOR_TECH','LT_FF_ARMOR_TECH','STEALTH_ARMOR_TECH','COMPACT_HS_TECH','XLGYRO_TECH','HDGYRO_TECH','CGYRO_TECH')
    profiles=[('normal',0,0)]+[(n,bit(n),0) for n in s1]+[(n,0,bit(n)) for n in s2]+[('combined',sum(bit(n) for n in s1),sum(bit(n) for n in s2))]
    rows=[];fixtures=[]
    for name,a,b in profiles:
        for complexrepair in (False,True):
            for quad in (False,True):
                rows.append(f'50 200 {int(quad)} {a} {b} {int(complexrepair)}')
                fixtures.append((f'{name}-{complexrepair}-{quad}',dict(name='u',tonnage=50,max_speed=0,movement='QUAD' if quad else 'BIPED',specials=a,specials2=b,core={'engine_rating':200}),complexrepair))
    for tons in (1,10,11,20,21,99,100,101):
        for rating in (0,1,20,21,100,101,399,400,401):
            rows.append(f'{tons} {rating} 0 0 0 1');fixtures.append((f'size-{tons}-{rating}',dict(name='u',tonnage=tons,max_speed=0,core={'engine_rating':rating}),True))
    raw='\n'.join(rows)+'\n';(OUT/'parts-oracle.input').write_text(raw)
    expected=subprocess.run([str(exe)],input=raw,text=True,capture_output=True,check=True).stdout
    (OUT/'parts-oracle.stdout').write_text(expected)
    actions=[D('ProperArmor'),D('ProperInternal'),D('ProperMyomer')]+[D('alias_part',p,loc) for p in range(394,420) for loc in range(8)]
    for (label,unit,complexrepair),line in zip(fixtures,expected.splitlines(),strict=True):
        case('repair','c-oracle-material-'+label,actions,[q('results',list(map(int,line.split())))],units=[unit],config={'complexrepair':complexrepair})
