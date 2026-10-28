"""Generate, replay and independently verify one declared Symfony command task."""
import asyncio
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import traceback
import uuid

from poclib import ROOT, execute, load, metadata, new_id, prepare, source_integrity, start, stop


REQUIRED = ('fixture_integrity', 'executed_identity', 'prepared_baseline', 'maker_generation',
            'declared_task', 'native_mago', 'semantic_replay', 'enriched_framework',
            'behavior', 'defective_restored_control', 'task_integrity', 'cleanup')


def run_slice(run_id=None, *, keep_running=False, capture_identity):
    from evidence import digest, write_json
    from magolib import prepare_mago, run_native
    from mago_contract import issues, source_inventory
    from matelib import call, fresh, prepare_mate
    from mate_contract import payload
    from mcp_client import connect
    from slice2_contract import (COMMAND, TEST, TARGETS, SYMBOL, REPOSITORY, compare_native,
                                 sha, task_inputs, validate_agent_evidence, verify_suites, verify_task_delta)
    from verifier import expected_suite, snapshot, verify_suite

    data = prepare(run_id or new_id('slice2'))
    directory = Path(data['evidence'])/'slice2'/('attempt-'+uuid.uuid4().hex)
    directory.mkdir(parents=True)
    source = metadata(data)
    app = Path(data['app'])
    context = {'run_id': data['run_id'], 'workspace': data['app'], 'attempt_id': directory.name,
               'source_context_sha256': digest(source), 'command': 'app:tags:count'}
    checks = {name: {**context, 'name': name, 'status': 'not_exercised'} for name in REQUIRED}
    write_json(directory/'source.json', source)
    write_json(directory/'task.json', task_inputs(ROOT))
    state = {}

    def save():
        result = {**context, 'schema': 1, 'kind': 'mago_first_slice2',
                  'status': 'pass' if all(row['status'] == 'pass' for row in checks.values()) else 'incomplete',
                  'inventory': list(REQUIRED), 'checks': list(checks.values()), 'evidence': str(directory),
                  'execution_kind': 'Scripted Maker generation and declared-output replay, independently verified.',
                  'actual_agent_evidence': str(ROOT/'docs/evidence/slice2/fresh-agent/index.json'),
                  'interpretation': 'Fresh adaptive agent evidence is separately retained. Native findings remain '
                                    'findings; enriched CLI results do not imply LSP worker propagation.'}
        write_json(directory/'results.json', result)
        write_json(Path(data['evidence'])/'slice2-result.json', result)
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

    def evidence_path(name):
        return '/evidence/'+str((directory/name).relative_to(Path(data['evidence'])))

    def native(name, argv, exits=(0, 1)):
        row = run_native(data, argv, directory=directory/name)
        assert row['exit'] in exits, name+': native tool failure '+str(row['exit'])
        return row

    def baseline():
        assert not any((app/path).exists() for path in TARGETS), 'Slice 2 requires a fresh task workspace'
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
        return {'status': 'pass', 'original': original, 'tool': state['native_tool'],
                'preparation_id': state['preparation_before']['preparation_id'],
                'analyzer_findings': len(state['before_analysis']), 'lint_findings': len(state['before_lint'])}

    def maker():
        help_result = retained('maker-help', ['php', 'bin/console', 'make:command', '--help'])
        assert b'make:command [<name>]' in help_result.stdout and b'--no-interaction' in help_result.stdout
        retained('maker', ['php', 'bin/console', 'make:command', 'app:tags:count', '--no-interaction'])
        generated = app/COMMAND
        assert generated.is_file() and not generated.is_symlink(), 'Maker did not create the command'
        (directory/'generated-TagsCountCommand.php').write_bytes(generated.read_bytes())
        generated_state = snapshot(app)
        changed = {p for p in state['baseline']['entries'].keys() | generated_state['entries'].keys()
                   if state['baseline']['entries'].get(p) != generated_state['entries'].get(p)}
        assert changed == {COMMAND}, 'Unexpected Maker-generated changes: '+str(changed)
        return {'status': 'pass', 'generated_files': sorted(changed), 'generated_sha256': sha(generated),
                'help_discovered_from_installed_command': True}

    def task():
        declaration = task_inputs(ROOT)
        agent = validate_agent_evidence(ROOT, declaration)
        # These are the two outputs produced in the separate fresh adaptive MCP
        # exercise. Applying them here is explicitly a deterministic replay.
        for target, row in declaration['files'].items():
            destination = app/target
            assert not destination.is_symlink(), 'Task target must not be a symlink'
            shutil.copy2(ROOT/'fixtures/slice2'/row['asset'], destination)
            destination.chmod(0o644)
        state['task'] = declaration
        return {'status': 'pass', 'kind': 'scripted replay of separately retained fresh agent output',
                'files': {target: sha(app/target) for target in TARGETS},
                'fresh_agent_index': 'docs/evidence/slice2/fresh-agent/index.json', 'fresh_agent': agent}

    def mago_checks():
        before_fix = {target: (app/target).read_text() for target in TARGETS}
        # The pinned CLI forbids --reporting-format together with --fix. Native
        # JSON diagnostics are retained separately before/after this write call.
        fix = native('safe-fix', ['lint', '--fix', *TARGETS])
        diff = ''.join(line for target in TARGETS for line in difflib.unified_diff(
            before_fix[target].splitlines(True), (app/target).read_text().splitlines(True),
            fromfile='before/'+target, tofile='after/'+target))
        (directory/'safe-fix.diff').write_text(diff)
        native('format-before', ['format', '--check', *TARGETS])
        native('format-write', ['format', *TARGETS], exits=(0,))
        formatted = {target: sha(app/target) for target in TARGETS}
        native('format-after', ['format', '--check', *TARGETS], exits=(0,))
        native('format-stability', ['format', *TARGETS], exits=(0,))
        assert formatted == {target: sha(app/target) for target in TARGETS}, 'Formatter is not stable'
        for target in TARGETS:
            assert sha(app/target) == state['task']['files'][target]['sha256'], 'Native checks changed the declared final task output'
        state['after_analysis_row'] = native('after-analyze', ['analyze', '--reporting-format', 'json'])
        state['after_analysis'] = issues(state['after_analysis_row'])
        final_lint = issues(native('after-lint', ['lint', '--reporting-format', 'json']))
        result = {'status': 'pass', 'analysis': compare_native(state['before_analysis'], state['after_analysis']),
                  'lint': compare_native(state['before_lint'], final_lint), 'safe_fix_exit': fix['exit'],
                  'safe_fix_diff': str(directory/'safe-fix.diff'), 'formatter_stable': True,
                  'source_inventory': source_inventory(app), 'baseline_or_suppression_generated': False}
        write_json(directory/'native-result.json', result)
        return result

    async def semantic_queries():
        answers = {}
        async with connect('/tmp', directory/'semantic-replay', command=[str(ROOT/'bin/serena-mcp'), '--run', data['run_id']]) as repl:
            answers['command'] = await repl.code(f's.lsp.find_symbol("TagsCountCommand", relative_path={COMMAND!r}, include_body=True)')
            body = json.loads(answers['command'])
            assert len(body) == 1 and '$this->tags->count([])' in body[0]['body']
            answers['repository'] = await repl.code(rf's.lsp.find_declaration({COMMAND!r}, r"readonly (TagRepository) \$tags", include_info=True)')
            assert json.loads(answers['repository'])['relative_path'] == 'src/Repository/TagRepository.php'
            answers['count'] = await repl.code(rf's.lsp.find_declaration({COMMAND!r}, r"tags->(count)\(", include_info=True)')
            assert json.loads(answers['count'])['relative_path'].startswith('vendor/doctrine/')
            answers['references'] = await repl.code('import json; json.dumps([{"file": x.get_relative_path(), "line": x.line, "character": x.character} '
                                                   'for x in s.lsp.find_referencing_symbols("TagRepository", "src/Repository/TagRepository.php").references])')
            assert len([ref for ref in json.loads(answers['references']) if ref['file'] == COMMAND]) == 2
            for target in TARGETS:
                answers[target+'-diagnostics'] = await repl.code(f's.lsp.get_diagnostics_for_file({target!r}, min_severity=4)')
                assert json.loads(answers[target+'-diagnostics']) == {}, 'New PHP has LSP diagnostics'
        write_json(directory/'semantic-replay/answers.json', answers)
        return {'status': 'pass', 'kind': 'deterministic MCP semantic replay, not fresh agent success',
                'evidence': str(directory/'semantic-replay'), 'lsp_enrichment_claimed': False}

    def framework():
        command = [str(ROOT/'bin/poc'), 'mago-enriched', '--run', data['run_id'],
                   '--symbol', SYMBOL, '--symbol', REPOSITORY, '--', 'analyze', '--reporting-format', 'json']
        stale = retained('enriched-stale', command, exits=(3,), host=True)
        assert b'mate-prepare' in stale.stderr and not stale.stdout, 'Stale rejection lacks explicit refresh instruction'
        state['prepared_final'] = prepare_mate(data)
        response = retained('enriched-final', command, exits=(state['after_analysis_row']['exit'],), host=True)
        report = json.loads(response.stdout)
        attestations = [issue for issue in report['issues'] if issue.get('code') == 'byte-kitsune/symfony-wiring/analysis-attestation']
        assert len(attestations) == 1, 'Wiring extension execution attestation missing'
        native_report = [issue for issue in report['issues'] if issue not in attestations]
        compare_native(state['after_analysis'], native_report)
        # Locate the real public invocation by preparation and retained graph;
        # no direct private analyzer call substitutes for the public CLI proof.
        candidates = []
        for path in (Path(data['evidence'])/'mago/enriched').glob('*/invocation.json'):
            row = json.loads(path.read_text())
            if row.get('preparation_id') == state['prepared_final']['preparation_id'] and (path.parent/'graph.json').is_file():
                candidates.append(path)
        assert len(candidates) == 1, 'Missing or ambiguous public enriched-analysis evidence'
        invocation = json.loads(candidates[0].read_text())
        graph = json.loads((candidates[0].parent/'graph.json').read_text())
        symbols = graph['symbols']
        assert symbols[SYMBOL]['declaration'], 'New command missing from Mago codebase'
        assert any(ref['target'] == REPOSITORY.lower() and ref['kind'] == 'Signature' for ref in symbols[SYMBOL]['references']), 'Command repository reference absent from Mago graph'
        binding = [ref for ref in symbols[REPOSITORY]['references']
                   if ref['target'] == r'doctrine\bundle\doctrinebundle\registry' and ref['kind'] == 'Body']
        assert len(binding) == 1, 'Missing concrete compiled-binding contribution'
        analyzed = {row['path'] for row in graph['files']}
        assert set(TARGETS) <= analyzed, 'Public enriched analysis omitted new command or test'
        console = retained('compiled-command', ['env', 'APP_ENV=dev', 'APP_DEBUG=1', 'php', 'bin/console',
                                               'debug:container', SYMBOL, '--env=dev', '--format=json'])
        console_value = json.loads(console.stdout)
        mate = call(data, ['tools:call', 'symfony-service-detail', '--id='+SYMBOL, '--context=inspection-dev', '--format=json'])
        (directory/'mate-command.stdout').write_bytes(mate.stdout)
        (directory/'mate-command.stderr').write_bytes(mate.stderr)
        assert mate.returncode == 0, 'Mate command inspection failed'
        mate_value = payload(mate.stdout)
        assert mate_value['class'] == console_value['class'] == SYMBOL
        assert mate_value['arguments'][0]['name'] == 'tags'
        assert mate_value['arguments'][0]['value'] == console_value['arguments'][0]['id'] == REPOSITORY
        assert any(tag['name'] == 'console.command' for tag in console_value['tags']), 'New service is not registered as a command'
        fresh(data)
        return {'status': 'pass', 'stale_rejected': True, 'refreshed_preparation_id': state['prepared_final']['preparation_id'],
                'public_invocation': str(candidates[0]), 'native_exit': invocation.get('native_exit', invocation.get('exit')),
                'service': SYMBOL, 'constructor_parameter': 'tags', 'dependency': REPOSITORY,
                'contribution': binding, 'attestation': attestations, 'source_and_tests_analyzed': len(analyzed),
                'lsp_worker_propagation': 'known blocker; not claimed by this CLI result'}

    def behavior():
        retained('combined-list', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml',
                                 '--list-tests-xml', evidence_path('combined-list.xml')])
        combined = expected_suite(directory/'combined-list.xml', app)
        write_json(directory/'combined-suite.json', combined)
        retained('combined-suite', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml',
                                   '--log-junit', evidence_path('combined.xml')])
        suites = verify_suites(state['original'], combined, directory/'combined.xml', directory/'original-after.xml')
        retained('feature-focused', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml', TEST,
                                    '--log-junit', evidence_path('feature-focused.xml')])
        # Exercise bin/console in separate real processes as well as CommandTester.
        # Preserve the owned test DB and any SQLite sidecars for original-suite reuse.
        database = app/'data/database_test.sqlite'
        paths = [Path(str(database)+suffix) for suffix in ('', '-wal', '-shm', '-journal')]
        saved = {path: path.read_bytes() if path.exists() else None for path in paths}
        runtime = []
        seed = r'''require 'vendor/autoload.php';
(new Symfony\Component\Dotenv\Dotenv())->bootEnv('/app/.env');
$kernel = new App\Kernel('test', true); $kernel->boot();
$manager = $kernel->getContainer()->get('doctrine')->getManager();
$connection = $manager->getConnection();
$connection->executeStatement('DELETE FROM symfony_demo_post_tag');
$connection->executeStatement('DELETE FROM symfony_demo_tag');
for ($i = 0; $i < (int) $argv[1]; ++$i) { $manager->persist(new App\Entity\Tag('slice2-runtime-'.$i)); }
$manager->flush(); $kernel->shutdown();'''
        try:
            for count in (0, 3):
                retained('runtime-seed-'+str(count), ['env', 'APP_ENV=test', 'APP_DEBUG=1', 'php', '-r', seed, str(count)])
                response = retained('runtime-count-'+str(count), ['env', 'APP_ENV=test', 'APP_DEBUG=1', 'php',
                                    'bin/console', 'app:tags:count', '--no-interaction', '--no-ansi'])
                assert response.stdout == ('Tag count: '+str(count)+'\n').encode(), 'Command output does not match persisted row count'
                runtime.append({'persisted_tags': count, 'stdout': response.stdout.decode(), 'exit': response.returncode})
        finally:
            for path, content in saved.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(content)
        retained('application-checks', ['/opt/poc/docker/check'])
        return {**suites, 'real_console_states': runtime, 'database_restored': True}

    def negative():
        target = app/COMMAND
        original = target.read_bytes()
        assert original.count(b'$this->tags->count([])') == 1
        try:
            target.write_bytes(original.replace(b'$this->tags->count([])', b'($this->tags->count([]) + 1)'))
            (directory/'defective-TagsCountCommand.php').write_bytes(target.read_bytes())
            response = retained('defective-feature', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml', TEST,
                                 '--log-junit', evidence_path('defective-feature.xml')], exits=(1,))
            assert b'Failed asserting that two strings are identical' in response.stdout, 'Negative control failed for an unrelated cause'
        finally:
            target.write_bytes(original)
        retained('restored-feature', ['php', 'vendor/bin/phpunit', '--configuration', 'phpunit.dist.xml', TEST,
                                     '--log-junit', evidence_path('restored-feature.xml')])
        fresh(data)
        return {'status': 'pass', 'kind': 'expected-negative feature behavior control',
                'mutation': 'Persisted tag count plus one', 'defective_exit': 1, 'restored_exit': 0,
                'restored_source_sha256': sha(target)}

    def integrity():
        prepared = fresh(data)
        result = verify_task_delta(state['baseline'], snapshot(app), state['task'],
                                   reference_sha256=prepared['wiring_reference_sha256'])
        source_integrity()
        diff = ''.join(line for target in TARGETS for line in difflib.unified_diff([], (app/target).read_text().splitlines(True),
                     fromfile='/dev/null', tofile='b/'+target))
        (directory/'final-task.diff').write_text(diff)
        write_json(directory/'final-application.json', snapshot(app))
        result['final_task_diff'] = str(directory/'final-task.diff')
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
        record('maker_generation', maker, ('prepared_baseline',))
        record('declared_task', task, ('maker_generation',))
        record('native_mago', mago_checks, ('declared_task',))
        record('semantic_replay', lambda: asyncio.run(semantic_queries()), ('native_mago',))
        record('enriched_framework', framework, ('native_mago',))
        record('behavior', behavior, ('enriched_framework',))
        record('defective_restored_control', negative, ('behavior',))
        record('task_integrity', integrity, ('enriched_framework', 'defective_restored_control'))
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
