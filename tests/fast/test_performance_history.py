"""Trusted baseline selection against bounded mocked Actions metadata."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/ci'))
from performance import collect_observation
from performance_history import lookup_baseline, source_timing

NOW = 1793200000
REPO = 'xormania/mago-serena_v2-poc'


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')


def observed(run_id='99'):
    ci = {'run_id': run_id, 'attempt': 1, 'source_sha': 'a'*40, 'workflow_head_sha': 'a'*40}
    with tempfile.TemporaryDirectory() as directory:
        return collect_observation(Path(directory), [], ci, {
            'GITHUB_WORKSPACE': str(ROOT), 'GITHUB_REF': 'refs/heads/master',
            'GITHUB_EVENT_NAME': 'push', 'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64',
            'RUNNER_ENVIRONMENT': 'github-hosted', 'ImageOS': 'ubuntu24', 'ImageVersion': '1'})


def run(run_id=98, **changes):
    return {'id': run_id, 'run_attempt': 1, 'head_sha': 'a'*40, 'event': 'push',
            'head_branch': 'master', 'status': 'completed', 'conclusion': 'success',
            'created_at': stamp(NOW-120), 'path': '.github/workflows/poc.yml',
            'repository': {'full_name': REPO}, 'head_repository': {'full_name': REPO}, **changes}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.current = observed()
        self.current['observed_unix'] = NOW
        self.packet = {'ci': self.current['ci'], 'performance': self.current}
        self.event = {'repository': {'full_name': REPO, 'default_branch': 'master'},
                      'workflow_run': run(99, created_at=stamp(NOW-60))}
        self.previous = copy.deepcopy(self.current)
        self.previous['ci']['run_id'] = '98'
        self.previous['observed_unix'] = NOW-90
        self.previous_packet = {'ci': self.previous['ci'], 'performance': self.previous}

    def test_selects_identified_prior_and_requires_preexisting_visible_cache_index(self):
        cache = {'actions_caches': [{'id': 1, 'ref': 'refs/heads/master',
                  'key': 'index-mago-serena-linux-amd64-v1-1-xyz', 'created_at': stamp(NOW-80)}]}
        with patch('performance_history._json', side_effect=[{'workflow_runs': [run()]}, cache]), \
             patch('performance_history.download', return_value=self.previous_packet) as download:
            baseline, audit = lookup_baseline(self.packet, self.event, 'fake', now=NOW)
        self.assertEqual(baseline['observation']['ci']['run_id'], '98')
        self.assertTrue(baseline['cache_entry']['accessible'])
        self.assertEqual(audit['status'], 'baseline_selected')
        self.assertEqual(download.call_count, 1)

    def test_cache_created_by_source_run_cannot_establish_prior_reuse_expectation(self):
        cache = {'actions_caches': [{'id': 1, 'ref': 'refs/heads/master',
                  'key': 'index-mago-serena-linux-amd64-v1-1-xyz', 'created_at': stamp(NOW-10)}]}
        with patch('performance_history._json', side_effect=[{'workflow_runs': [run()]}, cache]), \
             patch('performance_history.download', return_value=self.previous_packet):
            baseline, _ = lookup_baseline(self.packet, self.event, 'fake', now=NOW)
        self.assertFalse(baseline['cache_entry']['accessible'])

    def test_stale_foreign_and_future_runs_never_downloaded(self):
        rows = [run(1, created_at=stamp(NOW-8*86400)),
                run(2, repository={'full_name': 'foreign/repo'}),
                run(3, created_at=stamp(NOW))]
        with patch('performance_history._json', return_value={'workflow_runs': rows}), \
             patch('performance_history.download') as download:
            baseline, audit = lookup_baseline(self.packet, self.event, 'fake', now=NOW)
        self.assertIsNone(baseline)
        self.assertEqual(audit['status'], 'comparison_unavailable')
        download.assert_not_called()

    def test_legacy_missing_artifacts_have_three_download_limit_and_no_retry(self):
        rows = [run(n, created_at=stamp(NOW-120-n)) for n in range(10, 20)]
        with patch('performance_history._json', return_value={'workflow_runs': rows}), \
             patch('performance_history.download', return_value=None) as download:
            baseline, audit = lookup_baseline(self.packet, self.event, 'fake', now=NOW)
        self.assertIsNone(baseline)
        self.assertEqual(download.call_count, 3)
        self.assertEqual(audit['downloads_attempted'], 3)

    def test_invalid_history_is_visible_without_throwing_away_current_observation(self):
        with patch('performance_history._json', side_effect=TimeoutError()):
            baseline, audit = lookup_baseline(self.packet, self.event, 'fake', now=NOW)
        self.assertIsNone(baseline)
        self.assertEqual(audit['status'], 'history_lookup_failed')
        self.assertEqual(audit['exception_type'], 'TimeoutError')

    def test_incompatible_observation_is_identified_and_not_compatible(self):
        self.previous['context']['runner']['image_version'] = 'different'
        with patch('performance_history._json', return_value={'workflow_runs': [run()]}), \
             patch('performance_history.download', return_value=self.previous_packet):
            baseline, audit = lookup_baseline(self.packet, self.event, 'fake', now=NOW)
        self.assertEqual(audit['status'], 'incomparable_baseline_selected')
        from performance import assess
        report = assess(self.current, baseline)
        self.assertFalse(report['comparison']['compatible'])
        self.assertFalse(report['provider_eligible'])

    def test_completed_job_timing_is_separate_from_command_sums(self):
        job = {'id': 7, 'name': 'acceptance', 'started_at': stamp(NOW-55),
               'completed_at': stamp(NOW), 'steps': [
                   {'name': 'Set up job', 'started_at': stamp(NOW-55), 'completed_at': stamp(NOW-53)},
                   {'name': 'Post checkout', 'started_at': stamp(NOW-2), 'completed_at': stamp(NOW)}]}
        with patch('performance_history._json', return_value={'total_count': 1, 'jobs': [job]}):
            result = source_timing(self.event, 'fake')
        self.assertEqual(result['job_wall_s'], 55)
        self.assertEqual(result['queue_s'], 5)
        self.assertEqual(result['setup_s'], 2)
        self.assertEqual(result['cleanup_s'], 2)
        self.assertEqual(result['resolution_s'], 1)


if __name__ == '__main__':
    unittest.main()
