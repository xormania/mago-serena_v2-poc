"""Real collector regressions for slice producer layouts; provider boundary is mocked."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

CI = Path(__file__).resolve().parents[2]/'tools/ci'
sys.path.insert(0, str(CI))
from capture_step import LOG_LIMIT, SLICE_RESULT_LIMIT, SLICE_SOURCE_LIMIT, collect
from jev import MAX_PACKET, MODEL, canonical, diagnose

SOURCE_SHA = 'a'*40
CAUSE = 'Missing concrete compiled-binding contribution'


def context_digest(source):
    return hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_attempt(root, *, slice_name='slice1', attempt='attempt-first', status='fail', reason=CAUSE, step_attempt=1, latest=True, stage='symfony_wiring'):
    run = root/'owned-run'
    directory = run/slice_name/attempt
    directory.mkdir(parents=True, exist_ok=True)
    source = {'revision': SOURCE_SHA, 'run': {'run_id': run.name, 'app': '/owned/app'},
              'source_manifest': {'host.py': {'sha256': 'f'*64}}}
    context = {'run_id': run.name, 'workspace': '/owned/app', 'source_context_sha256': context_digest(source)}
    checks = [{**context, 'name': stage, 'status': status, 'reason': reason, 'step_attempt': step_attempt}]
    value = {**context, 'schema': 1, 'kind': 'mago_first_'+slice_name,
             'status': 'pass' if status == 'pass' else 'incomplete',
             'inventory': [stage], 'checks': checks, 'evidence': str(directory)}
    # Slice 1 predates an explicit attempt_id; the folder remains its identity.
    if slice_name != 'slice1':
        value['attempt_id'] = attempt
        checks[0]['attempt_id'] = attempt
    (directory/'source.json').write_text(json.dumps(source))
    (directory/'results.json').write_text(json.dumps(value))
    if status == 'fail':
        (directory/(stage+'-error.txt')).write_text(
            'Traceback (most recent call last):\n'+('  earlier frame\n'*2000)+
            '  File "framework_checks.py", line 172, in run\n    assert concrete_binding\nAssertionError: '+reason+'\n')
    if latest:
        (run/(slice_name+'-result.json')).write_text(json.dumps(value))
    return directory, value, source


class SliceCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'artifacts'
        self.root.mkdir()

    def packet(self, **kwargs):
        return collect(self.root, self.root/'packet.json', run_id='123', attempt=2,
                       source_sha=SOURCE_SHA, **kwargs)

    def outer(self, status='fail', slice_name='slice1'):
        ci = self.root/'ci'
        ci.mkdir(exist_ok=True)
        (ci/'step-attempts.jsonl').write_text(json.dumps(
            {'step': slice_name, 'attempt': 1, 'status': status,
             'log': slice_name+'-attempt-1.log', 'log_truncated': False})+'\n')
        # The actual stage reason is far beyond the console-selected window.
        (ci/(slice_name+'-attempt-1.log')).write_text(
            'fail: symfony_wiring\nContainer stopped\n'+('ordinary output\n'*2000)+CAUSE+'\n')

    def test_nested_failure_supplies_actual_cause_and_traceback_tail_once(self):
        directory, _, source = write_attempt(self.root)
        self.outer()
        packet = self.packet()
        outer = next(row for row in packet['excerpts'] if row['id'] == 'slice1.attempt1')
        nested = [row for row in packet['excerpts'] if 'provenance' in row]
        self.assertNotIn(CAUSE, outer['text'])
        self.assertEqual(len(nested), 1)  # latest summary does not duplicate it
        self.assertEqual(len(packet['checks']), 1)  # wrapper and cause are one failure
        self.assertEqual(packet['checks'][0]['excerpt_ids'], [outer['id'], nested[0]['id']])
        self.assertIn(CAUSE, nested[0]['text'])
        self.assertIn('assert concrete_binding', nested[0]['text'])
        self.assertIn('AssertionError', nested[0]['text'])
        self.assertTrue(nested[0]['truncated'])
        self.assertEqual(nested[0]['provenance'], {
            'run_id': 'owned-run', 'attempt_id': 'attempt-first', 'context_sha256': context_digest(source),
            'source_sha': SOURCE_SHA, 'step_attempt': 1, 'stage': 'symfony_wiring',
            'source': 'slice1/attempt-first/results.json'})
        self.assertEqual(packet['ci']['source_sha'], SOURCE_SHA)
        self.assertEqual(packet['ci']['attempt'], 2)
        self.assertLessEqual(len(canonical(packet)), MAX_PACKET)

    def test_failure_reaches_real_provider_payload_at_mock_boundary(self):
        write_attempt(self.root)
        packet = self.packet()
        eid = packet['excerpts'][0]['id']
        reply = {'model': MODEL, 'answers': {name: {'type': 'choice', 'choice': choice}
                 for name, choice in {'layer': 'semantic_behavior', 'probe': 'repeat_isolated_semantic_query',
                                      'support_1': eid, 'support_2': 'none'}.items()}}
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        response.read.return_value = canonical(reply)
        provider = mock.Mock()
        provider.open.return_value = response
        result = diagnose(packet, self.root/'mock-provider', key='synthetic-key', opener=provider)
        self.assertEqual(result['status'], 'diagnosed')
        self.assertEqual(result['transport'], 'mock')
        self.assertEqual(provider.open.call_count, 1)
        sent = json.loads(provider.open.call_args.args[0].data)['state']
        self.assertIn(CAUSE, sent['excerpts'][0]['text'])
        self.assertEqual(sent['excerpts'][0]['provenance']['stage'], 'symfony_wiring')
        self.assertFalse(result['probe_executed'])

    def test_slice3_runtime_cause_reaches_mock_provider_with_original_context(self):
        cause = 'Failed request marker s3-test has no matching profiler token'
        directory, _, _ = write_attempt(self.root, slice_name='slice3',
                                       reason=cause, stage='failed_request')
        (directory/'failed_request-error.txt').write_text(
            'Traceback (most recent call last):\nAssertionError: '+cause+'\n')
        self.outer(slice_name='slice3')
        packet = self.packet()
        self.assertEqual(len(packet['checks']), 1)
        self.assertEqual(packet['checks'][0]['step'], 'slice3')
        excerpt = next(row for row in packet['excerpts'] if 'provenance' in row)
        self.assertEqual(excerpt['provenance']['stage'], 'failed_request')
        self.assertEqual(excerpt['provenance']['source'], 'slice3/attempt-first/results.json')
        self.assertIn(cause, excerpt['text'])
        reply = {'model': MODEL, 'answers': {name: {'type': 'choice', 'choice': choice}
                 for name, choice in {'layer': 'setup_environment', 'probe': 'inspect_setup_log',
                                      'support_1': excerpt['id'], 'support_2': 'none'}.items()}}
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        response.read.return_value = canonical(reply)
        provider = mock.Mock()
        provider.open.return_value = response
        result = diagnose(packet, self.root/'slice3-mock-provider', key='synthetic-key', opener=provider)
        self.assertEqual(result['transport'], 'mock')
        self.assertEqual(result['status'], 'diagnosed')
        self.assertEqual(provider.open.call_count, 1)
        sent = json.loads(provider.open.call_args.args[0].data)['state']
        observed = next(row for row in sent['excerpts'] if 'provenance' in row)
        self.assertIn(cause, observed['text'])
        self.assertEqual(observed['provenance'], excerpt['provenance'])
        self.assertFalse(result['probe_executed'])

    def test_all_healthy_slices_make_zero_provider_requests(self):
        for slice_name in ('slice1', 'slice2', 'slice3'):
            write_attempt(self.root, slice_name=slice_name, status='pass', reason='healthy')
        packet = self.packet()
        provider = mock.Mock()
        result = diagnose(packet, self.root/'all-healthy-provider', key='synthetic-key', opener=provider)
        self.assertEqual(result['status'], 'nothing_to_diagnose')
        self.assertEqual(packet['checks'], [])
        provider.open.assert_not_called()

    def test_slice3_context_mismatch_is_rejected(self):
        directory, value, _ = write_attempt(self.root, slice_name='slice3', stage='runtime_reads')
        value['checks'][0]['attempt_id'] = 'attempt-foreign'
        (directory/'results.json').write_text(json.dumps(value))
        (directory.parent.parent/'slice3-result.json').write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'stage identity'):
            self.packet()

    def test_earlier_failed_retry_retained_when_latest_attempt_passes(self):
        write_attempt(self.root, slice_name='slice2', attempt='attempt-earlier', step_attempt=3)
        write_attempt(self.root, slice_name='slice2', attempt='attempt-latest', status='pass', reason='healthy')
        packet = self.packet()
        self.assertEqual(len(packet['checks']), 1)
        row = packet['excerpts'][0]
        self.assertEqual(row['step'], 'slice2')
        self.assertEqual(row['attempt'], 3)
        self.assertEqual(row['provenance']['attempt_id'], 'attempt-earlier')
        self.assertEqual(row['provenance']['source'], 'slice2/attempt-earlier/results.json')
        self.assertEqual(packet['checks'][0]['status'], 'fail')

    def test_recovered_outer_step_keeps_its_nested_failed_attempt(self):
        write_attempt(self.root, attempt='attempt-earlier')
        write_attempt(self.root, attempt='attempt-latest', status='pass', reason='healthy')
        self.outer(status='pass')
        packet = self.packet()
        self.assertEqual([row['status'] for row in packet['checks']], ['pass', 'fail'])
        failed = packet['checks'][1]
        excerpt = next(row for row in packet['excerpts'] if row['id'] in failed['excerpt_ids'])
        self.assertIn(CAUSE, excerpt['text'])
        self.assertEqual(excerpt['provenance']['attempt_id'], 'attempt-earlier')

    def test_healthy_run_ignores_unrelated_artifacts_and_makes_no_provider_call(self):
        write_attempt(self.root, status='pass', reason='healthy')
        (self.root/'owned-run/unrelated-error.txt').write_text('password=do-not-ingest\n'+CAUSE)
        packet = self.packet()
        provider = mock.Mock()
        result = diagnose(packet, self.root/'healthy-provider', key='synthetic-key', opener=provider)
        self.assertEqual(result['status'], 'nothing_to_diagnose')
        self.assertEqual(packet['checks'], [])
        self.assertEqual(packet['excerpts'], [])
        provider.open.assert_not_called()

    def test_relative_root_cli_matches_absolute_producer_evidence_paths(self):
        write_attempt(self.root)
        event = self.root.parent/'event.json'
        event.write_text('{}')
        env = {**os.environ, 'GITHUB_EVENT_PATH': str(event), 'GITHUB_SHA': SOURCE_SHA,
               'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2'}
        result = subprocess.run([sys.executable, str(CI/'capture_step.py'), 'collect',
                                 '--root', 'artifacts', '--out', 'packet.json'],
                                cwd=self.root.parent, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads((self.root.parent/'packet.json').read_text())
        self.assertIn(CAUSE, packet['excerpts'][0]['text'])

    def test_excerpt_is_bounded_sanitized_and_trace_tail_survives(self):
        reason = CAUSE+' password=secret-value '+('é'*4000)
        directory, _, _ = write_attempt(self.root, reason=reason)
        (directory/'symfony_wiring-error.txt').write_text(
            'long frames\n'*10000+'Authorization: Bearer secret-bearer\nAssertionError: '+CAUSE+'\n')
        packet = self.packet()
        text = packet['excerpts'][0]['text']
        self.assertIn(CAUSE, text)
        self.assertIn('AssertionError', text)
        self.assertNotIn('secret-value', text)
        self.assertNotIn('secret-bearer', text)
        self.assertLessEqual(len(text.encode()), 1600)
        self.assertTrue(packet['excerpts'][0]['truncated'])

    def test_mismatched_or_malformed_evidence_is_rejected(self):
        mutations = {
            'foreign_run': lambda value, source: value.update(run_id='foreign'),
            'foreign_workspace': lambda value, source: value.update(workspace='/other/app'),
            'foreign_source': lambda value, source: source.update(revision='b'*40),
            'wrong_digest': lambda value, source: value.update(source_context_sha256='b'*64),
            'foreign_attempt': lambda value, source: value.update(attempt_id='attempt-other'),
            'foreign_stage_context': lambda value, source: value['checks'][0].update(source_context_sha256='b'*64),
            'duplicate_stage': lambda value, source: value['checks'].append(value['checks'][0]),
            'path_stage': lambda value, source: value['checks'][0].update(name='../outside'),
            'invalid_reason': lambda value, source: value['checks'][0].update(reason=[]),
            'invalid_attempt': lambda value, source: value['checks'][0].update(step_attempt=True),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                directory, value, source = write_attempt(root)
                mutate(value, source)
                (directory/'source.json').write_text(json.dumps(source))
                (directory/'results.json').write_text(json.dumps(value))
                (directory.parent.parent/'slice1-result.json').write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    collect(root, root/'packet', run_id='1', attempt=1, source_sha=SOURCE_SHA)

    def test_wrong_summary_and_nonfinite_json_are_rejected(self):
        directory, value, _ = write_attempt(self.root)
        summary = directory.parent.parent/'slice1-result.json'
        value['checks'][0]['reason'] = 'foreign mirrored result'
        summary.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'mirror'):
            self.packet()
        summary.unlink()
        (directory/'results.json').write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON field'):
            self.packet()

    def test_symlinks_and_oversized_declared_files_are_rejected(self):
        for name, limit in [('results.json', SLICE_RESULT_LIMIT), ('source.json', SLICE_SOURCE_LIMIT),
                            ('symfony_wiring-error.txt', LOG_LIMIT)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                directory, _, _ = write_attempt(root)
                target = directory/name
                with target.open('wb') as stream:
                    stream.truncate(limit+1)
                with self.assertRaisesRegex(ValueError, 'bounded slice evidence'):
                    collect(root, root/'packet', run_id='1', attempt=1, source_sha=SOURCE_SHA)
        directory, _, _ = write_attempt(self.root)
        target = directory/'symfony_wiring-error.txt'
        target.unlink()
        target.symlink_to(directory/'source.json')
        with self.assertRaisesRegex(ValueError, 'bounded slice evidence'):
            self.packet()


if __name__ == '__main__':
    unittest.main()
