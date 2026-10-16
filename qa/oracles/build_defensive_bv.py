"""Build a standalone C oracle from the original defensive-BV source body."""
from pathlib import Path
import argparse
import re

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, default=ROOT/'btmux/btmux/btech/src/btech')
parser.add_argument('--output', type=Path, default=ROOT/'tmp/core-bv-oracle.c')
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
source=(args.source_root/'mech.utils.c').read_text()
header=(args.source_root/'mech.h').read_text()
body=source[source.index('void Calc_AddOffBV('):source.index('/* Calculate Offensive BV 2.0')]
needed=set(re.findall(r'\b[A-Z][A-Z0-9_]+\b',body))
definitions={m[1]:m[0] for m in re.finditer(r'^#define\s+([A-Z][A-Z0-9_]*)\s+[^\n]+',header,re.M)}
needed |= {'AMMO_BASE_INDEX','BOMB_BASE_INDEX','SPECIAL_BASE_INDEX','CARGO_BASE_INDEX','WEAPON_BASE_INDEX','NUM_WEAPONS','NUM_BOMBS'}
for _ in range(3):
 for name in list(needed):
  if name in definitions:needed.update(re.findall(r'\b[A-Z][A-Z0-9_]+\b',definitions[name]))
shim='''#include <stdio.h>
#include <stdint.h>
#include <math.h>
struct slot {unsigned short type;};
struct section {int armor,internal,config;struct slot crit[12];};
typedef struct {int type,move,tons;unsigned int specials,specials2;float speed,jump;struct section sec[8];} MECH;
struct {int btech_cost_debug;} mudconf;
struct {unsigned int special;int battlevalue,ammo_bv;} MechWeapons[192];
#define SendDebug(x) ((void)0)
#define tprintf(...) ""
#define MechSpecials(m) ((m)->specials)
#define MechSpecials2(m) ((m)->specials2)
#define MechType(m) ((m)->type)
#define MechMove(m) ((m)->move)
#define MechTons(m) ((m)->tons)
#define MechJumpSpeed(m) ((m)->jump)
#define MMaxSpeed(m) ((m)->speed)
#define MechSections(m) ((m)->sec)
#define GetPartType(m,s,c) ((m)->sec[s].crit[c].type)
#define IsSpecial(p) ((p)>=SPECIAL_BASE_INDEX && (p)<CARGO_BASE_INDEX)
#define IsAmmo(p) ((p)>=AMMO_BASE_INDEX && (p)<BOMB_BASE_INDEX)
#define IsWeapon(p) ((p)>=WEAPON_BASE_INDEX && (p)<AMMO_BASE_INDEX)
#define Special2I(p) ((p)-SPECIAL_BASE_INDEX)
#define Ammo2WeaponI(p) ((p)-AMMO_BASE_INDEX)
#define Weapon2I(p) ((p)-WEAPON_BASE_INDEX)
int mech_armorpoints(MECH*m){int n=0;for(int i=0;i<8;i++)n+=m->sec[i].armor;return n;}
int mech_intpoints(MECH*m){int n=0;for(int i=0;i<8;i++)n+=m->sec[i].internal;return n;}
'''
main='''
int main(void){MECH m={0};
while(scanf("%d%d%d%u%u%f%f",&m.type,&m.move,&m.tons,&m.specials,&m.specials2,&m.speed,&m.jump)==7){
for(int s=0;s<8;s++){scanf("%d%d%d",&m.sec[s].armor,&m.sec[s].internal,&m.sec[s].config);for(int c=0;c<12;c++)scanf("%hu",&m.sec[s].crit[c].type);}
MechWeapons[0].special=AMS;MechWeapons[0].battlevalue=32;MechWeapons[0].ammo_bv=11;
MechWeapons[1].special=GAUSS;MechWeapons[1].battlevalue=320;
printf("%.9g\\n",Calculate_Defensive_BV(&m));
}return 0;}
'''
args.output.write_text(shim+'\n'.join(definitions[n] for n in sorted(needed) if n in definitions)+'\n'+body+main)
