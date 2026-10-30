"""Local admin UI plus an optional contributor-only HTTPS proxy ingress."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64, copy, hashlib, json, math, os, random, secrets, signal, subprocess, sys, threading, time, uuid
import torch
from .model import Config, Noah, encode, make_batch, pack_tensors, parameters, unpack_tensors, set_parameters
from .evolution import Evolution

ROOT = Path(__file__).resolve().parents[1]

class Coordinator:
    def __init__(self, data_dir=None, config=None):
        torch.set_num_threads(2)
        torch.manual_seed(17)
        self.lock = threading.RLock()
        self.data = Path(data_dir or os.environ.get('NOAH_DATA', ROOT / 'data'))
        self.data.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.data / 'noah-transformer.pt'
        source = (ROOT / 'training' / 'corpus.jsonl').read_bytes()
        self.corpus_hash = hashlib.sha256(source).hexdigest()
        documents = [json.loads(line) for line in source.decode('utf-8').splitlines() if line.strip()]
        self.train_ids = sum((encode(d['text'], True) for d in documents if d['split'] == 'train'), [])
        self.validation_docs = [encode(d['text'], True) for d in documents if d['split'] == 'validation']
        self.languages = sorted({d['language'] for d in documents})
        self.model = Noah(config or Config())
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.0006, weight_decay=.01)
        self.step, self.history = 0, []
        initial_loss_override=None
        fresh=os.environ.get('NOAH_FRESH')=='1'
        if fresh and self.checkpoint.exists(): raise ValueError('NOAH_FRESH requires a new NOAH_DATA directory to preserve existing training.')
        if self.checkpoint.exists():
            saved = torch.load(self.checkpoint, map_location='cpu', weights_only=True)
            if saved['format'] != 'noah-transformer-v1' or saved['corpus_hash'] != self.corpus_hash:
                raise ValueError('Checkpoint/data version mismatch; use a new NOAH_DATA directory.')
            self.model = Noah(Config(**saved['config']))
            self.model.load_state_dict(saved['weights'])
            self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.0006, weight_decay=.01)
            self.optimizer.load_state_dict(saved['optimizer'])
            self.step, self.history = saved['step'], saved.get('history', [])
            initial_loss_override=saved.get('initial_loss')
        elif config is None and not fresh and (ROOT/'checkpoints'/'noah-seed.npz').exists():
            seed=json.loads((ROOT/'checkpoints'/'noah-seed.json').read_text(encoding='utf-8'))
            raw=(ROOT/'checkpoints'/'noah-seed.npz').read_bytes()
            if seed['format']!='noah-seed-v1' or seed['corpus_hash']!=self.corpus_hash or hashlib.sha256(raw).hexdigest()!=seed['sha256']: raise ValueError('Noah seed checksum or corpus version mismatch')
            self.model=Noah(Config(**seed['config']))
            set_parameters(self.model,base64.b64encode(raw).decode('ascii'))
            self.optimizer=torch.optim.AdamW(self.model.parameters(),lr=.0006,weight_decay=.01)
            self.step,self.history=seed['step'],seed.get('history',[])
        self.loss = self.evaluate()
        self.initial_loss = initial_loss_override if initial_loss_override is not None else self.history[0]['loss'] if self.history else self.loss
        if not self.history: self.history.append({'step': self.step, 'loss': self.loss})
        self.active, self.duty, self.worker, self.worker_id = False, 20, None, None
        self.token = secrets.token_hex(32)
        self.invite = os.environ.get('NOAH_JOIN_TOKEN', '')
        self.nodes, self.credentials, self.jobs, self.events = {}, {}, {}, []
        self.random = random.Random(2026)
        self.event('Noah coordinator ready. Training is paused.')
        self.evolution = Evolution(self)

    def event(self, text):
        self.events.insert(0, {'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'message': text})
        del self.events[30:]

    @torch.no_grad()
    def evaluate(self):
        self.model.eval()
        losses = []
        context = self.model.config.context
        for ids in self.validation_docs:
            x, y = make_batch(ids, [0, max(0, len(ids)-context-1)], context)
            losses.append(self.model(x, y)[1].item())
        return sum(losses) / len(losses)

    def save(self):
        payload = {'format':'noah-transformer-v1', 'config':asdict(self.model.config), 'weights':self.model.state_dict(), 'optimizer':self.optimizer.state_dict(), 'step':self.step, 'corpus_hash':self.corpus_hash, 'initial_loss':self.initial_loss, 'history':self.history[-300:]}
        temporary = self.checkpoint.with_suffix('.tmp')
        torch.save(payload, temporary)
        temporary.replace(self.checkpoint)
        (self.data / 'model-card.json').write_text(json.dumps({'name':'Noah', 'architecture':'causal decoder-only Transformer', 'initialization':'random, seed 17; no pretrained weights', 'parameters':sum(p.numel() for p in self.model.parameters()), 'step':self.step, 'validationLoss':self.loss, 'initialValidationLoss':self.initial_loss, 'tokenizer':'UTF-8 bytes + BOS/EOS/PAD', 'dataLanguages':self.languages, 'corpusSHA256':self.corpus_hash, 'capability':'early research; multilingual encoding is not evidence of multilingual proficiency'}, ensure_ascii=False, indent=2), encoding='utf-8')

    def status(self):
        return {'name':'Noah', 'scope':'local-admin', 'backend':'transformer', 'training':self.active, 'duty':self.duty, 'managedWorker':self.worker is not None and self.worker.poll() is None, 'model':{'name':'Noah', 'stage':'Seed', 'type':'causal Transformer', 'step':self.step, 'parameters':sum(p.numel() for p in self.model.parameters()), 'vocab':259, 'validationLoss':self.loss, 'initialLoss':self.initial_loss, 'trainCharacters':len(self.train_ids), 'validationCharacters':sum(map(len,self.validation_docs)), 'accepted':self.step, 'languages':self.languages}, 'nodes':[{**n, 'online':time.time()*1000-n['lastSeen']<15000} for n in self.nodes.values()], 'history':self.history[-200:], 'events':self.events, 'evolution':self.evolution.status()}

    def stop_worker(self):
        if self.worker and self.worker.poll() is None:
            self.worker.terminate()
            try: self.worker.wait(timeout=5)
            except subprocess.TimeoutExpired: self.worker.kill()
        self.worker = None
        if self.worker_id in self.nodes: self.nodes[self.worker_id]['lastSeen'] = 0
        self.event('Local contribution stopped.')

    def start_worker(self, port):
        if self.worker and self.worker.poll() is None: return
        env = {**os.environ, 'NOAH_URL':f'http://127.0.0.1:{port}', 'NOAH_TOKEN':self.token}
        log = open(self.data / 'worker.log', 'ab')
        try:
            self.worker = subprocess.Popen([sys.executable,'-m','training.worker','--managed','--device','cpu'], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        finally: log.close()
        self.event('Local CPU contributor started after explicit consent.')

    def handle(self, path, body, credential, public=False, port=4317):
        node_routes = {'/api/nodes/join','/api/nodes/leave','/api/tasks/next','/api/tasks/result'}
        if public:
            permitted = path in node_routes and (secrets.compare_digest(credential,self.invite) if path.endswith('/join') and self.invite else self.credentials.get(body.get('id')) == credential and bool(credential))
        else:
            permitted = secrets.compare_digest(credential,self.token) or (path in node_routes and not path.endswith('/join') and bool(credential) and self.credentials.get(body.get('id')) == credential)
        if not permitted: raise PermissionError('Unauthorized')
        with self.lock:
            if path == '/api/evolution':
                action=body.get('action')
                if action=='start': self.evolution.start(body,port)
                elif action=='pause': self.evolution.pause()
                elif action=='rollback': self.evolution.rollback()
                else: raise ValueError('Unknown iteration action')
                return self.evolution.status()
            if path == '/api/training':
                if not isinstance(body.get('active'), bool): raise ValueError('Invalid training state')
                if not body['active']: self.evolution.pause()
                self.active = body['active']
                if type(body.get('duty')) is int and 5 <= body['duty'] <= 50: self.duty = body['duty']
                self.event('Training opened.' if self.active else 'Training paused.')
                if not self.active: self.save()
                return {'ok':True}
            if path == '/api/worker':
                if body.get('start'):
                    if body.get('consent') is not True: raise ValueError('Explicit consent required')
                    self.start_worker(port)
                else:
                    self.evolution.pause()
                    self.stop_worker()
                return {'ok':True}
            if path == '/api/nodes/join':
                if len(self.nodes) >= 100: raise ValueError('Node limit reached')
                node, key = str(uuid.uuid4()), secrets.token_hex(32)
                self.nodes[node] = {'id':node,'name':str(body.get('name','Volunteer'))[:80], 'cpu':str(body.get('cpu','CPU'))[:120], 'threads':max(1,min(256,int(body.get('threads',1)))), 'lastSeen':time.time()*1000, 'batches':0, 'computeMs':0, 'device':str(body.get('device','cpu'))[:40]}
                self.credentials[node] = key
                if body.get('managed') and not public and self.worker: self.worker_id = node
                self.event('Contributor joined: '+self.nodes[node]['name'])
                return {'id':node,'accessToken':key}
            if path == '/api/nodes/leave':
                if body.get('id') in self.nodes: self.nodes[body['id']]['lastSeen'] = 0
                return {'ok':True}
            if path in {'/api/tasks/next','/api/tasks/result'}:
                node = self.nodes.get(body.get('id'))
                if node is None: raise ValueError('Unknown node')
                node['lastSeen'] = time.time()*1000
            if path == '/api/tasks/next':
                self.jobs = {key:job for key,job in self.jobs.items() if time.time()-job['created']<120}
                if not self.active or len(self.jobs)>=8 or any(j['node']==node['id'] for j in self.jobs.values()): return {'job':None}
                key = str(uuid.uuid4())
                positions = [self.random.randrange(len(self.train_ids)-self.model.config.context-1) for _ in range(2)]
                self.jobs[key] = {'node':node['id'],'step':self.step,'created':time.time(),'positions':positions}
                return {'job':key,'backend':'transformer','version':self.step,'config':asdict(self.model.config),'weights':pack_tensors(parameters(self.model)),'ids':self.train_ids,'positions':positions,'duty':self.duty}
            if path == '/api/tasks/result':
                job = self.jobs.get(body.get('job'))
                if not job or job['node'] != node['id']: raise ValueError('Unknown job')
                del self.jobs[body['job']]
                if not self.active or body.get('version') != job['step'] or self.step-job['step']>2: return {'accepted':False,'reason':'Paused or stale'}
                if not isinstance(body.get('loss'),(int,float)) or not math.isfinite(body['loss']) or not 0<=body['loss']<=100: raise ValueError('Invalid loss')
                gradients = unpack_tensors(body.get('gradient'), parameters(self.model))
                for gradient in gradients.values():
                    if gradient.abs().max().item()>100: raise ValueError('Gradient out of range')
                previous = {name:p.detach().clone() for name,p in self.model.named_parameters()}
                optimizer_state = copy.deepcopy(self.optimizer.state_dict())
                self.optimizer.zero_grad(set_to_none=True)
                for name,p in self.model.named_parameters(): p.grad = gradients[name]
                norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(),1.0)
                if not torch.isfinite(norm): raise ValueError('Nonfinite gradient norm')
                self.optimizer.step()
                candidate_loss = self.evaluate()
                if not math.isfinite(candidate_loss) or candidate_loss>self.loss+.25:
                    with torch.no_grad():
                        for name,p in self.model.named_parameters(): p.copy_(previous[name])
                    self.optimizer.load_state_dict(optimizer_state)
                    return {'accepted':False,'reason':'Validation guard'}
                self.step += 1
                self.loss = candidate_loss
                self.history.append({'step':self.step,'loss':self.loss})
                del self.history[:-300]
                node['batches'] += 1
                node['computeMs'] += min(120000,max(0,float(body.get('duration',0))))
                if self.step % 5 == 0: self.save()
                try: self.evolution.observe()
                except Exception as error:
                    self.evolution.error=str(error)
                    self.evolution.pause('error')
                return {'accepted':True,'step':self.step,'validationLoss':self.loss}
            if path in {'/api/sample','/api/chat'}:
                prompt = str(body.get('prompt',''))[:600]
                if path.endswith('/chat'):
                    messages = body.get('messages',[])
                    if not isinstance(messages,list) or not messages: raise ValueError('Missing prompt')
                    prompt = str(messages[-1].get('content',''))[:600]
                text = self.model.generate(prompt,96)
                return {'text':text or '…','step':self.step,'experimental':True,'source':'Noah / independently initialized Transformer'}
            raise ValueError('Unknown endpoint')

def main():
    coordinator = Coordinator()
    port = int(os.environ.get('PORT','4317'))
    public_port = int(os.environ.get('NOAH_PUBLIC_PORT','0'))
    if public_port and (len(coordinator.invite)<32 or public_port==port): raise ValueError('A distinct ingress port and 32-character invite are required')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def send(self, status, value, content_type='application/json; charset=utf-8'):
            data = value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(data)
        def boundary(self):
            public = self.server.server_address[1] == public_port
            if public:
                if self.command!='POST' or self.headers.get('Origin'): raise PermissionError('Contributor API only')
            else:
                if self.headers.get('Host') not in {f'127.0.0.1:{port}',f'localhost:{port}'}: raise PermissionError('Invalid host')
                if self.headers.get('Origin') not in {None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'}: raise PermissionError('Invalid origin')
            return public
        def do_GET(self):
            try:
                self.boundary()
                if self.path=='/api/session': return self.send(200,{'token':coordinator.token})
                with coordinator.lock:
                    if self.path=='/api/status': return self.send(200,coordinator.status())
                    if self.path=='/api/model/export':
                        coordinator.save()
                        return self.send(200,coordinator.checkpoint.read_bytes(),'application/octet-stream')
                files={'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/i18n.js':('i18n.js','text/javascript'),'/style.css':('style.css','text/css'),'/mascot.svg':('mascot.svg','image/svg+xml'),'/mark.svg':('mark.svg','image/svg+xml'),'/companion.png':('companion.png','image/png')}
                if self.path not in files: return self.send(404,{'error':'Not found'})
                filename,mime=files[self.path]
                return self.send(200,(ROOT/'public'/filename).read_bytes(),mime+'; charset=utf-8')
            except PermissionError as error: self.send(403,{'error':str(error)})
            except Exception as error: self.send(400,{'error':str(error)})
        def do_POST(self):
            try:
                public=self.boundary()
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=24*1024*1024: raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict): raise ValueError('Invalid request body')
                result=coordinator.handle(self.path,body,self.headers.get('X-Noah-Token',''),public,port)
                self.send(200,result)
            except PermissionError as error: self.send(403,{'error':str(error)})
            except Exception as error: self.send(400,{'error':str(error)})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    stopped=threading.Event()
    def iteration_clock():
        while not stopped.wait(1):
            with coordinator.lock:
                try: coordinator.evolution.tick()
                except Exception as error:
                    coordinator.evolution.error=str(error)
                    coordinator.evolution.pause('error')
    threading.Thread(target=iteration_clock,daemon=True).start()
    if public_port:
        ingress=ThreadingHTTPServer(('127.0.0.1',public_port),Handler)
        threading.Thread(target=ingress.serve_forever,daemon=True).start()
    print(f'Noah: http://127.0.0.1:{port} | {sum(p.numel() for p in coordinator.model.parameters()):,} parameters | from scratch',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        stopped.set()
        with coordinator.lock:
            coordinator.active=False; coordinator.stop_worker(); coordinator.save()
        server.server_close()

if __name__=='__main__': main()
