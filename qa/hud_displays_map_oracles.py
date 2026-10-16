"""Complete uncolored map sketches from C literals and independent grid fixtures."""
from hud_displays_common import *
from hud_displays_catalog import CROOT
import ast


def c_patterns():
    text=(CROOT/'mech.maps.c').read_text().split('hexrow[2][310] = {',1)[1].split('};',1)[0]
    return [''.join(ast.literal_eval(s) for s in re.findall(r'"(?:[^"\\]|\\.)*"',part)) for part in text.split(',')]


def tactical_oracle(sx,sy,width,height,own,terrain):
    patterns=c_patterns();cols=3*width+1;rows=[list(' '*(cols+7)) for _ in range(2*height+4)]
    for y in range(2*height+1):rows[y+3][4:4+cols]=patterns[(y+sx)%2][:cols]
    for y in range(sy,sy+height):
        for x in range(sx,sx+width):
            glyph,elev=terrain.get((x,y),(' ',0));top,bottom={' ':(' ','_'),'~':('~','~'),'/':('#','+'),'?':('~','+')}.get(glyph,(glyph,glyph))
            line=4+2*(y-sy)-(x%2);col=5+3*(x-sx)
            rows[line][col:col+2]='**' if (x,y)==own else top*2
            rows[line+1][col:col+2]=bottom+(str(elev) if elev else bottom)
    for x in range(width):
        for i,char in enumerate(f'{sx+x:3d}'):rows[i][5+3*x]=char
    for y in range(height):rows[4+2*y][:3]=f'{sy+y:3d}';rows[4+2*y][-3:]=f'{sy+y:3d}'
    return [''.join(row) for row in rows]


def map_oracles():
    for size,pos,window in [((8,8),(0,0),(0,0,8,8)),((8,8),(7,0),(0,0,8,8)),((8,8),(0,7),(0,0,8,8)),((8,8),(7,7),(0,0,8,8)),((100,100),(50,50),(40,43,21,14)),((100,100),(51,50),(41,43,21,14)),((100,100),(50,50),(30,38,40,24))]:
        doc=document([unit(at=[*pos,0],tac_range=30)]);doc['map']['size']=list(size)
        if window[2]==40:doc['units'][0]['display']=dict(tacsize='24 40')
        sx,sy,width,height=window;terr={};hexes=[]
        choices=[('GRASSLAND',' ',0),('WATER','~',2),('LIGHT_FOREST','`',3),('HEAVY_FOREST','"',1),('ROAD','#',0),('BRIDGE','/',0),('HIGHWATER','?',0)]
        for x in range(sx,sx+width):
            for y in range(sy,sy+height):
                if (x,y)==pos:continue
                name,glyph,elev=choices[(x+y)%len(choices)];terr[x,y]=(glyph,elev);hexes.append(dict(at=[x,y],terrain=name,elevation=elev))
        doc['map']['hexes']=hexes;doc['actions']=[command('tactical')]
        yield Case('supplement/full-tactical-'+'-'.join(map(str,(*size,*pos,width))),doc).expect('results.0.rows',tactical_oracle(*window,pos,terr))
    for width,x in [(8,3),(9,4),(100,50),(100,51)]:
        doc=document([unit(at=[x,5,0],lrs_range=30)]);doc['map']['size']=[width,12];doc['map']['hexes']=[dict(at=[i,4],terrain='ROAD',elevation=i%9) for i in range(width)];doc['actions']=[command('lrs','t')]
        sx=max(0,x-35);ex=sx+70
        if ex>=width:ex=width-1;sx=max(0,ex-70)
        rows=['    '+''.join(f'{i:3d}'[digit] for i in range(sx,ex+1)) for digit in range(3)]
        for y in range(11):
            a=f'{y:3d} ';b='    '
            for i in range(sx,ex,2):
                glyph='#' if y==4 else ' '
                a+=glyph+' ' if sx%2 else ' '+glyph;b+=' '+glyph if sx%2 else glyph+' '
            if (ex-sx)%2==0:
                glyph='#' if y==4 else ' '
                if sx%2:a+=glyph;b+=' '
                else:b+=glyph
            b+=f' {y:<3d}';rows += [a,b]
        yield Case(f'supplement/full-lrs-{width}-{x}',doc).expect('results.0.rows',rows)
    # Ordinary LOS calculation, no overridden cell flags.
    doc=document([unit(at=[50,50,0],lrs_range=30)]);doc['map'].update(dark=True,mapvis=3,light=0,hexes=[dict(at=[80,50],terrain='LIGHT_FOREST',elevation=7)])
    doc['actions']=[command('lrs','l')]
    yield Case('supplement/real-dark-los-mask',doc).expect('results.0.cells',dict(x=80,y=50,terrain=None,elevation=None),'has_fields')
    # Four HUD corners and bearing-center requests have exact bounded start fields.
    for x,y in [(0,0),(7,0),(0,7),(7,7)]:
        doc=document([unit(at=[x,y,0],lrs_range=30)]);doc['map']['size']=[8,8];doc['actions']=[hud('key=test'),hud('t 4')]
        yield Case(f'supplement/hud-corner-{x}-{y}',doc).expect('results.1.records.0.payload',f'0,{max(0,y-2)},7,{min(8,y+2)-1},1000,main,-1,8,8')
