import base64, io, tempfile, unittest, zipfile
from pathlib import Path
import numpy as np
import torch
from .model import Config, Noah, encode, decode, pack_tensors, unpack_tensors, parameters
from .coordinator import Coordinator
from .worker import compute

class TrainingTests(unittest.TestCase):
    def test_multilingual_byte_roundtrip(self):
        for text in ['你好，诺亚。','Hello, Noah.','こんにちは','Hola, Noah.','مرحبا يا نوح']:
            self.assertEqual(decode(encode(text)),text)

    def test_attention_cannot_see_future(self):
        torch.manual_seed(1)
        model=Noah(Config(context=16,width=32,heads=4,layers=1)).eval()
        one=torch.tensor([[1,2,3,4,5]])
        two=torch.tensor([[1,2,3,10,11]])
        with torch.no_grad():
            a=model(one)[0][:,:3]; b=model(two)[0][:,:3]
        self.assertTrue(torch.allclose(a,b,atol=1e-6))

    def test_safe_tensor_transport(self):
        model=Noah(Config(context=16,width=32,heads=4,layers=1))
        values=parameters(model)
        restored=unpack_tensors(pack_tensors(values),values)
        for name,p in values.items(): self.assertTrue(torch.equal(p,restored[name]))
        bad={name:p.detach().clone() for name,p in values.items()}
        next(iter(bad.values())).view(-1)[0]=float('nan')
        with self.assertRaises(ValueError): unpack_tensors(pack_tensors(bad),values)

    def test_two_contributor_identities_training_pause_and_checkpoint(self):
        with tempfile.TemporaryDirectory(prefix='noah-training-test-') as directory:
            c=Coordinator(directory,Config(context=32,width=32,heads=4,layers=1))
            key=c.token
            with self.assertRaises(PermissionError): c.handle('/api/training',{'active':True},'invalid')
            with self.assertRaises(ValueError): c.handle('/api/worker',{'start':True},key)
            first=c.handle('/api/nodes/join',{'name':'first'},key)
            second=c.handle('/api/nodes/join',{'name':'second'},key)
            self.assertIsNone(c.handle('/api/tasks/next',{'id':first['id']},first['accessToken'])['job'])
            c.handle('/api/training',{'active':True},key)
            task=c.handle('/api/tasks/next',{'id':first['id']},first['accessToken'])
            with self.assertRaises(PermissionError): c.handle('/api/tasks/next',{'id':first['id']},second['accessToken'])
            result=compute(task)
            payload={'id':first['id'],'job':task['job'],'version':task['version'],'duration':10,**result}
            before=next(c.model.parameters()).detach().clone()
            self.assertTrue(c.handle('/api/tasks/result',payload,first['accessToken'])['accepted'])
            self.assertFalse(torch.equal(before,next(c.model.parameters())))
            with self.assertRaises(ValueError): c.handle('/api/tasks/result',payload,first['accessToken'])
            task=c.handle('/api/tasks/next',{'id':second['id']},second['accessToken'])
            result=compute(task)
            c.handle('/api/training',{'active':False},key)
            self.assertFalse(c.handle('/api/tasks/result',{'id':second['id'],'job':task['job'],'version':task['version'],**result},second['accessToken'])['accepted'])
            loaded=Coordinator(directory)
            self.assertEqual(loaded.step,1)
            self.assertAlmostEqual(loaded.loss,c.loss,places=6)
            self.assertFalse(loaded.active)

if __name__=='__main__': unittest.main()
