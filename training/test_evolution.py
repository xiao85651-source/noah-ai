import copy, os, tempfile, unittest
from unittest.mock import patch
from .coordinator import Coordinator
from .model import Config
from .worker import compute
from .evolution import atomic_json, decision, read_release
from .gateway import ServingModel

class EvolutionTests(unittest.TestCase):
    def test_gate_rejects_language_and_audit_regressions(self):
        base={'validation':{'loss':2.0,'languages':{'en':2.0,'zh':2.0}},'audit':{'loss':2.0,'languages':{'en':2.0,'zh':2.0}}}
        candidate=copy.deepcopy(base)
        self.assertFalse(decision(candidate,base)[0])
        candidate['validation']['loss']=1.9
        self.assertTrue(decision(candidate,base)[0])
        candidate['validation']['languages']['zh']=2.2
        self.assertEqual(decision(candidate,base)[1],'language_regression')
        candidate['validation']['languages']['zh']=2.0;candidate['audit']['loss']=2.2
        self.assertEqual(decision(candidate,base)[1],'audit_regression')

    def test_real_iteration_release_hot_reload_rollback_and_recovery(self):
        with tempfile.TemporaryDirectory(prefix='noah-evolution-') as directory:
            c=Coordinator(directory,Config(context=32,width=32,heads=4,layers=1)); key=c.token
            with self.assertRaises(ValueError): c.handle('/api/evolution',{'action':'start'},key)
            with self.assertRaises(PermissionError): c.handle('/api/evolution',{'action':'start','local':False},'wrong')
            with self.assertRaises(PermissionError): c.handle('/api/evolution',{'action':'start','local':False},key,public=True)
            c.handle('/api/evolution',{'action':'start','local':False,'reviewEvery':5,'maxSteps':10,'maxMinutes':1},key)
            baseline=c.evolution.current()['id']
            node=c.handle('/api/nodes/join',{'name':'Voluntary iteration tester'},key)
            for _ in range(30):
                if not c.evolution.active: break
                task=c.handle('/api/tasks/next',{'id':node['id']},node['accessToken'])
                result=compute(task)
                c.handle('/api/tasks/result',{'id':node['id'],'job':task['job'],'version':task['version'],'duration':10,**result},node['accessToken'])
            self.assertEqual(c.step,10)
            self.assertFalse(c.active);self.assertFalse(c.evolution.active)
            self.assertEqual(c.evolution.reason,'step_budget')
            self.assertEqual(len(c.evolution.records),3)
            selected=c.evolution.current()
            self.assertNotEqual(selected['id'],baseline)
            with patch.dict(os.environ,{'NOAH_FOLLOW_RELEASES':'1','NOAH_RELEASES':str(c.evolution.folder)}):
                serving=ServingModel()
                self.assertEqual(serving.release,selected['id'])
                c.evolution.rollback(); serving.refresh()
                self.assertNotEqual(serving.release,selected['id'])
                last_good=serving.release
                artifact=c.evolution.folder/selected['id']/'weights.npz'
                artifact.write_bytes(b'corrupted release')
                atomic_json(c.evolution.folder/'current.json',{'release':selected['id']})
                serving.refresh();self.assertEqual(serving.release,last_good)
                with self.assertRaises(ValueError): read_release(c.evolution.folder,selected['id'])
            with self.assertRaises(ValueError): read_release(c.evolution.folder,'../../outside')
            restored=Coordinator(directory)
            self.assertEqual(restored.step,10)
            self.assertFalse(restored.evolution.active)
            self.assertEqual(len(restored.evolution.records),3)

    def test_deadline_stops_a_session_without_contributors(self):
        with tempfile.TemporaryDirectory(prefix='noah-evolution-deadline-') as directory:
            c=Coordinator(directory,Config(context=32,width=32,heads=4,layers=1))
            c.evolution.start({'local':False,'maxMinutes':1},4317)
            c.evolution.started-=61
            c.evolution.tick()
            self.assertFalse(c.active);self.assertFalse(c.evolution.active)
            self.assertEqual(c.evolution.reason,'time_budget')

if __name__=='__main__': unittest.main()
