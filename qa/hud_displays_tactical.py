"""Tactical glyphs with independent coordinate-to-text offsets."""
from hud_displays_common import *
from hud_displays_contacts import pair


def cell(case,index,x,y,upper=None,lower=None,window=(40,43,21,14)):
    sx,sy,width,height=window;ry=3+(y-sy)*2+1-(x&1);rx=5+(x-sx)*3
    for dy,value in ((0,upper),(1,lower)):
        if value is not None:case.expect(f'results.{index}.rows.{ry+dy}',r'^.{'+str(rx)+'}'+re.escape(value),'regex')


def tactical():
    for name,n,row,meta in examples('tactical'):
        doc,u,t=pair();doc['units']=[u];doc.pop('diagnostic_cache');u['tac_range']=30;case=Case(name,doc,meta)
        if n==1:
            names={'grass':'GRASSLAND','water':'WATER','bridge':'BRIDGE','highwater':'HIGHWATER','road':'ROAD','forest':'LIGHT_FOREST'}
            terrain=row['terrain'];spec=dict(at=[50,49],terrain=names.get(terrain,names[row['underlay']]),elevation=int(row['elev']))
            if terrain in ('fire','smoke'):spec.update(overlay=terrain.upper(),duration=60)
            doc['map']['hexes']=[spec];doc['actions']=[command('tactical','' if row['mode']=='default' else row['mode'])]
            cell(case,0,50,49,'  ' if row['top']=='spaces' else row['top'],row['bottom'])
        elif n==2:
            doc['map']['hexes']=[dict(at=[50,50],terrain='GRASSLAND',elevation=int(row['difference']))]
            doc['actions']=[command('tactical',row['mode'])];cell(case,0,50,49,lower=',,' if row['cliff']=='true' else '__')
        elif n==3:
            doc['map']['dark']=row['dark']=='true';doc['actions']=[command('tactical',row['mode'])]
            case.expect('results.0.ok',row['outcome']=='map')
            if row['outcome']!='map':case.expect('results.0.message',row['outcome'])
        elif n==4:
            u['tac_range']=int(row['range'])
            if row['preference']!='unset':u['display']=dict(tacsize=row['preference'])
            doc['actions']=[command('tactical')];case.expect('results.0.window.2',int(row['width'])).expect('results.0.window.3',int(row['height'])).expect('results.0.warnings',int(row['warnings']),'length')
        elif n==5:
            if row['kind']!='none':doc['map']['map_objects']=[dict(kind='MINE',x=50,y=48,datac=5 if row['kind']=='trigger' else 1,datas=20)]
            if row['nb']=='false':doc['map']['hexes']=[dict(at=[50,49],terrain='MOUNTAINS',elevation=9)]
            doc['actions']=[command('tactical','m')];cell(case,0,50,48,lower='<>' if row['marker']=='<>' else '  ')
        else:
            t.update(formed('DS'));t['at']=[50,47,0 if row['state']!='airborne-below-orbit' else 5];t.pop('real');t['started']=row['state']!='shutdown';t['sections']=[dict(index=5,slots=[dict(index=0,special='DS_MECHDOOR')])];t['aerospace']=dict(landed=row['state']=='landed',bays=[2000,-1,-1,-1]);doc['units'].append(t);doc['diagnostic_cache']=[dict(viewer='u',target='target',flags=14)]
            doc['actions']=[command('tactical')]
            case.expect('results.0.plain','@','excludes' if row['door']=='absent' else 'contains')
            # Source hex directions, even-column parity; five solid side cells plus one bay.
            for x,y in [(50,46),(51,47),(51,48),(50,48),(49,48),(49,47)]:
                if row['footprint']=='1':cell(case,0,x,y,'  ')
                else:
                    sx,sy=40,43;ry=3+(y-sy)*2+1-(x&1);rx=5+(x-sx)*3
                    case.expect(f'results.0.rows.{ry}',r'^.{'+str(rx)+r'}(?:@@|==)','regex')
        yield case
