"""Runtime policy regressions; real request/source/boot controls live in slice 3."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'bin'))
import matelib


class RuntimeCommandTests(unittest.TestCase):
    def test_stale_source_profiler_read_avoids_compiled_guard(self):
        # The prior call() unconditionally fresh()'d tools:call and resources:read.
        # A valid already-recorded profile must remain readable after a source edit.
        with tempfile.TemporaryDirectory() as directory:
            data = {'run_id': 'stale', 'app': '/owned/app', 'evidence': directory}
            runtime = {'observations': [{'token': 'aabbcc', 'request_time_unix': 42}],
                       'read_paths': ['var/cache/dev/profiler'], 'container_id': 'selected'}
            with mock.patch.object(matelib, 'runtime_identity', return_value=runtime), \
                 mock.patch.object(matelib, 'fresh', side_effect=AssertionError('Application/dependencies changed')) as fresh, \
                 mock.patch.object(matelib, 'compose', return_value=['mate']), \
                 mock.patch.object(matelib, 'environment', return_value={}), \
                 mock.patch.object(matelib.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'{"token":"aabbcc"}', b'')):
                result = matelib.call(data, ['tools:call', 'symfony-profiler-get', '--token=aabbcc', '--format=json'])
            self.assertEqual(result.returncode, 0)
            fresh.assert_not_called()
            record = json.loads(next(Path(directory).rglob('invocation.json')).read_text())
            self.assertTrue(record['runtime']['historical'])
            self.assertFalse(record['runtime']['current_application_state'])
            self.assertEqual(record['runtime']['observations'][0]['request_time_unix'], 42)
            self.assertIsNone(record['application_sha256'])

    def test_compiled_service_aliases_and_global_options_cannot_bypass_freshness(self):
        variants = [
            ['tools:call', 'symfony-service-detail', '--id=SomeClass'],
            ['tools:ca', 'symfony-service-detail', '--id=SomeClass'],
            ['-n', '--no-ansi', 'tools:ca', 'symfony-service-detail'],
            ['--unknown-global=tools:list', 'tools:call', 'symfony-service-detail'],
            ['resources:r', 'symfony-profiler://profile/aabbcc/exception'],
            ['tools:call', 'symfony-profiler-get-suffix', '--token=aabbcc'],
        ]
        for argv in variants:
            with self.subTest(argv=argv):
                self.assertEqual(matelib.command_policy(argv)['kind'], 'compiled')
                with mock.patch.object(matelib, 'fresh', side_effect=AssertionError('stale')) as fresh:
                    with self.assertRaisesRegex(AssertionError, 'stale'):
                        matelib.call({}, argv)
                fresh.assert_called_once()

    def test_exact_runtime_names_work_with_known_leading_global_flags_and_json(self):
        result = matelib.command_policy(['--no-interaction', '-vv', 'tools:call', 'monolog-search',
                    '--json={"environment":"dev","kernelContext":"inspection-dev","limit":1}', '--limit=20'])
        self.assertEqual(result['kind'], 'runtime')
        self.assertEqual(result['parameters']['limit'], '20')
        self.assertEqual(matelib.command_policy(['-n', 'resources:read',
                    'symfony-profiler://profile/aabbcc/exception', '--format=json'])['token'], 'aabbcc')

    def test_runtime_context_limits_and_ambiguous_arguments_are_rejected(self):
        invalid = [
            ['symfony-profiler-list', '--context=prod'],
            ['symfony-profiler-list', '--context=inspection-dev', '--limit=-1'],
            ['symfony-profiler-list', '--context=inspection-dev', '--limit=101'],
            ['symfony-profiler-get', '--token=../../aabbcc'],
            ['monolog-search', '--environment=prod', '--kernelContext=inspection-dev'],
            ['monolog-search', '--environment=dev'],
            ['symfony-profiler-get', '--token=aabbcc', 'symfony-service-detail'],
            ['symfony-profiler-get', '--token=aabbcc', '--token=bbccdd'],
            ['symfony-profiler-get', '--json={"token":"aabbcc","context":"prod"}'],
            ['symfony-profiler-get', '--json'],
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(AssertionError):
                matelib.command_policy(['tools:call', *arguments])

    def test_missing_foreign_config_and_container_runtime_identity_rejected(self):
        for problem in ('missing', 'run', 'environment', 'config', 'container'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'app/mate').mkdir(parents=True)
                (root/'app/var/cache/dev/profiler').mkdir(parents=True)
                (root/'trusted').mkdir()
                config = root/'app/mate/config.php'
                config.write_text('selected fixed config')
                data = {'app': str(root/'app'), 'trusted': str(root/'trusted'), 'run_id': 'owned'}
                record = {'run_id': 'foreign' if problem == 'run' else 'owned', 'workspace': data['app'],
                          'environment': 'prod' if problem == 'environment' else 'dev', 'context': 'inspection-dev',
                          'config_sha256': 'changed' if problem == 'config' else matelib.sha(config),
                          'container_id': 'foreign' if problem == 'container' else 'owned-container'}
                if problem != 'missing':
                    (root/'trusted/mate-runtime.json').write_text(json.dumps(record))
                with mock.patch.object(matelib.subprocess, 'check_output', return_value='owned-container\n'), \
                     mock.patch.object(matelib, 'compose', return_value=['docker']), \
                     mock.patch.object(matelib, 'environment', return_value={}):
                    with self.assertRaises(AssertionError):
                        matelib.runtime_identity(data, {'tool': 'symfony-profiler-get', 'token': 'aabbcc'})

    def test_missing_symlink_and_oversized_runtime_data_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            data = {'app': directory}
            with self.assertRaisesRegex(AssertionError, 'missing'):
                matelib.runtime_files(data, ['var/log'])
            log = Path(directory)/'var/log'
            log.mkdir(parents=True)
            (log/'dev.log').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(AssertionError, 'symlink'):
                matelib.runtime_files(data, ['var/log'])
            (log/'dev.log').unlink()
            (log/'dev.log').write_text('bounded')
            with mock.patch.object(matelib, 'RUNTIME_MAX_BYTES', 1):
                with self.assertRaisesRegex(AssertionError, 'budget'):
                    matelib.runtime_files(data, ['var/log'])

    def test_runtime_instruction_refresh_preserves_owner_text_outside_its_block(self):
        with tempfile.TemporaryDirectory() as directory:
            owner = Path(directory)/'AGENTS.md'
            original = 'Owner instructions with significant trailing spaces  \n\tIndented instruction.\n\n'
            owner.write_text(original)
            matelib.install_runtime_instructions(owner, 'First managed instructions')
            first = owner.read_text()
            self.assertTrue(first.startswith(original))
            owner.write_text(first+'\nAfter-block owner instructions  \n')
            before, rest = owner.read_text().split('<!-- POC RUNTIME BEGIN -->', 1)
            _, after = rest.split('<!-- POC RUNTIME END -->', 1)
            matelib.install_runtime_instructions(owner, 'Refreshed managed instructions')
            expected = before+'<!-- POC RUNTIME BEGIN -->\nRefreshed managed instructions\n<!-- POC RUNTIME END -->'+after
            self.assertEqual(owner.read_text(), expected)

    def test_explicit_refresh_archives_original_observation_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'app/var/cache/dev/profiler').mkdir(parents=True)
            (root/'app/var/log').mkdir()
            (root/'evidence').mkdir()
            profile = root/'app/var/cache/dev/profiler/index.csv'
            profile.write_text('aabbcc,127.0.0.1,GET,/failed,42,,500\n')
            log = root/'app/var/log/dev.log'
            log.write_text('failed request\n')
            data = {'run_id': 'owned', 'app': str(root/'app')}
            manifest = matelib.preserve_runtime(data, root/'evidence')
            profile.unlink()
            log.unlink()
            self.assertEqual(len(manifest), 2)
            self.assertEqual((root/'evidence/runtime-before-refresh/var/log/dev.log').read_text(), 'failed request\n')
            record = json.loads((root/'evidence/runtime-before-refresh.json').read_text())
            self.assertTrue(record['historical'])


if __name__ == '__main__':
    unittest.main()
