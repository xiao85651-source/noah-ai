"""HTTPS-platform edge: owner-authenticated console, separate invited node ingress."""
import base64
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from training.google_login import AUTH_PATHS, PUBLIC_ORIGINS, GoogleLogin

NODE_PATHS={'/api/nodes/join','/api/nodes/leave','/api/tasks/next','/api/tasks/result'}

@dataclass
class Settings:
    origin: str
    password: str
    invitation: str
    storage: str
    user: str='owner'
    admin_port: int=4317
    node_port: int=4318
    google_client_id: str=''
    auth_origins: tuple=()

    def validate(self):
        parsed=urlsplit(self.origin)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('NOAH_CLOUD_ORIGIN must be a plain HTTPS origin')
        if self.storage not in {'persistent','ephemeral-test'}: raise ValueError('Choose explicit storage mode')
        if len(self.password)<32 or len(self.invitation)<32 or self.password==self.invitation:
            raise ValueError('Distinct owner and invitation secrets of at least 32 characters are required')
        if any('CHANGE' in secret.upper() or '<' in secret for secret in [self.password,self.invitation]):
            raise ValueError('Replace example secrets before starting')
        if not self.user or ':' in self.user: raise ValueError('Invalid owner username')
        if self.admin_port==self.node_port: raise ValueError('Separate internal ports are required')

def owner_authorized(header,settings):
    try:
        scheme,encoded=(header or '').split(' ',1)
        if scheme.lower()!='basic': return False
        user,password=base64.b64decode(encoded,validate=True).decode('utf-8').split(':',1)
        return hmac.compare_digest(user.encode(),settings.user.encode()) and hmac.compare_digest(password.encode(),settings.password.encode())
    except (ValueError,UnicodeError): return False

