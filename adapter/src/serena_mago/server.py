"""Bridge full document sync and UTF-16 wire positions to SolidLSP's Python indices.

No semantic answers are synthesized: requests, symbol ranges, references and edits
come from the actual Mago process. The protocol trace retains the wire values.
"""
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
from urllib.parse import unquote, urlparse

from solidlsp.dependency_provider import LanguageServerDependencyProvider
from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_process import StdioLanguageServer

log = logging.getLogger(__name__)


class MagoDependency(LanguageServerDependencyProvider):
    def create_launch_command(self):
        binary = os.environ.get("MAGO_BINARY", "mago")
        resolved = shutil.which(binary)
        if not resolved:
            raise FileNotFoundError(f"Mago executable {binary!r} missing; run ./bin/poc up to build the pinned backend")
        identity = Path("/opt/toolchain-runtime.json")
        if identity.exists():
            expected = json.loads(identity.read_text())["mago_binary_sha256"]
            actual = hashlib.sha256(Path(resolved).read_bytes()).hexdigest()
            if actual != expected:
                raise RuntimeError(f"Mago binary identity mismatch: {resolved}")
        return [resolved, "language-server"]

    def create_launch_command_env(self):
        return {"MAGO_EXPERIMENTAL_SERVER": "1"}


class MagoTransport(StdioLanguageServer):
    """Use SolidLSP's supported transport extension point, without patching it."""

    def __init__(self, *args, owner, **kwargs):
        self.owner = owner
        self.documents = {}
        super().__init__(*args, **kwargs)

    def text(self, uri):
        if uri in self.documents:
            return self.documents[uri]
        if uri and uri.startswith("file:"):
            return Path(unquote(urlparse(uri).path)).read_text(encoding="utf-8")
        raise ValueError(f"Cannot convert position without a file URI: {uri}")

    def convert(self, value, uri=None, *, wire=False):
        if isinstance(value, list):
            return [self.convert(x, uri, wire=wire) for x in value]
        if not isinstance(value, dict):
            return value
        uri = value.get("uri", value.get("targetUri", value.get("textDocument", {}).get("uri", uri)))
        if "line" in value and "character" in value:
            line = self.text(uri).split("\n")[value["line"]]
            col = value["character"]
            if wire:
                col = len(line[:col].encode("utf-16-le")) // 2
            else:
                col = len(line.encode("utf-16-le")[:col * 2].decode("utf-16-le", errors="strict"))
            return {**value, "character": col}
        result = {}
        for key, item in value.items():
            if key == "changes" and isinstance(item, dict):
                result[key] = {u: self.convert(edits, u, wire=wire) for u, edits in item.items()}
            else:
                result[key] = self.convert(item, uri, wire=wire)
        return result

    def send_request(self, method, params=None):
        if method == "initialize":
            return super().send_request(method, params)
        uri = (params or {}).get("textDocument", {}).get("uri")
        response = super().send_request(method, self.convert(params, uri, wire=True))
        return self.convert(response, uri)

    def send_notification(self, method, params=None):
        if method in ("textDocument/didOpen", "textDocument/didChange"):
            uri = params["textDocument"]["uri"]
            if method.endswith("didOpen"):
                self.documents[uri] = params["textDocument"]["text"]
            else:
                changes = params["contentChanges"]
                if any("range" in x for x in changes):
                    text = self.owner.open_file_buffers[uri].contents
                    params = {**params, "contentChanges": [{"text": text}]}
                else:
                    text = changes[-1]["text"]
                self.documents[uri] = text
        super().send_notification(method, params)


class MagoServer(SolidLanguageServer):
    def __init__(self, config, repository_root_path, solidlsp_settings):
        super().__init__(config, repository_root_path, None, "php", solidlsp_settings)

    def _create_dependency_provider(self):
        return MagoDependency(self._custom_settings, self._ls_resources_dir)

    def _create_language_server_interface(self, logging_fn):
        return MagoTransport(
            self._get_process_launch_info(), owner=self, ls_id=self.ls_id,
            determine_log_level=self._determine_log_level, logger=logging_fn,
            start_independent_lsp_process=self.config.start_independent_lsp_process,
        )

    def _create_base_initialize_params(self):
        return {"capabilities": {
            "general": {"positionEncodings": ["utf-16"]},
            "textDocument": {
                "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                "definition": {"linkSupport": True},
                "synchronization": {"didSave": True},
            },
            "workspace": {"workspaceFolders": True, "workspaceEdit": {"documentChanges": True}},
        }}

    def _start_server(self):
        self.server.on_notification("window/logMessage", lambda p: log.info("Mago: %s", p))
        self.server.on_notification("textDocument/publishDiagnostics", lambda p: None)
        self.server.on_notification("$/progress", lambda p: None)
        self.server.on_request("client/registerCapability", lambda p: None)
        self.server.start()
        response = self.server.send.initialize(self._create_initialize_params())
        if response.get("serverInfo", {}).get("name") != "mago-server":
            raise RuntimeError("Selected process is not the Mago language server")
        self.capabilities = response["capabilities"]
        if self.capabilities.get("positionEncoding", "utf-16") != "utf-16":
            raise RuntimeError("Mago selected an unsupported position encoding")
        if self.capabilities.get("textDocumentSync", {}).get("change") != 1:
            raise RuntimeError("Pinned Mago must negotiate full document synchronization")
        if not self.capabilities.get("documentSymbolProvider"):
            raise RuntimeError("Mago did not advertise document symbols")
        self.server.notify.initialized({})
        identity = {"backend": "mago", "pid": self.server._process._popen.pid,
                    "command": self._get_process_launch_info().cmd, "initialize": response,
                    "root": self.repository_root_path}
        log.info("MAGO_BACKEND_IDENTITY %s", json.dumps(identity))
        evidence = os.environ.get("POC_EVIDENCE")
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
            Path(evidence, f"backend-{identity['pid']}.json").write_text(json.dumps(identity, indent=2))

    def _observe_server_notification(self, method, params):
        if method == "textDocument/publishDiagnostics":
            params = self.server.convert(params)
        super()._observe_server_notification(method, params)

    def _supports_pull_diagnostics(self):
        return False

    def _accept_published_diagnostics(self, diagnostics):
        return True  # An empty publication is the evidence that an error cleared.

    def _get_published_diagnostics_wait_timeout(self, pull_diagnostics_failed):
        return 10.0

    def _get_wait_time_for_cross_file_referencing(self):
        return 0  # Mago bootstrap finishes inside initialize.

    def is_ignored_dirname(self, dirname):
        return super().is_ignored_dirname(dirname) or dirname in {"var", ".serena", ".phpunit.cache"}

    def request_rename_symbol_edit(self, relative_file_path, line, column, new_name):
        # Keep the request document open until validation is complete. The base
        # request closes its own context before returning the WorkspaceEdit.
        with self.open_file(relative_file_path):
            edit = super().request_rename_symbol_edit(relative_file_path, line, column, new_name)
            for change in (edit or {}).get("documentChanges", []):
                if "textDocument" not in change:
                    raise ValueError("Mago resource operations are unsupported; no edits applied")
                doc = change["textDocument"]
                buffer = self.open_file_buffers.get(doc["uri"])
                if doc.get("version") is not None and (buffer is None or doc["version"] != buffer.version):
                    raise ValueError("Stale Mago WorkspaceEdit document version; no edits applied")
            return edit
