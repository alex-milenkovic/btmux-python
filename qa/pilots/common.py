"""Public CLI recorder and source-derived fixture constants."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,os,re,shutil,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tmp/qa-pilots'
CROOT=ROOT/'btmux/btmux/btech/src/btech'
LOC={'LA':0,'RA':1,'LT':2,'RT':3,'CT':4,'LL':5,'RL':6,'HEAD':7}
ATTRS=['Build','Reflexes','Intuition','Learn','Charisma']
XP_MAX=16777216

def f32(x):return struct.unpack('f',struct.pack('f',x))[0]
def sha(x):return hashlib.sha256(x).hexdigest()
def env():return dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),TMPDIR=str(ROOT/'tmp'))
def source_table():
    constants={}
    for name,value in re.findall(r'^#define\s+(\w+)\s+([^\n/]+)',(CROOT/'btechstats_global.h').read_text(),re.M):
        try:constants[name]=eval(value,{'__builtins__':{}},constants)
        except (NameError,SyntaxError,TypeError):pass
    rows=[]
    for name,typ,flags,threshold in re.findall(r'\{"([^"]+)",\s*(CHAR_\w+),\s*([^,]+),\s*(\d+)\}',(CROOT/'btechstats.h').read_text()):
        short=''.join(name[i:i+3] for i,c in enumerate(name) if c.isupper())
        if len(short)<=3:short=name[:5]
        rows.append(dict(code=len(rows),name=name,type=constants[typ],flags=eval(flags,{'__builtins__':{}},constants),threshold=int(threshold),short=short))
    assert len(rows)==119
    return rows
TABLE=source_table()
INDEX={v['name']:v['code'] for v in TABLE}

def character(ident=101,**kw):
    result=dict(id=ident,name='Alice' if ident==101 else 'Bob',location=10 if ident==101 else 20,wizard=True,
        values={**dict.fromkeys(ATTRS,5),'Gunnery-Battlemech':4,'Piloting-Battlemech':4})
    result.update(kw);return result

def unit(name='u',ident=10,cls='MECH',**kw):
    result=dict(name=name,id=ident,contact_id='UU' if name=='u' else 'VV',team=1 if name=='u' else 2,
        started=True,in_character=True,at=[3,3,0],**{'class':cls},
        sections=[dict(index=i,armor=100,internal=30,internal_orig=30) for i in range(8)])
    result.update(kw);return result

def doc(actions,characters=None,units=None,streams=None,**kw):
    result=dict(characters=[character()] if characters is None else characters,units=[] if units is None else units,
        config=dict(periodic_updates=False,extended_gunnery=False,extended_piloting=False),
        map={'size':[15,15]},random={'streams':{'sensor.perception_xp':[1]*300,'sensor.detect':[1]*300,**(streams or {})}},actions=actions)
    result.update(kw);return result

def ch(kind,**kw):return dict(op='character',kind=kind,caller=101,**kw)
def dg(kind='read',**kw):return dict(op='character_diagnose',kind=kind,player=101,**kw)
def command(name,unit='u',args='',**kw):return dict(op='command',unit=unit,name=name,args=args,**kw)
def inspect():return {'op':'inspect'}
def advance(seconds):return dict(op='advance',seconds=seconds)
def rows(family):
    outline=0;header=None;example=0
    for line,t in enumerate((ROOT/'features/pilots'/f'{family}.feature').read_text().splitlines(),1):
        if t.strip().startswith('Scenario Outline:'):outline+=1;header=None;example=0
        if t.strip().startswith('|'):
            cells=[s.strip() for s in t.strip().strip('|').split('|')]
            if header is None:header=cells
            else:
                example+=1
                selected=os.environ.get('QA_PILOTS_CASE')
                if selected and selected not in (f'{outline:02d}-{example:02d}',cells[0]):continue
                yield f'{outline:02d}-{example:02d}',outline,dict(zip(header,cells)),line

def nums(s):return [] if s=='none' else [int(x) for x in s.split(',')]
def yes(s):return s=='True'
def health(out,ident=101):return list(map(int,out['state']['characters'][str(ident)]['categories']['health'].split(',')))
def events(state,kind):return [e for e in state['events'] if e['kind']==kind]

class Audit:
    def __init__(self,family):self.family=family;self.records=[];self.current=None
    def cli(self,name,document,*,storage=None,fresh=True,mode='diagnostic',identity=None,status=0):
        folder=OUT/self.family/name;folder.mkdir(parents=True,exist_ok=True)
        root=Path(storage) if storage else folder/'storage'
        if fresh and root.exists():shutil.rmtree(root)
        d=deepcopy(document)
        d.setdefault('pilots',{}).setdefault('root',str(root/'characters'))
        d.setdefault('construction',{}).setdefault('root',str(root/'templates'))
        d.setdefault('file_root',str(root/'maps'))
        raw=json.dumps(d,indent=2)+'\n';(folder/'input.json').write_text(raw)
        p=subprocess.run([sys.executable,'-m','tools.pilots','--input',str(folder/'input.json')],cwd=ROOT,env=env(),text=True,capture_output=True,timeout=120)
        (folder/'stdout.json').write_text(p.stdout);(folder/'stderr.txt').write_text(p.stderr)
        self.current=dict(id=name,mode=mode,identity=identity,input=str((folder/'input.json').relative_to(ROOT)),input_sha256=sha(raw.encode()),stdout_sha256=sha(p.stdout.encode()),stderr_sha256=sha(p.stderr.encode()),status=p.returncode,checks=[])
        self.records.append(self.current)
        self.eq('exit status',p.returncode,status)
        if p.returncode!=0:raise AssertionError(p.stderr[:500])
        return json.loads(p.stdout)
    def eq(self,label,actual,expected):
        passed=actual==expected
        self.current['checks'].append(dict(label=label,actual=actual,expected=expected,passed=passed))
        if not passed:print('FAIL',self.family,self.current['id'],label,str(actual)[:220],str(expected)[:220],flush=True)
    def true(self,label,actual):self.eq(label,bool(actual),True)
    def near(self,label,actual,expected,tolerance=1e-6):self.eq(label,abs(actual-expected)<=tolerance,True)
    def error(self,value,fragment):self.true('error '+fragment,isinstance(value,dict) and value.get('ok') is False and fragment.lower() in value.get('error','').lower())
    def save(self):
        result=dict(family=self.family,cases=len(self.records),assertions=sum(len(x['checks']) for x in self.records),failures=sum(not c['passed'] for x in self.records for c in x['checks']),results=self.records)
        OUT.mkdir(parents=True,exist_ok=True);(OUT/(self.family+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        print({k:v for k,v in result.items() if k!='results'},flush=True);return result
