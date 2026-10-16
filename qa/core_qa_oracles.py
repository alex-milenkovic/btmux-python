"""Compile independent C reference oracles, then compare documented CLI outputs.

No Python production code is loaded. Generated C and binaries stay under tmp.
"""
import json
from pathlib import Path
import re
import subprocess
from core_simulation_qa import ROOT,OUT,D,case,check as q

SRC=ROOT/'btmux/btmux/btech/src'


def function(source,name,returns='(?:int|float|void)'):
    m=re.search(r'^'+returns+r' '+name+r'\(',source,re.M)
    if not m:raise ValueError('missing C function '+name)
    start=source.index('{',m.start());pos=start+1;depth=1
    while depth:
        depth+=(source[pos]=='{')-(source[pos]=='}');pos+=1
    return source[m.start():pos]+'\n'


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'mt-oracle.c';exe=OUT/'mt-oracle'
    path.write_text(r'''#include <stdio.h>
#include <stdlib.h>
#include "mt19937ar.c"
int main(int argc,char**argv){
if(argc>2 && argv[1][0]=='s' && argv[1][1]=='t'){init_genrand(5489);int n=atoi(argv[2]);for(int i=0;i<n;i++)genrand_int32();printf("{\"index\":%d,\"state\":[",mti);for(int i=0;i<N;i++)printf("%s%lu",i?",":"",mt[i]);puts("]}");return 0;}
if(argc>2 && argv[1][0]=='a'){unsigned long keys[1000];int n=atoi(argv[2]);for(int i=0;i<n;i++)keys[i]=(unsigned long)(i*997+0x123);init_by_array(keys,n);}
else if(argc>1)init_genrand(strtoul(argv[1],NULL,0));
printf("[");for(int i=0;i<1300;i++)printf("%s%lu",i?",":"",genrand_int32());puts("]");return 0;}
''')
    subprocess.run(['cc','-O0','-I'+str(SRC/'include'),'-I'+str(SRC),str(path),'-o',str(exe)],check=True,capture_output=True)
    for label,args,rng in [('default',[],{}),('seed0',['0'],{'seed':0}),('seed5489',['5489'],{'seed':5489}),('high-mask',['4294972785'],{'seed':4294972785})]+[(f'array{n}',['array',str(n)],{'array_seed':[i*997+0x123 for i in range(n)]}) for n in (1,4,624,625,900)]:
        expected=json.loads(subprocess.check_output([str(exe),*args],text=True))
        case('randomness','c-oracle-'+label,[D('genrand_int32')]*1300,[q('results',expected),q('state.random.words_consumed',1300)],random=rng)
    source=(SRC/'btech/mech.utils.c').read_text()
    names=('AcceptableDegree','FindComponents','FindXYRange','FindRange','FindXY','FindBearing','FindZBearing','RealCoordToMapCoord','MapCoordToRealCoord','MyHexDist')
    prefix='''#include <stdio.h>
#include <math.h>
#define SCALEMAP 322.5
#define XSCALE 0.1547
#define ROOT3 558.58638544096289
#define ALPHA 93.097730906827152
#define ANGLE_ALPHA 0.28867513459481287
#define FULL_Y SCALEMAP
#define HALF_Y (0.5 * FULL_Y)
#define DEG2RAD(d) ((float)(d) * (3.14159265f / 180.f))
#define RAD2DEG(d) ((float)(d) * (180.f / 3.14159265f))
#define TWOPIOVER360 0.0174533
#define fcos cos
#define fsin sin
'''
    main='''int main(){float x,y;short hx,hy;
for(int ix=-1;ix<=14;ix++)for(int iy=-2;iy<=8;iy++){
float base=(float)(ix*ALPHA/2),yy=(float)(iy*SCALEMAP/4);
for(int side=-1;side<=1;side++){x=side<0?nextafterf(base,-INFINITY):side>0?nextafterf(base,INFINITY):base;RealCoordToMapCoord(&hx,&hy,x,yy);printf("hex %.17g %.17g %d %d\\n",x,yy,hx,hy);}}
for(int box=0;box<3;box++)for(int boundary=0;boundary<4;boundary++)for(int k=1;k<4;k++){
float yy=k*SCALEMAP/8;double edge=boundary==0?3*ALPHA+2*ANGLE_ALPHA*yy:boundary==1?3*ALPHA+2*ANGLE_ALPHA*(FULL_Y-(yy+HALF_Y)):boundary==2?6*ALPHA+2*ANGLE_ALPHA*yy:ALPHA+ROOT3-2*ANGLE_ALPHA*yy;
float xx=(float)(edge+box*ROOT3);if(boundary==1||boundary==2)yy+=HALF_Y;
for(int side=-1;side<=1;side++){x=side<0?nextafterf(xx,-INFINITY):side>0?nextafterf(xx,INFINITY):xx;RealCoordToMapCoord(&hx,&hy,x,yy);printf("hex %.17g %.17g %d %d\\n",x,yy,hx,hy);}}
for(int angle=-720;angle<=720;angle+=15){FindComponents(100,angle,&x,&y);printf("components %d %.17g %.17g\\n",angle,x,y);FindXY(100,200,angle,3,&x,&y);printf("xy %d %.17g %.17g\\n",angle,x,y);}
for(int x0=-2;x0<3;x0++)for(int y0=-2;y0<3;y0++){MapCoordToRealCoord(x0,y0,&x,&y);printf("center %d %d %.17g %.17g\\n",x0,y0,x,y);}
for(int x0=-3;x0<=3;x0++)for(int y0=-3;y0<=3;y0++)printf("bearing %d %d %d\\n",x0,y0,FindBearing(0,0,x0,y0));
return 0;}
'''
    path=OUT/'geometry-oracle.c';exe=OUT/'geometry-oracle'
    path.write_text(prefix+''.join(function(source,n) for n in names)+main)
    subprocess.run(['cc','-O0',str(path),'-lm','-o',str(exe)],check=True,capture_output=True)
    rows=subprocess.check_output([str(exe)],text=True).splitlines()
    groups={}
    for row in rows:
        kind,*cells=row.split();groups.setdefault(kind,[]).append(cells)
    for kind,rows in groups.items():
        actions=[];checks=[]
        for i,cells in enumerate(rows):
            if kind=='hex':
                x,y,hx,hy=map(float,cells);action=D('RealCoordToMapCoord',x,y);expected=[int(hx),int(hy)]
            elif kind in ('components','xy'):
                angle,x,y=map(float,cells);action=D('FindComponents',100,int(angle)) if kind=='components' else D('FindXY',100,200,int(angle),3);expected=[x,y]
            elif kind=='center':
                x,y,fx,fy=map(float,cells);action=D('MapCoordToRealCoord',int(x),int(y));expected=[fx,fy]
            else:
                x,y,expected=map(int,cells);action=D('FindBearing',0,0,x,y)
            actions.append(action);checks.append(q('results.'+str(i),expected))
        case('geometry','c-oracle-'+kind,actions,checks)
