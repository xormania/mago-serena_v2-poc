"""Synthetic/mock provider tests only: no network or local credential required."""
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

CI = Path(__file__).resolve().parents[2]/'tools/ci'
sys.path.insert(0,str(CI))
from jev import MODEL, PROBES, MAX_PACKET, MAX_RESPONSE, calibration_packets, canonical, diagnose, payload_for, sanitize, validate_packet, parse_json
from capture_step import capture, collect
from download_inputs import read_archive, download


def packet():
    return {'schema':1,'mode':'observed_ci','ci':{'run_id':'123','attempt':2,'source_sha':'a'*40,'workflow_head_sha':'a'*40},
            'checks':[{'id':'check1','status':'fail','step':'acceptance','attempt':1,'excerpt_ids':['e1']}],
            'excerpts':[{'id':'e1','step':'acceptance','attempt':1,'text':'disk/sent-text mismatch before the cross-file reference','truncated':False}],
            'allowed_probes':PROBES}


def reply(layer='document_state',probe='compare_document_hashes',support='e1'):
    return {'model':MODEL,'usage':{'input_tokens':100,'output_tokens':20}, 'answers':{
        name:{'type':'choice','choice':choice} for name,choice in {
            'layer':layer,'probe':probe,'support_1':support,'support_2':'none'}.items()}}


class Response:
    status = 200
    def __init__(self,value): self.value = value if isinstance(value,bytes) else canonical(value)
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,limit): return self.value[:limit]


class Provider:
    def __init__(self,value): self.value, self.calls = value, 0
    def open(self,request,timeout):
        self.calls += 1
        self.request = request
        if isinstance(self.value,Exception): raise self.value
        return Response(self.value)


class JevTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)/'result'

    def run_mock(self,value,**kwargs):
        self.provider = Provider(value)
        return diagnose(packet(),self.out,opener=self.provider,key='mock-key-never-live',**kwargs)

    def test_success_is_structured_and_mock_labelled(self):
        result = self.run_mock(reply())
        self.assertEqual(result['status'],'diagnosed')
        self.assertEqual(result['diagnosis']['supporting_excerpt_ids'],['e1'])
        self.assertFalse(result['probe_executed'])
        self.assertEqual(result['transport'],'mock')
        self.assertEqual(result['observed_model'],MODEL)
        self.assertEqual(result['usage']['input_tokens'],100)
        self.assertEqual(json.loads((self.out/'result.json').read_bytes())['usage']['input_tokens'],100)
        self.assertIsNone(result['actual_invoiced_cost'])
        self.assertAlmostEqual(result['estimated_input_cost_usd'],.0000042)
        self.assertGreaterEqual(result['latency_seconds'],0)
        self.assertEqual(self.provider.calls,1)

    def test_abstention(self):
        result = self.run_mock(reply('unknown','none','none'))
        self.assertEqual(result['status'],'abstained')
        self.assertTrue(result['diagnosis']['abstained'])

    def test_missing_or_malformed_usage_does_not_break_diagnosis(self):
        for usage in (None,'invalid',{}, {'input_tokens':'invalid'}):
            r=reply()
            if usage is None: r.pop('usage')
            else: r['usage']=usage
            with tempfile.TemporaryDirectory() as d:
                result=diagnose(packet(),Path(d)/'result',opener=Provider(r),key='mock-key')
                self.assertEqual(result['status'],'diagnosed')
                self.assertIsNone(result['estimated_input_cost_usd'])

    def test_missing_credentials_no_network(self):
        provider = Provider(reply())
        result = diagnose(packet(),self.out,key='',opener=provider)
        self.assertEqual(result['status'],'missing_credentials')
        self.assertEqual(provider.calls,0)

    def test_healthy_default_no_request_even_if_key_available(self):
        p = packet(); p['checks'][0]['status']='pass'
        provider = Provider(reply())
        result = diagnose(p,self.out,key='mock-key',opener=provider)
        self.assertEqual(result['status'],'nothing_to_diagnose')
        self.assertEqual(provider.calls,0)

    def test_timeout_has_no_retry(self):
        result = self.run_mock(TimeoutError('mock timeout'))
        self.assertEqual(result['status'],'timeout')
        self.assertEqual(self.provider.calls,1)

    def test_provider_failure(self):
        error = urllib.error.HTTPError('https://api.typesafe.ai',503,'unavailable',{},io.BytesIO(b'provider down'))
        result = self.run_mock(error)
        self.assertEqual(result['status'],'provider_failure')
        self.assertEqual(result['http_status'],503)
        self.assertEqual(self.provider.calls,1)

    def test_provider_error_body_preserves_telemetry_without_diagnosis(self):
        body=reply();body['usage']={'input_tokens':13,'output_tokens':2};body['cost_usd']=0.01
        error=urllib.error.HTTPError('https://api.typesafe.ai',503,'unavailable',{},io.BytesIO(canonical(body)))
        result=self.run_mock(error)
        self.assertEqual(result['status'],'provider_failure')
        self.assertEqual(result['observed_model'],MODEL)
        self.assertEqual(result['usage'],{'input_tokens':13,'output_tokens':2})
        self.assertEqual(result['cost']['provider_reported'],0.01)
        self.assertNotIn('diagnosis',result)
        self.assertEqual(self.provider.calls,1)

    def test_calibration_oversized_plan_refuses_before_any_request(self):
        import jev
        cases=list(calibration_packets())
        cases.append(('extra',cases[0][1],cases[0][2]))
        with mock.patch.object(jev,'calibration_packets',return_value=iter(cases)), mock.patch.object(jev,'diagnose') as diagnosis:
            with mock.patch.object(sys,'argv',['jev','--live','--calibration','--out',str(self.out)]):
                with self.assertRaisesRegex(ValueError,'at most 4'):
                    jev.main()
            diagnosis.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_malformed_json(self):
        result = self.run_mock(b'not json')
        self.assertEqual(result['status'],'malformed_response')
        self.assertEqual((self.out/'response.txt').read_text(),'not json')

    def test_invalid_excerpt_reference(self):
        self.assertEqual(self.run_mock(reply(support='invented'))['status'],'malformed_response')

    def test_invalid_probe(self):
        self.assertEqual(self.run_mock(reply(probe='execute_shell'))['status'],'malformed_response')

    def test_unbacked_hypothesis_rejected(self):
        self.assertEqual(self.run_mock(reply(support='none'))['status'],'malformed_response')

    def test_duplicate_support_rejected(self):
        r = reply(); r['answers']['support_2']['choice']='e1'
        self.assertEqual(self.run_mock(r)['status'],'malformed_response')

    def test_duplicate_json_fields_and_nonfinite_numbers_rejected(self):
        for raw in (b'{"model":"a","model":"b"}',b'{"value":NaN}',b'{"value":Infinity}',b'{"value":1e999}'):
            with self.assertRaises(ValueError):parse_json(raw)
        self.assertEqual(self.run_mock(b'{"model":"a","model":"b"}')['status'],'malformed_response')

    def test_wrong_provider_model_rejected_preserving_usage(self):
        r=reply(); r['model']='jev-latest'
        result=self.run_mock(r)
        self.assertEqual(result['status'],'malformed_response')
        self.assertEqual(result['usage']['input_tokens'],100)

    def test_incomplete_answers_rejected(self):
        r=reply(); del r['answers']['probe']
        self.assertEqual(self.run_mock(r)['status'],'malformed_response')

    def test_oversized_response_bounded_disclosed(self):
        result=self.run_mock(b'x'*(MAX_RESPONSE+10))
        self.assertEqual(result['status'],'malformed_response')
        self.assertTrue(result['response_truncated'])
        self.assertLessEqual((self.out/'response.txt').stat().st_size,MAX_RESPONSE)

    def test_request_and_response_redact_credentials(self):
        p=packet(); p['excerpts'][0]['text']='Authorization: Bearer mock-key-never-live password=secret-value'
        r=reply(); r['api_key']='mock-key-never-live'
        diagnose(p,self.out,key='mock-key-never-live',opener=Provider(r))
        saved=''.join(p.read_text() for p in self.out.iterdir())
        self.assertNotIn('mock-key-never-live',saved)
        self.assertNotIn('secret-value',saved)
        self.assertNotIn('secret-value',self.out.joinpath('request.json').read_text())

    def test_fresh_output_required_preserves_failed_attempt(self):
        self.run_mock(TimeoutError())
        before=(self.out/'result.json').read_bytes()
        with self.assertRaises(FileExistsError): diagnose(packet(),self.out,key='mock-key',opener=Provider(reply()))
        self.assertEqual(before,(self.out/'result.json').read_bytes())
        recovered=diagnose(packet(),self.out.with_name('second'),key='mock-key',opener=Provider(reply()))
        self.assertEqual(recovered['status'],'diagnosed')
        self.assertEqual(json.loads(before)['status'],'timeout')

    def test_packet_duplicate_stale_and_missing_identity(self):
        for mutate in [lambda p:p['excerpts'].append(p['excerpts'][0]),lambda p:p['ci'].pop('source_sha'),lambda p:p['checks'][0].update(excerpt_ids=['foreign'])]:
            p=packet(); mutate(p)
            with self.assertRaises(ValueError):validate_packet(p)
        with self.assertRaises(ValueError): validate_packet(packet(),{'run_id':'999'})

    def test_packet_bounds_and_probe_allowlist(self):
        p=packet();p['excerpts'][0]['text']='x'*2000
        with self.assertRaises(ValueError):validate_packet(p)
        p=copy.deepcopy(packet());p['allowed_probes']['shell']='bad'
        with self.assertRaises(ValueError):validate_packet(p)

    def test_calibration_explicit_synthetic_four_bounded_cases(self):
        rows=list(calibration_packets())
        self.assertEqual(len(rows),4)
        self.assertEqual([r[0] for r in rows],['closed-file','root-config','healthy','ambiguous'])
        for _,p,_ in rows:
            validate_packet(p)
            self.assertEqual(p['mode'],'calibration_replay')
            self.assertNotIn('expected',payload_for(p)['state'])


