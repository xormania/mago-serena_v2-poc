"""Deterministic performance decisions, parsing uncertainty and input bounds."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from performance import (PHASES, POLICY, assess, collect_observation, compile_fingerprint,
                         parse_buildkit, render_summary, validate_observation)

ROOT = Path(__file__).resolve().parents[2]
WARM = '''#14 importing cache manifest from gha:example
#14 DONE 0.2s
#27 [mago 4/4] RUN cargo build --locked --release -j 6 && cp target/release/mago /mago
#31 [mago-candidate 2/3] RUN cp /mago /mago-baseline && cargo build --locked --release -j "2"
#27 CACHED
#31 CACHED
#27 extracting sha256:123
#27 DONE 17.1s
#40 exporting to GitHub Actions Cache
#40 DONE 5.5s
'''
COLD = WARM.replace('#31 CACHED', '#31 0.8 Compiling mago v1.0\n#31 570.6 Finished `release` profile [optimized] target(s) in 9m 30s\n#31 DONE 570.7s')


class PerformanceReportTests(unittest.TestCase):
    def test_capture_uses_monotonic_elapsed_and_keeps_native_exit(self):
        import sys
        from capture_step import capture
        with tempfile.TemporaryDirectory() as directory, \
             patch('capture_step.time.time', side_effect=[1_700_000_000, 1_699_999_000]), \
             patch('capture_step.time.monotonic', side_effect=[100, 102.75]):
            code = capture('fast', 1, [sys.executable, '-c', 'raise SystemExit(23)'], directory)
            row = json.loads((Path(directory)/'step-attempts.jsonl').read_text())
        self.assertEqual(code, 23)
        self.assertEqual(row['elapsed_s'], 2.75)
        self.assertEqual(row['status'], 'fail')
        self.assertLess(row['finished_unix'], row['started_unix'])

    def observation(self, *, raw=WARM, ref='refs/heads/master', build_s=47, stamp=1_700_000_000):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'ci').mkdir()
            (root/'ci/build-attempt-1.log').write_text(raw)
            rows = [{'step': name, 'attempt': 1, 'status': 'pass',
                     'elapsed_s': build_s if name == 'build' else 70 if name == 'slice3' else 20,
                     'started_unix': stamp + i*100} for i, name in enumerate(PHASES)]
            rows[2]['log'] = 'build-attempt-1.log'
            ci = {'run_id': '123', 'attempt': 1, 'source_sha': 'a'*40, 'workflow_head_sha': 'b'*40}
            env = {'GITHUB_WORKSPACE': str(ROOT), 'GITHUB_REF': ref, 'GITHUB_EVENT_NAME': 'push',
                   'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64', 'RUNNER_ENVIRONMENT': 'github-hosted',
                   'PERFORMANCE_RUNNER_CLASS': 'ubuntu-latest', 'ImageOS': 'ubuntu24', 'ImageVersion': '20261025'}
            result = collect_observation(root, rows, ci, env)
            result['observed_unix'] = stamp+1000
            return result

    def set_duration(self, obs, name, value):
        next(row for row in obs['phases'] if row['id'] == name)['elapsed_s'] = value
        obs['timing']['step_sum_s'] = sum(row['elapsed_s'] or 0 for row in obs['phases'])

    def prior(self, current):
        prior = copy.deepcopy(current)
        prior['observed_unix'] -= 3600
        prior['ci']['run_id'] = '122'
        return prior

    def test_interleaving_and_cached_extraction_keep_compile_outcomes(self):
        build, evidence = parse_buildkit(WARM)
        self.assertEqual(build['baseline']['outcome'], 'cached')
        self.assertEqual(build['baseline']['duration_s'], 17.1)
        self.assertIsNone(build['baseline']['compile_duration_s'])
        self.assertEqual(build['candidate']['outcome'], 'cached')
        self.assertEqual(build['export']['duration_s'], 5.5)
        self.assertIn('CACHED', next(row['text'] for row in evidence if row['id'].endswith('baseline')))

    def test_compilation_duration_comes_from_vertex_not_line_timestamps(self):
        build, evidence = parse_buildkit(COLD)
        self.assertEqual(build['candidate']['outcome'], 'executed')
        self.assertEqual(build['candidate']['compile_duration_s'], 570.7)
        self.assertEqual(build['baseline']['outcome'], 'cached')
        self.assertIn('Finished', next(row['text'] for row in evidence if row['id'].endswith('candidate')))

    def test_truncation_missing_headers_and_manifest_only_are_unknown(self):
        for raw in ('#14 importing cache manifest from gha:x\n#14 DONE 0.2s',
                    '#31 CACHED\n#31 DONE 9.3s',
                    '#31 [mago-candidate 2/3] RUN cargo build --release\n#31 DONE 400.3s'):
            with self.subTest(raw=raw):
                build, _ = parse_buildkit(raw, truncated=True)
                self.assertEqual(build['candidate']['outcome'], 'unknown')
                self.assertIsNone(build['candidate']['compile_duration_s'])
        self.assertEqual(parse_buildkit(COLD, truncated=True)[0]['candidate']['outcome'], 'executed')

    def test_failed_compile_and_contradictory_vertex_never_manufacture_cache_hit(self):
        raw = '#9 [mago-candidate 2/3] RUN cargo build --release\n#9 ERROR: process failed'
        self.assertEqual(parse_buildkit(raw)[0]['candidate']['outcome'], 'failed')
        self.assertEqual(parse_buildkit(COLD+'#31 CACHED\n')[0]['candidate']['outcome'], 'unknown')
        self.assertEqual(parse_buildkit(COLD.replace('#31', '#888'))[0]['candidate']['outcome'], 'executed')

    def test_warm_success_summary_without_history_needs_no_provider(self):
        report = assess(self.observation())
        self.assertIn('warm_reuse', report['classifications'])
        self.assertIn('insufficient_evidence', report['classifications'])
        self.assertFalse(report['provider_eligible'])
        summary = render_summary(report)
        self.assertIn('Jev performance eligibility: **no**', summary)
        self.assertIn('captured', summary.lower())
        self.assertIn('missing_baseline', summary)

    def test_pr_to_master_explains_population_without_comparing_timing(self):
        now = self.observation(raw=COLD, build_s=651)
        before = self.prior(self.observation(ref='refs/pull/6/merge'))
        report = assess(now, before)
        self.assertIn('explained_cold_population', report['classifications'])
        self.assertFalse(report['provider_eligible'])
        self.assertFalse(report['comparison']['compatible'])
        self.assertTrue(report['comparison']['configuration_compatible'])
        self.assertEqual(report['comparison']['deltas'], [])

    def test_default_branch_cache_is_visible_to_pr_so_ref_difference_is_not_explanation(self):
        now = self.observation(raw=COLD, ref='refs/pull/7/merge', build_s=651)
        before = self.prior(self.observation())
        report = assess(now, before)
        self.assertNotIn('explained_cold_population', report['classifications'])
        self.assertFalse(report['provider_eligible'])
        wrapper = {'observation': before, 'cache_entry': {
            'accessible': True, 'source': 'github_cache_inventory', 'observed_at_unix': now['observed_unix']}}
        self.assertIn('unexpected_recompilation', assess(now, wrapper)['classifications'])

    def test_matching_inputs_need_positive_current_cache_presence_before_recompile_signal(self):
        now = self.observation(raw=COLD, build_s=651)
        before = self.prior(self.observation())
        for cache_entry in ({}, {'accessible': False}, {'accessible': True, 'source': 'github_cache_inventory', 'observed_at_unix': now['observed_unix']-600}):
            with self.subTest(cache_entry=cache_entry):
                self.assertFalse(assess(now, {'observation': before, 'cache_entry': cache_entry})['provider_eligible'])
        report = assess(now, {'observation': before, 'selection_reason': 'most recent validated same-ref observation',
                             'cache_entry': {'accessible': True, 'source': 'github_cache_inventory', 'observed_at_unix': now['observed_unix']+30}})
        self.assertTrue(report['provider_eligible'])
        self.assertIn('unexpected_recompilation', report['classifications'])
        self.assertEqual(report['comparison']['deltas'], [])

    def test_slow_verification_requires_relative_and_absolute_significance(self):
        now = self.observation()
        before = self.prior(now)
        for seconds in (100, 125):
            self.set_duration(now, 'slice3', seconds)
            self.assertFalse(assess(now, before)['provider_eligible'])
        self.set_duration(now, 'slice3', 140)
        report = assess(now, before)
        self.assertEqual([s['kind'] for s in report['signals']], ['slow_verification'])
        self.assertNotIn('unexpected_recompilation', report['classifications'])
        delta = next(row for row in report['comparison']['deltas'] if row['phase'] == 'slice3')
        self.assertEqual(delta['delta_s'], 70)
        self.assertEqual(delta['ratio'], 2)

    def test_config_inventory_runner_and_stale_changes_disable_relative_comparison(self):
        now = self.observation()
        self.set_duration(now, 'slice3', 200)
        for kind in ('runner', 'inventory', 'fingerprint', 'stale'):
            before = self.prior(self.observation())
            if kind == 'runner':
                before['context']['runner']['class'] = 'large'
            elif kind == 'inventory':
                before['inventory']['gates'][0]['expected_checks'] += 1
            elif kind == 'fingerprint':
                before['fingerprint']['inputs']['build_args']['MAGO_BUILD_JOBS'] = '4'
                import hashlib
                raw = json.dumps(before['fingerprint']['inputs'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
                before['fingerprint']['sha256'] = hashlib.sha256(raw).hexdigest()
            else:
                before['observed_unix'] -= 8*86400
            with self.subTest(kind=kind):
                report = assess(now, before)
                self.assertFalse(report['comparison']['compatible'])
                self.assertFalse(report['provider_eligible'])
                self.assertEqual(report['comparison']['deltas'], [])

    def test_absolute_budget_is_advisory_and_can_include_explained_cold_build(self):
        now = self.observation(raw=COLD, build_s=901)
        before = self.prior(self.observation(ref='refs/pull/6/merge'))
        report = assess(now, before)
        self.assertIn('explained_cold_population', report['classifications'])
        self.assertIn('absolute_budget_breach', report['classifications'])
        self.assertTrue(report['provider_eligible'])
        self.assertEqual(next(row for row in now['phases'] if row['id'] == 'build')['status'], 'pass')
        policy = {**POLICY, 'cold_build_budget_s': 1200}
        self.assertFalse(assess(now, before, policy)['provider_eligible'])

    def test_missing_measurements_are_explicit_without_zero_success(self):
        now = self.observation()
        phase = next(row for row in now['phases'] if row['id'] == 'slice3')
        phase.update(status='cancelled', elapsed_s=None)
        now['timing']['step_sum_s'] -= 70
        report = assess(now)
        self.assertIn('| slice3 / 1 | cancelled | unavailable |', render_summary(report))
        self.assertFalse(report['provider_eligible'])

    def test_malformed_metrics_references_and_identity_are_rejected(self):
        base = self.observation()
        for value in (True, -1, float('nan'), float('inf'), '2', 9_000_000):
            now = copy.deepcopy(base)
            now['phases'][0]['elapsed_s'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_observation(now)
        bad = copy.deepcopy(base)
        bad['build']['candidate']['evidence_ids'] = ['missing']
        with self.assertRaises(ValueError):
            validate_observation(bad)
        with self.assertRaises(ValueError):
            validate_observation(base, {**base['ci'], 'attempt': 2})
        bad = copy.deepcopy(base)
        bad['provider_eligible'] = True
        with self.assertRaises(ValueError):
            validate_observation(bad)

    def test_compile_fingerprint_changes_only_relevant_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'patches').mkdir()
            dockerfile = (ROOT/'Dockerfile').read_text()
            patch = (ROOT/'patches/mago-lsp-extensions.patch').read_bytes()
            (root/'Dockerfile').write_text(dockerfile)
            (root/'patches/mago-lsp-extensions.patch').write_bytes(patch)
            baseline = compile_fingerprint(root)['sha256']
            (root/'README.md').write_text('unrelated documentation')
            (root/'Dockerfile').write_text(dockerfile.replace('COPY adapter ./adapter', 'COPY adapter ./adapter\nRUN echo runtime-only'))
            self.assertEqual(compile_fingerprint(root)['sha256'], baseline)
            (root/'patches/mago-lsp-extensions.patch').write_bytes(patch+b'\n')
            self.assertNotEqual(compile_fingerprint(root)['sha256'], baseline)
            (root/'patches/mago-lsp-extensions.patch').write_bytes(patch)
            self.assertNotEqual(compile_fingerprint(root, platform='linux/arm64')['sha256'], baseline)
            self.assertNotEqual(compile_fingerprint(root, build_args={'MAGO_BUILD_JOBS': '4'})['sha256'], baseline)

    def test_unsafe_log_reference_and_oversized_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [{'step': 'build', 'attempt': 1, 'status': 'pass', 'elapsed_s': 1, 'started_unix': 1, 'log': '../private'}]
            with self.assertRaises(ValueError):
                collect_observation(root, rows, self.observation()['ci'], {'GITHUB_WORKSPACE': str(ROOT)})
        with self.assertRaises(ValueError):
            parse_buildkit('x'*(1024*1024+1))


if __name__ == '__main__':
    unittest.main()
