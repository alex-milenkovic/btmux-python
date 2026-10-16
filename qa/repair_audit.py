"""Reconcile the reviewed source ledger, owner definitions and complete UI results.

This is accounting, not a replacement for behavioral assertions in the UI suite.
Reads source/AST as text; never imports or calls the engine.
"""
import ast,csv
from collections import Counter
from qa.repair_support import *

def definition(owner):
    plain=owner.split('[')[0];parts=plain.split('.')
    for i in range(len(parts)-1,0,-1):
        path=ROOT/('/'.join(parts[:i])+'.py')
        if path.exists():break
    else:raise AssertionError('Missing owner file: '+owner)
    tree=ast.parse(path.read_text());node=tree
    parent=None
    for name in parts[i:]:
        parent=node
        node=next(n for n in node.body if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    body=ast.get_source_segment(path.read_text(),node)
    delegated=[]
    if '[' in owner and owner.split('[',1)[1][:-1].lower() not in body.lower():
        calls={n.func.attr for n in ast.walk(node) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='self'}
        for helper in parent.body:
            if isinstance(helper,ast.FunctionDef) and helper.name in calls:
                fragment=ast.get_source_segment(path.read_text(),helper)
                if owner.split('[',1)[1][:-1].lower() in fragment.lower():delegated.append(dict(name=helper.name,line=helper.lineno,sha256=hashlib.sha256(fragment.encode()).hexdigest()))
        assert delegated,owner
    return dict(path=str(path.relative_to(ROOT)),line=node.lineno,delegated=delegated,sha256=hashlib.sha256(body.encode()).hexdigest())

def audit():
    rows=list(csv.DictReader((ROOT/'specs/repair-economy/functions.csv').open()));source=json.loads((ROOT/'specs/repair-economy/source-inventory.json').read_text());summary=json.loads((OUTPUT/'summary.json').read_text())
    assert summary['passed'] and sum(summary['examples_passed'].values())==433
    assert len(rows)==134 and len({r['function'] for r in rows})==134
    baseline=dict(Counter(r['current_status'] for r in rows));final=dict(Counter(r['final_status'] for r in rows))
    assert baseline=={'absent':117,'partial':2,'complete':2,'source-inert':13}
    assert final=={'complete':121,'source-inert':13}
    files=[]
    for f in source['source_files']:
        b=(ROOT/f['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==f['sha256'];file_rows=[r for r in rows if r['source_file']==Path(f['path']).name];assert len(file_rows)==f['bodies']
        lines=b.decode().splitlines()
        for r in file_rows:assert r['function'] in '\n'.join(lines[int(r['line'])-1:int(r['line'])+2]),r
        files.append(dict(**f,verified=True))
    manifest=json.loads(MANIFEST.read_text());features={}
    for f in manifest['features']:
        stem=Path(f['path']).stem;expected={f'{stem}/{i:02}-{j:02}' for i,s in enumerate(f['scenarios'],1) for j,_ in enumerate(s['examples'],1)}
        actual={r['case'] for r in summary['results'] if r['case'] in expected and r['passed']};assert actual==expected;features[stem]=sorted(actual)
    ledger=[]
    for r in rows:
        owners=[definition(o) for o in r['final_owner'].split(';')]
        evidence=sorted({c for f in r['feature_families'].split(';') for c in features[f]})
        assert evidence
        ledger.append(dict(function=r['function'],source_file=r['source_file'],source_line=int(r['line']),baseline=r['current_status'],final=r['final_status'],owners=owners,reviewed_behavior_families=r['feature_families'].split(';'),independent_ui_cases=evidence))
    # Scripts have only standard-library and independently authored QA imports.
    imports={}
    stdlib=sys.stdlib_module_names
    for p in sorted([*(ROOT/'qa').glob('repair_*.py'),ROOT/'qa/run_repair_economy.py']):
        names=[]
        for n in ast.walk(ast.parse(p.read_text())):
            if isinstance(n,ast.Import):names.extend(a.name for a in n.names)
            if isinstance(n,ast.ImportFrom):names.append(n.module or '')
        assert all(n.split('.')[0] in stdlib or n.startswith('qa.repair_') for n in names),(p,names)
        imports[str(p.relative_to(ROOT))]=names
    result=dict(passed=True,baseline=baseline,final=final,remaining_absent=0,remaining_partial=0,source_files=files,ledger=ledger,qa_imports=imports,ui_summary_sha256=hashlib.sha256((OUTPUT/'summary.json').read_bytes()).hexdigest())
    (OUTPUT/'source-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k in ('passed','baseline','final','remaining_absent','remaining_partial')},indent=2));return result

if __name__=='__main__':audit()
