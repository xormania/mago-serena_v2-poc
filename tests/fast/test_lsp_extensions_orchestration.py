"""A failed focused gate must retain its evidence and purge only its owned run."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('lsp_extensions_orchestration', ROOT/'tests/integration/lsp_extensions.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class FreshLspExtensionsTests(unittest.TestCase):
    def test_selected_image_identity_and_failure_cleanup(self):
        tag = 'mago-serena-poc:lsp-workers-test'
        for scenario in ('pass', 'probe_failure', 'image_mismatch'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                data = {'run_id': 'lspext-ci-owned', 'evidence': directory}
                expected = 'sha256:'+'a'*64
                actual = 'sha256:'+'b'*64 if scenario == 'image_mismatch' else expected
                identity = lambda selected, source: {'image_id': actual}
                def start(selected, *, build, validate_image):
                    self.assertIs(selected, data)
                    self.assertFalse(build)
                    validate_image(selected)
                with patch.dict(probe.os.environ, {'POC_IMAGE': tag}), \
                        patch.object(probe, 'prepare', return_value=data), \
                        patch.object(probe, 'new_id', return_value=data['run_id']) as new_id, \
                        patch.object(probe, 'metadata', return_value={'source_manifest': {}}), \
                        patch.object(probe, 'environment', return_value={'POC_IMAGE': tag}), \
                        patch.object(probe, 'compose', return_value=['docker', 'compose']), \
                        patch.object(probe, 'docker', return_value='docker'), \
                        patch.object(probe.subprocess, 'check_output', side_effect=[
                            json.dumps({'services': {'php': {'image': tag}}}), expected+'\n']), \
                        patch.object(probe.subprocess, 'run', return_value=SimpleNamespace(stdout=b'logs', stderr=b'')), \
                        patch.object(probe.runpy, 'run_path', return_value={'capture_identity': identity}), \
                        patch.object(probe, 'start', side_effect=start), \
                        patch.object(probe, 'prepare_mate') as prepare_mate, \
                        patch.object(probe, 'run', return_value={'status': 'pass'}) as run, \
                        patch.object(probe, 'stop') as stop:
                    if scenario == 'probe_failure':
                        run.side_effect = RuntimeError('worker failed')
                    if scenario == 'pass':
                        self.assertEqual(probe.run_fresh(), {'status': 'pass'})
                    else:
                        with self.assertRaises(RuntimeError if scenario == 'probe_failure' else AssertionError):
                            probe.run_fresh()
                    new_id.assert_called_once_with('lspext-ci')
                    stop.assert_called_once_with(data, purge=True)
                    if scenario == 'image_mismatch':
                        prepare_mate.assert_not_called()
                        run.assert_not_called()
                    else:
                        run.assert_called_once_with(data['run_id'], restore_preparation=False)
                record = json.loads((Path(directory)/'fresh-result.json').read_text())
                self.assertEqual(record['status'], 'pass' if scenario == 'pass' else 'fail')
                self.assertEqual(record['cleanup'], 'pass')
                self.assertEqual(record['image'], tag)
                self.assertTrue((Path(directory)/'metadata.json').is_file())
                self.assertEqual((Path(directory)/'container.log').read_text(), 'logs')
                if scenario != 'pass':
                    self.assertIn('error', record)


if __name__ == '__main__':
    unittest.main()