def make_handler(settings,google_login=None):
    settings.validate()
    identity=google_login or GoogleLogin(settings.google_client_id)
    public_origins=set(settings.auth_origins or PUBLIC_ORIGINS)|{settings.origin}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def send(self,status,body,mime='application/json; charset=utf-8',headers=None,owner_challenge=True):
            raw=body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            if status==401 and owner_challenge:self.send_header('WWW-Authenticate','Basic realm="Noah owner", charset="UTF-8"')
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers();self.wfile.write(raw)
        def public_auth(self,path):
            origin=self.headers.get('Origin')
            cors={'Vary':'Origin'}
            if origin in public_origins:
                cors.update({'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type, Authorization','Access-Control-Max-Age':'600'})
            def answer(status,body):return self.send(status,body,headers=cors,owner_challenge=False)
            if (origin is not None and origin not in public_origins) or (self.command in {'POST','OPTIONS'} and origin not in public_origins):
                return answer(403,{'error':'invalid_origin'})
            if self.command=='OPTIONS':return answer(204,b'')
            if self.command=='GET':
                if path=='/api/auth/config':return answer(200,{'enabled':identity.enabled,'clientId':identity.client_id,'provider':'google'})
                if path=='/api/auth/challenge':return answer(*identity.challenge())
                if path=='/api/auth/me':return answer(*identity.me(self.headers.get('Authorization')))
                return answer(405,{'error':'method_not_allowed'})
            if self.command!='POST' or path not in {'/api/auth/google','/api/auth/logout'}:
                return answer(405,{'error':'method_not_allowed'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=18000:return answer(413,{'error':'request_too_large'})
                if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':
                    return answer(415,{'error':'json_required'})
                self.connection.settimeout(15)
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):return answer(400,{'error':'invalid_request'})
            except (ValueError,OSError):return answer(400,{'error':'invalid_request'})
            if path=='/api/auth/google':return answer(*identity.login(body))
            identity.logout(self.headers.get('Authorization'))
            return answer(204,b'')
        def relay(self):
            try:
                path=urlsplit(self.path).path
                if path in AUTH_PATHS:return self.public_auth(path)
                body=None
                if self.command=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=24*1024*1024:return self.send(413,{'error':'Invalid request size'})
                    self.connection.settimeout(20);body=self.rfile.read(length)
                if self.path=='/healthz' and self.command=='GET':
                    with urlopen(f'http://127.0.0.1:{settings.admin_port}/api/status',timeout=3) as response:
                        ready=response.status==200
                    return self.send(200,{'ready':ready,'storage':settings.storage,'trainingEnabled':settings.storage=='persistent'})
                node=self.path in NODE_PATHS
                if node:
                    if self.command!='POST' or self.headers.get('Origin'):
                        return self.send(403,{'error':'Installed contributor clients only'})
                else:
                    if not owner_authorized(self.headers.get('Authorization'),settings):
                        return self.send(401,{'error':'Owner authentication required'})
                    if self.headers.get('Origin') not in {None,settings.origin}:
                        return self.send(403,{'error':'Invalid owner origin'})
                if settings.storage=='ephemeral-test' and self.command=='POST':
                    return self.send(403,{'error':'Free connectivity test: training disabled until persistent storage is configured'})
                port=settings.node_port if node else settings.admin_port
                request=Request(f'http://127.0.0.1:{port}'+self.path,data=body,method=self.command,
                    headers={'Content-Type':'application/json','X-Noah-Token':self.headers.get('X-Noah-Token','')})
                try: upstream=urlopen(request,timeout=60)
                except HTTPError as error: upstream=error
                with upstream:
                    raw=upstream.read(32*1024*1024+1)
                    if len(raw)>32*1024*1024:return self.send(502,{'error':'Upstream response too large'})
                    if self.path=='/api/status' and upstream.status==200:
                        value=json.loads(raw);value['cloud']={'storage':settings.storage,'trainingEnabled':settings.storage=='persistent'}
                        raw=json.dumps(value,ensure_ascii=False).encode('utf-8')
                    self.send(upstream.status,raw,upstream.headers.get('Content-Type','application/json'))
            except (ValueError,OverflowError): self.send(400,{'error':'Invalid request'})
            except OSError: self.send(503,{'error':'Coordinator unavailable'})
        do_GET=relay
        do_POST=relay
        def do_OPTIONS(self):
            path=urlsplit(self.path).path
            if path in AUTH_PATHS:return self.public_auth(path)
            self.send(403,{'error':'Origin not allowed'})
    return Handler

def main():
    origin=os.environ.get('NOAH_CLOUD_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL','').rstrip('/')
    settings=Settings(origin,os.environ.get('NOAH_OWNER_PASSWORD',''),
                      os.environ.get('NOAH_JOIN_TOKEN',''),os.environ.get('NOAH_STORAGE_MODE',''),
                      os.environ.get('NOAH_OWNER_USER','owner'),
                      int(os.environ.get('NOAH_INTERNAL_ADMIN_PORT','4317')),int(os.environ.get('NOAH_INTERNAL_NODE_PORT','4318')),
                      os.environ.get('NOAH_GOOGLE_CLIENT_ID','').strip(),
                      tuple(value.strip() for value in os.environ.get('NOAH_AUTH_ORIGINS','').split(',') if value.strip()))
    settings.validate()
    root=Path(__file__).resolve().parents[1]
    data=Path(os.environ.get('NOAH_DATA','/var/data/noah'))
    if not data.is_absolute():raise ValueError('Use an absolute persistent data path')
    data.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'PORT':str(settings.admin_port),'NOAH_PUBLIC_PORT':str(settings.node_port),'NOAH_DATA':str(data)}
    server=ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','10000'))),make_handler(settings))
    try:child=subprocess.Popen([sys.executable,'-m','training.coordinator'],cwd=root,env=env)
    except Exception:server.server_close();raise
    def stop(*_):threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop)
    if hasattr(signal,'SIGINT'):signal.signal(signal.SIGINT,stop)
    print('Noah cloud edge started; TLS must be terminated by the hosting platform. Training starts paused.',flush=True)
    try:server.serve_forever()
    finally:
        server.server_close()
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait()

if __name__=='__main__':main()
