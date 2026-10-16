"""Independent raw inventory and public per-file loads into separate fresh units."""
from qa.template_catalog_common import *
from collections import Counter
from qa.construction_qa_catalog import source_weapons
import re

def git(*args,input=None):
    return subprocess.check_output(['git','-C',str(UP),*args],input=input)

def run():
    a=Audit('inventory')
    # Independent walk: enumerate raw data before consulting production reports.
    paths=[];excluded=[]
    for directory,dirs,files in os.walk(UP,followlinks=False):
        for name in list(dirs):
            p=Path(directory)/name
            if name=='.git' or p.is_symlink():dirs.remove(name);excluded.append(p.relative_to(UP).as_posix())
        for name in files:
            p=Path(directory)/name
            if p.is_symlink():excluded.append(p.relative_to(UP).as_posix())
            else:paths.append(p.relative_to(UP).as_posix())
    paths.sort();hashes={name:sha((UP/name).read_bytes()) for name in paths}
    manifest=sha(''.join(n+'\t'+hashes[n]+'\n' for n in paths).encode())
    records=[r.split(b'\t',1) for r in git('ls-tree','-rz',PIN).split(b'\0') if r]
    objects=git('cat-file','--batch',input=b''.join(r[0].split()[2]+b'\n' for r in records))
    offset=0;blob_paths=[];logical=[];raw_equal=[]
    for metadata,name in records:
        end=objects.index(b'\n',offset);size=int(objects[offset:end].split()[-1]);expected=objects[end+1:end+1+size];offset=end+size+2
        name=name.decode();blob_paths.append(name);actual=(UP/name).read_bytes()
        logical.append(actual.replace(b'\r\n',b'\n')==expected.replace(b'\r\n',b'\n'));raw_equal.append(actual==expected)
    forward=a.command('raw-forward',['audit','--path',UP],exit=2)
    a.eq('independent candidate paths',[r['path'] for r in forward['files']],paths)
    a.eq('pinned Git paths',sorted(blob_paths),paths);a.eq('every pinned logical blob',all(logical),True)
    a.eq('pin',git('rev-parse','HEAD').decode().strip(),PIN);a.eq('manifest',forward['manifest_sha256'],manifest)
    a.eq('metadata exclusions',[r['path'] for r in forward['exclusions']],sorted(excluded))
    active={r[0] for r in source_weapons()}
    a.eq('inactive Clan source names absent',bool({'CL.MediumLaser','CL.SmallLaser'}&active),False)
    keys=Counter(Path(p).name[:24].lower() for p in paths)
    a.eq('independent collision groups',forward['ambiguities'],[{'lookup_key':k,'members':[p for p in paths if Path(p).name[:24].lower()==k]} for k,n in sorted(keys.items()) if n>1])
    backward=a.command('raw-reverse',['audit','--path',UP,'--reverse'],exit=2)
    a.eq('all reverse-order semantic fields',backward,forward)
    classes=['Mech','Vehicle','VTOL','Naval','Spheroid_DropShip','AeroFighter','Mechwarrior','Aerodyne_DropShip','Battlesuit']
    source_results=[];types=Counter();failures=Counter()
    for start in range(0,len(forward['files']),50):
        batch=forward['files'][start:start+50];units=[];actions=[];cases=[]
        for offset,row in enumerate(batch):
            name=row['path'];text=(UP/name).read_bytes().decode('ascii')
            decl=re.search(r'^Type\s*\{\s*([^}]*?)\s*\}',text,re.M)[1]
            cause='Invalid section' if decl=='AeroFighter' else 'Invalid critical item: CL.MediumLaser' if name=='AS7-DC' else 'Invalid critical item: CL.SmallLaser' if name=='Elemental' else 'bounds' if name=='Uller-D' else None
            unit=f'u{start+offset:04d}';units.append({'name':unit,'construction':{'zeroed':True}})
            index=len(actions);actions.append(D('load_modern',name)|{'unit':unit})
            if not cause:actions.append(R(unit))
            cases.append((row,name,text,decl,cause,unit,index))
        inp=doc(actions,catalog=False,units=units);inp['editors']=[];inp['random']={'seed':5489}
        inp['construction'].update(root=str(UP),create_root=False)
        out=a.cli(f'batch-{start:04d}',inp)
        for row,name,text,decl,cause,unit,index in cases:
            types[decl]+=1;result=out['results'][index];state=out['state']['units'][unit]
            read=out['results'][index+1] if not cause else None
            a.eq('raw hash',row['raw_sha256'],hashes[name]);a.eq('declared type',row['declared_type'],decl)
            a.eq('source compatibility outcome',row['outcome'],'failed' if cause else 'loaded')
            a.eq('independent CLI load',result.get('ok'),not bool(cause))
            if cause:
                if decl=='AeroFighter':a.eq('obsolete aero source locations',bool(re.search(r'^(Fuselage|Cockpit|Engine)\r?$',text,re.M)),True)
                error=str(result);a.eq('concrete source rejection',cause in error,True);failures[cause]+=1
                a.eq('audit retains first modern error',cause in row['error'],True)
            else:
                a.eq('final class',row['final_class'].lower(),decl.lower())
                for field in ('tonnage','max_speed','jump_speed'):
                    a.eq('audit vs independent '+field,row['state'][field],read[field])
                a.eq('all armor',row['state']['armor'],[s['armor'] for s in state['sections']])
                a.eq('all internals',row['state']['internals'],[s['internal'] for s in state['sections']])
                a.eq('all mounts',row['state']['mounts'],len(state['weapons']))
            source_results.append({'path':name,'raw_sha256':hashes[name],'declared_type':decl,'expected_error':cause,
                                   'cli_case':a.current['id'],'cli_unit':unit,'audit':row})
        print('Independent files',start+len(batch),'/',len(paths),flush=True);a.save()
    a.eq('independent per-type counts',forward['by_declared_type'],dict(sorted(types.items())))
    a.eq('independent failure denominator',forward['failures'],sum(failures.values()))
    a.eq('raw files unchanged',{n:sha((UP/n).read_bytes()) for n in paths},hashes)
    (OUT/'independent-files.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in source_results))
    a.save()

if __name__=='__main__':run()
