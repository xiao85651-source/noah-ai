"""A volunteer explicitly runs this installed source; tasks contain data, never code."""
import argparse, json, os, platform, time
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import torch
from .model import Config, Noah, make_batch, pack_tensors, parameters, set_parameters

def compute(task, device='cpu'):
    config=Config(**task['config']); config.validate()
    if len(task['ids'])>1_000_000 or not all(type(t) is int and 0<=t<259 for t in task['ids']): raise ValueError('Invalid token data')
    if not 1<=len(task['positions'])<=8 or any(type(p) is not int or p<0 or p+config.context>=len(task['ids']) for p in task['positions']): raise ValueError('Invalid batch')
    if not isinstance(task.get('duty'),int) or not 5<=task['duty']<=50: raise ValueError('Invalid duty cycle')
    model=Noah(config).to(device)
    set_parameters(model,task['weights'])
    x,y=make_batch(task['ids'],task['positions'],config.context,device)
    model.train(); model.zero_grad(set_to_none=True)
    _,loss=model(x,y); loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
    gradients=pack_tensors({name:p.grad for name,p in model.named_parameters()})
    return {'gradient':gradients,'loss':loss.item()}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--managed',action='store_true')
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    args=parser.parse_args()
    torch.set_num_threads(1)
    if args.device=='cuda' and not torch.cuda.is_available(): raise ValueError('CUDA is unavailable; use --device cpu or install a matching official PyTorch CUDA build.')
    base=os.environ.get('NOAH_URL','http://127.0.0.1:4317').rstrip('/')
    parsed=urlparse(base)
    local=parsed.scheme=='http' and parsed.hostname=='127.0.0.1'
    if not local and (parsed.scheme!='https' or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment): raise ValueError('Remote coordinators require a plain HTTPS origin')
    if args.managed and not local: raise ValueError('Managed mode is restricted to the local UI')
    if not args.managed:
        print(f'Noah volunteer client | device: {args.device}\nComputing uses electricity and generates heat. No idle, temperature or battery detection is implemented. Ctrl+C stops contribution.\nOnly installed training code runs; the coordinator sends model tensors and public training data.')
        if input('Type JOIN to voluntarily join: ').strip()!='JOIN': return
    token=os.environ.get('NOAH_TOKEN') or os.environ.get('NOAH_NODE_TOKEN','')
    def api(path,body=None):
        request=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Noah-Token':token})
        with urlopen(request,timeout=120) as response:
            raw=response.read(24*1024*1024+1)
            if len(raw)>24*1024*1024: raise ValueError('Response too large')
            return json.loads(raw)
    if not token:
        if not local: raise ValueError('NOAH_NODE_TOKEN invitation is required')
        token=api('/api/session')['token']
    invitation=token
    def join():
        nonlocal token
        token=invitation
        registration=api('/api/nodes/join',{'name':os.environ.get('NOAH_NODE_NAME','Noah volunteer'),'cpu':platform.processor() or platform.machine(),'threads':os.cpu_count() or 1,'device':args.device,'managed':args.managed})
        token=registration['accessToken']
        return registration['id']
    node=join()
    print('Connected. Waiting for training jobs. Ctrl+C to leave.',flush=True)
    try:
        while True:
            try:
                task=api('/api/tasks/next',{'id':node})
                if not task.get('job'): time.sleep(1.5); continue
                start=time.monotonic()
                result=compute(task,args.device)
                duration=(time.monotonic()-start)*1000
                status=api('/api/tasks/result',{'id':node,'job':task['job'],'version':task['version'],'duration':duration,**result})
                print(f"step={status.get('step','-')} accepted={status.get('accepted')} loss={result['loss']:.4f} compute_ms={duration:.1f}",flush=True)
                time.sleep(max(.3,duration/1000*(100/task['duty']-1)))
            except KeyboardInterrupt: raise
            except Exception as error:
                print(type(error).__name__+': '+str(error),flush=True)
                if getattr(error,'code',None)==403:
                    try: node=join()
                    except Exception: pass
                time.sleep(3)
    except KeyboardInterrupt:
        try: api('/api/nodes/leave',{'id':node})
        except Exception: pass
        print('Contribution stopped.',flush=True)

if __name__=='__main__': main()
