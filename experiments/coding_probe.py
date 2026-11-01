"""Bounded response-only fine-tuning of Noah's own weights; not a general code model."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import time
import torch
from torch.nn import functional as F
from training.model import Noah, Config, BOS, EOS, PAD, encode, decode
from training.research_eval import check_pure_function

OPS = [('add','a + b'), ('subtract','a - b'), ('multiply','a * b'), ('divide','a / b')]
TEMPLATES = {
 'train':['Write Python to {op} a and b.', 'Python function: {op} a and b.', 'Please {op} a and b in Python.',
          'Implement {op} for a and b.', 'Task: {op} a and b.', 'Create a function to {op} a and b.',
          'Return code to {op} a and b.', 'In Python, {op} a and b.', 'Can you {op} a and b?',
          'Operation: {op}. Inputs: a, b.', 'Compute: {op} a and b.', 'Generate Python: {op} a and b.'],
 'validation':['Produce Python to {op} a and b.', 'Your task is to {op} a and b.',
               'Use Python to {op} a and b.', 'Function requested: {op} a and b.'],
 'audit':['I need Python that will {op} a and b.', 'Build code to {op} a and b.',
          'Solve this: {op} a and b.', 'Output a function to {op} a and b.']}

def records():
    data=[]
    for split, templates in TEMPLATES.items():
        for number, template in enumerate(templates):
            for op, expression in OPS:
                data.append({'id':f'{split}-{number}-{op}', 'split':split, 'operation':op,
                    'prompt':template.format(op=op)+'\nUse def solve(a,b). Python only.\n',
                    'answer':f'def solve(a,b):\n    return {expression}\n',
                    'provenance':'Project-authored synthetic examples, authored by coding assistant'})
    assert len({r['prompt'] for r in data})==len(data)
    return data

def batch(rows):
    sequences=[[BOS,*encode(r['prompt']),*encode(r['answer']),EOS] for r in rows]
    length=max(len(s)-1 for s in sequences)
    if length>128: raise ValueError('Example exceeds model context')
    x=torch.full((len(rows),length),PAD,dtype=torch.long)
    y=torch.full_like(x,-100)
    for i,(r,s) in enumerate(zip(rows,sequences)):
        x[i,:len(s)-1]=torch.tensor(s[:-1])
        start=len(encode(r['prompt']))
        y[i,start:len(s)-1]=torch.tensor(s[1+start:])
    return x,y

@torch.no_grad()
def generate(model,prompt):
    model.eval(); tokens=[BOS,*encode(prompt)]; output=[]
    for _ in range(64):
        logits=model(torch.tensor([tokens[-128:]]))[0][0,-1]
        logits[[BOS,PAD]]=-float('inf'); token=int(logits.argmax())
        if token==EOS: break
        tokens.append(token); output.append(token)
    return decode(output)

def cases(op):
    pairs=[(2,5),(-4,2),(0,3),(7,-2),(1.5,2),(13,7)]
    function={'add':lambda a,b:a+b,'subtract':lambda a,b:a-b,
              'multiply':lambda a,b:a*b,'divide':lambda a,b:a/b}[op]
    return [[[a,b],function(a,b)] for a,b in pairs]

@torch.no_grad()
def evaluate(model, rows):
    model.eval(); result=[]
    for row in rows:
        output=generate(model,row['prompt'])
        result.append({'id':row['id'],'output':output,'passed':check_pure_function(output,cases(row['operation']))})
    x,y=batch(rows)
    loss=F.cross_entropy(model(x)[0].reshape(-1,259),y.reshape(-1),ignore_index=-100).item()
    return {'passed':sum(r['passed'] for r in result),'total':len(rows),'responseLoss':loss,'results':result}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--source',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); out=Path(args.output); out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2); torch.manual_seed(2041); rng=random.Random(2041)
    raw=Path(args.source).read_bytes(); saved=torch.load(args.source,map_location='cpu',weights_only=True)
    assert saved['format']=='noah-transformer-v1' and saved['profile']=='research-v1'
    model=Noah(Config(**saved['config'])); model.load_state_dict(saved['weights'])
    dataset=records(); train=[r for r in dataset if r['split']=='train']
    validation=[r for r in dataset if r['split']=='validation']; audit=[r for r in dataset if r['split']=='audit']
    data_bytes=(json.dumps(dataset,ensure_ascii=False,indent=2)+'\n').encode()
    (out/'dataset.json').write_bytes(data_bytes)
    policy={'maxSteps':600,'maxSeconds':300,'seed':2041,'batchSize':8,'learningRate':0.0004,
            'releaseGate':'All 16 validation and all 16 audit prompts pass functional tests; at most a narrow experiment release',
            'scope':'Same four operations across disjoint prompt templates; synthetic wording generalization only, not unseen task families'}
    (out/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    before={s:evaluate(model,rows) for s,rows in [('validation',validation),('audit',audit)]}
    (out/'before.json').write_text(json.dumps(before,indent=2)+'\n')
    print(json.dumps({'stage':'baseline','validation':before['validation']['passed'],'audit':before['audit']['passed']}),flush=True)
    optimizer=torch.optim.AdamW(model.parameters(),lr=policy['learningRate']); started=time.monotonic(); step=0
    while step<policy['maxSteps'] and time.monotonic()-started<policy['maxSeconds']:
        x,y=batch(rng.sample(train,8)); model.train(); optimizer.zero_grad(set_to_none=True)
        loss=F.cross_entropy(model(x)[0].reshape(-1,259),y.reshape(-1),ignore_index=-100)
        if not torch.isfinite(loss): raise ValueError('Nonfinite loss')
        loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.0); optimizer.step(); step+=1
        if step%100==0: print(json.dumps({'stage':'training','step':step,'loss':loss.item()}),flush=True)
        time.sleep(.03)
    checkpoint={'format':'noah-coding-probe-v1','config':asdict(model.config),'weights':model.state_dict(),
                'optimizer':optimizer.state_dict(),'steps':step,'sourceStep':saved['step'],
                'sourceSHA256':hashlib.sha256(raw).hexdigest(),'datasetSHA256':hashlib.sha256(data_bytes).hexdigest(),
                'torchRNG':torch.get_rng_state(),'pythonRNG':rng.getstate()}
    torch.save(checkpoint,out/'candidate.pt')
    after={s:evaluate(model,rows) for s,rows in [('validation',validation),('audit',audit)]}
    restored=Noah(Config(**saved['config'])); restored.load_state_dict(torch.load(out/'candidate.pt',weights_only=True)['weights'])
    assert evaluate(restored,audit)==after['audit']
    passed=all(after[s]['passed']==after[s]['total'] for s in ['validation','audit'])
    report={'sourceStep':saved['step'],'stepsAdded':step,'elapsedAfterBaselineSeconds':round(time.monotonic()-started,1),
            'before':before,'after':after,'restoreVerified':True,'narrowExperimentGatePassed':passed,
            'generalAssistantReleaseEligible':False,'halfAssistantCapabilityMeasured':False,
            'websiteModelChanged':False,'policy':policy}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['before','after','policy']}),flush=True)
    print(json.dumps({'validation':after['validation']['passed'],'audit':after['audit']['passed'],'eachTotal':16}),flush=True)

if __name__=='__main__': main()
