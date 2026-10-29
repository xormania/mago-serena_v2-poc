"""Check native graph forwarding and the exact candidate Serena facade patch."""
import ast
from contextlib import contextmanager
import importlib.util
import inspect
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "adapter/src"))
from serena_mago.server import MagoServer
from serena.repl.api import lsp_api
from serena.repl.facade import ApiScope, Facade

spec = importlib.util.spec_from_file_location("apply_serena", ROOT / "patches/apply_serena.py")
apply_serena = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_serena)


class NativeGraphForwarding(unittest.TestCase):
    def setUp(self):
        self.value = MagoServer.__new__(MagoServer)
        self.value.capabilities = {"experimental": {"symbolReferencesProvider": True}}
        self.response = {"source": {"symbol": "App\\Repository\\TagRepository", "member": "__construct"},
                         "references": [{"kind": "body", "target": {
                             "symbol": "Doctrine\\Bundle\\DoctrineBundle\\Registry", "member": ""}}]}
        self.send = Mock(return_value=self.response)
        self.value.server = SimpleNamespace(send_request=self.send)
        self.opened = []

        @contextmanager
        def opened(path):
            self.opened.append(path)
            yield SimpleNamespace(uri="file:///app/" + path)

        self.value._open_file_context = opened

    def query(self):
        return self.value.request_symbol_references("src/Repository/TagRepository.php",
                                                   "App\\Repository\\TagRepository", "__construct")

    def test_preserves_raw_native_response_without_positions_or_added_edges(self):
        self.assertIs(self.query(), self.response)
        self.send.assert_called_once_with("mago/symbolReferences", {
            "textDocument": {"uri": "file:///app/src/Repository/TagRepository.php"},
            "symbol": "App\\Repository\\TagRepository", "member": "__construct"})
        self.assertEqual(self.opened, ["src/Repository/TagRepository.php"])

    def test_changed_graph_is_queried_again_and_empty_stays_empty(self):
        self.assertIs(self.query(), self.response)
        empty = {"source": self.response["source"], "references": []}
        self.send.return_value = empty
        self.assertIs(self.query(), empty)
        self.assertEqual(self.send.call_count, 2)

    def test_baseline_capability_cannot_silently_claim_enrichment(self):
        self.value.capabilities = {}
        with self.assertRaisesRegex(RuntimeError, "does not support"):
            self.query()
        self.send.assert_not_called()

    def test_native_failure_is_not_replaced_by_last_good_graph(self):
        self.query()
        self.send.side_effect = RuntimeError("external host php: analysis unavailable")
        with self.assertRaisesRegex(RuntimeError, "external host php"):
            self.query()

    def test_malformed_response_fails_explicitly(self):
        for response in (None, [], {"references": None}):
            self.send.return_value = response
            with self.subTest(response=response), self.assertRaisesRegex(RuntimeError, "Malformed"):
                self.query()


class SerenaFacadePatch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "serena/repl/api/lsp_api.py"
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(Path(inspect.getfile(lsp_api)).read_bytes())
        # CI runs inside the patched image; restore only this owned temporary
        # copy so the same test still exercises first application and the guard.
        if apply_serena.digest(self.target) == apply_serena.CANDIDATE_SHA256:
            subprocess.run(["git", "apply", "--reverse", str(ROOT / "patches/serena-symbol-references.patch")],
                           cwd=self.root, check=True)

    def patched_api(self):
        apply_serena.apply(self.root)
        tree = ast.parse(self.target.read_text())
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "LspApi")
        method = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == "get_symbol_references")
        namespace = vars(lsp_api).copy()
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(self.target), "exec"), namespace)
        api_class = type("CandidateLspApi", (lsp_api.LspApi,), {"get_symbol_references": namespace[method.name]})
        project = SimpleNamespace(validate_relative_path=Mock(), ls_sync_file_system_changes=Mock())
        agent = SimpleNamespace(get_active_project_or_raise=lambda: project)
        api = api_class(agent)
        server = SimpleNamespace(request_symbol_references=Mock(return_value={"references": []}))
        retriever = SimpleNamespace(get_language_server=Mock(return_value=server))
        api._create_symbol_retriever = lambda: retriever
        return api, project, server

    def test_exact_base_application_and_idempotence(self):
        apply_serena.apply(self.root)
        self.assertEqual(apply_serena.digest(self.target), apply_serena.CANDIDATE_SHA256)
        apply_serena.apply(self.root)
        self.target.write_text(self.target.read_text() + "\n# different source\n")
        with self.assertRaisesRegex(RuntimeError, "exact pinned base"):
            apply_serena.apply(self.root)

    def test_method_is_discoverable_and_forwards_real_backend_data(self):
        api, project, server = self.patched_api()
        facade = Facade.from_api(api, ApiScope())
        self.assertIn("get_symbol_references", facade.enabled_method_names)
        self.assertIn("no source positions", facade.describe_member("get_symbol_references"))
        result = api.get_symbol_references("src/Repository/TagRepository.php", "App\\Repository\\TagRepository", "__construct")
        self.assertIs(result, server.request_symbol_references.return_value)
        project.validate_relative_path.assert_called_once_with("src/Repository/TagRepository.php")
        project.ls_sync_file_system_changes.assert_called_once_with()
        server.request_symbol_references.assert_called_once_with("src/Repository/TagRepository.php", "App\\Repository\\TagRepository", "__construct")

    def test_other_backend_is_explicitly_unsupported(self):
        api, _, server = self.patched_api()
        del server.request_symbol_references
        with self.assertRaisesRegex(ValueError, "does not support"):
            api.get_symbol_references("src/Other.php", "Other")


if __name__ == "__main__":
    unittest.main()
