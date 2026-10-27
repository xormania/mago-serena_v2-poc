"""Independent expectations derived from pinned input files, never LSP answers."""
import difflib
from pathlib import Path

DEMO_RENAME = {'src/Repository/PostRepository.php': 1, 'src/Controller/BlogController.php': 1}


def snapshot(root):
    root = Path(root)
    return {str(p.relative_to(root)): p.read_bytes() for directory in ('src', 'tests', 'config', 'templates', 'translations')
            for p in (root / directory).rglob('*') if p.is_file() and p != root/'config/reference.php'}


def verify_rename(before, root, evidence):
    after = snapshot(root)
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    assert changed == set(DEMO_RENAME), f'Unexpected changed files: {changed}'
    diff = []
    for path, count in DEMO_RENAME.items():
        old = before[path]
        assert old.count(b'findLatest') == count
        assert after[path] == old.replace(b'findLatest', b'findLatestPublished'), path
        diff.extend(difflib.unified_diff(old.decode().splitlines(True), after[path].decode().splitlines(True), fromfile='a/'+path, tofile='b/'+path))
    Path(evidence, 'rename.diff').write_text(''.join(diff))
    return sorted(changed)


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
