#!/usr/bin/env python3
"""Real SDK worker: CLI positive control, baseline omission or candidate graph."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', default='mago')
    parser.add_argument('--autoload', default=os.environ.get('MAGO_REPRO_AUTOLOAD'))
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--helpers', type=Path, help='Directory containing lsp_client.py and trace.py')
    parser.add_argument('--candidate', action='store_true')
    args = parser.parse_args()
    if not args.autoload or not Path(args.autoload).is_file():
        parser.error('--autoload or MAGO_REPRO_AUTOLOAD must select the matched Composer SDK autoloader')
    here = Path(__file__).resolve().parent
    helper_paths = [*(parent/'tests/integration' for parent in here.parents), Path('/opt/poc/tests/integration')]
    helpers = args.helpers or next((p for p in helper_paths
                                    if (p/'lsp_client.py').is_file()), None)
    if helpers is None:
        parser.error('Pass --helpers with the repository stdlib LSP client directory')
    sys.path.insert(0, str(helpers.resolve()))
    from lsp_client import LspClient
    binary = shutil.which(args.binary)
    if binary is None:
        parser.error('Mago binary not found')
    out = args.evidence.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = {'schema': 1, 'mode': 'candidate' if args.candidate else 'baseline', 'status': 'running',
              'binary': binary, 'binary_sha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
              'version': subprocess.check_output([binary, '--version'], text=True).strip(),
              'autoload': str(Path(args.autoload).resolve()), 'scope': 'Explicit SDK test dependency; no Symfony claim'}
    saved_env = {key: os.environ.get(key) for key in ('MAGO_REPRO_STARTS', 'MAGO_REPRO_GRAPH')}
    try:
        with tempfile.TemporaryDirectory(prefix='mago-lsp-worker-repro-') as directory:
            root = Path(directory)
            (root/'src').mkdir()
            shutil.copy2(here/'Example.php', root/'src/Example.php')
            shutil.copy2(here/'worker.php', root/'worker.php')
            command = ['php', str(root/'worker.php'), str(Path(args.autoload).resolve())]
            config = ('version = "1"\nphp-version = "8.5"\nthreads = 1\n[source]\npaths = ["src"]\n'
                      '[extension-hosts.php]\nworkers = 1\nrequest-timeout-ms = 5000\nshutdown-timeout-ms = 1000\n'
                      'command = '+json.dumps(command)+'\n')
            (root/'mago.toml').write_text(config)
            (out/'configuration.toml').write_text(config)
            os.environ.update(MAGO_REPRO_STARTS=str(out/'cli-starts.txt'), MAGO_REPRO_GRAPH=str(out/'cli-graph.json'))
            cli = subprocess.run([binary, '--workspace', str(root), 'analyze', '--reporting-format', 'json'],
                                 cwd=root, capture_output=True, timeout=60)
            for name, content in (('cli.stdout.json', cli.stdout), ('cli.stderr', cli.stderr)):
                assert len(content) <= 1048576, 'Unexpectedly large CLI report'
                (out/name).write_bytes(content)
            assert cli.returncode in (0, 1), cli.stderr.decode()[-2000:]
            graph = json.loads((out/'cli-graph.json').read_text())
            assert any(edge == {'kind': 'Body', 'target': 'repro\\concrete'} for edge in graph), graph
            assert (out/'cli-starts.txt').is_file(), 'Real CLI worker did not start'
            result['cli'] = {'exit': cli.returncode, 'worker_started': True, 'body_edge': True}
            for stage in (('on', 'off') if args.candidate else ('on',)):
                starts, observed = out/(stage+'-starts.txt'), out/(stage+'-graph.json')
                os.environ.update(MAGO_REPRO_STARTS=str(starts), MAGO_REPRO_GRAPH=str(observed))
                (root/'mago.toml').write_text(config + ('enabled = false\n' if stage == 'off' else ''))
                client = LspClient([binary, '--workspace', str(root), 'language-server'], root, out/('lsp-'+stage))
                try:
                    init = client.initialize()
                    uri = (root/'src/Example.php').as_uri()
                    client.open('src/Example.php')
                    symbols = client.request('textDocument/documentSymbol', {'textDocument': {'uri': uri}}, timeout=20)
                    assert symbols, 'Native LSP control failed'
                    row = {'worker_started': starts.exists(), 'observer_ran': observed.exists(), 'native_symbols': True}
                    result['lsp_'+stage] = row
                    if args.candidate:
                        assert init['capabilities']['experimental']['symbolReferencesProvider'] is True
                        response = client.request('mago/symbolReferences', {'textDocument': {'uri': uri},
                            'symbol': 'Repro\\Service', 'member': '__construct'}, timeout=20)
                        row['response'] = response
                        edge = {'kind': 'body', 'target': {'symbol': 'repro\\concrete', 'member': ''}}
                        assert (edge in response['references']) == (stage == 'on'), response
                        assert row['worker_started'] == (stage == 'on'), row
                    else:
                        assert not row['worker_started'] and not row['observer_ran'], row
                finally:
                    client.close()
            result['status'] = 'pass'
    except Exception as exc:
        result.update(status='fail', error={'type': type(exc).__name__, 'message': str(exc)[-4000:]})
        raise
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
