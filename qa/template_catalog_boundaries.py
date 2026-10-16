"""Independent configuration, immutable storage, EOL, audit and C2 boundaries."""
from qa.template_catalog_common import *
from qa.construction_qa_numeric import blank
from qa.template_catalog_oracle import f32
import shutil

def run():
    a=Audit('boundaries');fresh=OUT/'fresh-dependency'
    result=a.command('fresh-setup',['setup','--path',fresh]);a.eq('explicit setup pin',result['observed_revision'],PIN)
    for name,args in [('fresh-verify',['verify','--path',fresh]),('fresh-idempotent',['setup','--path',fresh]),('raw-verify',['verify','--path',UP])]:
        r=a.command(name,args);a.eq('pinned revision',r['observed_revision'],PIN);a.eq('verified',r['outcome'].startswith('verified'),True)
    default=ROOT/'btmux-mechs'
    if not default.exists():default.symlink_to(fresh,target_is_directory=True)
    for line,outline,row in feature_rows('configuration'):
        if 'precedence' not in outline:continue
        for elsewhere in (False,True):
            cwd=OUT if elsewhere else ROOT;d=doc([T('lookup','WVR-6R')]);option=row['option']
            extra={'BTMUX_TEMPLATE_CATALOG':os.path.relpath(fresh,cwd)} if row['environment']!='none' else {'BTMUX_TEMPLATE_CATALOG':''}
            if option=='omitted':d['construction'].pop('catalog')
            else:d['construction']['catalog']={'true':True,'false':False}.get(option,os.path.relpath(UP,cwd))
            out=a.cli(f'configuration-{line}-{int(elsewhere)}',d,cwd=cwd,extra_env=extra)
            result=out['results'][0];a.eq('precedence lookup',result.get('selected',{}).get('origin') if result.get('selected') else None,None if row['selected']=='disabled' else 'upstream')
    for ref in ('WVR-6R','wvr-6r','BLR-1G','WHM-6R'):
        out=a.cli('lookup-'+ref.replace('wvr','lower'),doc([T('list'),T('lookup',ref)]))
        a.eq('upstream selection',out['results'][1]['selected']['path'],'WVR-6R' if ref.lower()=='wvr-6r' else ref)
        a.eq('full ordinary listing',len(out['results'][0]['entries']),1745)
    names=sorted(json.loads((OUT/'startup.json').read_text())['catalog_hashes'])
    out=a.cli('all-ordinary-reference-lookups',doc([T('lookup',name) for name in names]))
    report=json.loads((OUT/'inventory/raw-forward/stdout.json').read_text())
    byname={row['path']:row for row in report['files']}
    for name,result in zip(names,out['results']):
        a.eq('ordinary reference '+name,result['selected']['path'],byname[name]['reference_winner'])
        a.eq('raw design is discoverable '+name,byname[name]['discoverable'],True)
    d=doc([T('lookup','WVR-6R')]);d['construction']['catalog']=str(UP)
    out=a.cli('explicit-over-missing-env',d,extra_env={'BTMUX_TEMPLATE_CATALOG':str(OUT/'absent')})
    a.eq('explicit wins bad environment',out['results'][0]['selected']['origin'],'upstream')
    d['construction']['catalog']=str(OUT/'absent')
    a.cli('missing-explicit-over-good-env',d,extra_env={'BTMUX_TEMPLATE_CATALOG':str(fresh)},exit=1)
    d['construction']['catalog']=False
    out=a.cli('disabled-over-missing-env',d,extra_env={'BTMUX_TEMPLATE_CATALOG':str(OUT/'absent')})
    a.eq('disabled means no catalog fallback',out['results'][0]['path'],None)
    for state,path,outcome in [('missing',OUT/'absent','missing-error'),('drift',fresh,'drift-error'),('wrong',fresh,'revision-error')]:
        p=fresh/'WVR-6R';before=p.read_bytes()
        if state=='drift':p.write_bytes(before+b'Name { Drift }\n')
        if state=='wrong':subprocess.run(['git','-C',str(fresh),'checkout','--detach',PIN+'^'],check=True,capture_output=True)
        try:
            r=a.command('verify-'+state,['verify','--path',path],exit=1);a.eq('actionable outcome',r['outcome'],outcome)
            d=doc([]);d['construction']['catalog']=str(path);out=a.cli('session-'+state,d,exit=1)
            a.eq('configuration error',outcome in out['error'],True)
            if state=='drift':a.eq('verification never normalizes',p.read_bytes()==before+b'Name { Drift }\n',True)
        finally:
            if state=='drift':p.write_bytes(before)
            if state=='wrong':subprocess.run(['git','-C',str(fresh),'checkout','--detach',PIN],check=True,capture_output=True)
    # Dual-origin shadow, immutable per-unit restore and replay.
    acts=[T('load','WVR-6R'),T('load','WVR-6R',unit='v'),E('settons','40'),T('save','WVR-6R',clock='QA'),T('list'),T('lookup','WVR-6R'),T('load','WVR-6R',unit='v'),R('v'),T('restore'),R(),T('load','WVR-6R',unit='v',origin='upstream'),R('v'),T('load','WVR-6R',unit='v',origin='custom'),R('v'),{'op':'diagnose','kind':'do_magic','unit':'v','args':[]},R('v')]
    out=a.cli('origin-shadow',doc(acts,units=[{'name':'u'},{'name':'v'}]));rs=out['results']
    a.eq('custom chosen',rs[5]['selected']['origin'],'custom');a.eq('all origins',sorted(x['origin'] for x in rs[5]['ambiguities']),['custom','upstream'])
    for idx,tons in ((7,40),(9,55),(11,55),(13,40),(15,40)):a.eq('origin retains design '+str(idx),rs[idx]['tonnage'],tons)
    a.eq('restore origin',rs[9]['template_origin'],'upstream');a.eq('replay custom max speed',rs[15]['max_speed'],86)
    # All writes are aimed at actual production mutation guards. Upstream is
    # hashed before/after by the final integrity audit, never chmod-dependent.
    for op in ('save','write','delete'):
        out=a.cli('reject-origin-'+op,doc([T('load','WVR-6R'),T(op,'WVR-6R',origin='upstream',text='forbidden')]))
        a.eq('upstream mutation refused',out['results'][1]['ok'],False)
    for overlap in (UP,UP/'nested',UP.parent):
        d=doc([]);d['construction']['root']=str(overlap);d['construction']['files']={'WVR-6R':'forbidden'}
        out=a.cli('overlap-'+str(len(a.rows)),d,exit=1);a.eq('overlap rejected', 'overlap' in out['error'],True)
    custom=OUT/'guard-custom';custom.mkdir(exist_ok=True);link=custom/'escape'
    if not link.exists():link.symlink_to(UP,target_is_directory=True)
    for operation in ('write','delete'):
        out=a.cli('symlink-'+operation,doc([T(operation,'escape/WVR-6R',text='forbidden'),T('write','CUSTOM',text=modern())]),root=custom)
        a.eq('symlink refused',out['results'][0]['ok'],False);a.eq('custom still writable',out['results'][1]['ok'],True)
    d=doc([]);d['construction']['files']={'escape/WVR-6R':'forbidden'}
    a.cli('symlink-fixture',d,root=custom,exit=1)
    d=doc([]);d['file_root']=str(UP/'qa-forbidden-map-root')
    out=a.cli('map-root-overlap',d,exit=1);a.eq('inherited map storage guard','overlap' in out['error'],True)
    maproot=OUT/'guard-maps';maproot.mkdir(exist_ok=True)
    if not (maproot/'WVR-6R').exists():(maproot/'WVR-6R').symlink_to(UP/'WVR-6R')
    d=doc([]);d['file_root']=str(maproot);d['files']={'WVR-6R':{'text':'forbidden'}}
    out=a.cli('map-fixture-symlink',d,exit=1);a.eq('inherited map fixture guard','read-only' in out['error'],True)
    r=a.command('audit-output-upstream',['audit','--path',UP,'--output',UP/'qa-forbidden-report'],exit=1)
    a.eq('audit report cannot mutate dependency',r['outcome'],'incomplete')
    out=a.cli('custom-editor',doc([T('load','WVR-6R'),E('savetemp2','CUSTOM',clock='QA'),T('read','CUSTOM'),T('delete','CUSTOM')]))
    a.eq('editor custom save',out['results'][1]['ok'],True);a.eq('custom delete',out['results'][3]['ok'],True)
    for ref in ('WVR-6R','BLR-1G','WHM-6R','Grendel-Prime'):
        semantic=[]
        for ending in ('LF','CRLF'):
            text=(UP/ref).read_bytes().replace(b'\r\n',b'\n').decode()
            if ending=='CRLF':text=text.replace('\n','\r\n')
            d=doc([T('load',ref),R(),E('restore'),R(),E('loadnew',ref),R()],catalog=False);d['construction']['files']={ref:text}
            out=a.cli(ref+'-'+ending,d)
            reads=[out['results'][i] for i in (1,3,5)];sem=[{k:r[k] for k in ('slots','type','move','tonnage','max_speed','jump_speed','real_num_sinks','name','tac_range','radio_range')} for r in reads]
            a.eq('ordinary editor restore parity',sem,[sem[0]]*3);semantic.append(sem[0])
        a.eq('LF CRLF semantic parity',*semantic)
    for line,outline,r in feature_rows('line_endings'):
        if 'parser behavior' not in outline:continue
        fixture=r['fixture'];text='Tons { 55 }\n'
        suffix={'valid-multiline':'Name { First\nsecond\nlast }\nLeft_Arm\nArmor { 14 }\n',
                'unknown-section':'BadSection\n','unknown-mode':'Left_Arm\nCRIT_1 { IS.MediumLaser - NotAMode 3 }\n',
                'CRIT13':'Left_Arm\nCRIT_13 { HeatSink - - }\n','interior-carriage-return-section':'Left_\rArm\n',
                'unterminated-final-section':'Left_Arm'}[fixture];text+=suffix
        if r['ending']=='CRLF':text=text.replace('\n','\r\n')
        if r['ending']=='mixed':text=text.replace('second\n','second\r\n')
        d=doc([D('load_fields','TEST'),R()],catalog=False);d['construction']['files']={'TEST':text}
        out=a.cli('eol-'+str(line),d);a.eq('earlier tons retained',out['results'][1]['tonnage'],55)
        if fixture=='valid-multiline':a.eq('source multiline',out['results'][1]['name'],'First\r\nsecond\r\nlast ')
        else:
            a.eq('source error',out['results'][0]['ok'],False)
            cause='mode' if fixture=='unknown-mode' else 'bounds' if fixture=='CRIT13' else 'section'
            a.eq('concrete rejection cause',cause in out['results'][0]['error'].lower(),True)
            if fixture=='unknown-mode':a.eq('part write precedes invalid mask',out['results'][1]['slots'][0][0]['source_part_id'],79)
    for ending in ('LF','CRLF'):
        content=legacy(specials=32,radio=55)
        if ending=='CRLF':content=content.replace('\n','\r\n')
        d=doc([T('load','OLD'),R(),I()],catalog=False);d['construction']['files']={'OLD':content}
        out=a.cli('legacy-'+ending,d);a.eq('legacy literal4196',out['results'][2]['units']['u']['specials']&32,0);a.eq('legacy radio',out['results'][1]['radio_range'],55)
    for flag in ('Clan','DoubleHS'):
        for reverse in (False,True):
            fields=['Heat_Sinks { 31 }',f'Specials {{ {flag} }}']
            if reverse:fields.reverse()
            d=doc([D('load_fields','CAP'),R(),I()],catalog=False);d['construction']['files']={'CAP':'\r\n'.join(fields)+'\r\n'}
            out=a.cli(f'sink-capacity-{flag}-{int(reverse)}',d)
            a.eq('C dissipation survives flag assignment',out['results'][1]['real_num_sinks'],31)
            a.eq('partial physical group retains capacity',out['results'][2]['units']['u']['num_sinks'],15.5)
    d=doc([T('load','CAP'),R()],catalog=False)
    d['construction']['files']={'CAP':legacy(specials=8,radio=55).replace('50 20 40 20 10 ','50 20 40 20 31 ')}
    out=a.cli('legacy-sink-capacity',d);a.eq('legacy C dissipation preserved',out['results'][1]['real_num_sinks'],31)
    for line,outline,r in feature_rows('jump_cap'):
        if 'corrected shared' in outline:speed=float(r['speed']);count=int(r['slots']);improved=int(r['improved']);expected=float(r['jump'])
        else:speed=64.5;count=4;improved=0;expected=43
        u=blank();u['max_speed']=speed;u['specials2']=128*improved;u['core']['real_num_sinks']=10
        for j in range(count):u['sections'][j//12]['slots'][j%12].update(type=404,firemode={'destroyed':1,'disabled':2}.get(r.get('condition'),0))
        out=a.cli('jump-'+str(line),doc([{'op':'diagnose','kind':'do_sub_magic','args':[]},R(),I()],catalog=False,units=[u]))
        a.eq('approved C2',out['results'][1]['jump_speed'],expected)
        a.eq('independent float32 formula',out['results'][1]['jump_speed'],min(count//2 if improved else count,int(f32(speed)/10.75*(1 if improved else 2/3)))*10.75)
        a.eq('unchanged engine sink calculation',out['results'][1]['real_num_sinks'],8)
    for loud in (False,True):
        u=blank();u['max_speed']=64.5;u['specials']=8;u['core']['real_num_sinks']=99
        for j in range(3):u['sections'][0]['slots'][j].update(type=403)
        for j in range(8):u['sections'][1]['slots'][j].update(type=404)
        out=a.cli('loud-sinks-'+str(int(loud)),doc([{'op':'diagnose','kind':'do_sub_magic','args':[loud]},R(),I()],catalog=False,units=[u]))
        a.eq('loud leaves corrected jet cap',out['results'][1]['jump_speed'],43)
        a.eq('source loud sink assignment order',out['results'][1]['real_num_sinks'],99 if loud else 18)
        a.eq('source full original sink count',out['results'][2]['units']['u']['original_sinks'],18)
    for movement in ('HULL','FOIL'):
        for terrain,z,allowed in [('WATER',0,True),('GRASSLAND',0,False),('WATER',1,False)]:
            d=doc([C('heading','120'),C('speed','10.75'),I()],catalog=False,
                  units=[{'name':'u','class':'NAVAL','movement':movement,'started':True,'at':[6,6,z]}])
            d['map']['default']=[terrain,3 if terrain=='WATER' else 0]
            out=a.cli(f'naval-{movement}-{terrain}-{z}',d)
            a.eq('C surface heading guard',out['results'][0]['accepted'],allowed)
            a.eq('C surface speed guard',out['results'][1]['accepted'],allowed)
    # Every small audit fixture executes the real public inventory/load loop.
    for line,outline,r in feature_rows('audit'):
        if 'complete failure reporting' not in outline:continue
        path=OUT/'audit-fixtures'/str(line);path.mkdir(parents=True,exist_ok=True)
        fixture=r['fixture'];valid='Type { Mech }\nTons { 50 }\n';files={'A':valid}
        if fixture=='valid-invalid-valid':files={'A':valid,'B':'Type { Mech }\nBadSection\n','Z':valid}
        if fixture.startswith('same-key'):files={'A':valid,'sub/a':valid if fixture=='same-key-two-valid-files' else 'BadSection\n'}
        if fixture=='unknown-type-and-valid':files={'A':'Type { unknown }\n','Z':valid}
        if fixture=='valid-plus-git-metadata':files['.git/ignored']='bad'
        if fixture=='nested-valid-not-discoverable':files={'one/two/Z':valid}
        for name,text in files.items():p=path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        result=a.command('audit-fixture-'+str(line),['audit','--path',path],exit=2 if int(r['failures']) else 0)
        for key in ('candidates','successes','failures'):a.eq('complete '+key,result[key],int(r[key]))
        a.eq('collision groups',len(result['ambiguities']),int(r['ambiguities']));a.eq('honest outcome',result['outcome'],r['outcome'])
        if fixture=='nested-valid-not-discoverable':a.eq('deep file attempted without reference visibility',result['files'][0]['discoverable'],False)
    a.save()

if __name__=='__main__':run()
