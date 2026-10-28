"""Replay and independently verify one real failed Symfony request and repair."""
import asyncio
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import traceback
import uuid

from poclib import ROOT, execute, load, metadata, new_id, prepare, source_integrity, start, stop

REQUIRED = ('fixture_integrity', 'executed_identity', 'prepared_baseline', 'healthy_request',
            'defective_request', 'runtime_diagnosis', 'boot_failure_control', 'semantic_repair',
            'native_mago', 'enriched_framework', 'repaired_request', 'behavior', 'task_integrity', 'cleanup')


def run_slice(run_id=None, *, keep_running=False, capture_identity):
    from evidence import digest, write_json
    from magolib import prepare_mago, run_native
    from mago_contract import issues, source_inventory
    from matelib import fresh, prepare_mate
    from mate_contract import payload
    from mcp_client import connect
    from slice3_contract import (CONTROLLER, TEST, SYMBOL, REPOSITORY, compare_native, response_record,
                                 sha, task_inputs, validate_agent_evidence, verify_runtime_result, verify_suites, verify_task_delta)
    from verifier import expected_suite, snapshot, verify_suite

    data = prepare(run_id or new_id('s3-replay'))
    directory = Path(data['evidence'])/'slice3'/('attempt-'+uuid.uuid4().hex)
    directory.mkdir(parents=True)
    source = metadata(data)
    app = Path(data['app'])
    task = task_inputs(ROOT)
    context = {'run_id': data['run_id'], 'workspace': data['app'], 'attempt_id': directory.name,
               'source_context_sha256': digest(source), 'request': task['request']}
    checks = {name: {**context, 'name': name, 'status': 'not_exercised'} for name in REQUIRED}
    write_json(directory/'source.json', source)
    write_json(directory/'task.json', task)
    state = {'observations': {}}

    def save():
        result = {**context, 'schema': 1, 'kind': 'mago_first_slice3',
                  'status': 'pass' if all(row['status'] == 'pass' for row in checks.values()) else 'incomplete',
                  'inventory': list(REQUIRED), 'checks': list(checks.values()), 'evidence': str(directory),
                  'execution_kind': 'Deterministic fault injection and semantic repair replay; separately retained adaptive exercise.',
                  'actual_agent_evidence': str(ROOT/'docs/evidence/slice3/fresh-agent/index.json'),
                  'interpretation': 'Historical profiler/log observations retain exact request provenance. Native findings remain findings; CLI wiring does not establish LSP worker integration.'}
        write_json(directory/'results.json', result)
        write_json(Path(data['evidence'])/'slice3-result.json', result)
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
            assert status in ('pass', 'fail', 'blocked'), 'Invalid stage status'
            checks[name].update(status=status, detail=detail)
            if isinstance(detail, dict) and detail.get('reason'):
                checks[name]['reason'] = detail['reason']
        except Exception as exc:
            checks[name].update(status='fail', reason=str(exc))
            (directory/(name+'-error.txt')).write_text(traceback.format_exc())
        checks[name]['elapsed_s'] = round(time.monotonic()-started, 3)
        save()
        print(checks[name]['status']+': '+name, flush=True)

    def retained(name, argv, exits=(0,), *, host=False):
        if host:
            response = subprocess.run(argv, cwd='/tmp', capture_output=True, timeout=240)
        else:
            response = execute(data, *argv, capture_output=True, check=False)
        (directory/(name+'.stdout')).write_bytes(response.stdout)
        (directory/(name+'.stderr')).write_bytes(response.stderr)
        write_json(directory/(name+'.invocation.json'), {**context, 'argv': argv, 'exit': response.returncode,
                   'cwd': '/tmp' if host else '/app'})
        assert response.returncode in exits, name+': exit '+str(response.returncode)+'; see '+str(directory/(name+'.stderr'))
        return response

    def mate(name, argv, exits=(0,)):
        return retained(name, [str(ROOT/'bin/mate'), '--run', data['run_id'], '--', *argv], exits, host=True)

    def evidence_path(name):
        return '/evidence/'+str((directory/name).relative_to(Path(data['evidence'])))

    def native(name, argv, exits=(0, 1)):
        row = run_native(data, argv, directory=directory/name)
        assert row['exit'] in exits, name+': native tool failure '+str(row['exit'])
        return row

    def request(name, expected, *, profiled=True):
        # PHP/Symfony may retain a just-changed source timestamp briefly. Keep
        # every real response, then select only an observed expected response.
        attempts = []
        for number in range(1, 21):
            prefix = name+'-attempt-'+str(number)
            marker = 's3-'+name+'-'+uuid.uuid4().hex[:16]
            url = 'http://127.0.0.1:8000'+task['request']+'&s3_request='+marker
            log = app/'var/log/dev.log'
            previous = log.stat().st_size if log.is_file() else 0
            response = retained(prefix+'-http', ['curl', '--silent', '--show-error', '--max-time', '45',
                               '--max-filesize', '4000000', '--dump-header', evidence_path(prefix+'-headers.txt'),
                               '--output', evidence_path(prefix+'-body.html'), '--write-out', '%{http_code}', url])
            status = int(response.stdout)
            headers = (directory/(prefix+'-headers.txt')).read_text()
            attempts.append({'attempt': number, 'status': status, 'marker': marker, 'url': url,
                             'headers': prefix+'-headers.txt', 'body': prefix+'-body.html'})
            write_json(directory/(name+'-http-attempts.json'), attempts)
            if status != expected:
                time.sleep(1)
                continue
            if profiled:
                observation = response_record(headers, status=status, marker=marker, url=url)
            else:
                tokens = re.findall(r'^X-Debug-Token:\s*(\S+)', headers, re.M | re.I)
                observation = {'status': status, 'token': tokens[0] if len(tokens) == 1 else None,
                               'marker': marker, 'url': url, 'profile_created': len(tokens) == 1,
                               'interpretation': 'No profiler record is required when container compilation fails before profiling.'}
            observation['observed_unix'] = time.time()
            observation['body_sha256'] = sha(directory/(prefix+'-body.html'))
            observation['response_attempt'] = number
            for suffix in ('-headers.txt', '-body.html'):
                shutil.copy2(directory/(prefix+suffix), directory/(name+suffix))
            if log.is_file():
                with log.open('rb') as stream:
                    stream.seek(previous)
                    delta = stream.read(200001)
                assert len(delta) <= 200000, 'Request log append exceeds retention bound'
                (directory/(name+'-log-window.txt')).write_bytes(delta)
                observation['log_window'] = {'path': str(directory/(name+'-log-window.txt')), 'start': previous,
                                              'end': previous+len(delta), 'sha256': sha(directory/(name+'-log-window.txt'))}
            state['observations'][name] = observation
            write_json(directory/(name+'-observation.json'), observation)
            return observation
        raise AssertionError(name+': no HTTP '+str(expected)+' within 20 retained attempts')

    def profile(name, observation):
        token = observation['token']
        response = mate(name+'-profile', ['tools:call', 'symfony-profiler-get', '--token='+token, '--format=json'])
        value = payload(response.stdout)
        assert value['token'] == token and observation['marker'] in value['url'], 'Profile is not the requested HTTP observation'
        assert value['status_code'] == observation['status'] and value['context'] == 'inspection-dev', 'Wrong profile status/context'
        assert value.get('time') and value.get('time_formatted'), 'Profile timestamp missing'
        return value

    def archive(name, observation):
        target = directory/'preserved-runtime'/name
        target.mkdir(parents=True)
        token = observation['token']
        paths = list((app/'var/cache/dev/profiler').glob('*/*/'+token))
        assert len(paths) == 1 and paths[0].is_file() and not paths[0].is_symlink(), 'Profile storage does not match observed token'
        assert paths[0].stat().st_size <= 2_000_000, 'Profile archive exceeds bound'
        shutil.copy2(paths[0], target/('profile-'+token))
        for suffix in ('-headers.txt', '-observation.json', '-log-window.txt'):
            path = directory/(name+suffix)
            if path.is_file():
                shutil.copy2(path, target/path.name)
        write_json(target/'manifest.json', {p.name: {'size': p.stat().st_size, 'sha256': sha(p)} for p in target.iterdir()})
        return str(target)

    def baseline():
        assert not (app/TEST).exists(), 'Slice 3 requires a fresh regression workspace'
        assert sha(app/CONTROLLER) == task['final_controller_sha256'], 'Controller is not pristine before fault injection'
        execute(data, 'python', '/opt/poc/tests/integration/prime_project.py', log=directory/'prime-project.log')
        state['native_tool'] = prepare_mago(data)
        state['preparation_before'] = prepare_mate(data)
        state['baseline'] = snapshot(app)
        write_json(directory/'baseline-application.json', state['baseline'])
        write_json(directory/'baseline-source-inventory.json', source_inventory(app))
        retained('original-list', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml',
                                 '--list-tests-xml', evidence_path('original-list.xml')])
        state['original'] = expected_suite(directory/'original-list.xml', ROOT/'app')
        write_json(directory/'original-suite.json', state['original'])
        retained('original-before', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml',
                                    '--log-junit', evidence_path('original-before.xml')])
        original = verify_suite(state['original'], directory/'original-before.xml')
        state['before_analysis'] = issues(native('before-analyze', ['analyze', '--reporting-format', 'json']))
        state['before_lint'] = issues(native('before-lint', ['lint', '--reporting-format', 'json']))
        state['controller'] = (app/CONTROLLER).read_bytes()
        schemas = mate('mate-tools', ['tools:list', '--format=json'])
        names = json.loads(schemas.stdout)['tools']
        assert {'symfony-profiler-list', 'symfony-profiler-get', 'symfony-service-detail', 'monolog-search'} <= names.keys(), 'Runtime tools were not discovered'
        mate('mate-capabilities', ['debug:capabilities', '--format=json'])
        return {'status': 'pass', 'original': original, 'tool': state['native_tool'],
                'analyzer_findings': len(state['before_analysis']), 'lint_findings': len(state['before_lint']),
                'dependency_lock_sha256': sha(app/'composer.lock')}

    def healthy():
        row = request('healthy', 200)
        value = profile('healthy', row)
        assert b'<article class="post">' in (directory/'healthy-body.html').read_bytes(), 'Healthy filter has no real posts'
        return {'status': 'pass', 'observation': row, 'profile_time': value['time'], 'preserved': archive('healthy', row)}

    def defect():
        shutil.copy2(ROOT/'fixtures/slice3'/task['files'][TEST]['asset'], app/TEST)
        (app/TEST).chmod(0o644)
        before, after = task['defect']['before'].encode(), task['defect']['after'].encode()
        assert state['controller'].count(before) == 1, 'Fault target is not unique'
        (app/CONTROLLER).write_bytes(state['controller'].replace(before, after))
        (directory/'defective-BlogController.php').write_bytes((app/CONTROLLER).read_bytes())
        row = request('defective', 500)
        response = retained('defective-regression', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml', TEST,
                            '--log-junit', evidence_path('defective-regression.xml')], exits=(1,))
        assert b'500' in response.stdout and b'Unrecognized field' in response.stdout, 'Regression failed for an unrelated cause'
        rejected = mate('stale-compiled-service', ['--no-interaction', 'tools:ca', 'symfony-service-detail',
                        '--id='+REPOSITORY, '--context=inspection-dev', '--format=json'], exits=(3,))
        assert b'mate-prepare' in rejected.stderr and not rejected.stdout, 'Compiled inspection bypassed freshness'
        return {'status': 'pass', 'observation': row, 'regression_exit': response.returncode,
                'fault': task['defect'], 'compiled_service_stale_rejected': True}

    def diagnose():
        row = state['observations']['defective']
        value = profile('defective', row)
        listing = payload(mate('defective-profiles', ['--no-interaction', 'tools:call', 'symfony-profiler-list',
                          '--limit=20', '--url='+row['marker'], '--statusCode=500', '--context=inspection-dev', '--format=json']).stdout)
        assert any(p['token'] == row['token'] and row['marker'] in p['url'] for p in listing['profiles']), 'List omitted exact failing request'
        assert any(p['name'] == 'exception' for p in value['collectors']), 'Exception collector unavailable'
        collector = mate('defective-exception', ['resources:read', 'symfony-profiler://profile/'+row['token']+'/exception', '--format=json'])
        assert b'Unrecognized field' in collector.stdout and b'label' in collector.stdout and b'BlogController' in collector.stdout, 'Profiler exception does not locate defect'
        sql = mate('defective-doctrine', ['resources:read', 'symfony-profiler://profile/'+row['token']+'/db', '--format=json'])
        sql_data = json.loads(sql.stdout)
        assert isinstance(sql_data, list) and len(sql_data) == 1 and sql_data[0]['text']['untrusted_data']['name'] == 'db', 'SQL collector returned an error instead of data'
        marker_logs = payload(mate('defective-marker-logs', ['tools:call', 'monolog-search', '--term='+row['marker'],
                              '--environment=dev', '--kernelContext=inspection-dev', '--limit=20', '--format=json']).stdout)
        failure_logs = payload(mate('defective-exception-logs', ['tools:call', 'monolog-search', '--term=Unrecognized field',
                               '--environment=dev', '--kernelContext=inspection-dev', '--limit=20', '--format=json']).stdout)
        assert marker_logs['entries'] and failure_logs['entries'], 'Structured logs do not include route marker and failure'
        window = (directory/'defective-log-window.txt').read_text()
        assert row['marker'] in window and 'Unrecognized field' in window and 'label' in window, 'Appended log window does not correlate request and exception'
        preserved = archive('defective', row)
        # Deliberately exercise missing historical data and a foreign context.
        missing = mate('missing-profile', ['tools:call', 'symfony-profiler-get', '--token=000000', '--format=json'], exits=(1,))
        assert b'not found' in missing.stdout.lower()+missing.stderr.lower(), 'Missing profile error unclear'
        mate('wrong-runtime-context', ['tools:call', 'symfony-profiler-list', '--context=foreign', '--limit=1', '--format=json'], exits=(1, 3))
        retained('unknown-runtime-run', [str(ROOT/'bin/mate'), '--run', 's3-missing-'+uuid.uuid4().hex[:12], '--',
                 'tools:call', 'symfony-profiler-list', '--limit=1', '--format=json'], exits=(3,), host=True)
        return {'status': 'pass', 'profile_token': row['token'], 'profile_time': value['time'],
                'request_marker': row['marker'], 'exception_collector': True, 'sql_collector_read': sql.returncode == 0,
                'structured_marker_records': len(marker_logs['entries']), 'structured_exception_records': len(failure_logs['entries']),
                'preserved_before_any_refresh': preserved}

    def boot_failure():
        config = app/'config/services.yaml'
        content = config.read_bytes()
        assert content.count(b'\nservices:\n') == 1, 'Unexpected service fixture'
        changed = content.replace(b'\nservices:\n', b'\nservices:\n    s3.invalid_service:\n        class: App\\Slice3MissingService\n        public: true\n', 1)
        try:
            config.write_bytes(changed)
            compile_result = retained('unbootable-compile', ['env', 'APP_ENV=dev', 'APP_DEBUG=1', 'php', 'bin/console',
                                      'cache:warmup', '--env=dev', '--no-interaction'], exits=(1, 255))
            assert b'Slice3MissingService' in compile_result.stdout+compile_result.stderr, 'Compilation did not fail for declared defect'
            failed = request('unbootable', 500, profiled=False)
            previous = profile('historical-during-boot-failure', state['observations']['defective'])
            historical = mate('historical-exception-during-boot-failure', ['resources:read', 'symfony-profiler://profile/'+previous['token']+'/exception', '--format=json'])
            assert b'Unrecognized field' in historical.stdout and b'BlogController' in historical.stdout, 'Historical collector unavailable during boot failure'
            logs = payload(mate('logs-during-boot-failure', ['tools:call', 'monolog-search', '--term=Unrecognized field',
                           '--environment=dev', '--kernelContext=inspection-dev', '--limit=20', '--format=json']).stdout)
            assert logs['entries'], 'Historical logs became unavailable during boot failure'
            assert previous['token'] == state['observations']['defective']['token']
            return {'status': 'pass', 'kind': 'Expected-negative pre-profiler boot/compile failure',
                    'compile_exit': compile_result.returncode, 'http': failed,
                    'historical_token_read': previous['token'], 'historical_logs_read': len(logs['entries']),
                    'absence_interpretation': 'A pre-profiler failure may have no profile; previously captured evidence remains readable.'}
        finally:
            config.write_bytes(content)

    async def repair():
        answers = {}
        async with connect('/tmp', directory/'semantic-replay', command=[str(ROOT/'bin/serena-mcp'), '--run', data['run_id']]) as repl:
            answers['method'] = await repl.code(f's.lsp.find_symbol("BlogController/index", relative_path={CONTROLLER!r}, include_body=True)')
            method = json.loads(answers['method'])
            assert len(method) == 1 and task['defect']['after'] in method[0]['body'], 'Semantic inspection omitted defective method'
            answers['entity'] = await repl.code('s.lsp.find_symbol("Tag", relative_path="src/Entity/Tag.php", depth=1, include_body=True)')
            assert 'name' in answers['entity'] and 'private readonly string $label' not in answers['entity']
            answers['repository'] = await repl.code(f's.lsp.find_symbol("TagRepository", relative_path="src/Repository/TagRepository.php", include_body=True)')
            answers['lookup'] = await repl.code(rf's.lsp.find_declaration({CONTROLLER!r}, r"tags->(findOneBy)\(", include_info=True)')
            assert 'vendor/doctrine/' in answers['lookup'], 'Inherited repository lookup was not resolved'
            replacement = method[0]['body'].replace(task['defect']['after'], task['defect']['before'])
            answers['edit'] = await repl.code(f's.edit.replace_symbol_body("BlogController/index", {CONTROLLER!r}, {replacement!r})')
            assert answers['edit'] == 'OK', 'Semantic repair failed'
            answers['fresh_method'] = await repl.code(f's.lsp.find_symbol("BlogController/index", relative_path={CONTROLLER!r}, include_body=True)')
            assert task['defect']['before'] in answers['fresh_method'] and task['defect']['after'] not in answers['fresh_method']
        assert (app/CONTROLLER).read_bytes() == state['controller'], 'Semantic repair did not restore exact original controller'
        write_json(directory/'semantic-replay/answers.json', answers)
        return {'status': 'pass', 'kind': 'Deterministic semantic diagnosis/edit replay, not a fresh adaptive agent',
                'restored_controller_sha256': sha(app/CONTROLLER), 'lsp_enrichment_claimed': False}

    def mago_checks():
        previous = (app/TEST).read_text()
        fix = native('safe-fix', ['lint', '--fix', TEST])
        (directory/'safe-fix.diff').write_text(''.join(difflib.unified_diff(previous.splitlines(True), (app/TEST).read_text().splitlines(True), fromfile='before/'+TEST, tofile='after/'+TEST)))
        native('format-before', ['format', '--check', TEST])
        native('format-write', ['format', TEST], exits=(0,))
        formatted = sha(app/TEST)
        native('format-after', ['format', '--check', TEST], exits=(0,))
        native('format-stability', ['format', TEST], exits=(0,))
        assert sha(app/TEST) == formatted == task['files'][TEST]['sha256'], 'Formatter changed declared task output or was unstable'
        state['after_analysis_row'] = native('after-analyze', ['analyze', '--reporting-format', 'json'])
        state['after_analysis'] = issues(state['after_analysis_row'])
        final_lint = issues(native('after-lint', ['lint', '--reporting-format', 'json']))
        result = {'status': 'pass', 'analysis': compare_native(state['before_analysis'], state['after_analysis']),
                  'lint': compare_native(state['before_lint'], final_lint), 'safe_fix_exit': fix['exit'],
                  'formatter_stable': True, 'source_inventory': source_inventory(app), 'suppression_or_baseline_generated': False}
        write_json(directory/'native-result.json', result)
        return result

    def framework():
        command = [str(ROOT/'bin/poc'), 'mago-enriched', '--run', data['run_id'], '--symbol', SYMBOL,
                   '--symbol', REPOSITORY, '--', 'analyze', '--reporting-format', 'json']
        stale = retained('enriched-stale', command, exits=(3,), host=True)
        assert b'mate-prepare' in stale.stderr and not stale.stdout
        # Failed response/profile/collector/log evidence was preserved above.
        state['prepared_final'] = prepare_mate(data)
        response = retained('enriched-final', command, exits=(state['after_analysis_row']['exit'],), host=True)
        report = json.loads(response.stdout)
        attestations = [issue for issue in report['issues'] if issue.get('code') == 'byte-kitsune/symfony-wiring/analysis-attestation']
        assert len(attestations) == 1, 'Wiring worker execution attestation missing'
        compare_native(state['after_analysis'], [issue for issue in report['issues'] if issue not in attestations])
        candidates = []
        for path in (Path(data['evidence'])/'mago/enriched').glob('*/invocation.json'):
            row = json.loads(path.read_text())
            if row.get('preparation_id') == state['prepared_final']['preparation_id'] and (path.parent/'graph.json').is_file():
                candidates.append(path)
        assert len(candidates) == 1, 'Missing or ambiguous public enriched-analysis evidence'
        invocation = json.loads(candidates[0].read_text())
        graph = json.loads((candidates[0].parent/'graph.json').read_text())
        assert graph['symbols'][SYMBOL]['declaration'], 'Repaired controller absent from source graph'
        binding = [ref for ref in graph['symbols'][REPOSITORY]['references'] if ref['target'] == r'doctrine\bundle\doctrinebundle\registry' and ref['kind'] == 'Body']
        assert len(binding) == 1, 'Concrete compiled repository dependency missing'
        assert {CONTROLLER, TEST} <= {row['path'] for row in graph['files']}, 'Public analysis omitted repaired source or regression'
        service = payload(mate('compiled-tag-repository', ['tools:call', 'symfony-service-detail', '--id='+REPOSITORY,
                          '--context=inspection-dev', '--format=json']).stdout)
        assert service['arguments'][0]['name'] == 'registry' and service['arguments'][0]['value'] == 'doctrine'
        fresh(data)
        return {'status': 'pass', 'stale_rejected': True, 'refreshed_preparation_id': state['prepared_final']['preparation_id'],
                'public_invocation': str(candidates[0]), 'native_exit': invocation['native_exit'], 'compiled_dependency': binding,
                'attestation': attestations, 'source_and_tests_analyzed': len(graph['files']),
                'lsp_worker_propagation': 'Not established by CLI proof'}

    def recovered():
        row = request('repaired', 200)
        value = profile('repaired', row)
        assert b'<article class="post">' in (directory/'repaired-body.html').read_bytes(), 'Repaired response has no filtered posts'
        result = {'observations': {key: state['observations'][key] for key in ('healthy', 'defective', 'repaired')}}
        verify_runtime_result(result)
        write_json(directory/'runtime-result.json', result)
        return {'status': 'pass', 'observation': row, 'profile_time': value['time'], 'preserved': archive('repaired', row)}

    def behavior():
        retained('combined-list', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml',
                                 '--list-tests-xml', evidence_path('combined-list.xml')])
        combined = expected_suite(directory/'combined-list.xml', app)
        write_json(directory/'combined-suite.json', combined)
        retained('combined-suite', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml',
                                   '--log-junit', evidence_path('combined.xml')])
        suites = verify_suites(state['original'], combined, directory/'combined.xml', directory/'original-after.xml')
        retained('regression-focused', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml', TEST,
                                       '--log-junit', evidence_path('regression-focused.xml')])
        retained('application-checks', ['/opt/poc/docker/check'])
        write_json(directory/'suite-verification.json', suites)
        return suites

    def integrity():
        prepared = fresh(data)
        result = verify_task_delta(state['baseline'], snapshot(app), task, reference_sha256=prepared['wiring_reference_sha256'])
        agent = validate_agent_evidence(ROOT, task)
        source_integrity()
        diff = ''.join(difflib.unified_diff([], (app/TEST).read_text().splitlines(True), fromfile='/dev/null', tofile='b/'+TEST))
        (directory/'final-task.diff').write_text(diff)
        write_json(directory/'final-application.json', snapshot(app))
        result.update(final_task_diff=str(directory/'final-task.diff'), actual_agent=agent)
        return result

    save()
    record('fixture_integrity', source_integrity)
    try:
        identity = {}
        start(data, validate_image=lambda item: identity.update(capture_identity(item, source)))
        for name in ('executed-identity.json', 'executed-identity.stderr', 'image-identity.json'):
            shutil.copy2(Path(data['evidence'])/name, directory/name)
        record('executed_identity', lambda: identity)
        record('prepared_baseline', baseline, ('executed_identity',))
        record('healthy_request', healthy, ('prepared_baseline',))
        record('defective_request', defect, ('healthy_request',))
        record('runtime_diagnosis', diagnose, ('defective_request',))
        record('boot_failure_control', boot_failure, ('runtime_diagnosis',))
        record('semantic_repair', lambda: asyncio.run(repair()), ('boot_failure_control',))
        record('native_mago', mago_checks, ('semantic_repair',))
        record('enriched_framework', framework, ('native_mago',))
        record('repaired_request', recovered, ('enriched_framework',))
        record('behavior', behavior, ('repaired_request',))
        record('task_integrity', integrity, ('behavior',))
    except Exception as exc:
        (directory/'startup-error.txt').write_text(traceback.format_exc())
        for row in checks.values():
            if row['status'] == 'not_exercised':
                row.update(status='blocked', reason='Startup failed: '+str(exc))
    finally:
        # Faults are task-owned; restore on interrupted/failed runs as well.
        if 'controller' in state:
            (app/CONTROLLER).write_bytes(state['controller'])
        if keep_running:
            checks['cleanup'].update(status='pass', detail='Selected disposable workspace intentionally retained running')
        else:
            record('cleanup', lambda: stop(load(data['run_id'])))
        result = save()
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'pass' else 1
