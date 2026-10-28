"""Real Mate and Mago wiring controls; no analyzer, parser or mock substitute."""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

from evidence import write_json
from mate_contract import CONTEXT, DEPENDENCY, SERVICE, compare, payload


def run(data):
    from matelib import ROOT, call, fresh, sha
    from poclib import execute
    app, evidence = Path(data['app']), Path(data['evidence'])/'framework'/uuid.uuid4().hex
    evidence.mkdir(parents=True)
    prepared = fresh(data)
    result = {'status': 'fail', 'run_id': data['run_id'], 'service': SERVICE,
              'preparation_id': prepared['preparation_id'], 'evidence': str(evidence), 'controls': {}}
    write_json(evidence/'result.json', result)

    def retained(name, response):
        (evidence/(name+'.stdout')).write_bytes(response.stdout)
        (evidence/(name+'.stderr')).write_bytes(response.stderr)
        return response

    def host(name, argv, expected=0):
        response = retained(name, subprocess.run(argv, cwd='/tmp', capture_output=True, timeout=180))
        write_json(evidence/(name+'.invocation.json'), {'argv': argv, 'cwd': '/tmp', 'exit': response.returncode})
        assert response.returncode == expected, name+': unexpected exit '+str(response.returncode)
        return response

    def mate(name, argv, expected=0):
        response = retained(name, call(data, argv))
        assert response.returncode == expected, name+': unexpected Mate exit '+str(response.returncode)
        return response

    def reject(name, mutation, restoration, needle, *, command='tools:call'):
        mutation()
        try:
            response = host(name, [str(ROOT/'bin/mate'), '--run', data['run_id'], '--',
                                   command, 'symfony-service-detail', '--id='+SERVICE,
                                   '--context='+CONTEXT, '--format=json'], expected=3)
            assert needle in response.stderr.decode(), name+': wrong rejection'
            assert response.stdout == b'', name+': rejected request emitted data'
            enriched = host(name+'-enriched', [str(ROOT/'bin/poc'), 'mago-enriched',
                            '--run', data['run_id'], '--', 'analyze', '--reporting-format', 'json'], expected=3)
            assert enriched.stdout == b'', name+': rejected enriched request emitted data'
        finally:
            restoration()
        fresh(data)
        result['controls'][name] = 'pass'

    schema = mate('schemas', ['tools:list', '--format=json'])
    schemas = json.loads(schema.stdout)['tools']
    assert schemas['symfony-service-detail']['input_schema']['required'] == ['id']
    for name in ('symfony-service-detail', 'symfony-services'):
        mate('schema-'+name, ['tools:inspect', name, '--format=json'])
    detail = host('outside-cwd-detail', [str(ROOT/'bin/mate'), '--run', data['run_id'], '--',
                                      'tools:call', 'symfony-service-detail', '--id='+SERVICE,
                                      '--context='+CONTEXT, '--format=json'])
    console = retained('console-service', execute(data, 'env', 'APP_ENV=dev', 'APP_DEBUG=1', 'php',
                      'bin/console', 'debug:container', SERVICE, '--env=dev', '--format=json', capture_output=True))
    dependency = retained('console-dependency', execute(data, 'env', 'APP_ENV=dev', 'APP_DEBUG=1', 'php',
                         'bin/console', 'debug:container', DEPENDENCY, '--env=dev', '--format=json', capture_output=True))
    result['compiled_wiring'] = compare(detail.stdout, console.stdout, dependency.stdout)
    repo_detail = mate('dependency-detail', ['tools:call', 'symfony-service-detail', '--id='+DEPENDENCY,
                                            '--context='+CONTEXT, '--format=json'])
    repo = payload(repo_detail.stdout)
    assert repo['arguments'][0]['value'] == 'doctrine', 'Unexpected ManagerRegistry service binding'
    assert repo['arguments'][0]['name'] == 'registry'
    missing = mate('missing-service', ['tools:call', 'symfony-service-detail', '--id=poc.missing.service',
                                      '--context='+CONTEXT, '--format=json'], expected=1)
    assert b'not found' in missing.stderr.lower() or b'not found' in missing.stdout.lower()
    result['controls']['missing-service'] = 'pass'
    host('unknown-run', [str(ROOT/'bin/mate'), '--run', 'slice1-no-such-run', '--', 'tools:list'], expected=3)
    result['controls']['unknown-run'] = 'pass'

    marker = ROOT/'workspaces'/data['run_id']/'run.json'
    marker_bytes = marker.read_bytes()
    altered = json.loads(marker_bytes)
    altered['project'] += '-wrong'
    reject('wrong-project', lambda: marker.write_text(json.dumps(altered)), lambda: marker.write_bytes(marker_bytes), 'Container project')
    altered = json.loads(marker_bytes)
    altered['app'] = '/tmp/not-the-selected-workspace'
    reject('wrong-workspace', lambda: marker.write_text(json.dumps(altered)), lambda: marker.write_bytes(marker_bytes), 'Invalid app workspace')
    source = app/'src/Form/Type/TagsInputType.php'
    source_bytes = source.read_bytes()
    reject('stale-source', lambda: source.write_bytes(source_bytes+b'\n'), lambda: source.write_bytes(source_bytes), 'Application/dependencies changed')
    reject('stale-source-abbreviated-command', lambda: source.write_bytes(source_bytes+b'\n'),
           lambda: source.write_bytes(source_bytes), 'Application/dependencies changed', command='tools:ca')
    xml = app/next(iter(prepared['metadata']))
    xml_bytes = xml.read_bytes()
    reject('absent-compiled-metadata', lambda: xml.unlink(), lambda: xml.write_bytes(xml_bytes), 'Dev metadata absent')
    reject('stale-compiled-metadata', lambda: xml.write_bytes(xml_bytes+b'\n'), lambda: xml.write_bytes(xml_bytes), 'Metadata changed')
    reference = app/'.mago/container-reference.dev.json'
    reference_bytes = reference.read_bytes()
    reject('absent-wiring-reference', lambda: reference.unlink(), lambda: reference.write_bytes(reference_bytes), 'Application/dependencies changed')

    # Owner content survives the installed init/rediscovery path; afterwards all
    # instruction bytes are restored before checking the original preparation.
    instruction_paths = [app/'AGENTS.md', app/'CLAUDE.md']
    instructions = {p: p.read_bytes() if p.exists() else None for p in instruction_paths}
    sentinel = b'Owner instruction retained by the slice-1 preservation control.\n\n'
    try:
        for p in instruction_paths:
            p.write_bytes(sentinel+(instructions[p] or b''))
        for name, argv in (('owner-init', ('php', 'vendor/bin/mate', 'init', '--no-interaction')),
                           ('owner-discover', ('php', 'vendor/bin/mate', 'discover', '--no-interaction'))):
            execute(data, *argv, log=evidence/(name+'.log'))
        assert all(p.read_bytes().startswith(sentinel) for p in instruction_paths), 'Owner instructions were overwritten'
        assert str(ROOT/'bin/mate') in (app/'AGENTS.md').read_text(), 'Generated instructions omit host wrapper'
        result['controls']['owner-instruction-preservation'] = 'pass'
    finally:
        for p, content in instructions.items():
            if content is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(content)
    fresh(data)

    def analysis(name, enabled, *, controlled_reference=False):
        if not controlled_reference:
            fresh(data)
        observation = evidence/(name+'-graph.json')
        if controlled_reference:
            # Deliberately invalid compiled facts cannot pass the ordinary guard.
            # Retain this explicit package-only negative probe separately.
            argv = ['env', 'POC_WIRING='+('1' if enabled else '0'),
                    'POC_WIRING_OBSERVATION=/evidence/'+str(observation.relative_to(Path(data['evidence']))),
                    'mago', '--workspace', '/app', '--config', '/app/.mago/wiring.toml', '--threads', '1',
                    'analyze', '--reporting-format', 'json']
            response = retained(name, execute(data, *argv, capture_output=True, check=False))
        else:
            invocations = Path(data['evidence'])/'mago/enriched'
            before = set(invocations.glob('*/invocation.json'))
            argv = [str(ROOT/'bin/poc'), 'mago-enriched', '--run', data['run_id']]
            if not enabled:
                argv.append('--extension-off')
            argv += ['--', 'analyze', '--reporting-format', 'json']
            response = retained(name, subprocess.run(argv, cwd='/tmp', capture_output=True, timeout=180))
            added = set(invocations.glob('*/invocation.json'))-before
            assert len(added) == 1, 'Public enriched command did not retain exactly one invocation'
            invocation = next(iter(added))
            recorded = json.loads(invocation.read_text())
            assert recorded['status'] in ('clean', 'findings'), 'Public enriched analysis failed: '+str(recorded)
            assert recorded['native_exit'] == response.returncode, 'Native enriched exit changed'
            observation.write_bytes(invocation.with_name('graph.json').read_bytes())
        write_json(evidence/(name+'.invocation.json'), {'argv': argv, 'exit': response.returncode,
                   'controlled_reference': controlled_reference, 'source_sha256': sha(source),
                   'reference_sha256': sha(reference), 'preparation_id': prepared['preparation_id']})
        assert response.returncode in (0, 1), 'Mago/worker failure: '+name
        report = json.loads(response.stdout)
        graph = json.loads(observation.read_text())
        assert graph['source_sha256'] == hashlib.sha256(source_bytes).hexdigest(), 'Observer analyzed wrong source'
        files = {row['path'] for row in graph['files']}
        assert {'src/Form/Type/TagsInputType.php', 'src/Repository/TagRepository.php', 'src/Form/PostType.php'} <= files
        attestations = [i for i in report['issues'] if i['code'] == 'byte-kitsune/symfony-wiring/analysis-attestation']
        assert len(attestations) == int(enabled), 'Extension execution attestation differs'
        if enabled:
            note = next(n for n in attestations[0]['notes'] if n.startswith('extension-attestation: '))
            attestation = json.loads(note.removeprefix('extension-attestation: '))
            assert attestation['complete'] is True and attestation['source_files'] == len(files) > 0
        return graph, report

    def binding(graph):
        return [r for r in graph['dependency_references']
                if r['target'] == 'doctrine\\bundle\\doctrinebundle\\registry' and r['kind'] == 'Body']

    off, off_report = analysis('extension-off', False)
    on, on_report = analysis('extension-on', True)
    assert not binding(off) and len(binding(on)) == 1, 'Missing concrete compiled-binding contribution'
    assert off['references'] == on['references'], 'Unexpected direct selected-service reference change'
    result['controls']['extension-off-on'] = 'pass'
    variant = json.loads(reference_bytes)
    variant['definitions'][DEPENDENCY]['arguments'][0] = 'poc.missing.registry'
    try:
        reference.write_text(json.dumps(variant)+'\n')
        # The ordinary host guard rejects this drift. The explicit raw invocation
        # below is a labelled disposable package control, never fresh analysis.
        try:
            fresh(data)
        except AssertionError as exc:
            assert 'Application/dependencies changed' in str(exc)
        else:
            raise AssertionError('Changed compiled reference escaped the host guard')
        invalid, _ = analysis('invalid-binding', True, controlled_reference=True)
        assert not binding(invalid), 'Plugin invented a concrete class for an unresolved binding'
    finally:
        reference.write_bytes(reference_bytes)
    restored, _ = analysis('extension-restored', True)
    assert len(binding(restored)) == 1
    result['controls']['invalid-binding-removed-and-restored'] = 'pass'
    result['extension'] = {'status': 'pass', 'backend': 'php', 'mago_source': '46df50c96d93d0ac3655c116c375574277cf0b30',
                           'extension_source': '28c3f54065b71fe046a7474ced401aeadc941b0f',
                           'contribution': 'TagRepository::__construct -> Doctrine\\Bundle\\DoctrineBundle\\Registry Body edge',
                           'direct_service_boundary': 'TagsInputType -> TagRepository already has a native Signature edge; Mago suppresses duplicate Body edges.',
                           'native_issue_counts': {'off': len(off_report['issues']), 'on': len(on_report['issues'])-1},
                           'clean_application_claim': False}
    result['status'] = 'pass'
    write_json(evidence/'result.json', result)
    fresh(data)
    return result
