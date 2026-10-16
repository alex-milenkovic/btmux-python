"""Read-only verification and explicit setup of the optional pinned design tree."""
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METADATA = {'.state', '.git', '.gitignore', '.gitattributes', '.github', 'README', 'README.md',
            'README.txt', 'LICENSE', 'LICENSE.md', 'COPYING'}


def dependency_lock():
    return json.loads(files('data').joinpath('template-catalog.lock.json').read_text(encoding='utf-8'))


def resolve_catalog(option, *, environ=None):
    if option is None or option is False:return None
    if option is not True and (not isinstance(option,str) or not option):
        raise ValueError('construction.catalog must be true, false or a directory string')
    env=os.environ if environ is None else environ
    path=option if isinstance(option,str) else env.get('BTMUX_TEMPLATE_CATALOG')
    return Path(path).resolve() if path else PROJECT_ROOT/dependency_lock()['directory']


def sha(data):return hashlib.sha256(data).hexdigest()


def inventory(root):
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('Catalog directory is missing')
    candidates=[];exclusions=[]
    def visit(directory):
        with os.scandir(directory) as scan:entries=sorted(scan,key=lambda e:e.name)
        for entry in entries:
            path=Path(entry.path);rel=path.relative_to(root).as_posix()
            if entry.name in METADATA:
                exclusions.append({'path':rel,'reason':'local template state' if entry.name=='.state' else 'Git metadata' if entry.name=='.git' else 'repository metadata'})
            elif entry.is_symlink():exclusions.append({'path':rel,'reason':'symlink (not followed)'})
            elif entry.is_dir(follow_symlinks=False):visit(path)
            elif entry.is_file(follow_symlinks=False):candidates.append(rel)
            else:exclusions.append({'path':rel,'reason':'not a regular file'})
    visit(root)
    return sorted(candidates),sorted(exclusions,key=lambda e:e['path'])


def git(root,*args,input=None):
    result=subprocess.run(['git','-C',str(root),*args],input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:raise ValueError(result.stderr.decode(errors='replace').strip())
    return result.stdout


def tracked_blobs(root):
    entries=[]
    for record in git(root,'ls-tree','-rz','HEAD').split(b'\0'):
        if not record:continue
        info,name=record.split(b'\t',1);mode,kind,oid=info.split()
        if kind==b'blob':entries.append((name.decode(),mode,oid))
    raw=git(root,'cat-file','--batch',input=b''.join(oid+b'\n' for _,_,oid in entries))
    offset=0;result={}
    for name,mode,oid in entries:
        end=raw.index(b'\n',offset);size=int(raw[offset:end].split()[-1]);offset=end+1
        result[name]=(mode,raw[offset:offset+size]);offset+=size+1
    return result


def verify(root, *, lock=None):
    lock=lock or dependency_lock();root=Path(root).resolve()
    report={'expected_revision':lock['revision'],'observed_revision':None,'outcome':'missing-error',
            'drift':[],'eol_only':[],'missing_tracked':[],'added':[]}
    if not root.is_dir():return report
    try:
        # Do not accidentally verify a containing project repository.
        if Path(git(root,'rev-parse','--show-toplevel').decode().strip()).resolve()!=root:
            raise ValueError('Catalog path is not a Git checkout root')
        report['observed_revision']=git(root,'rev-parse','HEAD').decode().strip()
        blobs=tracked_blobs(root)
        candidates,exclusions=inventory(root)
        report['exclusions']=exclusions
        report['added']=sorted(set(candidates)-set(blobs))
        safe_parents={}
        for name,(mode,expected) in sorted(blobs.items()):
            path=root/name
            if not path.exists():report['missing_tracked'].append(name);continue
            if path.parent not in safe_parents:safe_parents[path.parent]=path.parent.resolve().is_relative_to(root)
            if mode not in (b'100644',b'100755') or path.is_symlink() or not safe_parents[path.parent]:
                report['drift'].append({'path':name,'reason':'nonregular or escaped tracked path'});continue
            try:actual=path.read_bytes()
            except OSError as error:report['drift'].append({'path':name,'reason':str(error).replace(str(root),'<catalog>')});continue
            if actual==expected:continue
            if actual.replace(b'\r\n',b'\n')==expected.replace(b'\r\n',b'\n'):report['eol_only'].append(name)
            else:report['drift'].append({'path':name,'reason':'content differs from Git blob'})
        if report['observed_revision']!=lock['revision']:report['outcome']='revision-error'
        elif report['drift'] or report['missing_tracked'] or report['added']:report['outcome']='drift-error'
        else:report['outcome']='verified-EOL-only' if report['eol_only'] else 'verified'
    except (ValueError,OSError) as error:
        report['outcome']='revision-error';report['error']=str(error).replace(str(root),'<catalog>')
    return report


def require_verified(root):
    report=verify(root)
    if not report['outcome'].startswith('verified'):
        raise ValueError('Catalog configuration error: '+json.dumps(report,sort_keys=True)+
                         '; run python3 -m tools.template_catalog verify --path <catalog>')
    return report


def setup(root):
    root=Path(root).absolute();lock=dependency_lock()
    if not root.exists() and not root.is_symlink():
        root.parent.mkdir(parents=True,exist_ok=True)
        # Explicit setup is the only network path. Never touch an existing tree.
        subprocess.run(['git','clone','--no-checkout',lock['url'],str(root)],check=True)
        git(root,'checkout','--detach',lock['revision'])
    return verify(root)
