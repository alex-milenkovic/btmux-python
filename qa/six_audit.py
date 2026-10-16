"""Fighter APS generation and QA correspondence audit; no project API."""
import ast,hashlib,json
from pathlib import Path
from six_location_aerofighters import all_cases
from six_support import ROOT,OUTPUT,CATALOG

def main():
    manifest=json.loads((ROOT/'specs/six-location-aerofighters-acceptance-manifest.json').read_text());features=[]
    for feature in manifest['features']:
        file=feature['path'];stem=Path(file).stem
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==feature['sha256']
        ir=json.loads((ROOT/f'tmp/acceptance/six_location_aerofighters-{stem}.json').read_text())
        for parsed,spec in zip(ir['scenarios'],feature['scenarios']):
            assert parsed['name']==spec['name']
            assert parsed['examples']==spec['examples']
        assert len(ir['scenarios'])==len(feature['scenarios'])
        generated=ROOT/f'tmp/acceptance/generated/features-six-location-aerofighters-{stem}-feature_acceptance.py'
        tree=ast.parse(generated.read_text());assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='IR' for t in n.targets))
        assert json.loads(ast.literal_eval(assignment.value.args[0]))==ir
        meta=json.loads((ROOT/f'tmp/acceptance/generated/metadata/features-six-location-aerofighters-{stem}-feature.json').read_text())
        assert meta['implementation_hash']=='sha256:'+hashlib.sha256(generated.read_bytes()).hexdigest()
        assert meta['generated_files']==[str(generated.relative_to(ROOT))]
        features.append(dict(feature=file,sha256=feature['sha256'],outlines=len(ir['scenarios']),examples=sum(len(s['examples']) for s in ir['scenarios']),parsed_generated_match=True))
    cases=all_cases()
    references={name:hashlib.sha256((CATALOG/name).read_bytes()).hexdigest() for name in ('CHP-W5','DS.Union','Cavalry','WVR-6R')}
    summary=dict(features=features,approved_examples=sum(f['examples'] for f in features),qa_cases=len(cases),qa_example_correspondence=True,selected_original_sha256=references)
    assert summary['approved_examples']==260
    OUTPUT.mkdir(parents=True,exist_ok=True);(OUTPUT/'correspondence.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('260 approved parsed/generated examples match; '+str(len(cases))+' independent QA cases mapped; four selected original byte hashes recorded')

if __name__=='__main__':main()
