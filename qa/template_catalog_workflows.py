"""Real designs through ordinary commands; expectations come from the QA C oracle."""
from qa.template_catalog_common import *
from qa.template_catalog_oracle import parse,check
DESIGNS=['WVR-6R','BLR-1G','WHM-6R','MadCat-Prime','Grendel-Prime','GOL-1H','Demolisher','Cyrano','Sloth','Monitor','DS.Union','DS.Aero','MechWarrior']

def run():
    a=Audit('workflows')
    selected=os.environ.get('QA_CATALOG_DESIGNS','').split(',') if os.environ.get('QA_CATALOG_DESIGNS') else DESIGNS
    extras=os.environ.get('QA_CATALOG_EXTRAS','1')!='0'
    if selected!=DESIGNS:
        assert set(selected)<=set(DESIGNS)
        previous=json.loads((OUT/'workflows.json').read_text())['results']
        assert len(previous)>=30,'Targeted retry requires a completed initial run'
        replaced=set(selected)|{r+'-reload' for r in selected}|({'wolverine-restore-isolation'} if extras else set())
        a.rows=[r for r in previous if r['id'] not in replaced and not (extras and '-mount' in r['id'])]
    for ref in selected:
        expected=parse(ref)
        actions=[T('load',ref),R(),I()]
        gameplay=ref not in ('DS.Union','DS.Aero','MechWarrior')
        # Select a source energy or ballistic mount; avoid cluster expectation
        # dependency in the mandatory class motion/fire cases.
        weapon=next((i for i,m in enumerate(expected['mounts']) if 'PPC' in m['name'] or 'Laser' in m['name'] or 'AC/' in m['name']),0)
        if ref=='WVR-6R':weapon=0
        mount=expected['mounts'][weapon] if gameplay else None
        units=[{'name':'u','at':[6,6,3 if ref=='Cyrano' else 0]},
               {'name':'target','at':[6,2,0],'team':2,'facing':180,'desired_facing':180,
                'sections':[{'index':i,'armor':150,'armor_orig':150,'rear':150,'rear_orig':150} for i in (2,3,4)]}]
        if gameplay:
            actions += [pilot(),C('startup'),A(40),C('speed','10.75'),A(60),C('speed','stop'),A(10),I()]
            if expected['jump_speed']:
                actions += [C('jump','180 2'),A(2),I(),A(28),A(12),I(),C('jump','180 12'),I()]
            elif ref in ('BLR-1G','WHM-6R'):actions += [C('jump','180 2')]
            actions += [C('lock','01'),A(1),C('fire',f'{weapon} 01'),I(),A(mount['recycle']),I()]
            if expected['type']==0:actions += [E('repair','CT A 1')]
        actions += [T('save','QA-'+ref,clock='QA fixed'),I()]
        d=doc(actions,units=units,ordinary=gameplay)
        if ref=='Monitor':d['map']['default']=['WATER',3]
        out=a.cli(ref,d);results=out['results'];initial=results[2]['units']['u']
        a.eq('ordinary load',results[0]['ok'],True);check(a,expected,results[1],initial)
        inspections=[r for r in results if isinstance(r,dict) and 'units' in r]
        if gameplay:
            moved=inspections[1]['units']['u'];a.eq('crossed a hex',(moved['x'],moved['y'])!=(initial['x'],initial['y']),True)
            for action,result in zip(actions,results):
                if isinstance(result,dict) and 'accepted' in result:
                    allowed=not (action.get('name')=='jump' and (action['args']=='180 12' or not expected['jump_speed']))
                    a.eq('ordinary '+action.get('name',''),result['accepted'],allowed)
            shot=next(r for r in results if isinstance(r,dict) and 'attack' in r)
            a.eq('source weapon damage',shot['attack']['damage_dealt'],mount['damage']);a.eq('hit',shot['attack']['hit'],True)
            shot_i=next(i for i,r in enumerate(results) if r is shot);fired=results[shot_i+1]['units']['u'];recycled=results[shot_i+3]['units']['u']
            a.eq('source heat',fired['weap_heat'],mount['heat']);a.eq('source recycle',fired['weapons'][weapon]['recycle'],mount['recycle'])
            a.eq('recycle completes',recycled['weapons'][weapon]['recycle'],0)
            before=sum(s['data'] for ss in expected['slots'] for s in ss if 193<=s['source_part_id']<385)
            after=sum(s['data'] for ss in fired['sections'] for s in ss['slots'] if 193<=s['type']<385)
            a.eq('one ballistic round or no energy ammo',before-after,1 if 'AC/' in mount['name'] else 0)
            if expected['jump_speed']:
                jump=next(i for i,act in enumerate(actions) if act.get('name')=='jump')
                airborne=results[jump+2]['units']['u'];landed=results[jump+5]['units']['u'];rejected=results[jump+7]['units']['u']
                # C mech.h:47 rounded reciprocal remains the heat consumer's
                # convention; C2 changes only shared cap recomputation.
                a.eq('source jump heat while airborne',airborne['plus_heat'],max(3,expected['jump_speed']*.0930233))
                a.eq('jump changed position',(landed['x'],landed['y'])!=(moved['x'],moved['y']),True)
                a.eq('source two-hex south landing',landed['at'],[moved['x'],moved['y']+2,0])
                a.eq('persistent jump MP',landed['jump_mp'],expected['jump_speed']/10.75)
                a.eq('range rejection preserves position',rejected['at'],landed['at'])
                a.eq('range rejection preserves ammo',rejected['sections'],landed['sections'])
                a.eq('no pending jump/stabilization',any('JUMP' in e['kind'] for e in results[jump+5]['events']),False)
        custom=OUT/'workflows'/ref/'custom'
        reloaded=a.cli(ref+'-reload',doc([T('load','QA-'+ref),R(),I()]),root=custom)
        a.eq('fresh process custom origin',reloaded['results'][0]['origin'],'custom')
        check(a,expected,reloaded['results'][1],reloaded['results'][2]['units']['u'])
        a.save()
    if not extras:a.save();return
    # Rear arc and ammo mount cases have separate fresh random/target state.
    for ref,index,damage in [('BLR-1G',5,5),('BLR-1G',0,2),('WHM-6R',7,12)]:
        expected=parse(ref);m=expected['mounts'][index];rear=bool(m['fire']&32)
        acts=[T('load',ref),pilot(),C('startup'),A(40),I(),C('lock','01'),A(1),C('fire',f'{index} 01'),I(),A(m['recycle']),I(),E('repair','CT A 1'),T('save','QA-SHOT',clock='QA')]
        d=doc(acts,ordinary=True,units=[{'name':'u','at':[6,6,0]},{'name':'target','at':[6,9 if rear else 3,0],'team':2,'facing':0 if rear else 180,'desired_facing':0 if rear else 180,'sections':[{'index':i,'armor':150,'rear':150} for i in (2,3,4)]}])
        out=a.cli(f'{ref}-mount{index}',d);shot=out['results'][7];state=out['results'][8]['units']['u']
        a.eq('selected mount accepts',shot['accepted'],True);a.eq('exact damage',shot['attack']['damage_dealt'],damage)
        a.eq('heat',state['weap_heat'],m['heat']);a.eq('recycle',state['weapons'][index]['recycle'],m['recycle'])
        before=out['results'][4]['units']['u'];ammo=lambda u:sum(s['data'] for sec in u['sections'] for s in sec['slots'] if 193<=s['type']<385)
        a.eq('bin consumption',ammo(before)-ammo(state),0 if rear else 1)
        reloaded=a.cli(f'{ref}-mount{index}-reload',doc([T('load','QA-SHOT'),R(),I()]),root=OUT/'workflows'/f'{ref}-mount{index}'/'custom')
        check(a,expected,reloaded['results'][1],reloaded['results'][2]['units']['u'])
    acts=[T('load','WVR-6R'),T('load','WVR-6R',unit='v'),I(),E('repair','CT A 1'),T('restore'),I(),pilot(),C('startup'),A(40),C('lock','02'),A(1),C('fire','0 02'),I()]
    d=doc(acts,ordinary=True,units=[{'name':'u','at':[6,6,0]},{'name':'v','at':[4,6,0]},{'name':'target','at':[6,2,0],'team':2,'facing':180,'desired_facing':180}])
    out=a.cli('wolverine-restore-isolation',d)
    a.eq('other loaded unit unaffected',out['results'][2]['units']['v']['sections'],out['results'][5]['units']['v']['sections'])
    a.eq('original restored',out['results'][5]['units']['u']['sections'][4]['armor'],20)
    a.eq('reseated pilot resumes fire',out['results'][11]['attack']['damage_dealt'],5)
    a.save()

if __name__=='__main__':run()
