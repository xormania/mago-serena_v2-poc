"""Non-secret build identity, captured inside the image."""
import hashlib
import json
from pathlib import Path
import subprocess

def version(*args):
    return subprocess.check_output(args, text=True).splitlines()[0]

print(json.dumps({
    "lock": json.loads(Path('/opt/poc/toolchain.lock.json').read_text()),
    "php": version('php', '-v'), "python": version('python3', '--version'),
    "uv": version('uv', '--version'), "composer": version('composer', '--version'),
    "mago": version('mago', '--version'),
    "mago_source_sha": Path('/opt/mago-source.sha').read_text().strip(),
    "rust_build_version": Path('/opt/mago-rust-version.txt').read_text().strip(),
    "cargo_lock_sha256": Path('/opt/mago-cargo-lock.sha256').read_text().split()[0],
    "mago_binary_sha256": hashlib.sha256(Path('/usr/local/bin/mago').read_bytes()).hexdigest(),
    "python_lock_sha256": hashlib.sha256(Path('/opt/poc/uv.lock').read_bytes()).hexdigest(),
}, indent=2))
