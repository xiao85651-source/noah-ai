import json, os, subprocess, sys, time, unittest
from urllib.error import URLError
from .test_http import ROOT, free_port
from urllib.request import Request, urlopen
from urllib.error import HTTPError

class PublicGatewayTests(unittest.TestCase):
    def test_published_inference_without_training_or_admin_routes(self):
        port=free_port()
        env={**os.environ,'NOAH_CHAT_PORT':str(port),'NOAH_CHAT_RPM':'2'}
        env.pop('NOAH_CHAT_CHECKPOINT',None)
        process=subprocess.Popen([sys.executable,'-m','training.gateway'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        def call(path,body=None,headers=None):
            request=Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
            try:
                with urlopen(request,timeout=15) as response: return response.status,response.read(),response.headers
            except HTTPError as error: return error.code,error.read(),error.headers
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if process.poll() is not None: self.fail('Public gateway exited')
                try:
                    info=json.loads(call('/api/info')[1]);break
                except (URLError,ConnectionError): time.sleep(.1)
            else: self.fail('Public gateway readiness timeout')
            self.assertEqual(info['scope'],'public-inference-only')
            self.assertEqual(info['step'],100)
            self.assertFalse(info['pretrainedWeightsUsed'])
            self.assertEqual(call('/')[0],200)
            self.assertEqual(call('/companion.png')[0],200)
            for path in ['/api/session','/api/status','/api/model/export','/app.js','/training/model.py']:
                self.assertEqual(call(path)[0],404)
            for path in ['/api/training','/api/worker','/api/nodes/join']:
                self.assertEqual(call(path,{'start':True,'active':True})[0],404)
            payload={'messages':[{'role':'user','content':'Noah is'}]}
            self.assertEqual(call('/api/chat',payload,{'Origin':'https://example.com'})[0],403)
            self.assertEqual(call('/api/chat',{'messages':'bad'})[0],400)
            self.assertEqual(call('/api/chat',{'messages':[{'role':'user','content':'x'*601}]})[0],400)
            self.assertEqual(call('/api/chat',{'data':'x'*9000})[0],413)
            for _ in range(2):
                status,raw,_=call('/api/chat',payload)
                self.assertEqual(status,200)
                self.assertTrue(json.loads(raw)['text'])
                self.assertEqual(json.loads(raw)['step'],100)
            status,_,headers=call('/api/chat',payload)
            self.assertEqual(status,429)
            self.assertEqual(headers['Retry-After'],'60')
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)

if __name__=='__main__': unittest.main()
