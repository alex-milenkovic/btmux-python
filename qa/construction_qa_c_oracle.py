"""Compile unmodified source engine/internal bodies behind a minimal C fixture."""
from qa.construction_qa_common import *
from qa.construction_qa_numeric import table,blank
import re

def function(source,name):
    m=re.search(r'(?m)^(?:static )?(?:int|void) '+name+r'\([^;]*?\)\s*\{',source);assert m,name
    start=m.start();pos=m.end();depth=1
    while depth:
        depth+=(source[pos]=='{')-(source[pos]=='}');pos+=1
    return source[start:pos]
def compile_oracle():
    source=(CROOT/'mech.consistency.c').read_text();pre='''#include <stdio.h>
#include <stdlib.h>
#include <math.h>
typedef struct {int type,move,tons,rating,specials,mynum;int oi[8],ci[8];} MECH;
#define MAX(a,b) ((a)>(b)?(a):(b))
#define CTORSO 4
#define LTORSO 2
#define RTORSO 3
#define LARM 0
#define RARM 1
#define LLEG 5
#define RLEG 6
#define HEAD 7
#define CLASS_MECH 0
#define CLASS_VEH_GROUND 1
#define CLASS_VTOL 2
#define CLASS_VEH_NAVAL 3
#define MOVE_TRACK 1
#define MOVE_WHEEL 2
#define MOVE_HOVER 3
#define MOVE_VTOL 4
#define MOVE_HULL 5
#define MOVE_FOIL 6
#define MOVE_SUB 9
#define NUM_SECTIONS 8
#define MechType(m) ((m)->type)
#define MechMove(m) ((m)->move)
#define MechTons(m) ((m)->tons)
#define MechEngineSize(m) ((m)->rating)
#define MechSpecials(m) ((m)->specials)
#define MechIsQuad(m) ((m)->move==8)
#define GetSectOInt(m,i) ((m)->oi[i])
#define GetSectInt(m,i) ((m)->ci[i])
#define SetSectOInt(m,i,v) ((m)->oi[i]=(v))
#define SetSectInt(m,i,v) ((m)->ci[i]=(v))
#define MechType_Ref(m) "QA"
#define SendError(...) ((void)0)
#define tprintf(...) ""
#define Name(...) "QA"
#define tank_int(m) MAX((MechTons(m)+5)/10,1)
#define Table(i,j) (MechIsQuad(mech)?quad_loc_table[i][j]:mech_loc_table[i][j])
int round_to_halfton(int x) {return x/512*512+(x%512>1?512:0);}
'''
    for key,bit in [('ICE_TECH',22),('XL_TECH',21),('XXL_TECH',25),('LE_TECH',24),('CE_TECH',26)]:pre+=f'#define {key} (1<<{bit})\n'
    arrays='\n'.join(re.search(r'static (?:char|short) '+name+r'\[\].*?\};',source,re.S)[0] for name in ('mech_loc_table','quad_loc_table','int_data','engine_data'))
    bodies='\n'.join(function(source,n) for n in ('susp_factor','engine_weight','real_int','vehicle_int_check','mech_int_check'))
    main='''
int main(void){MECH m={0}; while(scanf("%d %d %d %d %d",&m.type,&m.move,&m.tons,&m.rating,&m.specials)==5){for(int i=0;i<8;i++){m.oi[i]=0;m.ci[i]=0;} mech_int_check(&m,0);printf("%d %d",susp_factor(&m),engine_weight(&m));for(int i=0;i<8;i++)printf(" %d",m.oi[i]);puts("");}return 0;}
'''
    path=OUT/'oracle';path.mkdir(exist_ok=True);(path/'source.c').write_text(pre+arrays+bodies+main)
    p=subprocess.run(['cc','-std=gnu99',str(path/'source.c'),'-lm','-o',str(path/'oracle')],capture_output=True,text=True);(path/'compile.stderr').write_text(p.stderr);assert p.returncode==0,p.stderr
    return path

def run(a):
    path=compile_oracle();source=(CROOT/'mech.consistency.c').read_text();body=re.search(r'engine_data\[\]\[2\].*?\};',source,re.S)[0]
    ratings=[int(x) for x in re.findall(r'\{(\d+),',body)]
    records=[];actions=[];indices=[]
    for cls,move in [(0,0),(1,1)]:
        for flag in (0,1<<21,1<<25,1<<24,1<<26,(1<<22)|(1<<21)):
            name=' '.join(table('specials')[i] for i in range(31) if flag>>i&1)
            # Explicitly reestablish class and flags before each diagnostic group.
            actions += [E('settype','M' if cls==0 else 'G'),E('setmove','Biped' if cls==0 else 'Track'),E('deltech','all')]
            if name:actions += [E('addtech',name)]
            for rating in ratings:
                records.append((cls,move,50,rating,flag));actions += [dict(op='core',values={'engine_rating':rating,'max_speed':0}),D('engine_weight')];indices.append(len(actions)-1)
    raw=''.join(' '.join(map(str,r))+'\n' for r in records);(path/'input.txt').write_text(raw)
    p=subprocess.run([str(path/'oracle')],input=raw,text=True,capture_output=True,check=True);(path/'stdout.txt').write_text(p.stdout)
    expected=[int(line.split()[1]) for line in p.stdout.splitlines()];assert len(expected)==len(records)
    d=a.run('weights/compiled-C-all-engine-rows',document(actions,units=[blank()]))
    for fixture,index,want in zip(records,indices,expected):a.eq('unmodified engine_weight '+str(fixture),d['results'][index],want)
