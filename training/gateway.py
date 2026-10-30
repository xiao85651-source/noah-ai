"""Read-only public chat surface. No training, process control or admin session API."""
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import base64, hashlib, json, os, threading, time
import torch
from .model import Config, Noah, set_parameters
from .evolution import read_release

ROOT=Path(__file__).resolve().parents[1]

def load_published_model():
    torch.set_num_threads(2)
    checkpoint=os.environ.get('NOAH_CHAT_CHECKPOINT')
    if checkpoint:
        record=torch.load(checkpoint,map_location='cpu',weights_only=True)
        if record['format']!='noah-transformer-v1': raise ValueError('Expected a Noah checkpoint')
        model=Noah(Config(**record['config']))
        model.load_state_dict(record['weights'])
        step=record['step']
    else:
        record=json.loads((ROOT/'checkpoints/noah-seed.json').read_text(encoding='utf-8'))
        raw=(ROOT/'checkpoints/noah-seed.npz').read_bytes()
        if record['format']!='noah-seed-v1' or hashlib.sha256(raw).hexdigest()!=record['sha256']:
            raise ValueError('Noah published seed checksum mismatch')
        model=Noah(Config(**record['config']))
        set_parameters(model,base64.b64encode(raw).decode('ascii'))
        step=record['step']
    return model.eval(),step

class ServingModel:
    def __init__(self):
        self.model,self.step=load_published_model()
        self.release=None; self.lock=threading.Lock()
        self.folder=Path(os.environ.get('NOAH_RELEASES',str(ROOT/'data'/'releases')))
        self.follow=os.environ.get('NOAH_FOLLOW_RELEASES')=='1'
        self.refresh()
    def refresh(self):
        if not self.follow or not (self.folder/'current.json').exists(): return
        try:
            release=json.loads((self.folder/'current.json').read_text(encoding='utf-8'))['release']
            if release==self.release: return
            model,meta=read_release(self.folder,release)
            if not meta['accepted']: return
            self.model,self.step,self.release=model,meta['step'],release
        except (OSError,ValueError,KeyError,RuntimeError):
            # Retain the last successfully verified in-memory serving version.
            pass

def main():
    serving=ServingModel()
    port=int(os.environ.get('NOAH_CHAT_PORT','4319'))
    hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
    hosts.update(h.strip() for h in os.environ.get('NOAH_CHAT_HOSTS','').split(',') if h.strip())
    origins={'http://'+h for h in hosts if h.startswith(('localhost:','127.0.0.1:'))}
    origins.update('https://'+h for h in hosts)
    rpm=max(1,min(120,int(os.environ.get('NOAH_CHAT_RPM','10'))))
    slots=threading.BoundedSemaphore(1)
    rate_lock=threading.Lock()
    requests=defaultdict(deque)
    def public_info():
        with serving.lock:
            serving.refresh()
            return {'name':'Noah','stage':'Seed','step':serving.step,'release':serving.release,'parameters':sum(p.numel() for p in serving.model.parameters()),
                    'experimental':True,'pretrainedWeightsUsed':False,'scope':'public-inference-only'}
    files={'/':('chat.html','text/html; charset=utf-8'),'/chat.js':('chat.js','text/javascript; charset=utf-8'),
           '/i18n.js':('i18n.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),
           '/mark.svg':('mark.svg','image/svg+xml'),'/companion.png':('companion.png','image/png'),
           '/transport.js':('transport.js','text/javascript; charset=utf-8'),'/runtime.json':('runtime.json','application/json; charset=utf-8'),
           '/train.html':('train.html','text/html; charset=utf-8'),'/train.js':('train.js','text/javascript; charset=utf-8'),'/train.css':('train.css','text/css; charset=utf-8')}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_): pass  # Prompts and IPs are not written to logs.
        def send(self,status,value,mime='application/json; charset=utf-8'):
            raw=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self'; frame-ancestors 'none'")
            if status in {429,503}: self.send_header('Retry-After','60' if status==429 else '2')
            self.end_headers()
            self.wfile.write(raw)
        def boundary(self):
            if self.headers.get('Host') not in hosts: raise PermissionError('Invalid host')
            if self.headers.get('Origin') not in {None,*origins}: raise PermissionError('Invalid origin')
        def do_GET(self):
            try:
                self.boundary()
                if self.path in {'/healthz','/api/info'}: return self.send(200,public_info())
                if self.path not in files: return self.send(404,{'error':'Not found'})
                name,mime=files[self.path]
                return self.send(200,(ROOT/'public'/name).read_bytes(),mime)
            except PermissionError as error: self.send(403,{'error':str(error)})
        def do_POST(self):
            try:
                self.boundary()
                if self.path!='/api/chat': return self.send(404,{'error':'Not found'})
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=8192: return self.send(413,{'error':'Request too large'})
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict): raise ValueError('Invalid request')
                messages=body.get('messages')
                if not isinstance(messages,list) or not 1<=len(messages)<=24: raise ValueError('Missing messages')
                for message in messages:
                    if not isinstance(message,dict) or message.get('role') not in {'user','assistant'} or not isinstance(message.get('content'),str):
                        raise ValueError('Invalid message')
                prompt=messages[-1]['content']
                if messages[-1]['role']!='user' or not prompt.strip() or len(prompt)>600: raise ValueError('Use a nonempty prompt of at most 600 characters')
                now=time.monotonic()
                # Behind a proxy this intentionally treats the proxy as one shared budget.
                # Do not trust arbitrary X-Forwarded-For. Configure edge per-IP limits before launch.
                address=self.client_address[0]
                with rate_lock:
                    for key in list(requests):
                        while requests[key] and now-requests[key][0]>=60: requests[key].popleft()
                        if not requests[key]: del requests[key]
                    if address not in requests and len(requests)>=4096: return self.send(503,{'error':'Service busy'})
                    if len(requests[address])>=rpm: return self.send(429,{'error':'rate_limited'})
                    requests[address].append(now)
                if not slots.acquire(blocking=False): return self.send(503,{'error':'busy'})
                try:
                    with serving.lock:
                        serving.refresh()
                        text=serving.model.generate(prompt,96)
                        return self.send(200,{'text':text or '…','step':serving.step,'release':serving.release,'experimental':True,'source':'Noah / own published weights'})
                finally: slots.release()
            except PermissionError as error: self.send(403,{'error':str(error)})
            except (ValueError,TypeError,KeyError): self.send(400,{'error':'Invalid chat request'})
            except Exception: self.send(500,{'error':'Generation failed'})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    print(f'Noah public chat preview: http://127.0.0.1:{port} | published step {serving.step} | training/admin routes absent',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
