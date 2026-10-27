"""A real, bounded stdio LSP client. Wire frames and stderr are evidence."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from trace import BoundedJsonl


class LspError(RuntimeError):
    pass


class LspClient:
    def __init__(self, command, root, evidence):
        self.root = Path(root).resolve()
        self.evidence = Path(evidence)
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.log = BoundedJsonl(self.evidence / 'direct-lsp.jsonl')
        self.stderr = (self.evidence / 'direct-lsp.stderr').open('w')
        self.process = subprocess.Popen(command, cwd=root, env={**os.environ, 'MAGO_EXPERIMENTAL_SERVER': '1'},
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        self.messages = queue.Queue()
        self.notifications = []
        self.next_id = 1
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                headers = {}
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        raise EOFError(f'LSP exited ({self.process.poll()})')
                    if line in (b'\r\n', b'\n'):
                        break
                    key, val = line.decode().split(':', 1)
                    headers[key.lower()] = val.strip()
                length = int(headers['content-length'])
                body = bytearray()
                while len(body) < length:
                    part = self.process.stdout.read(length - len(body))
                    if not part:
                        raise EOFError('Truncated LSP frame')
                    body.extend(part)
                msg = json.loads(body)
                self.messages.put(msg)
        except Exception as exc:
            self.messages.put(exc)

    def send(self, message):
        self.log.write(json.dumps({'direction': 'send', 'message': message}) + '\n')
        self.log.flush()
        payload = json.dumps({'jsonrpc': '2.0', **message}).encode()
        self.process.stdin.write(f'Content-Length: {len(payload)}\r\n\r\n'.encode() + payload)
        self.process.stdin.flush()

    def notify(self, method, params):
        self.send({'method': method, 'params': params})

    def receive(self, timeout):
        msg = self.messages.get(timeout=timeout)
        if isinstance(msg, Exception):
            raise msg
        self.log.write(json.dumps({'direction': 'receive', 'message': msg}) + '\n')
        self.log.flush()
        if 'method' in msg and 'id' in msg:
            self.send({'id': msg['id'], 'result': None})
        elif 'method' in msg:
            self.notifications.append(msg)
        return msg

    def request(self, method, params, timeout=60):
        request_id = self.next_id
        self.next_id += 1
        self.send({'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self.receive(max(0.01, deadline - time.monotonic()))
            if msg.get('id') == request_id and 'method' not in msg:
                if 'error' in msg:
                    raise LspError(json.dumps(msg['error']))
                return msg.get('result')
        raise TimeoutError(method)

    def initialize(self):
        response = self.request('initialize', {
            'processId': os.getpid(), 'rootUri': self.root.as_uri(),
            'workspaceFolders': [{'uri': self.root.as_uri(), 'name': self.root.name}],
            'capabilities': {'general': {'positionEncodings': ['utf-16']},
                             'textDocument': {'documentSymbol': {'hierarchicalDocumentSymbolSupport': True}},
                             'workspace': {'workspaceEdit': {'documentChanges': True}}},
        })
        self.notify('initialized', {})
        (self.evidence / 'capabilities.json').write_text(json.dumps(response, indent=2))
        return response

    def open(self, path):
        absolute = self.root / path
        self.notify('textDocument/didOpen', {'textDocument': {
            'uri': absolute.as_uri(), 'languageId': 'php', 'version': 1, 'text': absolute.read_text(),
        }})

    def close(self):
        try:
            self.request('shutdown', None, timeout=5)
            self.notify('exit', None)
            self.process.wait(timeout=5)
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait()
            self.log.close()
            self.stderr.close()
