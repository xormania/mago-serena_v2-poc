"""Real retained cold/warm evidence; synthetic mutations live in other tests."""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/ci'))
from performance import assess, collect_observation, parse_buildkit, render_summary

EVIDENCE = ROOT/'docs/evidence/ci-performance/advisory-v1'
WARM = '40798696741'
COLD = '40799634539'


def observed(run):
    return json.loads((EVIDENCE/f'observed-{run}.json').read_text())


def collect_retained(run):
    retained = observed(run)
    rows = [json.loads(line) for line in (EVIDENCE/f'steps-{run}.jsonl').read_text().splitlines()]
    # These test logs are selected excerpts, rather than the original complete
    # log. Disclose that fact to the parser even though original capture did not
    # truncate its much larger source member.
    next(row for row in rows if row['step'] == 'build')['log_truncated'] = True
    env = {'GITHUB_WORKSPACE': str(ROOT), 'GITHUB_ACTIONS': 'true',
           'GITHUB_REF': retained['ref'], 'GITHUB_EVENT_NAME': retained['event'],
           'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64', 'RUNNER_ENVIRONMENT': 'github-hosted',
           'PERFORMANCE_RUNNER_CLASS': 'ubuntu-latest', 'ImageOS': 'ubuntu24',
           'ImageVersion': retained['runner']['image_version']}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root/'ci').mkdir()
        (root/'ci/build-attempt-1.log').write_bytes((EVIDENCE/f'build-{run}.log').read_bytes())
        result = collect_observation(root, rows, retained['ci'], env)
    result['observed_unix'] = datetime.fromisoformat(retained['job']['completed_at'].replace('Z', '+00:00')).timestamp()
    return result


class HistoricalPerformanceTests(unittest.TestCase):
    def test_retained_ledgers_match_extraction_digests_and_identities(self):
        comparison = json.loads((EVIDENCE/'comparison.json').read_text())
        self.assertTrue(comparison['all_listed_blobs_equal'])
        self.assertFalse(comparison['warm_master_followup']['newer_unchanged_master_run_found'])
        for run in (WARM, COLD):
            retained = observed(run)
            self.assertEqual(run, retained['ci']['run_id'])
            raw = (EVIDENCE/f'steps-{run}.jsonl').read_bytes()
            self.assertEqual(retained['extraction']['steps_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual({'acceptance': 31, 'slice1': 9, 'slice2': 12, 'slice3': 14},
                {key: value['check_count'] for key, value in retained['gate_inventory'].items() if key != 'lsp_extensions'})
            self.assertEqual(19, retained['gate_inventory']['lsp_extensions']['control_count'])

    def test_observed_buildkit_cache_and_compile_results(self):
        warm, _ = parse_buildkit((EVIDENCE/f'build-{WARM}.log').read_bytes(), truncated=True)
        cold, _ = parse_buildkit((EVIDENCE/f'build-{COLD}.log').read_bytes(), truncated=True)
        self.assertEqual(('cached', 'cached'), (warm['baseline']['outcome'], warm['candidate']['outcome']))
        self.assertIsNone(warm['candidate']['compile_duration_s'])
        self.assertEqual('cached', cold['baseline']['outcome'])
        self.assertEqual(17.1, cold['baseline']['duration_s'])
        self.assertIsNone(cold['baseline']['compile_duration_s'])
        self.assertEqual('executed', cold['candidate']['outcome'])
        self.assertEqual(570.7, cold['candidate']['compile_duration_s'])
        for build, import_s, export_s in [(warm, .1, 5.5), (cold, .3, 25.3)]:
            self.assertEqual('success', build['import']['outcome'])
            self.assertEqual(import_s, build['import']['duration_s'])
            self.assertEqual('success', build['export']['outcome'])
            self.assertEqual(export_s, build['export']['duration_s'])
        self.assertEqual(253, observed(COLD)['measurements']['candidate_compile_entries'])

    def test_real_collection_and_boundary_classification_remain_advisory(self):
        warm, cold = collect_retained(WARM), collect_retained(COLD)
        self.assertEqual(warm['fingerprint'], cold['fingerprint'])
        warm_report = assess(warm)
        cold_report = assess(cold, {'observation': warm, 'selection_reason': 'retained historical PR observation; inaccessible PR merge-ref cache on master'})
        self.assertIn('warm_reuse', warm_report['classifications'])
        self.assertFalse(warm_report['provider_eligible'])
        self.assertIn('explained_cold_population', cold_report['classifications'])
        self.assertNotIn('unexpected_recompilation', cold_report['classifications'])
        self.assertNotIn('slow_verification', cold_report['classifications'])
        self.assertFalse(cold_report['provider_eligible'])
        self.assertFalse(cold_report['comparison']['deltas'])
        phases = {row['id']: row['elapsed_s'] for row in cold['phases']}
        self.assertEqual(651.353, phases['build'])
        self.assertAlmostEqual(469.772, sum(phases[key] for key in ('acceptance', 'slice1', 'slice2', 'slice3', 'lsp_extensions')))
        summary = render_summary(cold_report)
        for fact in ('651.353s', '570.700s', WARM, COLD, 'explained_cold_population', 'advisory'):
            self.assertIn(fact, summary)


if __name__ == '__main__':
    unittest.main()
