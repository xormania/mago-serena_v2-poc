"""Compose the one-service proof without confusing partial results with a pass."""
import hashlib
import json
from pathlib import Path
import shutil
import time
import traceback
import uuid

from poclib import ROOT, execute, load, metadata, new_id, prepare, source_integrity, start, stop


REQUIRED = ('fixture_integrity', 'executed_identity', 'mago_configuration',
            'framework_preparation', 'mago_php', 'service_semantics',
            'symfony_wiring', 'behavior', 'cleanup')


def run_slice(run_id=None, *, keep_running=False, capture_identity):
    from evidence import digest, write_json
    from magolib import prepare_mago, run_checks as check_php
    from matelib import prepare_mate, run_checks as check_framework
    from service_semantics import run_semantics
    from verifier import expected_suite, snapshot, verify_suite

    data = prepare(run_id or new_id('slice1'))
    directory = Path(data['evidence'])/'slice1'/('attempt-'+uuid.uuid4().hex)
    directory.mkdir(parents=True)
    source = metadata(data)
    context = {'run_id': data['run_id'], 'workspace': data['app'],
               'source_context_sha256': digest(source),
               'service': r'App\Form\Type\TagsInputType'}
    checks = {name: {**context, 'name': name, 'status': 'not_exercised'} for name in REQUIRED}
    write_json(directory/'source.json', source)

    def save():
        complete = all(row['status'] == 'pass' for row in checks.values())
        result = {**context, 'schema': 1, 'kind': 'mago_first_slice1',
                  'status': 'pass' if complete else 'incomplete',
                  'inventory': list(REQUIRED), 'checks': list(checks.values()),
                  'evidence': str(directory),
                  'interpretation': 'Calibrated capability checks; original whole-app findings remain findings. '
                                    'A passing CLI bridge does not assert LSP propagation.'}
        write_json(directory/'results.json', result)
        write_json(Path(data['evidence'])/'slice1-result.json', result)
        return result

    def record(name, function, dependencies=()):
        missing = [dep for dep in dependencies if checks[dep]['status'] != 'pass']
        if missing:
            checks[name].update(status='blocked', reason='Prerequisites failed: '+', '.join(missing))
            save()
            return
        started = time.monotonic()
        try:
            detail = function()
            status = detail.get('status', 'pass') if isinstance(detail, dict) else 'pass'
            assert status in ('pass', 'fail', 'blocked'), f'Invalid result status: {status}'
            checks[name].update(status=status, detail=detail)
        except Exception as exc:
            checks[name].update(status='fail', reason=str(exc))
            (directory/(name+'-error.txt')).write_text(traceback.format_exc())
        checks[name]['elapsed_s'] = round(time.monotonic()-started, 3)
        save()
        print(f"{checks[name]['status']}: {name}", flush=True)

    save()
    record('fixture_integrity', source_integrity)
    try:
        identity = {}
        start(data, validate_image=lambda item: identity.update(capture_identity(item, source)))
        for name in ('executed-identity.json', 'executed-identity.stderr', 'image-identity.json'):
            shutil.copy2(Path(data['evidence'])/name, directory/name)
        record('executed_identity', lambda: identity)
        # Serena expands its project configuration on first activation. Do that
        # before sealing framework metadata and the complete application snapshot.
        execute(data, 'python', '/opt/poc/tests/integration/prime_project.py',
                log=directory/'prime-project.log')
        record('mago_configuration', lambda: prepare_mago(data), ('executed_identity',))
        record('framework_preparation', lambda: prepare_mate(data), ('mago_configuration',))
        before = snapshot(data['app'])
        write_json(directory/'prepared-application.json', before)
        # Both tool families see one dependency overlay. Disposable source variants
        # restore exact bytes before subsequent metadata and semantic observations.
        record('mago_php', lambda: check_php(data), ('mago_configuration',))
        record('service_semantics', lambda: run_semantics(data), ('mago_configuration',))
        record('symfony_wiring', lambda: check_framework(data), ('framework_preparation',))

        def behavior():
            assert snapshot(data['app']) == before, 'A capability control left application/dependency changes'
            target = '/evidence/'+directory.relative_to(Path(data['evidence'])).as_posix()
            execute(data, 'php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml',
                    '--list-tests-xml', target+'/expected-tests.xml',
                    log=directory/'list-tests.log')
            inventory = expected_suite(directory/'expected-tests.xml', ROOT/'app')
            for name, expected in inventory['source_sha256'].items():
                assert hashlib.sha256((Path(data['app'])/name).read_bytes()).hexdigest() == expected, \
                    'Original behavioral test/configuration changed: '+name
            write_json(directory/'expected-suite.json', inventory)
            execute(data, 'env', 'APP_ENV=test', 'APP_DEBUG=1', 'php', 'vendor/bin/phpunit',
                    '--configuration', 'phpunit.dist.xml', '--log-junit', target+'/phpunit.xml',
                    log=directory/'phpunit.log')
            result = verify_suite(inventory, directory/'phpunit.xml')
            execute(data, '/opt/poc/docker/check', log=directory/'application-checks.log')
            assert snapshot(data['app']) == before, 'Behavior/runtime checks left application/dependency changes'
            source_integrity()
            return result

        record('behavior', behavior, ('executed_identity',))
    except Exception as exc:
        (directory/'startup-error.txt').write_text(traceback.format_exc())
        for row in checks.values():
            if row['status'] == 'not_exercised':
                row.update(status='blocked', reason='Startup failed: '+str(exc))
    finally:
        if keep_running:
            checks['cleanup'].update(status='pass', detail='Selected workspace intentionally retained running')
        else:
            record('cleanup', lambda: stop(load(data['run_id'])))
        result = save()
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'pass' else 1
