"""Mock-only activation/dedup checks; no provider or local credential is used."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error

CI=Path(__file__).resolve().parents[2]/'tools/ci'
sys.path.insert(0,str(CI))
from jev import calibration_plan, calibration_summary, canonical, diagnose, MODEL
from prepare_diagnosis import prepare, prior_reservation
from test_jev import packet, reply, Provider, Response


REPO='xormania/mago-serena_v2-poc'


def event():
    return {'repository':{'full_name':REPO,'default_branch':'master'},
        'workflow_run':{'id':123,'run_attempt':2,'head_sha':'a'*40,
                        'head_repository':{'full_name':REPO}}}


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.packet=self.root/'packet.json';self.packet.write_bytes(canonical(packet()))
        self.context={'trusted_sha':'b'*40,'run_id':'456','attempt':1,'event_name':'workflow_run'}

    def gate(self, source=None, provider=None, context=None):
        self.provider=provider or Provider({'total_count':0,'artifacts':[]})
        return prepare(source or event(),self.packet,self.root/'control',self.root/'output',self.root/'reservation',
                       context or self.context,'mock-actions-token',opener=self.provider)

    def test_first_failure_reserves_before_provider_authorization(self):
        result=self.gate()
        self.assertTrue(result['provider_needed'])
        self.assertEqual(result['reservation_name'],'jev-reservation-source-123-2')
        self.assertTrue((self.root/'reservation/reservation.json').is_file())
        self.assertFalse((self.root/'output').exists())
        self.assertEqual(result['tested_source_revision'],'a'*40)
        self.assertEqual(result['trusted_revision'],'b'*40)
        self.assertEqual(self.provider.calls,1)

    def test_healthy_evidence_only_no_secret_or_api_call(self):
        p=packet();p['checks'][0]['status']='pass';self.packet.write_bytes(canonical(p))
        with mock.patch('prepare_diagnosis.prior_reservation') as reservation:
            result=self.gate()
        reservation.assert_not_called()
        self.assertFalse(result['provider_needed'])
        self.assertEqual(result['status'],'nothing_to_diagnose')
        saved=json.loads((self.root/'output/result.json').read_text())
        self.assertFalse(saved['provider_request_attempted'])
        self.assertEqual(saved['provider_request_attempts'],0)
        self.assertEqual(self.provider.calls,0)

    def test_missing_evidence_is_explicit_no_provider_authorization(self):
        self.packet.unlink()
        result=self.gate()
        self.assertEqual(result['status'],'missing_evidence')
        self.assertFalse(result['provider_needed'])
        self.assertEqual(self.provider.calls,0)

    def test_same_source_attempt_duplicate_suppressed_even_if_artifact_expired(self):
        rows=[{'id':99,'name':'jev-reservation-source-123-2','expired':True,'workflow_run':{'id':789}}]
        class Transport:
            calls=0
            def open(self, request, timeout):
                self.calls+=1
                return Response({'total_count':1,'artifacts':rows} if self.calls==1 else {
                    'path':'.github/workflows/jev.yml','head_branch':'master','event':'workflow_run',
                    'repository':{'full_name':REPO}})
        result=self.gate(provider=Transport())
        self.assertEqual(result['status'],'duplicate_suppressed')
        self.assertFalse(result['provider_needed'])
        self.assertTrue(result['prior_reservation']['artifact_expired'])
        self.assertFalse((self.root/'reservation').exists())

    def test_untrusted_producer_cannot_forge_a_trusted_reservation(self):
        calls=[]
        class Transport:
            def open(self,request,timeout):
                calls.append(request.full_url)
                return Response({'total_count':1,'artifacts':[{'id':99,'name':'jev-reservation-source-123-2','workflow_run':{'id':789}}]} if len(calls)==1 else {
                    'path':'.github/workflows/poc.yml','head_branch':'attacker','event':'pull_request',
                    'repository':{'full_name':REPO}})
        result=self.gate(provider=Transport())
        self.assertTrue(result['provider_needed'])

    def test_inventory_api_failure_does_not_authorize_provider(self):
        with self.assertRaises(urllib.error.URLError):
            self.gate(provider=Provider(urllib.error.URLError('mock unavailable')))
        self.assertFalse((self.root/'reservation').exists())

    def test_incomplete_inventory_refused_not_treated_as_empty(self):
        with self.assertRaises(ValueError):self.gate(provider=Provider({'total_count':101,'artifacts':[]}))

    def test_foreign_packet_refused_before_api(self):
        p=packet();p['ci']['run_id']='999';self.packet.write_bytes(canonical(p))
        provider=Provider({'total_count':0,'artifacts':[]})
        with self.assertRaises(ValueError):self.gate(provider=provider)
        self.assertEqual(provider.calls,0)

    def test_calibration_reservation_ignores_consumer_attempt(self):
        source={'repository':event()['repository'],'inputs':{'calibration':'true'}}
        context={**self.context,'event_name':'workflow_dispatch'}
        result=self.gate(source=source,context=context)
        self.assertEqual(result['reservation_name'],'jev-reservation-calibration-456')
        self.assertTrue(result['provider_needed'])

    def test_calibration_rerun_cannot_authorize_four_more_requests(self):
        source={'repository':event()['repository'],'inputs':{'calibration':'true'}}
        result=self.gate(source=source,context={**self.context,'event_name':'workflow_dispatch','attempt':2})
        self.assertFalse(result['provider_needed'])
        self.assertEqual(result['status'],'consumer_rerun_suppressed')
        self.assertEqual(self.provider.calls,0)

    def test_superseded_cancelled_source_needs_no_provider_even_with_failure_excerpt(self):
        source=event();source['workflow_run']['conclusion']='cancelled'
        result=self.gate(source=source)
        self.assertFalse(result['provider_needed'])
        self.assertEqual(result['status'],'source_cancelled')
        self.assertEqual(self.provider.calls,0)

    def test_provider_requires_successful_reservation_upload(self):
        import yaml
        workflow=yaml.load((CI.parents[1]/'.github/workflows/jev.yml').read_text(),Loader=yaml.BaseLoader)
        steps=workflow['jobs']['diagnose']['steps']
        provider=next(s for s in steps if 'TYPESAFE_API_KEY' in s.get('env',{}))
        reserve=next(s for s in steps if s.get('id')=='reserve')
        self.assertLess(steps.index(reserve),steps.index(provider))
        self.assertIn("steps.reserve.outcome == 'success'",provider['if'])
        self.assertNotIn('continue-on-error',reserve)
        self.assertEqual([s for s in steps if 'TYPESAFE_API_KEY' in s.get('env',{})],[provider])
        output=next(s for s in steps if s['name']=='Preserve sanitized diagnostic output')
        self.assertIn('github.run_attempt',output['with']['name'])
        self.assertIn('-consumer-',output['with']['name'])


class CalibrationOutcomeTests(unittest.TestCase):
    def test_observed_duplicate_support_is_explicit_not_silently_deduplicated(self):
        p=packet();r=reply();r['answers']['support_2']['choice']='e1'
        with tempfile.TemporaryDirectory() as directory:
            result=diagnose(p,Path(directory)/'out',key='mock-key',opener=Provider(r))
        self.assertEqual(result['status'],'malformed_response')
        self.assertEqual(result['validation_error'],'Duplicate supporting reference')
        self.assertNotIn('diagnosis',result)

    def test_summary_partial_failure_preserves_each_outcome_and_mock_route(self):
        plan=calibration_plan();results=[]
        with tempfile.TemporaryDirectory() as directory:
            for row in plan:
                value=reply('unknown','none','none')
                if row['case']=='closed-file':value['answers']['support_1']['choice']='e1';value['answers']['support_2']['choice']='e1'
                results.append(diagnose(row['packet'],Path(directory)/row['case'],key='mock-key',opener=Provider(value),force=True))
        summary=calibration_summary(plan,results)
        self.assertEqual(summary['mode'],'mock_calibration_replay')
        self.assertEqual(summary['provider_request_attempts'],4)
        self.assertEqual(summary['valid_responses'],3)
        self.assertEqual(summary['outcome'],'incomplete_or_rejected_response')
        self.assertEqual(summary['cases'][0]['validation_error'],'Duplicate supporting reference')

    def test_cli_reports_rejected_response_without_aborting_other_cases(self):
        import jev
        plan=calibration_plan();results=[]
        for index,row in enumerate(plan):
            results.append({'status':'malformed_response' if index==0 else 'abstained',
                            'transport':'mock','provider_request_attempted':True,'provider_request_attempts':1,
                            'requested_model':MODEL,'observed_model':MODEL})
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(jev,'diagnose',side_effect=results) as provider:
            target=Path(directory)/'out'
            with mock.patch.object(sys,'argv',['jev','--live','--calibration','--out',str(target)]):
                self.assertEqual(jev.main(),1)
            self.assertEqual(provider.call_count,4)
            saved=json.loads((target/'calibration-summary.json').read_text())
            self.assertEqual(saved['valid_responses'],3)
            self.assertEqual(saved['provider_request_attempts'],4)
            self.assertEqual(saved['mode'],'mock_calibration_replay')


if __name__=='__main__':unittest.main()
