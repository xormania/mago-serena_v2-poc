"""Run the real provider CLI with workflow isolation and no credentials/network."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT/'tools/ci/jev.py'
PACKET = ROOT/'docs/evidence/ci-performance/advisory-v1/hosted-40810928800/source/diagnosis-input.json'


class IsolatedProviderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.cwd = self.root/'untrusted-cwd'
        self.cwd.mkdir()
        for name in ('performance.py', 'jev.py'):
            (self.cwd/name).write_text("raise AssertionError('Untrusted module was imported')\n")
        self.packet = json.loads(PACKET.read_text())

    def invoke(self, packet=None, *, calibration=False):
        out = self.root/'output'
        command = [sys.executable, '-I', str(ENTRY), '--live', '--out', str(out)]
        if calibration:
            command.append('--calibration')
        else:
            path = self.root/'packet.json'
            path.write_text(json.dumps(packet))
            command += ['--packet', str(path)]
        # A nonempty key could contact the real endpoint if eligibility regressed.
        # Empty credentials guarantee that every exact-CLI case remains key-free.
        result = subprocess.run(command, cwd=self.cwd,
            env={'TYPESAFE_API_KEY': '', 'PYTHONPATH': str(self.cwd)},
            text=True, capture_output=True, timeout=30)
        self.assertNotIn('ModuleNotFoundError', result.stderr)
        self.assertNotIn('Untrusted module was imported', result.stderr)
        return result, out

    def assert_result(self, packet, status, code):
        completed, out = self.invoke(packet)
        self.assertEqual(completed.returncode, code, completed.stderr)
        result = json.loads((out/'result.json').read_text())
        self.assertEqual(result['status'], status)
        self.assertEqual(result['provider_request_attempts'], 0)
        self.assertFalse(result['provider_request_attempted'])
        self.assertTrue((out/'performance-report.json').is_file())
        self.assertIn(status, (out/'summary.md').read_text())
        self.assertEqual((out/'response.txt').read_bytes(), b'')
        return result, out

    def test_retained_warm_packet_runs_from_foreign_cwd_under_isolation(self):
        result, _ = self.assert_result(self.packet, 'nothing_to_diagnose', 0)
        self.assertFalse(result['deterministic_performance']['provider_eligible'])

    def test_successful_performance_signal_reaches_keyless_provider_gate(self):
        packet = copy.deepcopy(self.packet)
        observation = packet['performance']
        next(row for row in observation['phases'] if row['id'] == 'build')['elapsed_s'] = 1000
        observation['timing']['step_sum_s'] = sum(row['elapsed_s'] or 0 for row in observation['phases'])
        observation['build']['candidate'].update(outcome='executed', duration_s=570.7, compile_duration_s=570.7)
        result, out = self.assert_result(packet, 'missing_credentials', 1)
        self.assertTrue(result['deterministic_performance']['provider_eligible'])
        payload = json.loads((out/'request.json').read_text())
        self.assertIn('compilation_cost', payload['questions']['layer']['criteria'])
        self.assertTrue(all(row['status'] == 'pass' for row in payload['state']['checks']))

    def test_failed_check_with_performance_observation_reaches_keyless_gate(self):
        packet = copy.deepcopy(self.packet)
        next(row for row in packet['checks'] if row['step'] == 'acceptance')['status'] = 'fail'
        result, out = self.assert_result(packet, 'missing_credentials', 1)
        self.assertFalse(result['deterministic_performance']['provider_eligible'])
        payload = json.loads((out/'request.json').read_text())
        self.assertTrue(any(row['status'] == 'fail' for row in payload['state']['checks']))

    def test_calibration_entry_remains_bounded_and_keyless_under_isolation(self):
        completed, out = self.invoke(calibration=True)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        summary = json.loads((out/'calibration-summary.json').read_text())
        self.assertEqual(summary['planned_cases'], 4)
        self.assertEqual(summary['completed_cases'], 4)
        self.assertEqual(summary['provider_request_attempts'], 0)
        self.assertTrue(all(row['status'] == 'missing_credentials' for row in summary['cases']))


if __name__ == '__main__':
    unittest.main()
