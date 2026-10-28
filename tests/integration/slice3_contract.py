"""Independent request, task delta, native report and suite checks for slice 3."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

CONTROLLER = 'src/Controller/BlogController.php'
TEST = 'tests/Controller/BlogTagFilterTest.php'
REFERENCE = '.mago/container-reference.dev.json'
SYMBOL = r'App\Controller\BlogController'
REPOSITORY = r'App\Repository\TagRepository'
FEATURE_IDS = {r'App\Tests\Controller\BlogTagFilterTest::testKnownTagFilter'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def task_inputs(root):
    root = Path(root)
    directory = root/'fixtures/slice3'
    value = json.loads((directory/'task.json').read_text())
    assert value.get('schema') == 1 and value.get('request') == '/en/blog/?tag=lorem', 'Wrong slice-3 task'
    assert value.get('healthy_status') == 200 and value.get('defective_status') == 500, 'Wrong HTTP contract'
    assert value.get('controller') == CONTROLLER and value.get('final_controller_sha256') == sha(root/'app'/CONTROLLER), 'Task must restore original controller'
    assert set(value.get('files', {})) == {TEST}, 'Task must declare exactly one new regression file'
    row = value['files'][TEST]
    assert row['asset'] == Path(TEST).name and sha(directory/row['asset']) == row['sha256'], 'Regression fixture changed'
    assert value['defect'] == {'before': "$tags->findOneBy(['name' => $request->query->get('tag')])",
                               'after': "$tags->findOneBy(['label' => $request->query->get('tag')])"}, 'Wrong fault injection'
    return value


def compare_native(before, after):
    previous = Counter(json.dumps(issue, sort_keys=True) for issue in before)
    current = Counter(json.dumps(issue, sort_keys=True) for issue in after)
    introduced, removed = current-previous, previous-current
    assert not introduced and not removed, 'Native diagnostic multiset changed: introduced='+str(list(introduced))+' removed='+str(list(removed))
    selected = [issue for issue in after if any(annotation.get('span', {}).get('file_id', {}).get('name') == TEST
                                               for annotation in issue.get('annotations', []))]
    assert not selected, 'New regression has native findings: '+str(selected)
    return {'before': len(before), 'after': len(after), 'introduced': [], 'removed': [], 'task_findings': [],
            'comparison': 'Complete native diagnostic bodies as an order-independent multiset'}


def verify_task_delta(before, after, task, *, reference_sha256):
    previous, current = before['entries'], after['entries']
    changed = {p for p in previous.keys() | current.keys() if previous.get(p) != current.get(p)}
    assert not changed-{TEST, REFERENCE}, 'Unexpected application task delta: '+str(sorted(changed))
    assert TEST not in previous, 'Regression test already existed'
    row = current.get(TEST, {})
    assert row.get('kind') == 'file' and row.get('mode') == 0o644, 'Wrong regression file kind/mode'
    assert row.get('sha256') == task['files'][TEST]['sha256'], 'Unexpected regression output'
    assert current.get(CONTROLLER) == previous.get(CONTROLLER), 'Controller was not restored exactly'
    assert current[CONTROLLER]['sha256'] == task['final_controller_sha256'], 'Wrong restored controller'
    reference = current.get(REFERENCE, {})
    assert reference.get('kind') == 'file' and reference.get('sha256') == reference_sha256, 'Unbound compiled reference'
    assert reference['mode'] == previous[REFERENCE]['mode'], 'Compiled reference mode changed'
    return {'status': 'pass', 'changed': sorted(changed), 'declared_task_files': [TEST],
            'controller_restored_sha256': current[CONTROLLER]['sha256'],
            'compiled_reference_sha256': reference_sha256, 'global_verifier_modified': False}


def verify_suites(original, combined, junit, projection):
    from verifier import verify_suite
    originals = {case['id']: case for case in original['cases']}
    all_cases = {case['id']: case for case in combined['cases']}
    assert {key: all_cases.get(key) for key in originals} == originals, 'Original suite identities changed'
    assert set(all_cases)-set(originals) == FEATURE_IDS, 'Unexpected regression-test identities'
    for path, digest in original['source_sha256'].items():
        assert combined['source_sha256'].get(path) == digest, 'Original test/configuration bytes changed: '+path
    complete = verify_suite(combined, junit)
    tree = ET.parse(junit)
    for parent in tree.iter():
        for case in list(parent):
            if case.tag == 'testcase' and case.attrib.get('class', '')+'::'+case.attrib.get('name', '') in FEATURE_IDS:
                parent.remove(case)
    for suite in tree.iter('testsuite'):
        cases = list(suite.iter('testcase'))
        suite.set('tests', str(len(cases)))
        suite.set('assertions', str(sum(int(case.attrib.get('assertions', 0)) for case in cases)))
    tree.write(projection, encoding='utf-8', xml_declaration=True)
    retained = verify_suite(original, projection)
    return {'status': 'pass', 'original': retained, 'combined': complete,
            'regression': {'tests': len(FEATURE_IDS), 'identities': sorted(FEATURE_IDS),
                           'assertions': complete['assertions']-retained['assertions']},
            'original_projection': str(projection)}


def response_record(headers, *, status, marker, url):
    """Derive the observation token from its response, never a latest-profile query."""
    matches = re.findall(r'^X-Debug-Token:\s*([0-9a-f]{6,64})\s*$', headers, re.M | re.I)
    assert len(matches) == 1, 'Request lacks a unique profiler response token'
    assert marker in url and re.fullmatch(r's3-[A-Za-z0-9-]{1,100}', marker), 'Request marker absent or invalid'
    assert status in (200, 500), 'Unexpected HTTP status'
    return {'status': status, 'token': matches[0], 'marker': marker, 'url': url,
            'provenance': 'X-Debug-Token header from this exact HTTP response'}


def verify_runtime_result(value):
    observations = value.get('observations', value)
    assert all(key in observations for key in ('healthy', 'defective', 'repaired')), 'Missing HTTP lifecycle observation'
    rows = [observations[key] for key in ('healthy', 'defective', 'repaired')]
    assert [row.get('status') for row in rows] == [200, 500, 200], 'HTTP lifecycle did not recover'
    assert len({row.get('token') for row in rows}) == 3 and all(re.fullmatch(r'[0-9a-f]{6,64}', row.get('token', '')) for row in rows), 'Request tokens missing or reused'
    assert len({row.get('marker') for row in rows}) == 3 and all(row.get('marker') in row.get('url', '') for row in rows), 'Request marker provenance missing'
    return {'status': 'pass', 'observations': rows}


def validate_agent_evidence(root, task):
    directory = Path(root)/'docs/evidence/slice3/fresh-agent'
    index_path = directory/'index.json'
    assert index_path.is_file() and not index_path.is_symlink() and index_path.stat().st_size <= 100_000, 'Fresh-agent evidence index absent or unbounded'
    index = json.loads(index_path.read_text())
    assert index.get('schema') == 1 and index.get('status') == 'pass' and index.get('kind') == 'fresh_adaptive_agent', 'Fresh adaptive agent did not pass'
    assert index.get('route') == 'host MCP -> Serena REPL -> Mago', 'Wrong fresh-agent semantic route'
    artifacts = index.get('artifacts', {})
    required = {'mcp/mcp.jsonl', 'result.json', 'runtime-result.json', 'public-invocation.json', 'public-graph.json',
                'before-analyze.stdout', 'after-analyze.stdout', 'before-lint.stdout', 'after-lint.stdout',
                'suite-verification.json', 'final-BlogController.php', 'final-BlogTagFilterTest.php'}
    assert required <= artifacts.keys() and len(artifacts) <= 160, 'Fresh-agent inventory incomplete or unbounded'
    total = 0
    for name, row in artifacts.items():
        relative = Path(name)
        assert name and not relative.is_absolute() and '..' not in relative.parts, 'Invalid agent artifact path'
        path = directory/relative
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()), 'Agent artifact absent or escaped'
        size = path.stat().st_size
        assert size == row['size'] and size <= 5_000_000, 'Agent artifact size mismatch or unbounded'
        total += size
        assert total <= 16_000_000 and sha(path) == row['sha256'], 'Agent artifact hash mismatch or aggregate bound exceeded'
    outputs = index.get('outputs', {})
    assert set(outputs) == {CONTROLLER, TEST}, 'Fresh agent must bind repaired controller and regression test'
    for path, expected in ((CONTROLLER, task['final_controller_sha256']), (TEST, task['files'][TEST]['sha256'])):
        row = outputs[path]
        assert row['artifact'] in artifacts and row['sha256'] == artifacts[row['artifact']]['sha256'] == expected, 'Replay task differs from fresh-agent output'
    records = [json.loads(line) for line in (directory/'mcp/mcp.jsonl').read_text().splitlines() if line]
    calls = [row for row in records if row.get('tool') == 'serena_repl']
    reads = [n for n, row in enumerate(calls) if 's.lsp.find_symbol(' in row.get('arguments', {}).get('code', '') and 'include_body=True' in row['arguments']['code']]
    edits = [n for n, row in enumerate(calls) if 's.edit.replace_symbol_body(' in row.get('arguments', {}).get('code', '')
             and any(block.get('text') == 'OK' for block in row.get('result', {}).get('content', []))]
    assert reads and edits and min(reads) < min(edits), 'No fresh semantic retrieval followed by successful edit'
    runtime = verify_runtime_result(json.loads((directory/'runtime-result.json').read_text()))
    public = json.loads((directory/'public-invocation.json').read_text())
    assert public['run_id'] == index['run_id'] and public['status'] in ('findings', 'clean') and public['exit'] == public['native_exit'] in (0, 1), 'Fresh public analysis incomplete'
    comparisons = {name: compare_native(json.loads((directory/('before-'+name+'.stdout')).read_text())['issues'],
                                       json.loads((directory/('after-'+name+'.stdout')).read_text())['issues']) for name in ('analyze', 'lint')}
    result = json.loads((directory/'result.json').read_text())
    assert result.get('status') == 'pass' and result.get('kind') == 'fresh_adaptive_agent', 'Fresh-agent result incomplete'
    return {'status': 'pass', 'kind': 'Verified retained adaptive trace, distinct from replay', 'run_id': index['run_id'],
            'index_sha256': sha(index_path), 'artifacts': len(artifacts), 'artifact_bytes': total,
            'successful_semantic_edits': len(edits), 'runtime': runtime, 'native': comparisons}
