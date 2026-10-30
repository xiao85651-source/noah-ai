"""Real process/HTTP smoke test, isolated from the owner's training data."""
import io, json, os, secrets, socket, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import torch
from .worker import compute

ROOT = Path(__file__).resolve().parents[1]

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

class HttpLifecycleTests(unittest.TestCase):
    def test_contributor_training_export_generation_and_restart(self):
        with tempfile.TemporaryDirectory(prefix='noah-http-') as directory:
            port, ingress = free_port(), free_port()
            while ingress == port: ingress = free_port()
            invite = secrets.token_hex(24)
            env = {**os.environ, 'PORT':str(port), 'NOAH_PUBLIC_PORT':str(ingress),
                   'NOAH_DATA':directory, 'NOAH_JOIN_TOKEN':invite}
            env.pop('NOAH_FRESH', None)
            process = None
            token = ''
            def call(path, body=None, credential=None, public=False, extra=None):
                headers = {'Content-Type':'application/json', 'X-Noah-Token':token if credential is None else credential, **(extra or {})}
                request = Request(f'http://127.0.0.1:{ingress if public else port}'+path,
                                  data=json.dumps(body).encode() if body is not None else None, headers=headers)
                try:
                    with urlopen(request, timeout=15) as response:
                        raw = response.read()
                        value = json.loads(raw) if 'json' in response.headers.get('Content-Type','') else raw
                        return response.status, value
                except HTTPError as error:
                    return error.code, json.loads(error.read())
            def start():
                nonlocal process, token
                process = subprocess.Popen([sys.executable,'-m','training.coordinator'],cwd=ROOT,env=env,
                                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                deadline = time.monotonic()+30
                while time.monotonic()<deadline:
                    if process.poll() is not None: self.fail('Coordinator exited before becoming ready')
                    try:
                        token = call('/api/session')[1]['token']
                        return
                    except (URLError, ConnectionError): time.sleep(.1)
                self.fail('Coordinator readiness timeout')
            def stop():
                if process and process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)
            try:
                start()
                status = call('/api/status')[1]
                self.assertFalse(status['training'])
                self.assertFalse(status['managedWorker'])
                initial_step = status['model']['step']
                self.assertEqual(call('/api/training',{'active':True},credential='')[0],403)
                self.assertEqual(call('/api/training',{'active':True},extra={'Origin':'https://example.com'})[0],403)
                self.assertEqual(call('/api/worker',{'start':True})[0],400)
                self.assertEqual(call('/api/session',public=True)[0],403)
                self.assertEqual(call('/api/training',{'active':True},invite,True)[0],403)
                self.assertEqual(call('/api/nodes/join',{'name':'unauthorized'},'bad',True)[0],403)
                node = call('/api/nodes/join',{'name':'Invited smoke tester'},invite,True)[1]
                self.assertIn('accessToken',node)
                self.assertIsNone(call('/api/tasks/next',{'id':node['id']},node['accessToken'],True)[1]['job'])
                self.assertEqual(call('/api/tasks/next',{'id':node['id']},invite,True)[0],403)
                call('/api/training',{'active':True,'duty':20})
                task = call('/api/tasks/next',{'id':node['id']},node['accessToken'],True)[1]
                result = compute(task)
                payload = {'id':node['id'],'job':task['job'],'version':task['version'],'duration':10,**result}
                accepted = call('/api/tasks/result',payload,node['accessToken'],True)[1]
                self.assertTrue(accepted['accepted'])
                self.assertEqual(accepted['step'],initial_step+1)
                self.assertEqual(call('/api/tasks/result',payload,node['accessToken'],True)[0],400)
                # The web consent action must start the actual installed worker process.
                self.assertEqual(call('/api/worker',{'start':True,'consent':True})[0],200)
                deadline = time.monotonic()+20
                while time.monotonic()<deadline:
                    status=call('/api/status')[1]
                    if status['model']['step']>initial_step+1: break
                    time.sleep(.2)
                self.assertGreater(status['model']['step'],initial_step+1)
                self.assertTrue(status['managedWorker'])
                call('/api/training',{'active':False})
                call('/api/worker',{'start':False})
                status=call('/api/status')[1]
                self.assertFalse(status['managedWorker'])
                self.assertFalse(status['training'])
                saved_step=status['model']['step']
                exported=call('/api/model/export')[1]
                checkpoint=torch.load(io.BytesIO(exported),map_location='cpu',weights_only=True)
                self.assertEqual(checkpoint['step'],saved_step)
                self.assertTrue(checkpoint['weights'])
                sample=call('/api/sample',{'prompt':'Noah is'})[1]
                chat=call('/api/chat',{'messages':[{'role':'user','content':'Hello, Noah'}]})[1]
                for generated in [sample,chat]:
                    self.assertTrue(generated['experimental'])
                    self.assertEqual(generated['step'],saved_step)
                    self.assertIsInstance(generated['text'],str)
                call('/api/nodes/leave',{'id':node['id']},node['accessToken'],True)
                stop(); start()
                restored=call('/api/status')[1]
                self.assertEqual(restored['model']['step'],saved_step)
                self.assertAlmostEqual(restored['model']['validationLoss'],status['model']['validationLoss'],places=6)
                self.assertFalse(restored['training'])
                self.assertFalse(restored['managedWorker'])
            finally:
                if process and process.poll() is None:
                    try: call('/api/worker',{'start':False})
                    except Exception: pass
                stop()

if __name__ == '__main__': unittest.main()
