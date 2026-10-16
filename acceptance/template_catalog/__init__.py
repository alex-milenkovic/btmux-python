"""Normal APS bindings for catalog integration; independent QA is separately owned."""
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from collections import Counter
from data.template_dependency import resolve_catalog,verify,inventory,sha,dependency_lock
from data.template_catalog import CatalogDirectory
from data.template_catalog_audit import audit,failure_detail,declared
from data.template_files import clear_mech,load_stream,load_template,isolated_template
from data.template_directory import TemplateDirectory
from entities.mech import Mech,FireMode as F
from entities.crittypes import i2special,Special
from systems.repairs import sub_magic,replay_template
from acceptance.construction_templates.integration import modern_text,base,run,fileop,edit,command,fire_actions

BINDINGS=[]
def step(pattern):
    def decorate(fn):BINDINGS.append((pattern,fn));return fn
    return decorate

def eq(actual,expected):assert actual==expected,(actual,expected)
def raw_manifest(root):
    return sha(''.join(name+'\t'+sha((root/name).read_bytes())+'\n' for name in inventory(root)[0]).encode())

def newunit():
    unit=Mech();clear_mech(unit,True);return unit

def upstream():
    root=resolve_catalog(True)
    assert root.is_dir(),'Run python3 -m tools.template_catalog setup or configure BTMUX_TEMPLATE_CATALOG'
    return root

@step(r'an isolated template catalog session with pinned inputs and writable scratch storage')
def fresh(w):
    w.clear();w['template_catalog']=True
    w['temp']=tempfile.TemporaryDirectory(dir='./tmp');w['root']=Path(w['temp'].name).resolve()
    w['upstream']=upstream()

def document(w,actions):
    doc=base(w['root'],actions);doc['construction']['catalog']=str(w['upstream']);return doc

@step(r'catalog option (.+) and environment (.+) with all named roots at the pinned revision')
def configure(w,option,environment):
    w['option']=option;w['environment']=environment
    for name in ('explicit-root','environment-root'):
        subprocess.run(['git','clone','--shared',str(w['upstream']),str(w['root']/name)],check=True,capture_output=True)

@step(r'ordinary catalog configuration resolves its read root')
def resolve(w):
    option={'true':True,'false':False,'omitted':None}.get(w['option'],w['option'])
    cwd=Path.cwd()
    try:
        os.chdir(w['root'])
        w['result']=resolve_catalog(option,environ={} if w['environment']=='none' else {'BTMUX_TEMPLATE_CATALOG':w['environment']})
    finally:os.chdir(cwd)

@step(r'the selected root is (.+)')
def selected(w,expected):
    value=None if expected=='disabled' else resolve_catalog(True,environ={}) if expected=='project-relative' else (w['root']/expected).resolve()
    eq(w['result'],value)

@step(r'the configured catalog has (.+)')
def verification_fixture(w,state):
    w['verification_state']=state;root=w['root']/'dependency';w['verify_root']=root
    if state=='missing':return
    subprocess.run(['git','clone','--shared','--no-checkout',str(w['upstream']),str(root)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'-c','core.autocrlf=false','checkout','HEAD','--','.'],check=True,capture_output=True)
    if state=='matching-CRLF':
        for name in inventory(root)[0]:
            p=root/name;p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    if state=='content-drift':(root/'WVR-6R').write_bytes(b'Tons { 77 }\n')
    if state=='wrong-revision':
        subprocess.run(['git','-C',str(root),'-c','user.name=APS','-c','user.email=aps@example.invalid','commit','--allow-empty','-m','wrong revision fixture'],check=True,capture_output=True)
    w['before']={p:sha((root/p).read_bytes()) for p in inventory(root)[0]}

@step(r'setup verification is requested')
def verify_run(w):w['result']=verify(w['verify_root'])

@step(r'the outcome is (.+) and every preexisting input byte is unchanged')
def verify_result(w,outcome):
    eq(w['result']['outcome'],outcome)
    if w['verify_root'].exists():eq(w['before'],{p:sha((w['verify_root']/p).read_bytes()) for p in inventory(w['verify_root'])[0]})

@step(r'an ordinary list and reference lookup requests (.+) from the pinned upstream catalog')
def lookup(w,reference):w['output']=run(w['root'],document(w,[fileop('list'),fileop('lookup',reference)]))

@step(r'the chosen design is (.+) with upstream provenance')
def lookup_result(w,reference):
    rows,found=w['output']['results'];eq(found['selected']['origin'],'upstream');eq(found['path'],reference)
    assert any(row['path']==reference and row['origin']=='upstream' for row in rows['entries'])

@step(r'the actual pinned catalog is inventoried without parsing filters')
def inventory_run(w):
    names,_=inventory(w['upstream']);w['types']=Counter(declared((w['upstream']/name).read_text(),'Type') for name in names)

@step(r'declared type (.+) has (\d+) candidates')
def inventory_result(w,kind,count):eq(w['types'][kind],int(count))

