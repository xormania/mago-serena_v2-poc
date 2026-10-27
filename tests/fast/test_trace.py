import json
from pathlib import Path
import tempfile
import unittest

from trace import BoundedJsonl


class TraceTests(unittest.TestCase):
    def test_bounded_and_disclosed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trace.jsonl'
            with BoundedJsonl(path, max_bytes=1000, max_record_bytes=100) as log:
                for i in range(100):
                    log.write(json.dumps({'id':i, 'text':'x'*500})+'\n')
            summary = json.loads(path.with_suffix('.jsonl.summary.json').read_text())
            self.assertLessEqual(path.stat().st_size, 1000)
            self.assertEqual(summary['truncated_records'], 100)
            self.assertGreater(summary['dropped_records'], 0)
            self.assertFalse(summary['protocol_traffic_modified'])
            for line in path.read_text().splitlines():
                self.assertTrue(json.loads(line)['trace_record_truncated'])
