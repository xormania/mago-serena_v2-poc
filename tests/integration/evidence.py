"""Run-bound inventories: an absent, old, duplicated or skipped check never passes."""
import hashlib
import json
from pathlib import Path
import re

INTEGRATION_REQUIRED = (
    'direct_lsp', 'demo_symbols', 'cross_file_references', 'composer_navigation', 'demo_rename',
    'interface_inheritance', 'invalid_rename', 'semantic_body_edit', 'position_accuracy', 'document_state',
    'diagnostics', 'external_edit', 'repl_persistence', 'partial_execution', 'restart_and_death',
    'negative_backend', 'negative_verifier', 'mago_external_span_control',
)
HOST_REQUIRED = ('fast_tests', 'source_integrity', 'setup_a', 'phpunit_a', 'setup_b', 'phpunit_b',
                 'application_checks', 'executed_identity', 'trusted_baseline', 'workspace_isolation', 'baseline_unchanged', 'cleanup')
REQUIRED = (*HOST_REQUIRED, *INTEGRATION_REQUIRED)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def make_plan(run_id, metadata, *, attempt_id='1'):
    context = digest(metadata)
    return {'schema': 2, 'run_id': run_id, 'attempt_id': attempt_id,
            'context_sha256': context, 'inventory': list(REQUIRED),
            'integration_inventory': list(INTEGRATION_REQUIRED)}


def check_record(plan, name, status='not_exercised', assertion='Not reached', **details):
    return {**{k: plan[k] for k in ('run_id', 'attempt_id', 'context_sha256')},
            'name': name, 'status': status, 'assertion': assertion, **details}


def validate(result, plan, *, integration=False, require_pass=True):
    expected = list(INTEGRATION_REQUIRED if integration else REQUIRED)
    assert plan.get('schema') == 2, 'Missing current trusted plan'
    assert plan.get('inventory') == list(REQUIRED), 'Stale or modified required inventory'
    assert plan.get('integration_inventory') == list(INTEGRATION_REQUIRED), 'Stale integration inventory'
    assert result.get('schema') == 2, 'Missing current result schema'
    for key in ('run_id', 'attempt_id', 'context_sha256'):
        assert result.get(key) == plan.get(key) and result.get(key), f'Wrong or missing {key}'
    assert result.get('inventory') == expected, 'Missing or stale result inventory'
    checks = result.get('checks')
    assert isinstance(checks, list), 'Missing checks'
    names = [c.get('name') for c in checks]
    assert len(names) == len(set(names)), 'Duplicate check result'
    assert set(names) == set(expected), f'Missing/unexpected results: {set(expected) ^ set(names)}'
    for check in checks:
        for key in ('run_id', 'attempt_id', 'context_sha256'):
            assert check.get(key) == plan[key], f'{check.get("name")}: stale/wrong {key}'
        assert check.get('status') in ('pass', 'fail', 'blocked', 'not_exercised'), 'Invalid check status'
        if require_pass:
            assert check['status'] == 'pass', f'{check["name"]}: {check["status"]}: {check.get("assertion", "")}'
    return len(checks)


def result_document(plan, checks, *, integration=False):
    return {**plan, 'inventory': list(INTEGRATION_REQUIRED if integration else REQUIRED), 'checks': checks}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def artifact_hashes(root):
    root = Path(root)
    excluded = {'results.json', 'report.txt', 'evidence-manifest.json'}
    result = {}
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink(), f'Evidence cannot be a symlink: {path}'
        if path.is_file() and path.relative_to(root).as_posix() not in excluded:
            with path.open('rb') as source:
                result[path.relative_to(root).as_posix()] = hashlib.file_digest(source, 'sha256').hexdigest()
    return result


def seal_artifacts(primary, secondary):
    inventory = {'schema': 1, 'primary':artifact_hashes(primary), 'secondary':artifact_hashes(secondary)}
    write_json(Path(primary)/'evidence-manifest.json', inventory)
    return digest(inventory)


def validate_runtime(actual, metadata):
    lock = metadata['toolchain']
    runtime = actual['runtime']
    assert runtime['lock'] == lock, 'Runtime toolchain lock differs'
    assert runtime['mago_source_sha'] == lock['sources']['mago'], 'Wrong compiled Mago source pin'
    assert runtime['cargo_lock_sha256'] == lock['lock_sha256']['mago_cargo'], 'Wrong Mago dependency lock'
    assert runtime['python_lock_sha256'] == lock['lock_sha256']['poc_uv'], 'Wrong Python dependency lock'
    assert runtime['mago_binary_sha256'] == actual['live_mago_binary_sha256'], 'Live Mago binary differs from build identity'
    assert actual['serena_direct_url']['vcs_info']['commit_id'] == lock['sources']['serena'], 'Wrong installed Serena source pin'
    for name, version in lock['versions'].items():
        text = runtime['rust_build_version'] if name == 'rust' else actual['live_versions'][name]
        assert re.search(r'(?<![0-9])'+re.escape(version)+r'(?![0-9])', text), f'Wrong runtime {name} version'
        built = runtime['rust_build_version'] if name == 'rust' else runtime[name]
        assert re.search(r'(?<![0-9])'+re.escape(version)+r'(?![0-9])', built), f'Wrong build {name} version'


def verify_artifacts(primary, secondary, result, metadata):
    primary, secondary = Path(primary), Path(secondary)
    inventory = json.loads((primary/'evidence-manifest.json').read_text())
    assert digest(inventory) == result.get('evidence_manifest_sha256'), 'Missing/stale evidence manifest'
    assert inventory == {'schema':1, 'primary':artifact_hashes(primary), 'secondary':artifact_hashes(secondary)}, 'Missing, added or modified retained evidence'
    records = {row['name']:row for row in result['checks']}
    prefixes = ('adapter/src/', 'tests/', 'docker/', 'config/', 'fixtures/')
    explicit = ('uv.lock', 'pyproject.toml', 'adapter/pyproject.toml', 'toolchain.lock.json')
    expected = {p:row['sha256'] for p,row in metadata['source_manifest'].items() if p.startswith(prefixes) or p in explicit}
    images = []
    for directory, run_id in ((primary,result['run_id']), (secondary,result['run_id']+'-b')):
        actual = json.loads((directory/'executed-identity.json').read_text())
        assert actual['run_id'] == run_id and actual['attempt_id'] == result['attempt_id'], 'Wrong retained execution identity'
        assert actual['installed_files'] == expected, 'Wrong retained installed code inventory'
        assert actual['installed_adapter']['sha256'] == expected['adapter/src/serena_mago/server.py'], 'Wrong retained adapter'
        validate_runtime(actual, metadata)
        images.append(json.loads((directory/'image-identity.json').read_text()))
        baseline = records['trusted_baseline']['detail'][run_id]
        for retained, trusted in (('application-baseline.json','application.json'),('expected-suite.json','expected-suite.json')):
            assert inventory['primary' if directory == primary else 'secondary'][retained] == baseline[trusted], 'Wrong retained trusted baseline'
    assert images == records['executed_identity']['detail'], 'Wrong retained image identity'
    assert images[0]['image_id'] == images[1]['image_id'] and images[0]['image_id'].startswith('sha256:'), 'Missing or inconsistent actual image IDs'