@step(r'a disposable catalog audit fixture contains (.+)')
def fixture(w,name):
    root=w['root']/'audit';root.mkdir();w['audit_root']=root
    valid='Type { Mech }\nTons { 50 }\n';invalid='Type { Mech }\nCRIT_13 { HeatSink - - - }\n'
    files={'one-valid':{'A':valid},'valid-invalid-valid':{'A':valid,'B':invalid,'C':valid},
       'same-key-two-valid-files':{'A':valid,'sub/a':valid},'same-key-valid-invalid':{'A':valid,'sub/a':invalid},
       'unknown-type-and-valid':{'A':'Type { unknown }\n','B':valid},
       'valid-plus-git-metadata':{'A':valid,'.git/description':'not a design'},
       'nested-valid-not-discoverable':{'one/two/A':valid}}[name]
    for path,text in files.items():p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)

@step(r'its real per-file audit runs in fresh state')
def audit_run(w):w['result']=audit(w['audit_root'])

@step(r'candidates successes failures and ambiguity groups are (\d+) (\d+) (\d+) and (\d+) with outcome (.+)')
def audit_result(w,candidates,successes,failures,ambiguities,outcome):
    r=w['result'];eq((r['candidates'],r['successes'],r['failures'],len(r['ambiguities']),r['outcome']),
                             (int(candidates),int(successes),int(failures),int(ambiguities),outcome))

@step(r'unchanged design (.+) is attempted through the corrected production loader')
def negative(w,reference):
    try:load_template(newunit(),w['upstream']/reference)
    except ValueError as error:w['result']=failure_detail(error,(w['upstream']/reference).read_text())
    else:raise AssertionError('Expected compatibility rejection')

@step(r'failure is classified as (.+) with cause (.+)')
def negative_result(w,classification,cause):eq((w['result']['classification'],w['result']['cause']),(classification,cause))

@step(r'a Mech has maximum speed (.+) KPH and (\d+) installed JumpJet slots with improved flag ([01])')
def jets(w,speed,slots,improved):
    u=newunit();u.max_speed=float(speed);u.specials2=int(improved)*128;u.tonnage=50;u.real_num_sinks=10
    for slot in [slot for sec in u.sections[:2] for slot in sec.criticals][:int(slots)]:slot.type=i2special(Special.JUMP_JET)
    w['unit']=u

@step(r'shared sub_magic recomputes mobility')
def recompute(w):sub_magic(w['unit'])

@step(r'persistent jump capacity is (\d+) MP and jump speed is (.+) KPH')
def jump_result(w,mp,jump):eq((w['unit'].jump_mp,w['unit'].jump_speed),(int(mp),float(jump)))

@step(r'four standard JumpJet slots at maximum64.5 KPH with slot condition (.+)')
def jet_condition(w,condition):
    jets(w,'64.5','4','0');w['unit'].real_num_sinks=10
    for slot in w['unit'].sections[2].criticals[:2]:slot.type=i2special(Special.HEAT_SINK)
    for slot in w['unit'].sections[0].criticals[:4]:slot.firemode={'intact':0,'destroyed':F.DESTROYED_MODE,'disabled':F.DISABLED_MODE}[condition]

@step(r'recomputation runs through (.+)')
def caller(w,caller):
    if caller=='sub-magic':sub_magic(w['unit'])
    elif caller=='repair-replay':replay_template(w['unit'],isolated_template(w['unit']))
    elif caller=='modern-load':
        load_stream(w['unit'],io.StringIO('Type { Mech }\nTons { 50 }\nMax_Speed { 64.5 }\nHeat_Sinks { 10 }\nLeft_Arm\nCRIT_1-4 { JumpJet - - - }\n'),'JETS')
    else:raise ValueError(caller)

@step(r'jump capacity is4 MP and the established sink calculation is unchanged')
def caller_result(w):eq((w['unit'].jump_mp,w['unit'].real_num_sinks),(4,10))

@step(r'unchanged CRLF design (.+) and its LF scratch equivalent')
def parity_setup(w,reference):w['reference']=reference

@step(r'each is loaded through ordinary production template loading')
def parity(w):
    reference=w['reference'];scratch=w['root']/'lf';scratch.mkdir()
    (scratch/reference).write_bytes((w['upstream']/reference).read_bytes().replace(b'\r\n',b'\n'))
    a=newunit();b=newunit();a._id=b._id=0
    assert TemplateDirectory(w['upstream']).loadnew(a,reference)
    assert TemplateDirectory(scratch).loadnew(b,reference)
    w['pair']=(a,b)

@step(r'both succeed with equal finalized design fields and jump capability (\d+)')
def parity_result(w,mp):
    a,b=w['pair'];eq(a.jump_mp,int(mp));eq(a.sections,b.sections)
    for attr in ('name','tonnage','unit_type','max_speed','jump_speed','real_num_sinks','specials','specials2','computer','radio','tac_range','radio_range'):
        eq(getattr(a,attr),getattr(b,attr))

