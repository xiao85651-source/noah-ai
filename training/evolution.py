"""Bounded weight iteration, measured promotion and atomic, reversible releases."""
from dataclasses import asdict
from pathlib import Path
import base64, hashlib, json, math, time, uuid
import torch
from .model import Config, Noah, encode, make_batch, pack_tensors, parameters, set_parameters

ROOT=Path(__file__).resolve().parents[1]

def atomic_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)

@torch.no_grad()
def measure(model,documents):
    model.eval(); losses={}
    for doc in documents:
        ids=encode(doc['text'],True); context=min(model.config.context,len(ids)-1)
        if context<16: raise ValueError('Evaluation document too short')
        positions=sorted({0,max(0,len(ids)-context-1)})
        x,y=make_batch(ids,positions,context)
        loss=model(x,y)[1].item()
        if not math.isfinite(loss): raise ValueError('Nonfinite evaluation')
        losses.setdefault(doc['language'],[]).append(loss)
    per_language={key:sum(values)/len(values) for key,values in losses.items()}
    return {'loss':sum(per_language.values())/len(per_language),'languages':per_language}

def decision(candidate,champion):
    if set(candidate['validation']['languages'])!=set(champion['validation']['languages']): return False,'suite_mismatch'
    if set(candidate['audit']['languages'])!=set(champion['audit']['languages']): return False,'suite_mismatch'
    if not candidate['validation']['loss']<=champion['validation']['loss']*.998: return False,'no_improvement'
    if any(loss>champion['validation']['languages'][lang]*1.03 for lang,loss in candidate['validation']['languages'].items()): return False,'language_regression'
    if candidate['audit']['loss']>champion['audit']['loss']*1.01: return False,'audit_regression'
    if any(loss>champion['audit']['languages'][lang]*1.03 for lang,loss in candidate['audit']['languages'].items()): return False,'audit_language_regression'
    return True,'passed'

def read_release(folder,release_id=None):
    folder=Path(folder).resolve()
    if release_id is None: release_id=json.loads((folder/'current.json').read_text(encoding='utf-8'))['release']
    if not isinstance(release_id,str) or len(release_id)>80 or not all(c.isalnum() or c=='-' for c in release_id): raise ValueError('Invalid release ID')
    directory=(folder/release_id).resolve()
    if directory.parent!=folder: raise ValueError('Invalid release path')
    meta=json.loads((directory/'model.json').read_text(encoding='utf-8'))
    path=directory/'weights.npz'
    if path.stat().st_size>32*1024*1024: raise ValueError('Release too large')
    raw=path.read_bytes()
    if meta['format']!='noah-release-v1' or meta['id']!=release_id or hashlib.sha256(raw).hexdigest()!=meta['sha256']: raise ValueError('Release checksum mismatch')
    model=Noah(Config(**meta['config']))
    set_parameters(model,base64.b64encode(raw).decode('ascii'))
    return model.eval(),meta

