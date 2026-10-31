"""Small fixed development probes. Scores never establish professional competence."""
import argparse
import ast
from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import torch
from .evolution import measure
from .curriculum import summary

PROBES = [
 {'id':'bio-evidence','domain':'biopharma','prompt':'Does an uncontrolled observation prove efficacy? Reply yes or no.\n','expected':['no','不能','否']},
 {'id':'bio-reference','domain':'biopharma','prompt':'No paper details given. Is its DOI verified? Reply yes or no.\n','expected':['no','不能','否']},
 {'id':'tech-rate','domain':'technology','prompt':'21 tasks / 7 seconds = ? Reply only the number.\n','expected':['3','3.0']},
 {'id':'tech-percent','domain':'technology','prompt':'40 changes to 50. Percent increase? Reply only the number.\n','expected':['25','25%','25.0']},
 {'id':'code-add','domain':'coding','prompt':'Python only: def solve(a,b) that adds a and b.\n','cases':[[[2,5],7],[[-4,4],0],[[0,0],0]]},
 {'id':'code-multiply','domain':'coding','prompt':'Python only: def solve(a,b) that multiplies a and b.\n','cases':[[[3,4],12],[[-2,5],-10],[[7,0],0]]},
]

def check_pure_function(source,cases):
    """Execute only a bounded arithmetic AST subset, never general generated code."""
    if not isinstance(source,str) or len(source.encode('utf-8'))>2048: return False
    if source.strip().startswith('```'):
        match=re.fullmatch(r'```(?:python)?\s*\n(.*?)\n```',source.strip(),re.S)
        if not match: return False
        source=match[1]
    try: tree=ast.parse(source)
    except (SyntaxError,ValueError): return False
    allowed=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Return,ast.BinOp,ast.UnaryOp,ast.Name,ast.Load,ast.Constant,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.USub,ast.UAdd)
    nodes=list(ast.walk(tree))
    if len(nodes)>80 or any(not isinstance(n,allowed) for n in nodes): return False
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef): return False
    function=tree.body[0]
    if function.name!='solve' or function.decorator_list or function.returns or function.type_comment: return False
    args=function.args
    if [a.arg for a in args.args]!=['a','b'] or args.posonlyargs or args.vararg or args.kwarg or args.kwonlyargs or args.defaults or args.kw_defaults: return False
    if any(a.annotation for a in args.args) or len(function.body)!=1 or not isinstance(function.body[0],ast.Return): return False
    if any(isinstance(n,ast.Name) and n.id not in {'a','b'} for n in nodes): return False
    if any(isinstance(n,ast.Constant) and (type(n.value) not in {int,float} or abs(n.value)>1000000) for n in nodes): return False
    runner="import json,sys\np=json.load(sys.stdin)\ng={'__builtins__':{}}\nexec(compile(p['source'],'<bounded-pure-function>','exec'),g)\nprint(json.dumps([g['solve'](*case[0]) for case in p['cases']]))"
    try:
        result=subprocess.run([sys.executable,'-I','-S','-c',runner],input=json.dumps({'source':source,'cases':cases}),text=True,capture_output=True,timeout=2)
        return result.returncode==0 and len(result.stdout)<4096 and json.loads(result.stdout)==[case[1] for case in cases]
    except (OSError,ValueError,subprocess.TimeoutExpired): return False

def evaluate_probes(model):
    results=[]
    for probe in PROBES:
        torch.manual_seed(2026)
        output=model.generate(probe['prompt'],128,temperature=.2)
        if 'cases' in probe: passed=check_pure_function(output,probe['cases'])
        else: passed=output.strip().lower() in probe['expected']
        results.append({'id':probe['id'],'domain':probe['domain'],'passed':passed,'output':output})
    return {'probes':results,'passed':sum(r['passed'] for r in results),'total':len(results)}

def evaluate(coordinator):
    probes=evaluate_probes(coordinator.model)
    return {'profile':coordinator.profile,'step':coordinator.step,'curriculum':summary(coordinator.profile),
            'validation':measure(coordinator.model,[d for d in coordinator.documents if d['split']=='validation']),
            'audit':measure(coordinator.model,coordinator.evolution.audit_docs),
            **probes,
            'scope':'tiny known development probes, not independent clinical/scientific/software validation',
            'specialistReady':False,'automaticPublicationAllowed':False}

def main():
    from .coordinator import Coordinator
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    if os.environ.get('NOAH_PROFILE')!='research-v1': raise ValueError('Set NOAH_PROFILE=research-v1')
    report=evaluate(Coordinator());path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['profile','step','passed','total','specialistReady']},ensure_ascii=False))

if __name__=='__main__': main()
