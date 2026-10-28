"""Narrow task-delta and suite assertions; the original verifier stays unchanged."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

COMMAND = 'src/Command/TagsCountCommand.php'
TEST = 'tests/Command/TagsCountCommandTest.php'
TARGETS = (COMMAND, TEST)
SYMBOL = r'App\Command\TagsCountCommand'
REPOSITORY = r'App\Repository\TagRepository'
REFERENCE = '.mago/container-reference.dev.json'
FEATURE_IDS = {
    r'App\Tests\Command\TagsCountCommandTest::testEmptyDatabase',
    r'App\Tests\Command\TagsCountCommandTest::testPopulatedDatabase',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def task_inputs(root):
    directory = Path(root)/'fixtures/slice2'
    task = json.loads((directory/'task.json').read_text())
    assert task.get('schema') == 1 and task.get('command') == 'app:tags:count', 'Wrong task declaration'
    assert task.get('stdout') == 'Tag count: N\n' and task.get('success_exit') == 0, 'Wrong behavioral contract'
    assert set(task['files']) == set(TARGETS), 'Task must declare exactly the command and its test'
    for target, row in task['files'].items():
        assert row['asset'] == Path(target).name and sha(directory/row['asset']) == row['sha256'], 'Task output changed: '+target
    return task


def validate_agent_evidence(root, task):
    """Bind replay outputs to the retained fresh session without executing it."""
    directory = Path(root)/'docs/evidence/slice2/fresh-agent'
    index_path = directory/'index.json'
    assert index_path.is_file() and not index_path.is_symlink() and index_path.stat().st_size <= 100_000, 'Fresh-agent evidence index absent or unbounded'
    index = json.loads(index_path.read_text())
    assert index.get('schema') == 1 and index.get('status') == 'pass', 'Fresh-agent route did not pass'
    assert index.get('kind') == 'fresh_adaptive_agent' and index.get('route') == 'host MCP -> Serena REPL -> Mago', 'Scripted replay is not fresh-agent evidence'
    artifacts = index.get('artifacts', {})
    required = {'mcp/mcp.jsonl', 'initial-source.json', 'initial-application.json.gz', 'application-delta.json',
                'native-tool.json', 'generated-TagsCountCommand.php',
                'final-TagsCountCommand.php', 'final-TagsCountCommandTest.php',
                'public-invocation.json', 'public-graph.json', 'native-comparison.json',
                'before-analyze.stdout', 'after-analyze.stdout', 'before-lint.stdout', 'after-lint.stdout',
                'suite-verification.json', 'runtime-result.json', 'defective-restored.json', 'result.json'}
    assert required <= artifacts.keys() and len(artifacts) <= 128, 'Fresh-agent artifact inventory incomplete or unbounded'
    total = 0
    for name, row in artifacts.items():
        relative = Path(name)
        assert name and not relative.is_absolute() and '..' not in relative.parts, 'Invalid agent artifact path'
        path = directory/relative
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(directory.resolve()), 'Agent artifact absent or escaped: '+name
        size = path.stat().st_size
        assert size == row['size'] and size <= 5_000_000, 'Agent artifact size mismatch or unbounded: '+name
        total += size
        assert total <= 12_000_000, 'Fresh-agent evidence exceeds aggregate bound'
        assert sha(path) == row['sha256'], 'Agent artifact hash mismatch: '+name
    assert set(index.get('outputs', {})) == set(TARGETS), 'Fresh agent did not produce the exact declared task delta'
    for target in TARGETS:
        output = index['outputs'][target]
        assert output['artifact'] in artifacts and output['sha256'] == artifacts[output['artifact']]['sha256'], 'Unbound fresh-agent output'
        assert output['sha256'] == task['files'][target]['sha256'], 'Replay task differs from fresh-agent output: '+target
    records = [json.loads(line) for line in (directory/'mcp/mcp.jsonl').read_text().splitlines() if line]
    calls = [row for row in records if row.get('tool') == 'serena_repl']
    retrievals = [number for number, row in enumerate(calls)
                  if 's.lsp.find_symbol(' in row.get('arguments', {}).get('code', '') and 'include_body=True' in row['arguments']['code']]
    edits = [number for number, row in enumerate(calls)
             if 's.edit.replace_symbol_body(' in row.get('arguments', {}).get('code', '')
             and any(block.get('text') == 'OK' for block in row.get('result', {}).get('content', []))]
    assert retrievals and edits and min(retrievals) < min(edits), 'Fresh session has no observed semantic retrieval followed by a successful edit'
    public = json.loads((directory/'public-invocation.json').read_text())
    assert public['status'] in ('findings', 'clean') and public['exit'] == public['native_exit'] in (0, 1), 'Fresh agent did not complete public enriched analysis'
    assert public['run_id'] == index['run_id'], 'Fresh public evidence belongs to another run'
    initial_source = json.loads((directory/'initial-source.json').read_text())
    assert initial_source['run']['run_id'] == index['run_id'] and initial_source['run']['app'] == public['host_workspace'], 'Fresh initial source belongs to another workspace'
    from evidence import digest
    with gzip.open(directory/'initial-application.json.gz', 'rb') as stream:
        raw = stream.read(5_000_001)
    assert len(raw) <= 5_000_000, 'Initial application manifest exceeds bound'
    initial_application = json.loads(raw)
    delta = json.loads((directory/'application-delta.json').read_text())
    assert digest(initial_application) == delta['initial_sha256'], 'Initial application manifest digest differs'
    for path, change in delta['changed_entries'].items():
        assert initial_application['entries'].get(path) == change['before'], 'Application delta does not match its initial manifest'
        if change['after'] is None:
            initial_application['entries'].pop(path, None)
        else:
            initial_application['entries'][path] = change['after']
    assert digest(initial_application) == delta['final_sha256'] == public['application_sha256'], 'Public analysis is not bound to the complete final application manifest'
    for target in TARGETS:
        assert public['source_sha256'][target] == task['files'][target]['sha256'], 'Public analysis did not use fresh final task source'
    graph = json.loads((directory/'public-graph.json').read_text())
    assert graph['symbols'][SYMBOL]['declaration']['location']['file'] == COMMAND, 'Fresh graph omitted the generated command'
    assert any(ref['target'] == REPOSITORY.lower() and ref['kind'] == 'Signature'
               for ref in graph['symbols'][SYMBOL]['references']), 'Fresh graph omitted the repository signature'
    assert any(ref['target'] == r'doctrine\bundle\doctrinebundle\registry' and ref['kind'] == 'Body'
               for ref in graph['symbols'][REPOSITORY]['references']), 'Fresh graph lacks the compiled framework contribution'
    tool = json.loads((directory/'native-tool.json').read_text())
    assert tool['revision'] == public['tool']['revision'] == public['tool']['sdk_source'] == '46df50c96d93d0ac3655c116c375574277cf0b30', 'Fresh-agent executable and SDK identity differ'
    comparisons = {}
    for name in ('analyze', 'lint'):
        comparisons[name] = compare_native(json.loads((directory/('before-'+name+'.stdout')).read_text())['issues'],
                                           json.loads((directory/('after-'+name+'.stdout')).read_text())['issues'])
    result = json.loads((directory/'result.json').read_text())
    assert result.get('status') == 'pass' and result.get('kind') == 'fresh_adaptive_agent', 'Fresh agent verification incomplete'
    return {'status': 'pass', 'kind': 'verified retained fresh-agent provenance, distinct from this replay',
            'run_id': index['run_id'], 'index_sha256': sha(index_path), 'artifacts': len(artifacts),
            'artifact_bytes': total, 'successful_semantic_edits': len(edits), 'native': comparisons}


def verify_task_delta(before, after, task, *, reference_sha256):
    """Permit two exact new PHP files and one freshly sealed framework export."""
    previous, current = before['entries'], after['entries']
    changed = {p for p in previous.keys() | current.keys() if previous.get(p) != current.get(p)}
    assert not (changed - set(TARGETS) - {REFERENCE}), 'Unexpected application task delta: '+str(sorted(changed))
    for target in TARGETS:
        assert target not in previous, 'Task target already existed before Maker: '+target
        row = current.get(target, {})
        assert row.get('kind') == 'file' and row.get('mode') == 0o644, 'Wrong task file type/mode: '+target
        assert row.get('sha256') == task['files'][target]['sha256'], 'Unexpected task output: '+target
    reference = current.get(REFERENCE, {})
    assert reference.get('kind') == 'file' and reference.get('sha256') == reference_sha256, 'Unbound compiled reference'
    assert reference.get('mode') == previous[REFERENCE]['mode'], 'Compiled reference mode changed'
    return {'status': 'pass', 'changed': sorted(changed), 'declared_task_files': list(TARGETS),
            'compiled_reference_sha256': reference_sha256, 'global_verifier_modified': False}


def compare_native(before, after):
    """Counts alone cannot distinguish a removed finding from a new one."""
    old = Counter(json.dumps(issue, sort_keys=True) for issue in before)
    new = Counter(json.dumps(issue, sort_keys=True) for issue in after)
    introduced, removed = new-old, old-new
    assert not introduced and not removed, 'Native diagnostic multiset changed: introduced='+str(list(introduced))+' removed='+str(list(removed))
    selected = [issue for issue in after if any(
        annotation.get('span', {}).get('file_id', {}).get('name') in TARGETS
        for annotation in issue.get('annotations', []))]
    assert not selected, 'New task PHP has native findings: '+str(selected)
    return {'before': len(before), 'after': len(after), 'introduced': [], 'removed': [],
            'task_findings': [], 'comparison': 'Complete diagnostic bodies as an order-independent multiset'}


def verify_suites(original, combined, junit, projection):
    """Verify the entire suite and separately retain the original identity set."""
    from verifier import verify_suite
    originals = {case['id']: case for case in original['cases']}
    all_cases = {case['id']: case for case in combined['cases']}
    assert {key: all_cases.get(key) for key in originals} == originals, 'Original suite identities changed'
    assert set(all_cases)-set(originals) == FEATURE_IDS, 'Unexpected feature-test identities'
    for path, digest in original['source_sha256'].items():
        assert combined['source_sha256'].get(path) == digest, 'Original test/configuration bytes changed: '+path
    complete = verify_suite(combined, junit)
    # The unchanged verifier requires an exact identity set. Project only the two
    # declared new cases out of a retained copy, then apply that same verifier.
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
            'feature': {'tests': len(FEATURE_IDS), 'identities': sorted(FEATURE_IDS),
                        'assertions': complete['assertions']-retained['assertions']},
            'original_projection': str(projection)}
