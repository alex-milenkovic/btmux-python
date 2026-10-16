"""Compile unchanged pure C bodies with explicit diagnostic macro fixtures."""
import hashlib
import json
import subprocess
from maps_environment_qa import ROOT,OUT

_cache=None
def oracle():
    global _cache
    if _cache is not None:return _cache
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'btmux/btmux/btech/src/btech'
    obj=(source/'map.obj.c').read_text();weather=(source/'map.weather.c').read_text()
    management=(source/'map.c').read_text()
    pre=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int map_width,map_height; char terrain[12][12]; } MAP;
#define BOUNDED(low,x,high) ((x)<(low)?(low):(x)>(high)?(high):(x))
#define WATER '~'
#define ICE '-'
#define BRIDGE '/'
#define ROAD '#'
#define GetTerrain(m,x,y) (m)->terrain[y][x]
#define SetTerrainBase(m,x,y,t) ((m)->terrain[y][x]=(t))
int dirs[6][2]={{0,-1},{1,0},{1,1},{0,1},{-1,1},{-1,0}};
struct {int x,y;char dir;} dirtable[4]={{1,0,'n'},{2,1,'e'},{1,2,'s'},{0,1,'w'}};
#define TAMMO 3
#define TBEAM 0
struct {int type;} MechWeapons[1];
static int raw[9];
#define MapEffectRain(m) raw[0]
#define MapEffectHvyRain(m) raw[1]
#define MapEffectBlizzard(m) raw[2]
#define MapEffectHvySnow(m) raw[3]
#define MapEffectFog(m) raw[4]
#define MapEffectSand(m) raw[5]
#define MapEffectHighWinds(m) raw[6]
#define MapEffectWinds(m) raw[7]
'''
    bodies=obj[obj.index('int FindXEven('):obj.index('#define NUM_SPREAD_HEX')]
    bodies+=obj[obj.index('int parse_coord('):obj.index('void add_entrances(')]
    bodies+=weather[weather.index('int calcWeatherGunEffects('):weather.index('int calcWeatherPilotEffects(')]
    bodies+=management[management.index('int water_distance('):management.index('int map_checkmapfile(')]
    main=r'''
int main(int argc,char **argv) {
 if(!strcmp(argv[1],"coord")) {
   int wind=atoi(argv[2]),i=atoi(argv[3]),odd=atoi(argv[4]);
   printf("[%d,%d]\n",odd?FindXOdd(wind,i):FindXEven(wind,i),odd?FindYOdd(wind,i):FindYEven(wind,i));
 } else if(!strcmp(argv[1],"parse")) {
   MAP map={atoi(argv[2]),atoi(argv[3])};int x=atoi(argv[6]),y=atoi(argv[7]);
   int ok=parse_coord(&map,atoi(argv[4]),argv[5],&x,&y);
   printf("[%d,%d,%d]\n",ok,x,y);
 } else if(!strcmp(argv[1],"bridge")) {
   MAP map={atoi(argv[2]),atoi(argv[3])};
   for(int y=0;y<map.map_height;y++)for(int x=0;x<map.map_width;x++)map.terrain[y][x]=argv[4][y*map.map_width+x];
   make_bridges(&map);printf("[");
   for(int y=0;y<map.map_height;y++)for(int x=0;x<map.map_width;x++)printf("%s%d",x||y?",":"",map.terrain[y][x]);
   printf("]\n");
 } else {
   MechWeapons[0].type=atoi(argv[2]);for(int i=0;i<8;i++)raw[i]=atoi(argv[i+3]);
   printf("%d\n",calcWeatherGunEffects(NULL,0));
 }
 return 0;
}
'''
    path=OUT/'source-oracle.c';path.write_text(pre+bodies+main)
    result=subprocess.run(['cc','-std=gnu99','-O0',str(path),'-o',str(OUT/'source-oracle')],text=True,capture_output=True)
    (OUT/'source-oracle-build.txt').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stderr)
    (OUT/'source-oracle-hashes.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,source/'map.obj.c',source/'map.weather.c',source/'map.c')},indent=2)+'\n')
    def run(*args):return json.loads(subprocess.check_output([str(OUT/'source-oracle'),*map(str,args)],text=True))
    _cache=run;return run
