"""Single-device warm-up from random weights or a local Noah checkpoint."""
import argparse, json, time
import torch
from .coordinator import Coordinator
from .model import make_batch

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--steps',type=int,default=100)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    args=parser.parse_args()
    if not 1<=args.steps<=100000: raise ValueError('Choose 1 to 100000 steps')
    if args.device=='cuda' and not torch.cuda.is_available(): raise ValueError('CUDA is unavailable')
    c=Coordinator()
    # Coordinator checkpoints stay on CPU for portable inference and contribution.
    c.model.to(args.device)
    for state in c.optimizer.state.values():
        for key,value in state.items():
            if isinstance(value,torch.Tensor): state[key]=value.to(args.device)
    start=time.monotonic()
    initial=c.loss
    for index in range(args.steps):
        positions=[c.random.randrange(len(c.train_ids)-c.model.config.context-1) for _ in range(2)]
        x,y=make_batch(c.train_ids,positions,c.model.config.context,args.device)
        c.model.train(); c.optimizer.zero_grad(set_to_none=True)
        _,loss=c.model(x,y); loss.backward()
        torch.nn.utils.clip_grad_norm_(c.model.parameters(),1.0)
        c.optimizer.step(); c.step+=1
        if (index+1)%10==0 or index==args.steps-1:
            # Evaluate with CPU tensors through the same held-out validation routine.
            c.model.to('cpu'); c.loss=c.evaluate()
            c.history.append({'step':c.step,'loss':c.loss})
            print(json.dumps({'step':c.step,'trainLoss':loss.item(),'validationLoss':c.loss}),flush=True)
            if args.device=='cuda':
                c.model.to('cuda')
                for state in c.optimizer.state.values():
                    for key,value in state.items():
                        if isinstance(value,torch.Tensor): state[key]=value.to('cuda')
    c.model.to('cpu')
    for state in c.optimizer.state.values():
        for key,value in state.items():
            if isinstance(value,torch.Tensor): state[key]=value.cpu()
    c.save()
    result={'name':'Noah','architecture':'causal Transformer','parameters':sum(p.numel() for p in c.model.parameters()),'stepsThisRun':args.steps,'totalSteps':c.step,'initialValidationLossThisRun':initial,'finalValidationLoss':c.loss,'elapsedSeconds':round(time.monotonic()-start,2),'pretrainedWeightsUsed':False,'languages':c.languages,'deviceTested':args.device,'scope':'local authored seed corpus; not a capable assistant'}
    (c.data/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)

if __name__=='__main__': main()
