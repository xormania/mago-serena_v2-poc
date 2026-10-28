"""Fast preflight regressions; native graph/exit controls run in framework_checks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'bin'))
import magolib


class EnrichedPreflightTests(unittest.TestCase):
    def test_unprepared_run_retains_reason_without_starting_mago(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('app', 'trusted', 'evidence'):
                (root/name).mkdir()
            data = {name: str(root/name) for name in ('app', 'trusted', 'evidence')}
            data['run_id'] = 'unprepared'
            with mock.patch.object(magolib, 'enriched_identity') as identity:
                result = magolib.run_enriched(data, ['analyze', '--reporting-format', 'json'])
            identity.assert_not_called()
            self.assertEqual((result['exit'], result['native_exit'], result['status']), (3, None, 'stale_preparation'))
            evidence = Path(result['evidence'])
            self.assertEqual((evidence/'stdout').read_bytes(), b'')
            self.assertIn('./bin/poc mate-prepare --run unprepared', (evidence/'stderr').read_text())
            self.assertEqual(json.loads((evidence/'invocation.json').read_text())['status'], 'stale_preparation')

    def test_mismatched_installed_sdk_cannot_use_a_matching_config(self):
        import shutil
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            (app/'.mago').mkdir()
            (app/'vendor/composer').mkdir(parents=True)
            for name in ('extensions.php', 'wiring.toml'):
                shutil.copy2(ROOT/'fixtures/mago'/name, app/'.mago'/name)
            (app/magolib.CONFIG).write_text('already prepared')
            (app/'vendor/composer/installed.json').write_text(json.dumps({'packages': [
                {'name': 'carthage-software/mago', 'source': {'reference': 'a'*40}},
                {'name': 'byte-kitsune/mago-symfony-wiring', 'source': {'reference': '28c3f54065b71fe046a7474ced401aeadc941b0f'}},
            ]}))
            with mock.patch.object(magolib, 'prepare_mago', return_value={}):
                with self.assertRaisesRegex(AssertionError, 'carthage-software/mago source'):
                    magolib.enriched_identity({'app': str(app)})

    def test_symbol_selection_is_bounded_and_does_not_accept_paths_or_expressions(self):
        self.assertEqual(magolib.selected_symbols([r'App\Command\TagsCountCommand']), [r'App\Command\TagsCountCommand'])
        for names in (['../Command.php'], ['A::method'], ['A', 'A'], ['A'+str(i) for i in range(9)]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                magolib.selected_symbols(names)

    def test_unscoped_enriched_writes_remain_rejected_before_launch(self):
        with self.assertRaisesRegex(ValueError, 'explicit existing'):
            magolib.run_enriched({}, ['analyze', '--fix'])

    def test_missing_malformed_or_incomplete_worker_evidence_cannot_report_shell_success(self):
        for native_exit in (0, 1):
            for failure in ('absent', 'malformed', 'coverage'):
                with self.subTest(native_exit=native_exit, failure=failure), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    for name in ('app/src', 'app/tests', 'trusted', 'state', 'evidence'):
                        (root/name).mkdir(parents=True)
                    (root/'app/src/Command.php').write_text('<?php class Command {}')
                    (root/'trusted/mate-preparation.json').write_text('{}')
                    data = {name: str(root/name) for name in ('app', 'trusted', 'state', 'evidence')}
                    data.update(run_id='worker-evidence', project='mago-evidence-test', port=0)
                    directory = root/'evidence/invocation'
                    prepared = {'preparation_id': 'prepare-test', 'application_sha256': 'a'*64,
                                'metadata': {}, 'wiring_reference_sha256': 'b'*64}
                    def native(*args, **kwargs):
                        if failure == 'malformed':
                            (directory/'graph.json').write_text('not JSON')
                        elif failure == 'coverage':
                            (directory/'graph.json').write_text(json.dumps({
                                'observer': 'poc/wiring-observer', 'wiring_enabled': False,
                                'symbols': {'Command': {}}, 'files': []}))
                        return SimpleNamespace(returncode=native_exit, stdout=b'{"issues":[]}', stderr=b'native stderr\n')
                    with mock.patch('matelib.fresh', return_value=prepared), \
                         mock.patch.object(magolib, 'enriched_identity', return_value={'config': '/app/config.toml'}), \
                         mock.patch.object(magolib.subprocess, 'run', side_effect=native):
                        result = magolib.run_enriched(data, ['analyze', '--reporting-format', 'json'],
                                                     symbols=['Command'], directory=directory, wiring_enabled=False)
                    self.assertEqual((result['status'], result['native_exit'], result['exit']), ('tool_failure', native_exit, 3))
                    stderr = (directory/'stderr').read_text()
                    self.assertIn('native stderr', stderr)
                    self.assertIn('mago-enriched:', stderr)
                    self.assertIn('native exit '+str(native_exit), stderr)


if __name__ == '__main__':
    unittest.main()