@step(r'a template fixture (.+) encoded with (.+)')
def parser_fixture(w,name,ending):
    texts={'valid-multiline':'Name { First\nsecond\nlast }\nLeft_Arm\nArmor { 14 }\n',
           'unknown-section':'Tons { 55 }\nUnknown\n','unknown-mode':'Tons { 55 }\nLeft_Arm\nCRIT_1 { HeatSink - - - }\nCRIT_2 { IS.MediumLaser - Unknown 4 }\n',
           'CRIT13':'Tons { 55 }\nLeft_Arm\nCRIT_13 { HeatSink - - - }\n',
           'interior-carriage-return-section':'Tons { 55 }\nLeft_\rArm\n',
           'unterminated-final-section':'Tons { 55 }\nLeft_Arm'}
    text=texts[name]
    if ending=='CRLF':text=text.replace('\n','\r\n')
    if ending=='mixed':text=text.replace('second\n','second\r\n')
    w['text']=text;w['parser_fixture']=name

@step(r'the central template parser reads it')
def parser_run(w):
    u=newunit();w['unit']=u;w['error']=None
    path=w['root']/'FIXTURE';path.write_bytes(w['text'].encode('ascii'));w['parser_path']=path
    try:load_template(u,path,finalize=False)
    except ValueError as error:w['error']=str(error)

@step(r'its outcome is (.+) with source ordered writes and unchanged input bytes')
def parser_result(w,outcome):
    eq(w['parser_path'].read_bytes(),w['text'].encode('ascii'))
    if outcome=='normalized-multiline':eq(w['error'],None);eq(w['unit'].name,'First\r\nsecond\r\nlast ');eq(w['unit'].sections[0].armor,14)
    else:
        needle={'section-error':'Invalid section','mode-error':'mode','bounds-error':'bounds','source-last-byte-deletion':'Invalid section'}[outcome]
        assert needle in w['error'],w['error'];eq(w['unit'].tonnage,55)

@step(r'upstream WVR-6R is loaded and the requested custom root has (.+)')
def storage_setup(w,state):w['storage_state']=state

@step(r'ordinary mutation (.+) is attempted')
def mutation(w,operation):
    state=w['storage_state'];actions=[fileop('load','WVR-6R')]
    if operation.startswith('save-'):actions+=[fileop('save',operation[5:])]
    elif operation.startswith('editor-save-'):actions+=[edit('settarget','u'),edit('savetemp2',operation[12:])]
    elif operation.startswith('write-'):actions+=[fileop('write',operation[6:],text='Tons { 50 }\n')]
    elif operation.startswith('delete-'):actions+=[fileop('delete','WVR-6R',origin='upstream')]
    elif operation=='fixture-write-WVR-6R':pass
    else:raise ValueError(operation)
    doc=document(w,actions)
    if state=='upstream-overlap':doc['construction']['root']=str(w['upstream'])
    if state=='symlink-into-upstream':
        root=Path(doc['construction']['root']);root.mkdir();(root/'WVR-6R').symlink_to(w['upstream']/'WVR-6R')
    if operation.startswith('fixture-write'):doc['construction']['files']={'WVR-6R':'overwrite'}
    w['before']=raw_manifest(w['upstream'])
    p=subprocess.run([os.sys.executable,'-m','tools.construction_templates'],input=json.dumps(doc),text=True,capture_output=True)
    w['process']=p;w['output']=json.loads(p.stdout or p.stderr)

@step(r'its outcome is (.+) and the upstream byte manifest is unchanged')
def mutation_result(w,outcome):
    if outcome=='custom-written':eq(w['process'].returncode,0);eq(w['output']['results'][-1]['ok'],True);assert (w['root']/'templates/CUSTOM').is_file()
    else:assert w['process'].returncode or w['output']['results'][-1]['ok'] is False,w['output']
    eq(raw_manifest(w['upstream']),w['before'])

@step(r'a catalog-loaded WVR-6R and a later distinct custom WVR-6R shadow')
def shadow_setup(w):w['shadow']='Name { Shadow }\nTons { 40 }\n'

@step(r'(default-load|explicit-upstream-load|restore-original-unit|explicit-custom-load) selects that reference')
def shadow(w,operation):
    selected={'default-load':fileop('load','WVR-6R'),'explicit-upstream-load':fileop('load','WVR-6R',origin='upstream'),
              'restore-original-unit':fileop('restore'),'explicit-custom-load':fileop('load','WVR-6R',origin='custom')}[operation]
    actions=[fileop('load','WVR-6R'),fileop('write','WVR-6R',text=w['shadow']),fileop('reset'),fileop('list'),selected,{'op':'construction_readout'}]
    w['output']=run(w['root'],document(w,actions))

@step(r'its source is (.+) and the two listed candidates retain distinct provenance')
def shadow_result(w,origin):
    r=w['output']['results'];eq(r[-1]['template_origin'],origin);eq(r[-1]['tonnage'],40 if origin=='custom' else 55)
    rows=[row for row in r[3]['entries'] if row['reference']=='WVR-6R'];eq({row['origin'] for row in rows},{'custom','upstream'})
    assert all(len(row['collisions'])==2 for row in rows)

from . import workflows
