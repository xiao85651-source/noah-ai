import base64
import copy
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request,urlopen
from unittest.mock import patch
from .cloud import Settings,make_handler
from .coordinator import Coordinator
from .curriculum import load_curriculum,summary,validate_research
from .evolution import decision
from .model import Config
from .research_eval import check_pure_function
from .test_http import ROOT,free_port
from .worker import compute

class ResearchTests(unittest.TestCase):
    def test_authored_splits_and_domain_regression_gate(self):
        records,_=load_curriculum('research-v1')
        self.assertEqual(summary('research-v1')['splits'],{'train':36,'validation':6,'audit':6})
        bad=copy.deepcopy(records);bad[-1]['group']=bad[0]['group']
        with self.assertRaises(ValueError):validate_research(bad)
        bad=copy.deepcopy(records);bad[0]['provenance']='unreviewed-web-copy'
        with self.assertRaises(ValueError):validate_research(bad)
        base={'validation':{'loss':2.,'languages':{'en':2.},'domains':{'biopharma':2.,'coding':2.}},'audit':{'loss':2.,'languages':{'en':2.},'domains':{'biopharma':2.,'coding':2.}}}
        candidate=copy.deepcopy(base);candidate['validation']['loss']=1.8;candidate['validation']['domains']['biopharma']=2.2
        self.assertEqual(decision(candidate,base),(False,'domain_regression'))
        candidate['developmentProbes']={'passed':0,'total':6}
        self.assertEqual(decision(candidate,base),(False,'research_probe_gate'))

    def test_research_gradients_reload_and_cross_profile_rejection(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'NOAH_PROFILE':'research-v1'}):
            c=Coordinator(directory,Config(context=32,width=32,heads=4,layers=1))
            self.assertEqual(c.step,0);self.assertEqual(c.profile,'research-v1')
            self.assertEqual(len(c.evolution.audit_docs),6)
            node=c.handle('/api/nodes/join',{'name':'Isolated researcher'},c.token)
            c.handle('/api/training',{'active':True},c.token)
            task=c.handle('/api/tasks/next',{'id':node['id']},node['accessToken'])
            outcome=c.handle('/api/tasks/result',{'id':node['id'],'job':task['job'],'version':task['version'],'duration':1,**compute(task)},node['accessToken'])
            self.assertTrue(outcome['accepted']);c.save()
            digest=hashlib.sha256(c.checkpoint.read_bytes()).hexdigest()
            self.assertEqual(Coordinator(directory).step,1)
            with patch.dict(os.environ,{'NOAH_PROFILE':'seed'}):
                with self.assertRaises(ValueError):Coordinator(directory)
            self.assertEqual(hashlib.sha256(c.checkpoint.read_bytes()).hexdigest(),digest)

    def test_bounded_generated_arithmetic_checks(self):
        cases=[[[2,3],5],[[-4,4],0]]
        self.assertTrue(check_pure_function('def solve(a,b):\n return a+b',cases))
        self.assertFalse(check_pure_function('def solve(a,b):\n return a-b',cases))
        for source in ['import os\ndef solve(a,b): return a+b','def solve(a,b): return a.__class__','def solve(a,b): return a**b','def solve(a,b): return eval(a)','def solve(a,b):\n while True: pass']:
            self.assertFalse(check_pure_function(source,cases))

class CloudBoundaryTests(unittest.TestCase):
    def test_real_proxy_owner_node_separation_and_free_read_only_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            admin,node_port=free_port(),free_port()
            while node_port==admin:node_port=free_port()
            invitation,password=secrets.token_hex(24),secrets.token_hex(24)
            env={**os.environ,'PORT':str(admin),'NOAH_PUBLIC_PORT':str(node_port),'NOAH_JOIN_TOKEN':invitation,'NOAH_DATA':directory,'NOAH_PROFILE':'research-v1'}
            env.pop('NOAH_FRESH',None)
            process=subprocess.Popen([sys.executable,'-m','training.coordinator'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            servers=[]
            def launch(storage):
                settings=Settings('https://example.test',password,invitation,storage,admin_port=admin,node_port=node_port)
                server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(settings));servers.append(server)
                threading.Thread(target=server.serve_forever,daemon=True).start();return server.server_port
            auth='Basic '+base64.b64encode(('owner:'+password).encode()).decode()
            def call(port,path,body=None,owner=False,token='',origin=None):
                headers={'Content-Type':'application/json','X-Noah-Token':token}
                if owner:headers['Authorization']=auth
                if origin:headers['Origin']=origin
                request=Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
                try:
                    with urlopen(request,timeout=10) as response:return response.status,response.read()
                except HTTPError as error:return error.code,error.read()
            try:
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    if process.poll() is not None:self.fail('Coordinator exited')
                    try:
                        with urlopen(f'http://127.0.0.1:{admin}/api/status',timeout=1):break
                    except (OSError,URLError):time.sleep(.1)
                else:self.fail('Coordinator readiness timeout')
                port=launch('persistent')
                self.assertEqual(call(port,'/api/session')[0],401)
                self.assertEqual(call(port,'/')[0],401)
                self.assertEqual(call(port,'/',owner=True)[0],200)
                self.assertEqual(call(port,'/api/status',owner=True,origin='https://foreign.test')[0],403)
                session=json.loads(call(port,'/api/session',owner=True)[1])['token']
                self.assertEqual(call(port,'/api/nodes/join',{'name':'bad'},token='wrong')[0],403)
                self.assertEqual(call(port,'/api/nodes/join')[0],403)
                status,raw=call(port,'/api/nodes/join',{'name':'Invited cloud tester'},token=invitation)
                self.assertEqual(status,200);key=json.loads(raw)['accessToken']
                self.assertEqual(call(port,'/api/session',token=key)[0],401)
                self.assertEqual(call(port,'/api/training',{'active':False},owner=True,token=session,origin='https://example.test')[0],200)
                free=launch('ephemeral-test')
                self.assertFalse(json.loads(call(free,'/healthz')[1])['trainingEnabled'])
                self.assertEqual(call(free,'/api/training',{'active':True},owner=True,token=session)[0],403)
                self.assertEqual(call(free,'/api/nodes/join',{'name':'blocked'},token=invitation)[0],403)
                self.assertEqual(json.loads(call(free,'/api/status',owner=True)[1])['cloud']['storage'],'ephemeral-test')
            finally:
                for server in servers:server.shutdown();server.server_close()
                if process.poll() is None:process.terminate();process.wait(timeout=10)

if __name__=='__main__':unittest.main()