class BoundaryTests(unittest.TestCase):
    def archive(self,names):
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,value in names: archive.writestr(name,value)
        return output.getvalue()

    def test_archive_valid_json_no_extraction(self):
        p=packet()
        self.assertEqual(read_archive(self.archive([('diagnosis-input.json',canonical(p))]),p['ci']),p)

    def test_archive_rejects_traversal_extra_members_bombs_and_foreign_run(self):
        good=canonical(packet())
        for names in [[('../diagnosis-input.json',good)],[('diagnosis-input.json',good),('run.sh',b'bad')],[('diagnosis-input.json',b'x'*(MAX_PACKET+1))]]:
            with self.assertRaises(ValueError):read_archive(self.archive(names),packet()['ci'])
        with self.assertRaises(ValueError):read_archive(self.archive([('diagnosis-input.json',good)]),{'run_id':'999'})

    def test_download_binds_source_and_strips_token_on_signed_redirect(self):
        raw=self.archive([('diagnosis-input.json',canonical(packet()))])
        event={'repository':{'full_name':'xormania/mago-serena_v2-poc'},'workflow_run':{'id':123,'run_attempt':2,'head_sha':'a'*40,'head_repository':{'full_name':'xormania/mago-serena_v2-poc'}}}
        calls=[]
        class Transport:
            def open(self,request,timeout):
                calls.append(request)
                if len(calls)==1:return Response({'total_count':1,'artifacts':[{'id':42,'name':'jev-input-123-2','size_in_bytes':len(raw),'expired':False}]})
                if len(calls)==2:raise urllib.error.HTTPError(request.full_url,302,'redirect',{'Location':'https://artifact.blob.core.windows.net/data?sig=fake'},io.BytesIO())
                return Response(raw)
        with tempfile.TemporaryDirectory() as d:
            result=download(event,Path(d)/'input.json','fake-actions-token',opener=Transport())
            self.assertEqual(result,packet())
        self.assertEqual(calls[0].get_header('Authorization'),'Bearer fake-actions-token')
        self.assertIsNone(calls[2].get_header('Authorization'))
        self.assertEqual(len(calls),3)

    def test_pull_request_merge_checkout_identity_is_distinct_from_workflow_head(self):
        p=packet();p['ci']['source_sha']='b'*40
        raw=self.archive([('diagnosis-input.json',canonical(p))])
        result=read_archive(raw,{'run_id':'123','attempt':2,'workflow_head_sha':'a'*40})
        self.assertEqual(result['ci']['source_sha'],'b'*40)
        self.assertEqual(result['ci']['workflow_head_sha'],'a'*40)
        with self.assertRaises(ValueError):read_archive(raw,{'workflow_head_sha':'c'*40})

    def test_download_missing_artifact_is_no_work_foreign_repo_refused(self):
        event={'repository':{'full_name':'xormania/mago-serena_v2-poc'},'workflow_run':{'id':123,'run_attempt':2,'head_sha':'a'*40,'head_repository':{'full_name':'xormania/mago-serena_v2-poc'}}}
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(download(event,Path(d)/'input','fake-token',opener=Provider({'total_count':0,'artifacts':[]})))
            event['workflow_run']['head_repository']['full_name']='foreign/repo'
            with self.assertRaises(ValueError):download(event,Path(d)/'input','fake-token',opener=Provider({}))

    def test_capture_keeps_original_exit_and_recovered_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.assertEqual(capture('unit',1,[sys.executable,'-c','raise SystemExit(7)'],root/'ci'),7)
            self.assertEqual(capture('unit',2,[sys.executable,'-c','pass'],root/'ci'),0)
            packet=collect(root,root/'packet.json',run_id='1',attempt=1,source_sha='a'*40)
            self.assertEqual([x['status'] for x in packet['checks']],['fail','pass'])
            self.assertTrue((root/'ci/unit-attempt-1.log').exists())
            with self.assertRaises(FileExistsError):capture('unit',1,[sys.executable,'-c','pass'],root/'ci')

    def test_internal_recovered_failure_is_retained_from_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=root/'test-run';run.mkdir()
            rows=[{'run_id':'test-run','attempt_id':'1','context_sha256':'f'*64,'name':'positions','status':'fail','assertion':'column mismatch','step_attempt':1},
                  {'run_id':'test-run','attempt_id':'1','context_sha256':'f'*64,'name':'positions','status':'pass','assertion':'pass','step_attempt':2}]
            (run/'integration-attempts.jsonl').write_text('\n'.join(json.dumps(x) for x in rows))
            p=collect(root,root/'packet',run_id='1',attempt=1,source_sha='a'*40)
            self.assertEqual(len(p['checks']),1)
            self.assertEqual(p['checks'][0]['status'],'fail')
            self.assertEqual(p['excerpts'][0]['provenance']['step_attempt'],1)

    def test_ci_action_setup_failure_is_explicit_not_defect_detection(self):
        with tempfile.TemporaryDirectory() as d:
            p=collect(d,Path(d)/'packet',run_id='1',attempt=1,source_sha='a'*40,step_outcomes={'builder':{'outcome':'failure'}})
            self.assertEqual(p['checks'][0]['status'],'fail')
            self.assertIn('before captured',p['excerpts'][0]['text'])

    def test_workflow_key_and_trusted_boundary(self):
        root=CI.parents[1]
        producer=(root/'.github/workflows/poc.yml').read_text()
        consumer=(root/'.github/workflows/jev.yml').read_text()
        self.assertNotIn('TYPESAFE_API_KEY',producer)
        self.assertEqual(consumer.count('TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}'),1)
        self.assertIn('ref: ${{ github.event.repository.default_branch }}',consumer)
        self.assertNotIn('ref: ${{ github.event.workflow_run.head_sha }}',consumer)
        self.assertIn('python3 -I trusted/tools/ci/jev.py',consumer)
        self.assertNotIn('pull_request_target',consumer)
        self.assertIn('steps.data.outputs.found',consumer)


if __name__=='__main__':unittest.main()
