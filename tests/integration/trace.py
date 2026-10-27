"""Bound trace retention without truncating actual protocol traffic."""
import hashlib
import json
from pathlib import Path


class BoundedJsonl:
    def __init__(self, path, max_bytes=2_000_000, max_record_bytes=32_000):
        self.path = Path(path)
        self.stream = self.path.open('w')
        self.max_bytes, self.max_record_bytes = max_bytes, max_record_bytes
        self.written = self.dropped = self.truncated = 0

    def write(self, line):
        data = line.encode()
        if len(data) > self.max_record_bytes:
            data = (json.dumps({'trace_record_truncated': True, 'original_bytes':len(data),
                               'sha256':hashlib.sha256(data).hexdigest(),
                               'excerpt':data[:self.max_record_bytes//2].decode(errors='replace')})+'\n').encode()
            self.truncated += 1
        if self.written + len(data) > self.max_bytes:
            self.dropped += 1
            return
        self.stream.write(data.decode())
        self.written += len(data)

    def flush(self):
        self.stream.flush()

    def close(self):
        if self.stream.closed:
            return
        self.stream.close()
        self.path.with_suffix(self.path.suffix+'.summary.json').write_text(json.dumps({
            'max_bytes':self.max_bytes, 'max_record_bytes':self.max_record_bytes,
            'retained_bytes':self.written, 'dropped_records':self.dropped,
            'truncated_records':self.truncated, 'protocol_traffic_modified':False,
        }, indent=2)+'\n')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
