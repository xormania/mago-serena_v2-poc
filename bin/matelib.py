"""Pinned Mate inspection and Symfony wiring preparation for one selected run."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import uuid

from poclib import ROOT, compose, environment, execute, load, metadata, require_running

sys.path.insert(0, str(ROOT/'tests/integration'))
from evidence import digest, write_json
from mate_contract import CONTEXT, application_state, metadata_hashes, validate_preparation


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected(run_id):
    data = load(run_id)
    workspace = ROOT/'workspaces'/run_id
    for key, expected in {'app': workspace/'app', 'state': workspace/'state',
                          'trusted': workspace/'trusted', 'evidence': ROOT/'artifacts'/run_id}.items():
        assert Path(data[key]) == expected and expected.is_dir() and not expected.is_symlink(), 'Invalid '+key+' workspace path'
    project = 'mago-poc-'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:8]+'-'+run_id
    assert data['project'] == project, 'Container project does not belong to this run'
    require_running(data)
    result = execute(data, 'python', '-c',
                     'import json,os; print(json.dumps({"run":os.environ.get("POC_RUN_ID"),"cwd":os.getcwd()}))',
                     capture_output=True, text=True)
    actual = json.loads(result.stdout)
    assert actual == {'run': run_id, 'cwd': '/app'}, 'Container workspace/run identity mismatch'
    return data


def invocation(data):
    return shlex.join([str(ROOT/'bin/mate'), '--run', data['run_id'], '--'])


def fresh(data):
    marker = Path(data['trusted'])/'mate-preparation.json'
    assert marker.is_file(), 'Metadata unprepared; run ./bin/poc mate-prepare --run '+data['run_id']
    record = json.loads(marker.read_text())
    validate_preparation(record, data, application_state(data['app']), metadata_hashes(data['app']))
    container = subprocess.check_output(compose(data, 'ps', '-q', 'php'), env=environment(data), text=True).strip()
    assert record['container_id'] == container, 'Container replaced; run mate-prepare explicitly'
    reference = Path(data['app'])/'.mago/container-reference.dev.json'
    assert reference.is_file() and not reference.is_symlink() and sha(reference) == record['wiring_reference_sha256'], 'Wiring reference absent/changed; run mate-prepare explicitly'
    return record


# Runtime observations and compiled framework facts have different lifetimes.
# These names are from the installed 0.15.0 schemas. No prefix match grants access.
RUNTIME_TOOLS = {
    'symfony-profiler-list': {'limit', 'method', 'url', 'ip', 'statusCode', 'context', 'from', 'to'},
    'symfony-profiler-get': {'token'},
    'monolog-search': {'term', 'regex', 'level', 'channel', 'environment', 'from', 'to', 'limit', 'kernelContext'},
    'monolog-context-search': {'key', 'value', 'level', 'environment', 'limit', 'kernelContext'},
    'monolog-tail': {'limit', 'level', 'environment', 'channel', 'kernelContext'},
    'monolog-list-files': {'environment', 'kernelContext'},
    'monolog-list-channels': {'kernelContext'},
    'server-info': set(),
}
GLOBAL_FLAGS = {'--silent', '--quiet', '--verbose', '--ansi', '--no-ansi', '--no-interaction',
                '-q', '-v', '-vv', '-vvv', '-n'}
INDEPENDENT = {'help', 'list', 'init', 'discover', 'tools:list', 'tools:inspect',
               'resources:list', 'resources:inspect', 'resources:templates:list',
               'debug:capabilities', 'debug:extensions', '--help', '-h', '--version', '-V'}
RUNTIME_MAX_FILES = 4096
RUNTIME_MAX_BYTES = 128 * 1024 * 1024


def command_policy(argv):
    """Only unambiguous exact commands can bypass compiled freshness.

    Console's abbreviations remain supported through its guarded normal path.
    Unknown leading global options conservatively require fresh metadata. Runtime
    calls accept the real long-option/JSON interface but reject ambiguous extra
    positional arguments and repeated options before dispatch.
    """
    index = 0
    while index < len(argv) and argv[index] in GLOBAL_FLAGS:
        index += 1
    if index == len(argv):
        return {'kind': 'compiled'}
    name = argv[index]
    if name in INDEPENDENT:
        return {'kind': 'discovery', 'command': name}
    if name == 'resources:read' and index + 1 < len(argv):
        import re
        match = re.fullmatch(r'symfony-profiler://profile/([0-9a-f]{6})(?:/([a-zA-Z0-9_.-]+))?', argv[index + 1])
        if match:
            for option in argv[index + 2:]:
                assert option in GLOBAL_FLAGS or option in ('--format=json', '--format=pretty', '--format=toon'), 'Profiler resources accept only an exact URI and --format=VALUE'
            return {'kind': 'runtime', 'command': name, 'uri': argv[index + 1],
                    'token': match[1], 'collector': match[2], 'parameters': {}}
    if name != 'tools:call' or index + 1 >= len(argv) or argv[index + 1] not in RUNTIME_TOOLS:
        return {'kind': 'compiled', 'command': name}
    tool = argv[index + 1]
    params, bag = {}, {}
    tokens = argv[index + 2:]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        i += 1
        if token in GLOBAL_FLAGS:
            continue
        assert token.startswith('--') and token != '--', 'Runtime tools require TOOL followed by long options; inspect the installed schema'
        key, equal, value = token[2:].partition('=')
        if not equal:
            if i < len(tokens) and (not tokens[i].startswith('-') or tokens[i][:2] == '-1'):
                value = tokens[i]
                i += 1
            else:
                value = True
        assert key not in params, 'Repeated runtime option: '+key
        params[key] = value
    if 'json' in params:
        raw_json = params.pop('json')
        assert isinstance(raw_json, str), 'Runtime --json requires a JSON object value'
        bag = json.loads(raw_json)
        assert isinstance(bag, dict), 'Runtime --json must be an object'
    if 'format' in params:
        assert params.pop('format') in ('json', 'pretty', 'toon'), 'Unsupported Mate output format'
    params = {**bag, **params}
    assert set(params) <= RUNTIME_TOOLS[tool], 'Unknown runtime tool parameter; inspect '+tool
    if 'limit' in RUNTIME_TOOLS[tool]:
        limit = params.get('limit', 20 if tool == 'symfony-profiler-list' else 100)
        assert not isinstance(limit, bool) and str(limit).isdigit() and 1 <= int(limit) <= 100, 'Runtime limit must be between 1 and 100'
    if tool == 'symfony-profiler-list':
        assert params.get('context') == CONTEXT, 'Profiler list requires --context='+CONTEXT
    if tool.startswith('monolog-'):
        assert params.get('kernelContext') == CONTEXT, 'Log inspection requires --kernelContext='+CONTEXT
        if 'environment' in RUNTIME_TOOLS[tool]:
            assert params.get('environment') == 'dev', 'Log inspection requires --environment=dev'
    if tool == 'symfony-profiler-get':
        import re
        assert isinstance(params.get('token'), str) and re.fullmatch(r'[0-9a-f]{6}', params['token']), 'Expected an exact six-character profiler token'
    return {'kind': 'runtime', 'command': name, 'tool': tool, 'parameters': params,
            'token': params.get('token')}


def runtime_files(data, names, *, missing_ok=False):
    """Scope reads and refresh archives to regular selected-dev files, with bounds."""
    app = Path(data['app'])
    found, size = [], 0
    for name in names:
        target = app/name
        for parent in [target, *target.parents]:
            assert not parent.is_symlink(), 'Runtime path must not be a symlink: '+str(parent)
            if parent == app:
                break
        if not target.exists():
            assert missing_ok, 'Runtime data directory missing: '+name+'; no application warmup was attempted'
            continue
        assert target.is_dir(), 'Runtime data path is not a directory: '+name
        for path in target.rglob('*'):
            assert not path.is_symlink(), 'Runtime evidence contains a symlink: '+str(path)
            if path.is_dir():
                continue
            assert path.is_file(), 'Runtime evidence must contain regular files'
            found.append(path)
            size += path.stat().st_size
            assert len(found) <= RUNTIME_MAX_FILES and size <= RUNTIME_MAX_BYTES, 'Runtime evidence exceeds bounded read/archive budget (4096 files / 128 MiB); retain and rotate it explicitly'
    return found


def runtime_identity(data, policy):
    """Validate runtime configuration and ownership, never boot the application."""
    marker = Path(data['trusted'])/'mate-runtime.json'
    assert marker.is_file() and not marker.is_symlink(), 'Runtime inspection unconfigured; run mate-prepare once in a healthy workspace'
    record = json.loads(marker.read_text())
    assert record.get('run_id') == data['run_id'] and record.get('workspace') == data['app'], 'Runtime configuration belongs to another workspace'
    assert record.get('environment') == 'dev' and record.get('context') == CONTEXT, 'Wrong runtime environment/context'
    config = Path(data['app'])/'mate/config.php'
    assert config.is_file() and not config.is_symlink() and sha(config) == record.get('config_sha256'), 'Runtime directory configuration changed; reconcile it explicitly'
    container = subprocess.check_output(compose(data, 'ps', '-q', 'php'), env=environment(data), text=True).strip()
    assert record.get('container_id') == container, 'Runtime container replaced; configure the selected run explicitly'
    tool = policy.get('tool', '')
    paths = [] if tool == 'server-info' else ['var/log'] if tool.startswith('monolog-') else ['var/cache/dev/profiler']
    runtime_files(data, paths)
    # Index rows supply request/time provenance even for a collector-only response.
    observations = []
    if policy.get('token'):
        import csv
        index = Path(data['app'])/'var/cache/dev/profiler/index.csv'
        if index.is_file():
            with index.open(newline='') as stream:
                for row in csv.reader(stream):
                    if len(row) >= 7 and row[0] == policy['token']:
                        observations.append({'token': row[0], 'method': row[2], 'url': row[3],
                                             'request_time_unix': int(row[4]), 'status_code': row[6]})
    return {**record, 'observations': observations, 'read_paths': paths}


def preserve_runtime(data, evidence):
    """Explicit refresh may delete profiles: archive them before cache:clear."""
    files = runtime_files(data, ['var/cache/dev/profiler', 'var/log'], missing_ok=True)
    destination = Path(evidence)/'runtime-before-refresh'
    manifest = {}
    for path in files:
        name = str(path.relative_to(data['app']))
        target = destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        manifest[name] = {'sha256': sha(target), 'bytes': target.stat().st_size}
    write_json(Path(evidence)/'runtime-before-refresh.json', {'run_id': data['run_id'],
               'workspace': data['app'], 'environment': 'dev', 'context': CONTEXT,
               'historical': True, 'files': manifest})
    return manifest


def call(data, argv):
    policy = command_policy(argv)
    runtime = runtime_identity(data, policy) if policy['kind'] == 'runtime' else None
    record = fresh(data) if policy['kind'] == 'compiled' else None
    directory = Path(data['evidence'])/'mate/invocations'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    command = compose(data, 'exec', '-T', '-w', '/app', 'php', 'env', 'APP_ENV=dev', 'APP_DEBUG=1',
                      'php', 'vendor/bin/mate', *argv)
    started = time.monotonic()
    result = subprocess.run(command, env=environment(data), capture_output=True, timeout=180)
    (directory/'stdout').write_bytes(result.stdout)
    (directory/'stderr').write_bytes(result.stderr)
    write_json(directory/'invocation.json', {'run_id': data['run_id'], 'workspace': data['app'],
               'argv': command, 'environment': 'dev', 'context': CONTEXT, 'exit': result.returncode,
               'elapsed_s': round(time.monotonic()-started, 6), 'policy': policy,
               'observed_at_unix': time.time(),
               'runtime': {'historical': policy.get('tool') != 'server-info',
                           'scope': 'mate_cli_process' if policy.get('tool') == 'server-info' else 'recorded_application_observation',
                           'current_application_state': False,
                           'observations': runtime['observations'], 'read_paths': runtime['read_paths'],
                           'container_id': runtime['container_id']} if runtime else None,
               'preparation_id': record['preparation_id'] if record else None,
               'application_sha256': record['application_sha256'] if record else None})
    return result


def invoke(data, argv):
    result = call(data, argv)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


def compiled_reference(data, evidence):
    # Raw Console views can contain scalar configuration. Keep them private in
    # disposable state; retain hashes, exact argv and only the sanitized export.
    evidence = Path(evidence)
    views = {}
    for name, extra in (('types', ['--types']), ('services', [])):
        argv = ['env', 'APP_ENV=dev', 'APP_DEBUG=1', 'php', 'bin/console', 'debug:container',
                '--env=dev', '--format=json', '--no-interaction', *extra]
        response = execute(data, *argv, capture_output=True, check=False)
        (evidence/(name+'.stderr')).write_bytes(response.stderr)
        assert response.returncode == 0, 'Compiled container export failed: '+name
        path = Path(data['state'])/('wiring-'+name+'.json')
        path.write_bytes(response.stdout)
        path.chmod(0o600)
        views[name] = {'argv': argv, 'exit': response.returncode, 'sha256': sha(path)}
    argv = ['php', 'vendor/byte-kitsune/mago-symfony-wiring/bin/create-container-reference.php',
            '--types=/state/wiring-types.json', '--services=/state/wiring-services.json',
            '--autoload=/app/vendor/autoload.php']
    response = execute(data, *argv, capture_output=True, check=False)
    (evidence/'reference.stderr').write_bytes(response.stderr)
    write_json(evidence/'export-invocations.json', {'views': views, 'exporter': {'argv': argv, 'exit': response.returncode}})
    assert response.returncode == 0, 'Compiled wiring sanitization failed; see reference.stderr'
    value = json.loads(response.stdout)
    assert value['environment'] == 'dev' and value['scope'] == 'compiled_container_autowiring'
    assert value['definitions'], 'Empty compiled service set'
    target = Path(data['app'])/'.mago/container-reference.dev.json'
    target.write_bytes(response.stdout)
    (evidence/'container-reference.dev.json').write_bytes(response.stdout)
    return target


def prepare_mate(data):
    data = selected(data['run_id'])
    app = Path(data['app'])
    overlay = ROOT/'fixtures/mate'
    declaration = json.loads((overlay/'overlay.json').read_text())
    assert declaration['base_lock_sha256'] == sha(ROOT/'app/composer.lock')
    for name, expected in declaration['files'].items():
        assert sha(overlay/name) == expected, f'Overlay changed: {name}'
    for name in ('composer.json', 'composer.lock'):
        assert sha(app/name) in (sha(ROOT/'app'/name), sha(overlay/name)), f'Refusing to replace edited {name}'
    attempt = 'prepare-'+uuid.uuid4().hex
    evidence = Path(data['evidence'])/'mate'/attempt
    evidence.mkdir(parents=True)
    marker = Path(data['trusted'])/'mate-preparation.json'
    marker.unlink(missing_ok=True)
    write_json(evidence/'source.json', metadata(data))
    for name in ('composer.json', 'composer.lock'):
        shutil.copy2(overlay/name, app/name)
    execute(data, 'composer', 'install', '--no-plugins', '--no-scripts', '--no-interaction', '--no-progress',
            log=evidence/'composer-install.log')
    config = app/'mate/config.php'
    config.parent.mkdir(exist_ok=True)
    literal = "'"+invocation(data).replace('\\', '\\\\').replace("'", "\\'")+"'"
    content = (overlay/'config.php.in').read_text().replace('__POC_INVOCATION__', literal)
    if not config.exists():
        config.write_text(content)
    else:
        assert config.read_text() == content, 'Existing mate/config.php needs the declared invocation/context; it was preserved'
    instructions = (overlay/'runtime-instructions.md.in').read_text().replace('__POC_INVOCATION__', invocation(data))
    owner = app/'AGENTS.md'
    existing = owner.read_text() if owner.exists() else ''
    begin, end = '<!-- POC RUNTIME BEGIN -->', '<!-- POC RUNTIME END -->'
    if begin in existing:
        before, rest = existing.split(begin, 1)
        assert end in rest, 'Incomplete owner runtime instruction block preserved'
        _, after = rest.split(end, 1)
        existing = before.rstrip()+'\n'+after.lstrip()
    owner.write_text(existing.rstrip()+'\n\n'+begin+'\n'+instructions+'\n'+end+'\n')
    preserve_runtime(data, evidence)
    container = subprocess.check_output(compose(data, 'ps', '-q', 'php'), env=environment(data), text=True).strip()
    write_json(Path(data['trusted'])/'mate-runtime.json', {'run_id': data['run_id'], 'workspace': data['app'],
               'environment': 'dev', 'context': CONTEXT, 'container_id': container, 'config_sha256': sha(config)})
    for name, argv in (
        ('init', ('php', 'vendor/bin/mate', 'init', '--no-interaction')),
        ('autoload', ('composer', 'dump-autoload', '--no-plugins', '--no-scripts', '--no-interaction')),
        ('discover', ('php', 'vendor/bin/mate', 'discover', '--no-interaction')),
        ('metadata', ('env', 'APP_ENV=dev', 'APP_DEBUG=1', 'php', 'bin/console', 'cache:clear', '--env=dev', '--no-interaction')),
    ):
        execute(data, *argv, log=evidence/(name+'.log'))
    assert sha(app/'composer.json') == sha(overlay/'composer.json'), 'Init unexpectedly changed the declared manifest'
    mago = app/'.mago'
    mago.mkdir(exist_ok=True)
    for name in ('extensions.php', 'wiring.toml'):
        source = ROOT/'fixtures/mago'/name
        destination = mago/name
        if destination.exists():
            assert destination.read_bytes() == source.read_bytes(), 'Existing .mago/'+name+' preserved; reconcile it explicitly'
        else:
            shutil.copy2(source, destination)
    # The prepared application seals both native and enriched configurations.
    # A later read must never create a config and invalidate its own preparation.
    from magolib import prepare_mago
    prepare_mago(data)
    reference = compiled_reference(data, evidence)
    state = application_state(app)
    xml = metadata_hashes(app)
    container = subprocess.check_output(compose(data, 'ps', '-q', 'php'), env=environment(data), text=True).strip()
    image = json.loads(subprocess.check_output(['docker', 'inspect', '--format', '{{json .Image}}', container], text=True))
    versions = execute(data, 'composer', 'show', '--format=json', capture_output=True, text=True).stdout
    (evidence/'installed-packages.json').write_text(versions)
    execute(data, 'php', '--version', log=evidence/'php-version.txt')
    execute(data, 'composer', '--version', log=evidence/'composer-version.txt')
    write_json(evidence/'application-state.json', state)
    record = {'schema': 1, 'run_id': data['run_id'], 'workspace': data['app'], 'environment': 'dev',
              'context': CONTEXT, 'preparation_id': attempt, 'preparation_exit': 0,
              'application_sha256': digest(state), 'metadata': xml, 'container_id': container, 'image_id': image,
              'wiring_reference_sha256': sha(reference),
              'overlay': declaration, 'invocation': invocation(data), 'evidence': str(evidence)}
    write_json(evidence/'preparation.json', record)
    write_json(marker, record)
    return record


def run_checks(data):
    from framework_checks import run
    return run(selected(data['run_id']))
