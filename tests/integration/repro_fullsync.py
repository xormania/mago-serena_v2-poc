"""Live minimal compatibility reproduction; never substitutes for MCP acceptance.

Run: ./bin/poc exec -- python - < tests/integration/repro_fullsync.py
"""
import json
import logging
import os
from pathlib import Path
import tempfile

from serena_mago.server import MagoServer
from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import LanguageServerConfig, LanguageServerRegistry
from solidlsp.settings import SolidLSPSettings


class UnbridgedMago(MagoServer):
    def _create_language_server_interface(self, logging_fn):
        return SolidLanguageServer._create_language_server_interface(self, logging_fn)

    def _observe_server_notification(self, method, params):
        return SolidLanguageServer._observe_server_notification(self, method, params)


evidence = Path(os.environ.get('POC_EVIDENCE','/evidence'))/'fullsync-reproduction'
evidence.mkdir(parents=True,exist_ok=True)
logging.basicConfig(filename=evidence/'trace.log',level=logging.DEBUG)
outcomes = {}
for cls in (UnbridgedMago, MagoServer):
    with tempfile.TemporaryDirectory(prefix='mago-sync-') as directory:
        root = Path(directory)
        original = '<?php class SyncProbe { public function value(): int { return 7; } }\n'
        (root/'Probe.php').write_text(original)
        (root/'mago.toml').write_text('version = "1"\nphp-version = "8.5"\n[source]\npaths = ["."]\n')
        settings = SolidLSPSettings(solidlsp_dir=str(root/'global'),project_data_path=str(root/'cache'))
        config = LanguageServerConfig(ls_id=LanguageServerRegistry.get_instance().resolve('mago'),trace_lsp_communication=True)
        ls = cls(config,directory,settings)
        ls.set_request_timeout(10)
        try:
            ls.start()
            with ls.open_file('Probe.php'):
                col = original.index('value')
                ls.delete_text_between_positions('Probe.php',{'line':0,'character':col},{'line':0,'character':col+5})
                ls.insert_text_at_position('Probe.php',0,col,'renamed')
                symbols = ls.server.send_request('textDocument/documentSymbol',{'textDocument':{'uri':(root/'Probe.php').as_uri()}})
                outcomes[cls.__name__] = {'advertised_sync':ls.capabilities['textDocumentSync'],'symbols_after_edit':symbols}
        finally:
            ls.stop()
assert 'renamed' not in json.dumps(outcomes['UnbridgedMago']['symbols_after_edit']), outcomes
assert 'renamed' in json.dumps(outcomes['MagoServer']['symbols_after_edit']), outcomes
(evidence/'result.json').write_text(json.dumps(outcomes,indent=2))
print(json.dumps(outcomes,indent=2))
