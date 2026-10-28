"""Non-secret build identity, captured inside the image."""
import hashlib
import json
from pathlib import Path
import subprocess

def version(*args):
    return subprocess.check_output(args, text=True).splitlines()[0]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

lock = json.loads(Path('/opt/poc/toolchain.lock.json').read_text())
mago_enabled = Path('/opt/mago-candidate-enabled').read_text().strip()
if mago_enabled not in ('0', '1'):
    raise RuntimeError('Invalid Mago candidate build selection')
serena_api = Path('/opt/venv/lib/python3.12/site-packages/serena/repl/api/lsp_api.py')
candidates = {
    'mago_lsp_extensions': {
        'base': Path('/opt/mago-source.sha').read_text().strip(),
        'patch_sha256': Path('/opt/mago-patch.sha256').read_text().split()[0],
        'enabled': mago_enabled == '1',
    },
    'serena_symbol_references': {
        'base': lock['sources']['serena'],
        'patch_sha256': sha('/opt/poc/patches/serena-symbol-references.patch'),
        'file_sha256': sha(serena_api),
        'enabled': True,
    },
}

print(json.dumps({
    "lock": lock,
    "candidates": candidates,
    "php": version('php', '-v'), "python": version('python3', '--version'),
    "uv": version('uv', '--version'), "composer": version('composer', '--version'),
    "mago": version('mago', '--version'),
    "mago_source_sha": Path('/opt/mago-source.sha').read_text().strip(),
    "rust_build_version": Path('/opt/mago-rust-version.txt').read_text().strip(),
    "cargo_lock_sha256": Path('/opt/mago-cargo-lock.sha256').read_text().split()[0],
    "mago_binary_sha256": sha('/usr/local/bin/mago'),
    "mago_baseline_binary_sha256": sha('/usr/local/bin/mago-baseline'),
    "python_lock_sha256": sha('/opt/poc/uv.lock'),
}, indent=2))
