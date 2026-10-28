"""Regressions for task scope, diagnostic deltas and original test identities."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests/integration'))
from slice2_contract import (COMMAND, TEST, TARGETS, REFERENCE, FEATURE_IDS,
                             compare_native, task_inputs, validate_agent_evidence, verify_suites, verify_task_delta)


class TaskDeltaTests(unittest.TestCase):
    def setUp(self):
        self.task = task_inputs(ROOT)
        self.before = {'entries': {
            'src/Existing.php': {'kind': 'file', 'mode': 0o644, 'sha256': 'a'*64},
            'phpunit.dist.xml': {'kind': 'file', 'mode': 0o644, 'sha256': 'b'*64},
            REFERENCE: {'kind': 'file', 'mode': 0o644, 'sha256': 'c'*64},
        }}
        self.after = copy.deepcopy(self.before)
        for target in TARGETS:
            self.after['entries'][target] = {'kind': 'file', 'mode': 0o644, 'sha256': self.task['files'][target]['sha256']}
        self.after['entries'][REFERENCE]['sha256'] = 'd'*64

    def test_exact_declared_additions_and_bound_export_pass(self):
        result = verify_task_delta(self.before, self.after, self.task, reference_sha256='d'*64)
        self.assertEqual(result['declared_task_files'], list(TARGETS))

    def test_undeclared_addition_and_original_configuration_change_fail(self):
        for target in ('src/Sneaky.php', 'phpunit.dist.xml'):
            with self.subTest(target=target):
                altered = copy.deepcopy(self.after)
                altered['entries'][target] = {'kind': 'file', 'mode': 0o644, 'sha256': 'e'*64}
                with self.assertRaisesRegex(AssertionError, 'Unexpected application task delta'):
                    verify_task_delta(self.before, altered, self.task, reference_sha256='d'*64)

    def test_modified_task_output_or_unbound_export_fails(self):
        altered = copy.deepcopy(self.after)
        altered['entries'][COMMAND]['sha256'] = 'e'*64
        with self.assertRaisesRegex(AssertionError, 'Unexpected task output'):
            verify_task_delta(self.before, altered, self.task, reference_sha256='d'*64)
        with self.assertRaisesRegex(AssertionError, 'Unbound compiled reference'):
            verify_task_delta(self.before, self.after, self.task, reference_sha256='e'*64)

    def test_equal_finding_counts_do_not_hide_replaced_findings(self):
        existing = {'code': 'existing', 'message': 'unchanged', 'annotations': []}
        replacement = {'code': 'new', 'message': 'regression', 'annotations': []}
        with self.assertRaisesRegex(AssertionError, 'Native diagnostic multiset changed'):
            compare_native([existing], [replacement])
        self.assertEqual(compare_native([existing, existing], [existing, existing])['introduced'], [])

    def test_existing_findings_on_new_files_are_still_rejected(self):
        issue = {'code': 'strict-types', 'annotations': [{'span': {'file_id': {'name': TEST}}}]}
        with self.assertRaisesRegex(AssertionError, 'New task PHP has native findings'):
            compare_native([issue], [issue])


class SuiteIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.old_case = {'id': r'App\Tests\OriginalTest::testOriginal', 'file': 'tests/OriginalTest.php', 'line': 3}
        self.original = {'schema': 1, 'configuration': 'phpunit.dist.xml', 'list_xml_sha256': 'a'*64,
                         'source_sha256': {'phpunit.dist.xml': 'b'*64, 'tests/OriginalTest.php': 'c'*64},
                         'cases': [self.old_case]}
        self.combined = copy.deepcopy(self.original)
        self.combined['source_sha256'][TEST] = 'd'*64
        self.combined['cases'] += [{'id': identity, 'file': TEST, 'line': line}
                                   for line, identity in enumerate(sorted(FEATURE_IDS), 10)]
        self.combined['cases'].sort(key=lambda case: case['id'])
        cases = []
        for case in self.combined['cases']:
            cls, method = case['id'].split('::')
            cases.append('<testcase class="'+cls+'" name="'+method+'" file="/app/'+case['file']+'" line="'+str(case['line'])+'" assertions="2"/>')
        (self.path/'all.xml').write_text('<testsuites><testsuite name="/app/phpunit.dist.xml" tests="3" errors="0" failures="0" skipped="0">'+''.join(cases)+'</testsuite></testsuites>')

    def test_dynamic_combined_total_and_exact_original_projection(self):
        result = verify_suites(self.original, self.combined, self.path/'all.xml', self.path/'old.xml')
        self.assertEqual(result['original']['tests'], 1)
        self.assertEqual(result['combined']['tests'], 3)
        self.assertEqual(result['feature']['tests'], 2)
        self.assertEqual(result['feature']['assertions'], 4)

    def test_extra_test_identity_is_not_silently_accepted(self):
        self.combined['cases'].append({'id': r'App\Tests\Command\TagsCountCommandTest::testSneaky', 'file': TEST, 'line': 99})
        with self.assertRaisesRegex(AssertionError, 'Unexpected feature-test identities'):
            verify_suites(self.original, self.combined, self.path/'all.xml', self.path/'old.xml')

    def test_original_bytes_and_dataset_identity_remain_required(self):
        changed = copy.deepcopy(self.combined)
        changed['source_sha256']['phpunit.dist.xml'] = 'e'*64
        with self.assertRaisesRegex(AssertionError, 'Original test/configuration bytes changed'):
            verify_suites(self.original, changed, self.path/'all.xml', self.path/'old.xml')
        changed = copy.deepcopy(self.combined)
        next(case for case in changed['cases'] if case['id'] == self.old_case['id'])['id'] += '#changed'
        with self.assertRaisesRegex(AssertionError, 'Original suite identities changed'):
            verify_suites(self.original, changed, self.path/'all.xml', self.path/'old.xml')


class AgentEvidenceTests(unittest.TestCase):
    def test_retained_fresh_session_binds_real_public_analysis_and_replay_outputs(self):
        result = validate_agent_evidence(ROOT, task_inputs(ROOT))
        self.assertGreaterEqual(result['successful_semantic_edits'], 1)
        self.assertEqual(result['native']['analyze']['introduced'], [])

    def test_missing_index_or_changed_artifact_cannot_claim_fresh_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(AssertionError, 'evidence index absent'):
                validate_agent_evidence(root, task_inputs(ROOT))
            destination = root/'docs/evidence/slice2/fresh-agent'
            shutil.copytree(ROOT/'docs/evidence/slice2/fresh-agent', destination)
            path = destination/'mcp/mcp.jsonl'
            content = path.read_bytes()
            # Same length: this must be rejected by content identity, not bounds.
            path.write_bytes(bytes([content[0] ^ 1])+content[1:])
            with self.assertRaisesRegex(AssertionError, 'artifact hash mismatch'):
                validate_agent_evidence(root, task_inputs(ROOT))

    def test_different_declared_output_is_not_accepted_as_fresh_agent_work(self):
        task = task_inputs(ROOT)
        task['files'][COMMAND]['sha256'] = '0'*64
        with self.assertRaisesRegex(AssertionError, 'Replay task differs from fresh-agent output'):
            validate_agent_evidence(ROOT, task)


if __name__ == '__main__':
    unittest.main()
