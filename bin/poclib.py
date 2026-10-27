"""Host orchestration. Every subprocess receives an argument array, never a shell string."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent


def docker():
    executable = os.environ.get('POC_DOCKER') or shutil.which('docker')
    local = ROOT / '.cache/tools/docker/docker'
    if not executable and local.is_file():
        executable = str(local)
        os.environ.setdefault('DOCKER_CLI_PLUGIN_EXTRA_DIRS', str(ROOT / '.cache/tools/cli-plugins'))
    if not executable:
        raise RuntimeError('Docker CLI missing. Install Docker Engine/Desktop and the Compose v2 plugin.')
    return executable


def run(args, log=None, check=True, **kwargs):
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with Path(log).open('w') as output:
            return subprocess.run(args, stdout=output, stderr=subprocess.STDOUT, check=check, **kwargs)
    return subprocess.run(args, check=check, **kwargs)


def load(run_id='dev'):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', run_id):
        raise ValueError('Invalid run id')
    marker = ROOT / 'workspaces' / run_id / 'run.json'
    if not marker.is_file():
        raise RuntimeError(f'Unknown run {run_id!r}; run ./bin/poc up or ./bin/poc agent-task first')
    data = json.loads(marker.read_text())
    if data['repository'] != str(ROOT) or data['run_id'] != run_id:
        raise RuntimeError('Workspace ownership marker does not match this checkout')
    return data


def prepare(run_id, port=0):
    workspace = ROOT / 'workspaces' / run_id
    if workspace.exists():
        return load(run_id)
    workspace.mkdir(parents=True)
    shutil.copytree(ROOT / 'app', workspace / 'app', ignore=shutil.ignore_patterns('vendor', 'var', '.serena', '.env.local', '.phpunit.cache', 'semantic', 'mago.toml'))
    app = workspace / 'app'
    (app / '.serena').mkdir()
    shutil.copy2(ROOT / 'config/project.yml', app / '.serena/project.yml')
    shutil.copy2(ROOT / 'config/mago.toml', app / 'mago.toml')
    shutil.copytree(ROOT / 'fixtures/semantic', app / 'semantic')
    for directory in (workspace / 'state', ROOT / 'artifacts' / run_id):
        directory.mkdir(parents=True)
    digest = hashlib.sha256(str(ROOT).encode()).hexdigest()[:8]
    data = {'schema': 1, 'run_id': run_id, 'repository': str(ROOT),
            'project': f'mago-poc-{digest}-{run_id}', 'app': str(app),
            'state': str(workspace / 'state'), 'evidence': str(ROOT / 'artifacts' / run_id), 'port': port}
    (workspace / 'run.json').write_text(json.dumps(data, indent=2) + '\n')
    return data


def compose(data, *args):
    return [docker(), 'compose', '--project-directory', str(ROOT), '-f', str(ROOT / 'compose.yaml'), '-p', data['project'], *args]


def environment(data):
    return {**os.environ, 'POC_APP': data['app'], 'POC_STATE': data['state'],
            'POC_EVIDENCE_DIR': data['evidence'], 'POC_PORT': str(data['port']),
            'POC_UID': str(os.getuid()), 'POC_GID': str(os.getgid())}


def execute(data, *args, **kwargs):
    return run(compose(data, 'exec', '-T', '-w', '/app', 'php', *args), env=environment(data), **kwargs)


def require_running(data):
    status = subprocess.run(compose(data, 'ps', '--status', 'running', '-q', 'php'), env=environment(data), text=True, capture_output=True)
    if status.returncode or not status.stdout.strip():
        raise RuntimeError(f"Development container is stopped. Start it with ./bin/poc up --run {data['run_id']}")


def start(data, build=False):
    env = environment(data)
    if build:
        run(compose(data, 'build'), env=env, log=Path(data['evidence']) / 'build.log')
    run(compose(data, 'up', '-d', '--no-build'), env=env)
    execute(data, '/opt/poc/docker/setup', log=Path(data['evidence']) / 'setup.log')
    # Poll actual HTTP readiness with a deadline, never assume startup succeeded.
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = execute(data, 'php', '-r', "exit(@file_get_contents('http://127.0.0.1:8000/en/blog/') === false ? 1 : 0);", check=False, capture_output=True)
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise TimeoutError(f"Demo HTTP readiness failed; inspect {data['evidence']}/setup.log")


def stop(data, purge=False):
    run(compose(data, 'down', '--remove-orphans'), env=environment(data))
    if purge:
        # Only a validated, owned workspace may be removed. Evidence is retained.
        load(data['run_id'])
        shutil.rmtree(ROOT / 'workspaces' / data['run_id'])


def new_id(prefix):
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{uuid.uuid4().hex[:6]}"


def source_integrity():
    original = json.loads((ROOT / 'fixtures/upstream.sha256.json').read_text())
    adapted = json.loads((ROOT / 'fixtures/adaptations.json').read_text())
    actual_paths = {str(p.relative_to(ROOT/'app')) for p in (ROOT/'app').rglob('*') if p.is_file()}
    if actual_paths != set(original):
        raise AssertionError(f'Unexpected baseline file set: {actual_paths ^ set(original)}')
    for path, digest in original.items():
        expected = adapted.get(path, {}).get('sha256', digest)
        actual = hashlib.sha256((ROOT / 'app' / path).read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f'Application baseline changed unexpectedly: {path}')
    return len(original)


def metadata(data):
    paths = [ROOT / 'uv.lock', ROOT / 'app/composer.lock', *sorted((ROOT / 'adapter').rglob('*.py'))]
    return {'run': data, 'source_files_verified': source_integrity(),
            'revision': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'dirty': bool(subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True)),
            'file_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'toolchain': json.loads((ROOT / 'toolchain.lock.json').read_text())}
