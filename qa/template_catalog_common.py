"""Independent catalog QA. Only stdlib and QA modules; public subprocess boundary."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,os,subprocess,sys,shutil
from qa.construction_qa_common import T,C,R,I,A,D,E,modern,legacy

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tmp/qa-template-catalog'
UP=Path(os.environ.get('QA_TEMPLATE_CATALOG',str(ROOT/'btmux-mechs'))).resolve()
PIN='b587745c0f6d41515e76b20109953b73f8277599'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def env(**extra):return dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),TMPDIR=str(ROOT/'tmp'))|extra
def initialize():
    """Make the reproducible input snapshot when starting in fresh scratch."""
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'startup.json'
    if path.exists():return
    if not UP.is_dir():raise ValueError('Set QA_TEMPLATE_CATALOG to the pinned existing design checkout')
    hashes={}
    for directory,dirs,files in os.walk(UP,followlinks=False):
        dirs[:]=[d for d in dirs if d!='.git' and not (Path(directory)/d).is_symlink()]
        for name in files:
            p=Path(directory)/name
            if p.is_file() and not p.is_symlink():hashes[p.relative_to(UP).as_posix()]=sha(p.read_bytes())
    contracts=['template-catalog.lock.json','features/core_simulation/repair.feature']+[str(p.relative_to(ROOT)) for p in (ROOT/'features/template_catalog').glob('*.feature')]
    sources=['template.c','mechrep.c','mech.utils.c','mech.h','btmacros.h','weapons.h','mech.move.c',
             'mech.consistency.c','weapons.vrt.h','aero.bomb.c','failures.h']
    record={'candidate':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'catalog':str(UP),'catalog_hashes':hashes,
            'catalog_status':subprocess.check_output(['git','-C',str(UP),'status','--porcelain=v1'],text=True),
            'contract':{p:sha((ROOT/p).read_bytes()) for p in contracts},
            'c':{p:sha((ROOT/'btmux/btmux/btech/src/btech'/p).read_bytes()) for p in sources},
            'local_pyproject_sha256':sha((ROOT/'pyproject.toml').read_bytes()) if (ROOT/'pyproject.toml').exists() else None}
    path.write_text(json.dumps(record,indent=2)+'\n')
def doc(actions,*,catalog=True,units=None,ordinary=False):
    return {'construction':{'catalog':str(UP) if catalog else False},'map':{'size':[24,24]},
      'units':units or [{'name':'u','at':[6,6,0]}], 'editors':[{'name':'e','id':1,'target':'u'}],
      'config':{'periodic_updates':ordinary,'lock_tick':0},
      'random':{'streams':{'visibility_change':[0]*2000,'failure_generic_chance':[5000]*500,
        'attack_rolls':[12]*50,'failure_weapon_chance':[1]*50,'hit_location_rolls':[7]*100,
        'damage_entry':[7]*100,'tow_rolls':[12]*50,'missile_pre_roll':[6]*100,
        'missile_cluster':[12]*50,'pilot_rolls':[12]*50,'fuel_check':[1]*1000,
        'sensor.detect':[1]*1000,'breach_rolls':[12]*50}},'actions':actions}
def pilot(unit='u'):return {'op':'construction_pilot','unit':unit,'actor':{'gunnery':4,'piloting':5,'health':{'build':5,'bruise':0,'lethal':0}}}
def feature_rows(family):
    outline='';header=None
    for line,text in enumerate((ROOT/'features/template_catalog'/f'{family}.feature').read_text().splitlines(),1):
        if text.strip().startswith('Scenario Outline:'):outline=text.strip().split(': ',1)[1];header=None
        if text.strip().startswith('|'):
            cells=[x.strip() for x in text.strip().strip('|').split('|')]
            if header is None:header=cells
            else:yield line,outline,dict(zip(header,cells))

class Audit:
    def __init__(self,family):self.family=family;self.rows=[];OUT.mkdir(parents=True,exist_ok=True)
    def cli(self,name,document,*,root=None,cwd=ROOT,extra_env=None,exit=0):
        path=OUT/self.family/name;path.mkdir(parents=True,exist_ok=True)
        document=deepcopy(document)
        if root is None and 'root' not in document.get('construction',{}) and (path/'custom').exists():
            shutil.rmtree(path/'custom')
        if 'file_root' not in document and (path/'maps').exists():shutil.rmtree(path/'maps')
        document.setdefault('construction',{}).setdefault('root',str(root or path/'custom'))
        document.setdefault('file_root',str(path/'maps'))
        raw=json.dumps(document,sort_keys=True,indent=2)+'\n';(path/'input.json').write_text(raw)
        p=subprocess.run([sys.executable,'-m','tools.construction_templates','--input',str(path/'input.json')],
            cwd=cwd,env=env(**(extra_env or {})),capture_output=True,text=True,timeout=120)
        (path/'stdout.json').write_text(p.stdout);(path/'stderr.txt').write_text(p.stderr)
        self.current={'id':name,'input':str((path/'input.json').relative_to(ROOT)),
                      'input_sha256':sha(raw.encode()),'stdout_sha256':sha(p.stdout.encode()),
                      'stderr_sha256':sha(p.stderr.encode()),'exit':p.returncode,'checks':[]}
        self.rows.append(self.current);self.eq('process status',p.returncode,exit)
        if p.returncode:return {'error':p.stderr,'results':[]}
        return json.loads(p.stdout)
    def command(self,name,args,*,exit=0):
        path=OUT/self.family/name;path.mkdir(parents=True,exist_ok=True)
        p=subprocess.run([sys.executable,'-m','tools.template_catalog',*map(str,args)],cwd=ROOT,env=env(),capture_output=True,text=True,timeout=600)
        (path/'stdout.json').write_text(p.stdout);(path/'stderr.txt').write_text(p.stderr)
        self.current={'id':name,'command':list(map(str,args)),'exit':p.returncode,
            'stdout_sha256':sha(p.stdout.encode()),'checks':[]};self.rows.append(self.current)
        self.eq('process status',p.returncode,exit)
        return json.loads(p.stdout or p.stderr)
    def eq(self,label,actual,expected):
        ok=actual==expected
        def compact(x):
            raw=json.dumps(x,sort_keys=True)
            return x if len(raw)<1200 else {'sha256':sha(raw.encode()),'bytes':len(raw)}
        self.current['checks'].append({'label':label,'actual':compact(actual),'expected':compact(expected),'passed':ok})
        if not ok:print('FAIL',self.family,self.current['id'],label,str(actual)[:180],str(expected)[:180],flush=True)
    def save(self):
        result={'family':self.family,'cases':len(self.rows),'assertions':sum(len(r['checks']) for r in self.rows),
                'failures':sum(not c['passed'] for r in self.rows for c in r['checks']),'results':self.rows}
        (OUT/(self.family+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        print({k:v for k,v in result.items() if k!='results'},flush=True)
        return result
