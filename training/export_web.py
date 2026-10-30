"""Export only our weights for browser inference, without Python dependencies at deploy time."""
from dataclasses import asdict
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import torch
from .gateway import load_published_model
from .evolution import read_release, atomic_json

def export(model,step,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    arrays=[];tensors={};offset=0
    for name,parameter in model.named_parameters():
        values=parameter.detach().cpu().numpy().astype('<f4').reshape(-1)
        arrays.append(values);tensors[name]={'offset':offset,'length':len(values),'shape':list(parameter.shape)};offset+=len(values)
    raw=np.concatenate(arrays).tobytes()
    reference=[]
    with torch.no_grad():
        for tokens in [[256,78,111,97,104],[256,228,189,160,229,165,189],[1,2,3,4,5,6]]:
            logits=model(torch.tensor([tokens]))[0][0,-1].tolist()
            reference.append({'tokens':tokens,'logits':logits})
    manifest={'format':'noah-browser-v1','config':asdict(model.config),'step':step,'parameters':offset,'sha256':hashlib.sha256(raw).hexdigest(),'tensors':tensors,'referenceCases':reference,'source':'Noah own independently trained weights','pretrainedWeightsUsed':False}
    temporary=folder/'noah-web.bin.tmp';temporary.write_bytes(raw);temporary.replace(folder/'noah-web.bin')
    atomic_json(folder/'noah-web.json',manifest)
    return manifest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release-dir');args=parser.parse_args()
    if args.release_dir:
        model,meta=read_release(args.release_dir);step=meta['step']
        if not meta['accepted']: raise ValueError('Only accepted releases can be exported')
    else: model,step=load_published_model()
    manifest=export(model,step,Path(__file__).resolve().parents[1]/'checkpoints')
    print(json.dumps({'step':step,'parameters':manifest['parameters'],'sha256':manifest['sha256']}))

if __name__=='__main__': main()
