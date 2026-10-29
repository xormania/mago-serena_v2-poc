"""Synthetic timing faults and mocked replies; no live calibration or credentials.

Every packet below passes through the actual collector and bounded ZIP reader.
Historical BuildKit observations are tested separately from these fault cases.
"""
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
import zipfile

CI = Path(__file__).resolve().parents[2]/'tools/ci'
sys.path.insert(0, str(CI))
from capture_step import collect
from download_inputs import read_archive, validate_source_association
from jev import MODEL, PROBES, canonical, diagnose, validate_packet
from performance import PHASES, assess, compile_fingerprint
from prepare_diagnosis import prepare
from test_jev import Provider, reply

ROOT = CI.parents[1]
REPO = 'xormania/mago-serena_v2-poc'


def build_log(candidate='cached'):
    finish = '#17 CACHED\n' if candidate == 'cached' else '#17 1.2 Compiling mago v1\n#17 DONE 570.7s\n'
    return ('#3 importing cache manifest from gha:sample\n#3 DONE 0.8s\n'
            '#9 [mago 3/3] RUN cargo build --locked --release -j 6\n#9 CACHED\n'
            '#17 [mago-candidate 3/4] RUN cp /mago /mago-baseline && cargo build --locked --release -j 2\n'+
            finish+'#22 exporting cache to GitHub Actions Cache\n#22 DONE 5.5s\n')


class PerformanceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.next_id = 0

    def produce(self, *, candidate='cached', build_s=47, phase=None, phase_s=60, failure=False, ref='refs/pull/7/merge'):
        self.next_id += 1
        directory = self.root/('capture-'+str(self.next_id))
        (directory/'ci').mkdir(parents=True)
        rows = []
        now = time.time()-1000
        for index, name in enumerate(PHASES):
            raw = build_log(candidate) if name == 'build' else 'synthetic healthy '+name+'\n'
            if failure and name == 'acceptance':
                raw = 'AssertionError: synthetic failure retained with its native verdict\n'
            path = directory/'ci'/(name+'-attempt-1.log')
            path.write_text(raw)
            rows.append({'step':name, 'attempt':1, 'status':'fail' if failure and name == 'acceptance' else 'pass',
                         'elapsed_s':build_s if name == 'build' else phase_s if name == phase else 60,
                         'started_unix':now+index*100, 'log':path.name, 'log_truncated':False,
                         'log_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        (directory/'ci/step-attempts.jsonl').write_bytes(b'\n'.join(canonical(row) for row in rows)+b'\n')
        env = {'GITHUB_WORKSPACE':str(ROOT), 'GITHUB_EVENT_NAME':'pull_request', 'GITHUB_REF':ref,
               'RUNNER_OS':'Linux', 'RUNNER_ARCH':'X64', 'RUNNER_ENVIRONMENT':'github-hosted',
               'PERFORMANCE_RUNNER_CLASS':'ubuntu-latest', 'ImageOS':'ubuntu24', 'ImageVersion':'synthetic-fixed-image'}
        with mock.patch.dict(os.environ, env):
            packet = collect(directory, directory/'packet.json', run_id='123', attempt=2, source_sha='a'*40)
        self.assertTrue((directory/'ci/performance.md').is_file())
        self.assertIn('47', (directory/'ci/performance.md').read_text()) if build_s == 47 else None
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('diagnosis-input.json', canonical(packet))
        packet = read_archive(archive_bytes.getvalue(), packet['ci'])
        return packet

    def baseline(self, packet, *, ref=None, phase=None, phase_s=60, candidate='cached', accessible=False):
        observation = copy.deepcopy(packet['performance'])
        observation['ci'].update(run_id='122', attempt=1, source_sha='b'*40, workflow_head_sha='b'*40)
        observation['observed_unix'] -= 120
        if ref is not None:
            observation['context']['ref'] = ref
        observation['build']['candidate']['outcome'] = candidate
        observation['build']['candidate']['compile_duration_s'] = None if candidate == 'cached' else 570.7
        observation['build']['candidate']['duration_s'] = None if candidate == 'cached' else 570.7
        for row in observation['phases']:
            if row['id'] == 'build':
                row['elapsed_s'] = 47 if candidate == 'cached' else 651
            if row['id'] == phase:
                row['elapsed_s'] = phase_s
        observation['timing']['step_sum_s'] = sum(row['elapsed_s'] or 0 for row in observation['phases'])
        return {'observation':observation, 'selection_reason':'synthetic identified prior observation for integration test',
                'cache_entry':{'accessible':accessible, 'source':'github_cache_inventory',
                               'observed_at_unix':packet['performance']['observed_unix']-1}}

    def gate(self, packet, baseline):
        self.next_id += 1
        directory = self.root/('gate-'+str(self.next_id))
        directory.mkdir()
        path = directory/'packet.json'
        path.write_bytes(canonical(packet))
        event = {'repository':{'full_name':REPO, 'default_branch':'master'},
                 'workflow_run':{'id':123, 'run_attempt':2, 'head_sha':'a'*40, 'conclusion':'success',
                                 'head_repository':{'full_name':REPO}}}
        context = {'trusted_sha':'c'*40, 'run_id':'456', 'attempt':1, 'event_name':'workflow_run'}
        reservation = Provider({'total_count':0, 'artifacts':[]})
        record = prepare(event, path, directory/'control', directory/'output', directory/'reservation',
                         context, 'fake-actions-token', opener=reservation, baseline=baseline)
        self.assertTrue((directory/'control/performance-summary.md').is_file())
        return record, directory, reservation

    def provider(self, packet, baseline, *, layer='compilation_cost', probe='inspect_compile_profile', support='performance.metrics'):
        self.next_id += 1
        directory = self.root/('provider-'+str(self.next_id))
        transport = Provider(reply(layer, probe, support))
        result = diagnose(packet, directory, key='fake-provider-key', opener=transport, baseline=baseline)
        return result, transport, directory

    def test_successful_absolute_budget_breach_passes_both_gates_one_mocked_request(self):
        packet = self.produce(candidate='executed', build_s=1000)
        record, directory, reservation = self.gate(packet, None)
        self.assertTrue(record['provider_needed'])
        self.assertTrue((directory/'reservation/reservation.json').is_file())
        self.assertEqual(reservation.calls, 1)
        self.assertTrue(all(row['status'] == 'pass' for row in packet['checks']))
        result, provider, out = self.provider(packet, None)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result['provider_request_attempts'], 1)
        self.assertEqual(result['status'], 'diagnosed')
        self.assertEqual(result['transport'], 'mock')
        self.assertEqual(result['diagnosis']['performance_hypothesis'], 'compilation_cost')
        payload = json.loads((out/'request.json').read_text())
        self.assertEqual(payload['state']['checks'], packet['checks'])
        self.assertIn('trusted_performance', payload['state'])
        self.assertNotIn('performance', payload['state'])
        self.assertNotIn('document_state', payload['questions']['layer']['criteria'])
        summary = (out/'summary.md').read_text()
        self.assertIn('Jev hypothesis', summary)
        self.assertIn('mock', summary)
        self.assertIn('not independently inspect', summary)

    def test_successful_unexpected_recompilation_uses_matching_visible_cache_evidence(self):
        packet = self.produce(candidate='executed', build_s=651)
        baseline = self.baseline(packet, accessible=True)
        report = assess(packet['performance'], baseline)
        self.assertIn('unexpected_recompilation', report['classifications'])
        record, _, _ = self.gate(packet, baseline)
        self.assertTrue(record['provider_needed'])
        result, provider, _ = self.provider(packet, baseline, layer='cache_reuse_visibility', probe='inspect_cache_availability')
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result['status'], 'diagnosed')

    def test_comparable_slow_verification_reaches_provider_without_cache_blame(self):
        packet = self.produce(phase='slice2', phase_s=150)
        baseline = self.baseline(packet, phase='slice2', phase_s=60)
        record, _, _ = self.gate(packet, baseline)
        self.assertTrue(record['provider_needed'])
        self.assertIn('slow_verification', record['performance_classifications'])
        self.assertNotIn('unexpected_recompilation', record['performance_classifications'])
        result, provider, out = self.provider(packet, baseline, layer='slow_verification', probe='compare_phase_evidence')
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result['status'], 'diagnosed')
        payload = json.loads((out/'request.json').read_text())
        delta = next(row for row in payload['state']['trusted_performance']['comparison']['deltas'] if row['phase'] == 'slice2')
        self.assertEqual(delta['delta_s'], 90)
        self.assertEqual(delta['ratio'], 2.5)

    def test_ordinary_warm_and_explained_cold_are_visible_with_zero_provider_calls(self):
        for cold in (False, True):
            with self.subTest(cold=cold):
                packet = self.produce(candidate='executed' if cold else 'cached', build_s=651 if cold else 47,
                                      ref='refs/heads/master' if cold else 'refs/pull/7/merge')
                baseline = self.baseline(packet, ref='refs/pull/6/merge' if cold else None)
                record, directory, reservation = self.gate(packet, baseline)
                self.assertFalse(record['provider_needed'])
                self.assertEqual(record['status'], 'nothing_to_diagnose')
                self.assertEqual(reservation.calls, 0)
                self.assertIn('explained_cold_population' if cold else 'warm_reuse', record['performance_classifications'])
                result, provider, out = self.provider(packet, baseline)
                self.assertEqual(provider.calls, 0)
                self.assertEqual(result['status'], 'nothing_to_diagnose')
                self.assertIn('Jev did not run', (out/'summary.md').read_text())
                self.assertFalse((directory/'reservation').exists())

    def test_incomparable_runner_inputs_inventory_and_missing_history_do_not_claim_regression(self):
        packet = self.produce(phase='slice2', phase_s=150)
        for kind in ('runner', 'fingerprint', 'inventory', 'missing'):
            with self.subTest(kind=kind):
                baseline = self.baseline(packet, phase='slice2', phase_s=60)
                if kind == 'runner':
                    baseline['observation']['context']['runner']['image_version'] = 'other-image'
                elif kind == 'fingerprint':
                    baseline['observation']['fingerprint'] = compile_fingerprint(ROOT, build_args={'MAGO_BUILD_JOBS':'3'})
                elif kind == 'inventory':
                    baseline['observation']['inventory']['definitions_sha256'] = 'f'*64
                else:
                    baseline = None
                record, _, _ = self.gate(packet, baseline)
                self.assertFalse(record['provider_needed'])
                self.assertNotIn('slow_verification', record['performance_classifications'])
                self.assertIn('insufficient_evidence', record['performance_classifications'])

    def test_failure_and_performance_share_one_request_and_preserve_failure_priority(self):
        packet = self.produce(candidate='executed', build_s=1000, failure=True)
        record, _, _ = self.gate(packet, None)
        self.assertTrue(record['provider_needed'])
        eid = next(row['excerpt_ids'][0] for row in packet['checks'] if row['status'] == 'fail')
        result, provider, out = self.provider(packet, None, layer='semantic_behavior', probe='verify_run_identity', support=eid)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result['status'], 'diagnosed')
        payload = json.loads((out/'request.json').read_text())
        self.assertEqual(payload['state']['checks'][0]['status'], 'fail')
        self.assertIn('Prioritize check failures', payload['questions']['layer']['instructions'])
        self.assertIn('absolute_budget_breach', payload['state']['trusted_performance']['classifications'])

    def test_untrusted_policy_flags_and_malformed_metrics_reject_before_provider(self):
        original = self.produce()
        variants = []
        for duration in (True, -1, float('nan'), float('inf')):
            packet = copy.deepcopy(original)
            packet['performance']['phases'][0]['elapsed_s'] = duration
            variants.append(packet)
        for mutation in (
            lambda p:p['performance'].update(provider_eligible=True),
            lambda p:p['performance']['ci'].update(run_id='999'),
            lambda p:p['performance']['build']['candidate'].update(evidence_ids=['foreign']),
            lambda p:p['performance']['evidence'].append({'id':'large', 'text':'x'*701, 'truncated':False}),
        ):
            packet = copy.deepcopy(original)
            mutation(packet)
            variants.append(packet)
        for index, packet in enumerate(variants):
            with self.subTest(index=index):
                provider = Provider(reply())
                with self.assertRaises((ValueError, TypeError)):
                    diagnose(packet, self.root/('invalid-'+str(index)), key='fake-key', opener=provider)
                self.assertEqual(provider.calls, 0)

    def test_missing_key_response_rejection_and_abstention_remain_advisory(self):
        packet = self.produce(candidate='executed', build_s=1000)
        result = diagnose(packet, self.root/'missing-key', key='', baseline=None)
        self.assertEqual(result['status'], 'missing_credentials')
        result, provider, _ = self.provider(packet, None, layer='insufficient_performance_evidence', probe='none', support='none')
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result['status'], 'abstained')
        result, _, _ = self.provider(packet, None, layer='compilation_cost', support='foreign')
        self.assertEqual(result['status'], 'malformed_response')
        self.assertTrue(all(row['status'] == 'pass' for row in packet['checks']))

    def test_performance_source_event_ref_and_merge_ancestry_are_verified(self):
        packet = self.produce()
        moment = packet['performance']['observed_unix']
        source = {'event':'pull_request', 'head_sha':'b'*40, 'pull_requests':[{'number':7}],
                  'created_at':datetime.fromtimestamp(moment-2000, timezone.utc).isoformat(),
                  'updated_at':datetime.fromtimestamp(moment+60, timezone.utc).isoformat()}
        valid = Provider({'sha':'a'*40, 'parents':[{'sha':'b'*40}, {'sha':'c'*40}]})
        validate_source_association(packet, source, REPO, valid, 'fake-actions-token')
        self.assertEqual(valid.calls, 1)
        self.assertIn('/git/commits/'+'a'*40, valid.request.full_url)
        for change in ({'event':'push', 'head_branch':'master'}, {'pull_requests':[{'number':8}]}):
            provider = Provider({})
            with self.assertRaises(ValueError):
                validate_source_association(packet, {**source, **change}, REPO, provider, 'fake-actions-token')
            self.assertEqual(provider.calls, 0)
        provider = Provider({'sha':'a'*40, 'parents':[{'sha':'c'*40}, {'sha':'d'*40}]})
        with self.assertRaises(ValueError):
            validate_source_association(packet, source, REPO, provider, 'fake-actions-token')
        self.assertEqual(provider.calls, 1)
        moment = packet['performance']['observed_unix']
        timed_source = {**source,
            'created_at':datetime.fromtimestamp(moment-2000, timezone.utc).isoformat(),
            'updated_at':datetime.fromtimestamp(moment+60, timezone.utc).isoformat()}
        validate_source_association(packet, timed_source, REPO,
            Provider({'sha':'a'*40, 'parents':[{'sha':'b'*40}, {'sha':'c'*40}]}), 'fake-actions-token')
        for field in ('observed_unix', 'started_unix', 'elapsed_s'):
            altered = copy.deepcopy(packet)
            if field == 'observed_unix':
                altered['performance'][field] = moment+10000
            elif field == 'started_unix':
                altered['performance']['phases'][0][field] = moment-10000
            else:
                altered['performance']['phases'][0][field] = 2_000_000
            transport = Provider({})
            with self.assertRaises(ValueError):
                validate_source_association(altered, timed_source, REPO, transport, 'fake-actions-token')
            self.assertEqual(transport.calls, 0)

    def test_unchecked_producer_eligibility_flags_never_authorize_a_request(self):
        packet = self.produce()
        packet.update(provider_needed=True, provider_eligible=True)
        result, provider, _ = self.provider(packet, None)
        self.assertEqual(result['status'], 'nothing_to_diagnose')
        self.assertEqual(provider.calls, 0)

    def test_new_packet_preserves_legacy_contract_and_legacy_packet_uses_new_consumer(self):
        packet = self.produce(candidate='executed', build_s=1000)
        self.assertEqual(packet['schema'], 1)
        self.assertEqual(packet['allowed_probes'], PROBES)
        self.assertNotIn('inspect_compile_profile', packet['allowed_probes'])
        legacy = copy.deepcopy(packet)
        del legacy['performance']
        validate_packet(legacy)
        result, provider, _ = self.provider(legacy, None)
        self.assertEqual(result['status'], 'nothing_to_diagnose')
        self.assertEqual(provider.calls, 0)


if __name__ == '__main__':
    unittest.main()
