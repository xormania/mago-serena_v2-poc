"""Inspect code loaded by the runtime interpreter, without environment/credentials."""
import hashlib
from importlib.metadata import version, distribution
import inspect
import json
from pathlib import Path
import subprocess

import serena_mago.server
import solidlsp.ls


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


root = Path('/opt/poc')
paths = [p for directory in ('adapter/src', 'tests', 'docker', 'config', 'fixtures')
         for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += [root/p for p in ('uv.lock', 'pyproject.toml', 'adapter/pyproject.toml', 'toolchain.lock.json')]
print(json.dumps({
    'schema': 1, 'run_id': __import__('os').environ.get('POC_RUN_ID'),
    'attempt_id': __import__('os').environ.get('POC_ATTEMPT_ID'),
    'installed_adapter': {'path': inspect.getfile(serena_mago.server), 'sha256': sha(inspect.getfile(serena_mago.server))},
    'installed_solidlsp': {'path': inspect.getfile(solidlsp.ls), 'sha256': sha(inspect.getfile(solidlsp.ls))},
    'serena_direct_url': json.loads(distribution('serena-agent').read_text('direct_url.json')),
    'live_mago_binary_sha256': sha('/usr/local/bin/mago'),
    'installed_files': {str(p.relative_to(root)): sha(p) for p in sorted(paths)},
    'distributions': {p: version(p) for p in ('serena-agent', 'serena-mago-adapter', 'mcp')},
    'runtime': json.loads(Path('/opt/toolchain-runtime.json').read_text()),
    'live_versions': {name: subprocess.check_output(command, text=True).splitlines()[0] for name, command in {
        'php': ['php','--version'], 'python': ['python','--version'], 'composer': ['composer','--version'],
        'uv': ['uv','--version'], 'mago': ['mago','--version']}.items()},
}, indent=2))
