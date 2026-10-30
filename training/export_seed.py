"""Export this project's own trained weights, without optimizer or local logs."""
from dataclasses import asdict
import base64, hashlib, json
from .coordinator import Coordinator, ROOT
from .model import pack_tensors, parameters

def main():
    c=Coordinator()
    folder=ROOT/'checkpoints'; folder.mkdir(exist_ok=True)
    raw=base64.b64decode(pack_tensors(parameters(c.model)))
    (folder/'noah-seed.npz').write_bytes(raw)
    metadata={'format':'noah-seed-v1','name':'Noah','config':asdict(c.model.config),'step':c.step,'corpus_hash':c.corpus_hash,'sha256':hashlib.sha256(raw).hexdigest(),'parameters':sum(p.numel() for p in c.model.parameters()),'validationLoss':c.loss,'history':c.history,'pretrainedWeightsUsed':False,'source':'Noah project own training run; not an external base model','capability':'Seed research checkpoint; not a reliable assistant'}
    (folder/'noah-seed.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps({'file':str(folder/'noah-seed.npz'),'bytes':len(raw),'step':c.step,'sha256':metadata['sha256']}))

if __name__=='__main__': main()
