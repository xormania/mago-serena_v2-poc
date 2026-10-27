"""Independent fixture, complete application and original-suite expectations.

The manifest records bytes, file type, permission bits and symbolic-link targets;
it never follows symbolic links. Owners, mtimes and inode numbers are deliberately
not compared: copying a disposable fixture changes them without changing behavior.
Only the explicitly named mutable caches/state/databases below are excluded.
Installed dependencies, root configuration, entrypoints and environment files are
included. Baselines belong outside the editable application (CI mounts /trusted
read-only), and must be captured before handing it to a model or semantic edits.
"""
import base64
from collections import Counter
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET

DEMO_RENAME = {'src/Repository/PostRepository.php': 1, 'src/Controller/BlogController.php': 1}
EXCLUDED_TREES = ('.git', '.serena/cache', '.serena/memories', '.phpunit.cache', 'var')
EXCLUDED_FILES = ('config/reference.php',)
DATABASES = ('data/database.sqlite', 'data/database_test.sqlite')


def _excluded(path):
    return (any(path == name or path.startswith(name + '/') for name in EXCLUDED_TREES)
            or path in EXCLUDED_FILES
            or any(path == name + suffix for name in DATABASES for suffix in ('', '-shm', '-wal', '-journal')))


def _sha256(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def snapshot(root):
    root = Path(root).resolve()
    entries = {}

    def walk(directory):
        for path in sorted(directory.iterdir()):
            name = path.relative_to(root).as_posix()
            if _excluded(name):
                continue
            info = path.lstat()
            entry = {'mode': stat.S_IMODE(info.st_mode)}
            if stat.S_ISLNK(info.st_mode):
                entry.update(kind='symlink', target=os.readlink(path))
            elif stat.S_ISDIR(info.st_mode):
                entry['kind'] = 'directory'
            elif stat.S_ISREG(info.st_mode):
                entry.update(kind='file', size=info.st_size, sha256=_sha256(path))
            else:
                # FIFOs/devices/sockets are not valid fixture inputs.
                raise AssertionError(f'Unexpected special application file: {name}')
            entries[name] = entry
            if entry['kind'] == 'directory':
                walk(path)

    walk(root)
    sources = {}
    for name in DEMO_RENAME:
        if entries.get(name, {}).get('kind') == 'file':
            sources[name] = base64.b64encode((root / name).read_bytes()).decode('ascii')
    return {'schema': 2, 'entries': entries, 'rename_sources_base64': sources,
            'exclusions': {'trees': list(EXCLUDED_TREES), 'files': list(EXCLUDED_FILES),
                           'databases_and_sqlite_sidecars': list(DATABASES)}}


def _validate_snapshot(value):
    assert value.get('schema') == 2 and isinstance(value.get('entries'), dict), 'Missing complete application manifest'
    assert value.get('exclusions') == {'trees': list(EXCLUDED_TREES), 'files': list(EXCLUDED_FILES),
                                       'databases_and_sqlite_sidecars': list(DATABASES)}, 'Unexpected manifest exclusions'
    for path in value['entries']:
        assert path and not path.startswith('/') and '..' not in Path(path).parts, f'Invalid manifest path: {path}'
    for path in DEMO_RENAME:
        entry = value['entries'].get(path, {})
        assert entry.get('kind') == 'file', f'Missing original rename source: {path}'
        data = base64.b64decode(value['rename_sources_base64'][path], validate=True)
        assert hashlib.sha256(data).hexdigest() == entry['sha256'] and len(data) == entry['size'], f'Unbound original source: {path}'


def save_snapshot(value, path, app_root=None):
    _validate_snapshot(value)
    path = Path(path)
    if app_root is not None:
        assert not path.resolve().is_relative_to(Path(app_root).resolve()), 'Baseline must be outside editable application'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as output:
        json.dump(value, output, sort_keys=True, indent=2)
        output.write('\n')


def load_snapshot(path):
    value = json.loads(Path(path).read_text())
    _validate_snapshot(value)
    return value


def verify_rename(before, root, evidence):
    _validate_snapshot(before)
    after = snapshot(root)
    previous, current = before['entries'], after['entries']
    changed = {p for p in previous.keys() | current.keys() if previous.get(p) != current.get(p)}
    assert changed == set(DEMO_RENAME), f'Unexpected changed files: {changed}'
    diff = []
    for path, count in DEMO_RENAME.items():
        old = base64.b64decode(before['rename_sources_base64'][path], validate=True)
        assert old.count(b'findLatest') == count
        expected = old.replace(b'findLatest', b'findLatestPublished')
        assert current[path] == {**previous[path], 'size': len(expected), 'sha256': hashlib.sha256(expected).hexdigest()}, f'Unexpected source or metadata change: {path}'
        assert Path(root, path).read_bytes() == expected, path
        diff.extend(difflib.unified_diff(old.decode().splitlines(True), expected.decode().splitlines(True), fromfile='a/'+path, tofile='b/'+path))
    Path(evidence).mkdir(parents=True, exist_ok=True)
    Path(evidence, 'rename.diff').write_text(''.join(diff))
    return sorted(changed)


def _xml(path):
    raw = Path(path).read_bytes()
    assert len(raw) <= 8_000_000, 'Suite XML exceeds evidence limit'
    assert b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'XML declarations are not allowed'
    return ET.fromstring(raw)


def _fixture_methods(root):
    """Discover the pinned Demo's public test methods without consulting LSP/JUnit.

    This intentionally supports this fixture's test* method convention, not a
    general PHP parser. Dataset expansion is supplied by PHPUnit's trusted
    pre-edit --list-tests-xml run and checked against these source declarations.
    """
    methods, sources = {}, {}
    root = Path(root)
    for path in sorted((root / 'tests').rglob('*.php')):
        assert not path.is_symlink(), 'Trusted test source must not be a symlink'
        relative = path.relative_to(root).as_posix()
        sources[relative] = _sha256(path)
        source = path.read_text()
        namespace = re.search(r'^namespace\s+([^;]+);', source, re.M)
        cls = re.search(r'^(?:(?:final|abstract)\s+)?class\s+(\w+)', source, re.M)
        if not namespace or not cls:
            continue
        class_name = namespace[1] + '\\' + cls[1]
        for method in re.finditer(r'public\s+function\s+(test\w+)\s*\(', source):
            methods[class_name + '::' + method[1]] = {'file': relative, 'line': source[:method.start()].count('\n') + 1}
    sources['phpunit.dist.xml'] = _sha256(root / 'phpunit.dist.xml')
    assert methods, 'No trusted fixture tests discovered'
    return methods, sources


def expected_suite(list_xml, trusted_fixture):
    """Bind trusted PHPUnit dataset identities to original fixture methods/files."""
    methods, sources = _fixture_methods(trusted_fixture)
    tree = _xml(list_xml)
    cases, seen = [], set()
    for cls in tree.findall('.//{*}testClass'):
        for method in cls.findall('{*}testMethod'):
            identity = method.attrib['id']
            base = cls.attrib['name'] + '::' + method.attrib['name']
            assert identity == base or identity.startswith(base + '#'), f'Unexpected listed identity: {identity}'
            assert base in methods, f'Test is not in trusted fixture: {base}'
            assert identity not in seen, f'Duplicate listed test identity: {identity}'
            seen.add(identity)
            expected = methods[base]
            assert Path(cls.attrib['file']).as_posix() == '/app/' + expected['file'], f'Unexpected listed test file: {cls.attrib}'
            cases.append({'id': identity, **expected})
    assert {case['id'].partition('#')[0] for case in cases} == set(methods), 'Trusted list omits or adds original test methods'
    assert cases, 'Missing trusted test identities'
    return {'schema': 1, 'configuration': 'phpunit.dist.xml', 'source_sha256': sources,
            'list_xml_sha256': _sha256(list_xml), 'cases': sorted(cases, key=lambda case: case['id'])}


def verify_suite(expected, junit_xml):
    """Require exactly the original class/method/dataset/file identities to pass."""
    assert expected.get('schema') == 1 and expected.get('cases'), 'Missing expected original suite inventory'
    expected_cases = expected['cases']
    source_hashes = expected.get('source_sha256', {})
    assert expected.get('configuration') == 'phpunit.dist.xml', 'Missing original fixture configuration'
    required_sources = {'phpunit.dist.xml', *(case['file'] for case in expected_cases)}
    assert required_sources <= source_hashes.keys(), 'Expected suite is missing trusted source hashes'
    assert all(re.fullmatch('[0-9a-f]{64}', digest) for digest in source_hashes.values()), 'Invalid trusted suite source hashes'
    assert re.fullmatch('[0-9a-f]{64}', expected.get('list_xml_sha256', '')), 'Missing trusted test list hash'
    assert len({case['id'] for case in expected_cases}) == len(expected_cases), 'Duplicate trusted test identity'
    tree = _xml(junit_xml)
    suites = list(tree.iter('testsuite'))
    assert suites and suites[0].attrib.get('name') == '/app/' + expected['configuration'], 'Original PHPUnit configuration did not run'
    for node in tree.iter():
        assert node.tag not in ('error', 'failure', 'skipped', 'incomplete', 'risky', 'warning'), f'Original suite has {node.tag}'
        if node.tag == 'testsuite':
            for key in ('errors', 'failures', 'skipped'):
                assert int(node.attrib.get(key, 0)) == 0, f'Original suite has {key}'
    observed, assertions = [], 0
    for case in tree.iter('testcase'):
        name = case.attrib.get('name', '')
        method, marker, dataset = name.partition(' with data set ')
        if marker:
            # PHPUnit 11's event id() uses # for both numeric and named datasets,
            # whereas JUnit renders the latter as `with data set "name"`.
            assert dataset.startswith('#') or (dataset.startswith('"') and dataset.endswith('"')), f'Invalid dataset identity: {name}'
            suffix = dataset if dataset.startswith('#') else '#' + dataset[1:-1]
        else:
            suffix = ''
        identity = case.attrib.get('class', '') + '::' + method + suffix
        file = case.attrib.get('file', '')
        assert file.startswith('/app/tests/'), f'Unexpected executed test file: {file}'
        observed.append({'id': identity, 'file': file.removeprefix('/app/'), 'line': int(case.attrib.get('line', 0))})
        count = int(case.attrib.get('assertions', 0))
        assert count > 0, f'Original test executed no assertions: {identity}'
        assertions += count
    actual_ids = [case['id'] for case in observed]
    duplicates = [key for key, count in Counter(actual_ids).items() if count > 1]
    assert not duplicates, f'Duplicate executed test identities: {duplicates}'
    missing = sorted({case['id'] for case in expected_cases} - set(actual_ids))
    extra = sorted(set(actual_ids) - {case['id'] for case in expected_cases})
    assert not missing and not extra, f'Original suite identities differ: missing={missing}, extra={extra}'
    assert sorted(observed, key=lambda case: case['id']) == expected_cases, 'Original test file/line identities differ'
    assert int(suites[0].attrib['tests']) == len(observed), 'JUnit aggregate count does not match executed identities'
    return {'tests': len(observed), 'assertions': assertions,
            'identities_sha256': hashlib.sha256(json.dumps(expected_cases, sort_keys=True).encode()).hexdigest()}


def position(root, path, text, occurrence=0):
    source = Path(root, path).read_text()
    offsets = []
    start = 0
    while (offset := source.find(text, start)) >= 0:
        offsets.append(offset)
        start = offset + len(text)
    offset = offsets[occurrence]
    line = source[:offset].count('\n')
    col = offset - source.rfind('\n', 0, offset) - 1
    return {'line': line, 'character': col}


def verify_symbol(answer, root, path, token):
    assert len(answer) == 1, answer
    expected = position(root, path, token)
    assert answer[0]['file'] == path, answer
    assert answer[0]['line'] == expected['line'], (answer, expected)
    assert answer[0]['column'] == expected['character'], (answer, expected)
    body = answer[0].get('body')
    if body:
        assert body in Path(root, path).read_text(), 'Reported body must be an exact source substring'
    return answer[0]
