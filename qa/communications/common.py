"""Public CLI recorder and source-derived fixture constants."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,os,re,shutil,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('QA_COMMS_OUTPUT',str(ROOT/'tmp/qa-c3-communications')))
CROOT=ROOT/'btmux/btmux/btech/src/btech'
LOC={'LA':0,'RA':1,'LT':2,'RT':3,'CT':4,'LL':5,'RL':6,'HEAD':7}
ATTRS=['Build','Reflexes','Intuition','Learn','Charisma']
XP_MAX=16777216

def f32(x):return struct.unpack('f',struct.pack('f',x))[0]
def sha(x):return hashlib.sha256(x).hexdigest()
def env():return dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(ROOT),TMPDIR=str(ROOT/'tmp'))
def constants():
    text=(CROOT/'mech.h').read_text()
    text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
    pending=dict(re.findall(r'^#define[ \t]+(\w+)[ \t]+([^\n]+)',text,re.M))
    values={}
    for _ in range(12):
        for name,expression in pending.items():
            try: values[name]=eval(expression,{'__builtins__':{}},values)
            except (NameError,SyntaxError,TypeError,ZeroDivisionError):pass
    return values
C=constants()

def character(ident=101,location=10,**kw):
    d=dict(id=ident,name='Pilot'+str(ident),location=location,wizard=True,
        values={**dict.fromkeys(ATTRS,5),'Gunnery-Battlemech':4,'Piloting-Battlemech':4,'Comm-Conventional':4})
    d.update(kw);return d

def unit(name='A',ident=None,kind='C3i',masters=0,**kw):
    ident=ident if ident is not None else 10*(ord(name[0])-64)
    d=dict(name=name,id=ident,contact_id=name[0]*2,team=1,started=True,in_character=True,
        at=[5,5,0],character=100+ident,**{'class':'MECH'},
        sections=[dict(index=i,armor=100,armor_orig=100,internal=30,internal_orig=30) for i in range(8)],
        communications=dict(radio_type=114,radio_range=80,freq=[123,456],freqmodes=[0,0],chantitle=['','']))
    if kind=='C3i':
        d['specials2']=C['C3I_TECH'];d['sections'][2]['slots']=[dict(index=0,special='C3I')]
    elif kind=='C3':
        d['specials']=C['C3_MASTER_TECH'] if masters else C['C3_SLAVE_TECH']
        d['working_c3_masters']=masters;d['total_c3_masters']=masters
        if masters:
            for i in range(masters):d['sections'][[2,3,4,0][i]]['slots']=[dict(index=j,special='C3_MASTER') for j in range(5)]
        else:d['sections'][2]['slots']=[dict(index=0,special='C3_SLAVE')]
    d.update(kw);return d

def doc(actions,units=None,characters=None,streams=None,**kw):
    units=[unit()] if units is None else units
    if characters is None:
        characters=[character(u['character'],u['id']) for u in units if 'character' in u]
    d=dict(characters=characters,units=units,config=dict(periodic_updates=False,extended_gunnery=False,extended_piloting=False),
        map={'size':[30,30]},random={'streams':{'sensor.perception_xp':[1]*1000,'sensor.detect':[1]*1000,**(streams or {})}},actions=actions)
    d.update(kw)
    if 'maps' in kw:d.pop('map',None)
    return d

def diag(kind,unit='A',**kw):return dict(op='communications_diagnose',kind=kind,unit=unit,**kw)
def setcomm(unit='A',**values):return diag('configure',unit,values=values)
def state(o,name='A'):return o['state']['units'][name]
def comm(o,name='A'):return state(o,name)['communications']
def inbox(o,ident=110):return o['state']['inboxes'].get(str(ident),[])
def peers(o,name='A',kind='C3i'):return comm(o,name)['c3' if kind=='C3' else 'c3i']['peers']
def runrow(a,ident,outline,row,line,d,mode='diagnostic'):
    return a.cli(ident,d,identity=dict(outline=outline,line=line,values=row),mode=mode)

def ch(kind,**kw):return dict(op='character',kind=kind,caller=101,**kw)
def dg(kind='read',**kw):return dict(op='character_diagnose',kind=kind,player=101,**kw)
def command(name,unit='A',args='',**kw):return dict(op='command',unit=unit,name=name,args=args,**kw)
def inspect():return {'op':'inspect'}
def advance(seconds):return dict(op='advance',seconds=seconds)
def rows(family):
    outline=0;header=None;example=0
    for line,t in enumerate((ROOT/'features/c3_communications'/f'{family}.feature').read_text().splitlines(),1):
        if t.strip().startswith('Scenario Outline:'):outline+=1;header=None;example=0
        if t.strip().startswith('|'):
            cells=[s.strip() for s in t.strip().strip('|').split('|')]
            if header is None:header=cells
            else:
                example+=1
                selected=os.environ.get('QA_COMMS_CASE')
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
        history=folder/'history'
        if (folder/'input.json').exists():
            history.mkdir(exist_ok=True);old=history/f'{len(list(history.iterdir()))+1:03d}';old.mkdir()
            for f in ('input.json','stdout.json','stderr.txt'):
                if (folder/f).exists():shutil.copyfile(folder/f,old/f)
        root=Path(storage) if storage else folder/'storage'
        if fresh and root.exists():shutil.rmtree(root)
        d=deepcopy(document)
        d.setdefault('pilots',{}).setdefault('root',str(root/'characters'))
        d.setdefault('construction',{}).setdefault('root',str(root/'templates'))
        d.setdefault('file_root',str(root/'maps'))
        raw=json.dumps(d,indent=2)+'\n';(folder/'input.json').write_text(raw)
        p=subprocess.run([sys.executable,'-m','tools.communications','--input',str(folder/'input.json')],cwd=ROOT,env=env(),text=True,capture_output=True,timeout=120)
        (folder/'stdout.json').write_text(p.stdout);(folder/'stderr.txt').write_text(p.stderr)
        self.current=dict(id=name,mode=mode,identity=identity,input=str((folder/'input.json').relative_to(ROOT)),input_sha256=sha(raw.encode()),stdout_sha256=sha(p.stdout.encode()),stderr_sha256=sha(p.stderr.encode()),status=p.returncode,checks=[])
        self.records.append(self.current)
        self.eq('exit status',p.returncode,status)
        if p.returncode!=0:raise AssertionError(p.stderr[:500])
        output=json.loads(p.stdout)
        for index,(action,result) in enumerate(zip(d['actions'],output['results'])):
            if action['op'] in ('schedule','section','core','configure','cache','template','personnel'):
                self.true('setup action '+str(index)+' '+action['op'],not isinstance(result,dict) or (result.get('ok') is not False and result.get('accepted') is not False))
        return output
    def eq(self,label,actual,expected):
        passed=actual==expected
        self.current['checks'].append(dict(label=label,actual=actual,expected=expected,passed=passed))
        if not passed:print('FAIL',self.family,self.current['id'],label,str(actual)[:220],str(expected)[:220],flush=True)
    def true(self,label,actual):self.eq(label,bool(actual),True)
    def near(self,label,actual,expected,tolerance=1e-6):self.eq(label,abs(actual-expected)<=tolerance,True)
    def error(self,value,fragment):self.true('error '+fragment,isinstance(value,dict) and value.get('ok') is False and fragment.lower() in value.get('error','').lower())
    def save(self):
        result=dict(family=self.family,cases=len(self.records),assertions=sum(len(x['checks']) for x in self.records),failures=sum(not c['passed'] for x in self.records for c in x['checks']),results=self.records)
        OUT.mkdir(parents=True,exist_ok=True);(OUT/(os.environ.get('QA_COMMS_REPORT',self.family)+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        print({k:v for k,v in result.items() if k!='results'},flush=True);return result

def cache(viewer,target,visibility='clear'):
    return dict(op='cache',unit=viewer,target=target,flags={'clear':3,'something':32771,'invisible':0}[visibility])

def combat_streams(**override):
    values={'visibility_change':0,'failure_generic_chance':5000,'failure_weapon_chance':1,'attack_rolls':12,
        'hit_location_rolls':7,'damage_entry':7,'pilot_rolls':12,'character_d6':6,'xp_old_gate':1,
        'critical_rolls':2,'critical_slot':0,'fall_directions':1,'breach_rolls':12,'fuel_check':1,
        'missile_pre_roll':6,'missile_cluster':12,'personal_variation':100,'personal_weak_point':2,
        'personal_half':1,'personal_block':1,'personal_to_normal':1,'personal_conversion':100,
        'swarm_location':7,'suit_choice':0,'suit_ejection':100,'physical_location':1,'physical_attack':12,'sensor.flash':100,'tow_rolls':12,'terrain_rolls':12}
    return {**{k:[v]*(2000 if k=='visibility_change' else 200) for k,v in values.items()},**override}
