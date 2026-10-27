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


def call(data, argv):
    # Console accepts command abbreviations. Only exact metadata-independent
    # commands bypass preparation; an abbreviated data command must stay guarded.
    independent = {'help', 'list', 'init', 'discover', 'tools:list', 'tools:inspect',
                   'resources:list', 'resources:inspect', 'resources:templates:list'}
    independent |= {'--help', '-h', '--version', '-V'}
    # Do not infer a command through global options: their values can resemble
    # command names. Prefixing options therefore conservatively requires freshness.
    record = None if argv and argv[0] in independent else fresh(data)
    directory = Path(data['evidence'])/'mate/invocations'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    command = compose(data, 'exec', '-T', '-w', '/app', 'php', 'env', 'APP_ENV=dev', 'APP_DEBUG=1',
                      'php', 'vendor/bin/mate', *argv)
    started = time.monotonic()
    result = subprocess.run(command, env=environment(data), capture_output=True, timeout=180)
    (directory/'stdout').write_bytes(result.stdout)
    (directory/'stderr').write_bytes(result.stderr)
    write_json(directory/'invocation.json', {'run_id': data['run_id'], 'workspace': data['app'],
               'argv': command, 'environment': 'dev', 'exit': result.returncode,
               'elapsed_s': round(time.monotonic()-started, 6),
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
        assert literal in config.read_text() and "'inspection-dev' => '%mate.root_dir%/var/cache/dev'" in config.read_text(), 'Existing mate/config.php needs the declared invocation/context; it was preserved'
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
