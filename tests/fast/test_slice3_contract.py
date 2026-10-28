"""Slice-3 regressions reject unrelated mutations and false request correlation."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests/integration'))
from slice3_contract import (CONTROLLER, TEST, REFERENCE, compare_native, response_record,
                             task_inputs, verify_runtime_result, verify_task_delta)


class Slice3ContractTests(unittest.TestCase):
    def test_equal_counts_do_not_hide_native_diagnostic_replacement(self):
        old = {'code': 'existing', 'message': 'old', 'annotations': []}
        with self.assertRaisesRegex(AssertionError, 'Native diagnostic multiset changed'):
            compare_native([old], [{**old, 'message': 'new'}])
        self.assertEqual(compare_native([old], [old])['introduced'], [])

    def test_observation_requires_response_token_and_unique_marker(self):
        row = response_record('HTTP/1.1 500 Error\nX-Debug-Token: abc123\n', status=500,
                              marker='s3-failure-123', url='http://localhost/?s3=s3-failure-123')
        self.assertEqual(row['token'], 'abc123')
        for headers in ('HTTP/1.1 500 Error\n', 'X-Debug-Token: abc123\nX-Debug-Token: def456\n'):
            with self.assertRaisesRegex(AssertionError, 'unique profiler response token'):
                response_record(headers, status=500, marker='s3-failure-123', url='http://localhost/?s3=s3-failure-123')
        with self.assertRaisesRegex(AssertionError, 'marker absent'):
            response_record('X-Debug-Token: abc123\n', status=500, marker='s3-other', url='http://localhost/')

    def test_recovery_cannot_reuse_a_historical_token(self):
        value = {'observations': {name: {'status': status, 'token': token, 'marker': 's3-'+name,
                                         'url': 'http://localhost/?id=s3-'+name}
                                  for name, status, token in [('healthy', 200, 'abc123'), ('defective', 500, 'def456'), ('repaired', 200, 'fed321')]}}
        self.assertEqual(verify_runtime_result(value)['status'], 'pass')
        value['observations']['repaired']['token'] = 'abc123'
        with self.assertRaisesRegex(AssertionError, 'tokens missing or reused'):
            verify_runtime_result(value)

    def test_final_task_rejects_controller_and_dependency_tampering(self):
        task = task_inputs(ROOT)
        before = {'entries': {CONTROLLER: {'kind': 'file', 'mode': 0o644, 'sha256': task['final_controller_sha256']},
                               REFERENCE: {'kind': 'file', 'mode': 0o644, 'sha256': 'a'*64},
                               'vendor/example.php': {'kind': 'file', 'mode': 0o644, 'sha256': 'c'*64}}}
        after = copy.deepcopy(before)
        after['entries'][TEST] = {'kind': 'file', 'mode': 0o644, 'sha256': task['files'][TEST]['sha256']}
        after['entries'][REFERENCE]['sha256'] = 'b'*64
        self.assertEqual(verify_task_delta(before, after, task, reference_sha256='b'*64)['declared_task_files'], [TEST])
        for name in (CONTROLLER, 'vendor/example.php', 'tests/Sneaky.php'):
            changed = copy.deepcopy(after)
            changed['entries'][name] = {'kind': 'file', 'mode': 0o644, 'sha256': 'e'*64}
            with self.assertRaisesRegex(AssertionError, 'Unexpected application task delta'):
                verify_task_delta(before, changed, task, reference_sha256='b'*64)
        with self.assertRaisesRegex(AssertionError, 'Unbound compiled reference'):
            verify_task_delta(before, after, task, reference_sha256='d'*64)


if __name__ == '__main__':
    unittest.main()
