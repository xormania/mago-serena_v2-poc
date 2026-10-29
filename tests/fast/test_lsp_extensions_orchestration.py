"""A failed focused gate must retain its evidence and purge only its owned run."""
import asyncio
from contextlib import asynccontextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

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

    def test_serena_controls_require_real_graph_difference_and_restore_config(self):
        for scenario in ('pass', 'missing_body', 'missing_signature'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                app = directory/'app'
                app.mkdir()
                config = app/'mago.toml'
                original = b'# exact original\r\nversion = "1"\r\n'
                config.write_bytes(original)
                data = {'run_id': 'lspext-ci-owned', 'app': str(app)}
                launches = []

                @asynccontextmanager
                async def connect(cwd, evidence, command):
                    enabled = 'enabled = true' in config.read_text()
                    launches.append((cwd, Path(evidence).name, command, config.read_text()))
                    references = []
                    if scenario != 'missing_signature':
                        references.append({'kind': 'signature', 'target': {'symbol': probe.MANAGER, 'member': ''}})
                    if enabled and scenario != 'missing_body':
                        references.append({'kind': 'body', 'target': {'symbol': probe.REGISTRY, 'member': ''}})
                    answer = {'source': {'symbol': probe.OWNER, 'member': '__construct'}, 'references': references}
                    async def code(cell):
                        if cell.startswith('s.info'):
                            return 'get_symbol_references is available'
                        if cell == 'import json':
                            return ''
                        self.assertIn('s.lsp.get_symbol_references', cell)
                        return json.dumps(answer)
                    yield SimpleNamespace(code=code)

                with patch.object(probe, 'connect', connect):
                    if scenario == 'pass':
                        result = asyncio.run(probe.run_serena(data, directory))
                        self.assertEqual(result['status'], 'pass')
                        self.assertTrue(result['controls']['on']['registry_body'])
                        self.assertFalse(result['controls']['off']['registry_body'])
                    else:
                        with self.assertRaises(AssertionError):
                            asyncio.run(probe.run_serena(data, directory))
                self.assertEqual(config.read_bytes(), original)
                record = json.loads((directory/'serena-result.json').read_text())
                self.assertEqual(record['status'], 'pass' if scenario == 'pass' else 'fail')
                self.assertEqual(launches[0][:3], ('/tmp', 'mcp-on', [str(ROOT/'bin/serena-mcp'), '--run', data['run_id']]))
                self.assertIn('workers = 1', launches[0][3])
                self.assertIn('POC_WIRING_OBSERVATION=/evidence/lsp-extensions/serena-observer.json', launches[0][3])
                if scenario == 'pass':
                    self.assertEqual(launches[1][1], 'mcp-off')
                    self.assertIn('enabled = false', launches[1][3])

    def test_host_result_includes_serena_and_honors_preparation_restore_selection(self):
        for restore in (True, False):
            with self.subTest(restore=restore), tempfile.TemporaryDirectory() as directory:
                data = {'run_id': 'lspext-ci-owned', 'evidence': directory}
                def native(*args, **kwargs):
                    path = Path(directory)/'lsp-extensions/result.json'
                    path.write_text(json.dumps({'status': 'pass', 'controls': {'native': 'pass'}}))
                    return SimpleNamespace(returncode=0, stdout=b'{}', stderr=b'')
                serena = {'status': 'pass', 'kind': 'deterministic_real_host_mcp'}
                with patch.object(probe, 'selected', return_value=data), \
                        patch.object(probe, 'fresh'), \
                        patch.object(probe, 'execute', side_effect=native), \
                        patch.object(probe, 'run_serena', new_callable=AsyncMock, return_value=serena) as forwarded, \
                        patch.object(probe, 'prepare_mate') as prepare_mate:
                    result = probe.run(data['run_id'], restore_preparation=restore)
                    self.assertEqual(result['serena'], serena)
                    forwarded.assert_awaited_once_with(data, Path(directory)/'lsp-extensions')
                    self.assertEqual(prepare_mate.call_count, int(restore))
                self.assertEqual(json.loads((Path(directory)/'lsp-extensions/host-result.json').read_text()), result)


if __name__ == '__main__':
    unittest.main()
