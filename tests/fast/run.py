"""Credential-free fast checks; dependencies come from the existing uv lock."""
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT/'tests/integration', ROOT/'adapter/src', ROOT/'tools/ci'):
    sys.path.insert(0, str(path))


if __name__ == '__main__':
    started = time.monotonic()
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests/fast'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = Path(os.environ.get('POC_FAST_EVIDENCE', ROOT/'artifacts/fast'))
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence/'results.json').write_text(json.dumps({
        'schema': 1, 'kind': 'deterministic_fast_tests', 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors),
        'skipped': len(result.skipped), 'elapsed_s': round(time.monotonic()-started, 3),
        'pass': result.wasSuccessful() and not result.skipped,
    }, indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful() or bool(result.skipped))