class Evolution:
    def __init__(self,coordinator):
        self.c=coordinator; self.folder=self.c.data/'releases'
        source=(ROOT/'training/audit.jsonl').read_bytes()
        self.audit_hash=hashlib.sha256(source).hexdigest()
        self.audit_docs=[json.loads(line) for line in source.decode('utf-8').splitlines() if line.strip()]
        self.validation=[json.loads(line) for line in (ROOT/'training/corpus.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        self.validation=[doc for doc in self.validation if doc['split']=='validation']
        self.active=False; self.cleanup_worker=False; self.owns_worker=False; self.started=0
        self.policy={'reviewEvery':25,'maxSteps':75,'maxMinutes':30}
        self.start_step=self.last_step=self.c.step; self.reason='idle'; self.error=None
        self.records=[]
        if (self.folder/'history.json').exists(): self.records=json.loads((self.folder/'history.json').read_text(encoding='utf-8'))[-100:]

    def metrics(self): return {'validation':measure(self.c.model,self.validation),'audit':measure(self.c.model,self.audit_docs)}

    def current(self):
        if not (self.folder/'current.json').exists(): return None
        release=json.loads((self.folder/'current.json').read_text(encoding='utf-8'))['release']
        # Loading validates both structure and model checksum before trusting metadata.
        return read_release(self.folder,release)[1]

    def snapshot(self,metrics,parent,accepted,reason):
        release=f'v{self.c.step:08d}-{uuid.uuid4().hex[:8]}'
        directory=self.folder/release; directory.mkdir(parents=True)
        raw=base64.b64decode(pack_tensors(parameters(self.c.model)))
        (directory/'weights.npz').write_bytes(raw)
        meta={'format':'noah-release-v1','id':release,'parent':parent,'step':self.c.step,'config':asdict(self.c.model.config),
              'sha256':hashlib.sha256(raw).hexdigest(),'corpusSHA256':self.c.corpus_hash,'auditSHA256':self.audit_hash,
              'metrics':metrics,'accepted':accepted,'reason':reason,'createdAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              'pretrainedWeightsUsed':False,'scope':'original tiny corpus; no general capability claim'}
        atomic_json(directory/'model.json',meta)
        if accepted: atomic_json(self.folder/'current.json',{'release':release})
        self.records.insert(0,{key:meta[key] for key in ['id','parent','step','accepted','reason','createdAt','metrics']})
        self.records=self.records[:100]; atomic_json(self.folder/'history.json',self.records)
        return meta

    def start(self,body,port):
        if self.active: return
        policy={key:body.get(key,value) for key,value in {'reviewEvery':25,'maxSteps':75,'maxMinutes':30}.items()}
        if any(type(v) is not int for v in policy.values()) or not 5<=policy['reviewEvery']<=200 or not policy['reviewEvery']<=policy['maxSteps']<=1000 or not 1<=policy['maxMinutes']<=120: raise ValueError('Invalid iteration budget')
        local=body.get('local',True)
        if not isinstance(local,bool) or (local and body.get('consent') is not True): raise ValueError('CPU contribution consent required')
        if self.cleanup_worker:
            self.c.stop_worker(); self.cleanup_worker=False
        champion=self.current()
        if champion and (champion['corpusSHA256']!=self.c.corpus_hash or champion['auditSHA256']!=self.audit_hash or champion['config']!=asdict(self.c.model.config)):
            raise ValueError('Release suite changed; use a new data directory')
        if not champion: self.snapshot(self.metrics(),None,True,'baseline')
        self.policy=policy; self.start_step=self.last_step=self.c.step; self.started=time.monotonic()
        self.active=True; self.reason='running'; self.error=None; self.owns_worker=False
        try:
            if local and not (self.c.worker and self.c.worker.poll() is None):
                self.c.start_worker(port); self.owns_worker=True
            self.c.active=True; self.c.event('Automatic iteration started with bounded budget.')
        except Exception:
            self.active=False; self.c.active=False; raise

    def pause(self,reason='paused'):
        if self.active:
            self.active=False; self.c.active=False; self.reason=reason
            self.cleanup_worker=self.owns_worker; self.c.save()
            self.c.event('Automatic iteration stopped: '+reason)

    def observe(self):
        if not self.active: return
        if self.c.step-self.last_step>=self.policy['reviewEvery']:
            champion=self.current(); metrics=self.metrics()
            accepted,reason=decision(metrics,champion['metrics'])
            meta=self.snapshot(metrics,champion['id'],accepted,reason)
            self.c.event(('Released: ' if accepted else 'Candidate retained, not released: ')+meta['id']+' / '+reason)
            self.last_step=self.c.step
        if self.c.step-self.start_step>=self.policy['maxSteps']: self.pause('step_budget')

    def tick(self):
        if self.active and time.monotonic()-self.started>=self.policy['maxMinutes']*60: self.pause('time_budget')
        if self.cleanup_worker:
            self.cleanup_worker=False; self.c.stop_worker()

    def rollback(self):
        self.pause('paused')
        champion=self.current()
        if not champion or not champion.get('parent'): raise ValueError('No previous published version')
        _,parent=read_release(self.folder,champion['parent'])
        if not parent['accepted']: raise ValueError('Cannot activate a rejected candidate')
        atomic_json(self.folder/'current.json',{'release':parent['id']})
        self.c.event('Public serving version rolled back to '+parent['id'])
        return parent['id']

    def status(self):
        try:
            current=json.loads((self.folder/'current.json').read_text(encoding='utf-8'))['release'] if (self.folder/'current.json').exists() else None
        except (ValueError,OSError,KeyError): current=None
        return {'active':self.active,'reason':self.reason,'error':self.error,'policy':self.policy,'stepsThisSession':self.c.step-self.start_step,
                'currentRelease':current,'history':self.records[:12],'suite':'authored-validation-and-audit-v1'}
