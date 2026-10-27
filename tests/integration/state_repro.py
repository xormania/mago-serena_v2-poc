"""Cross-file closed-document regression using an actual adapter and Mago.

Run in the PoC image: python /opt/poc/tests/integration/state_repro.py.
Target.php is inspected and closed, externally replaced, then a rename is
requested from Caller.php. The target is never reopened before that request.
"""
import hashlib
import logging
import json
import os
from pathlib import Path
import tempfile
import time

from serena_mago.server import MagoServer
from solidlsp.ls_config import LanguageServerConfig, LanguageServerRegistry
from solidlsp.settings import SolidLSPSettings


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def run(external=True):
    with tempfile.TemporaryDirectory(prefix='mago-closed-state-') as directory:
        root = Path(directory)
        original = '<?php class CloseTarget { /* éé */ public function target(): int { return 7; } }\n'
        # Equal UTF-8 prefix byte length isolates transport text selection from
        # the separate Mago incremental declaration-span defect.
        updated = original.replace('éé', '🧪') if external else original
        caller = '<?php function use_target(CloseTarget $x): int { return $x->target(); }\n'
        target_uri, caller_uri = (root/'Target.php').as_uri(), (root/'Caller.php').as_uri()
        (root/'Target.php').write_text(original)
        (root/'Caller.php').write_text(caller)
        (root/'mago.toml').write_text('version = "1"\nphp-version = "8.5"\n[source]\npaths = ["."]\n')
        settings = SolidLSPSettings(solidlsp_dir=str(root/'global'),project_data_path=str(root/'cache'))
        config = LanguageServerConfig(ls_id=LanguageServerRegistry.get_instance().resolve('mago'),trace_lsp_communication=os.environ.get('POC_TRACE') == '1')
        logging.basicConfig(level=logging.WARNING)
        ls = MagoServer(config,directory,settings)
        ls.set_request_timeout(10)
        try:
            ls.start()
            with ls.open_file('Target.php'):
                inspected = ls.server.send_request('textDocument/documentSymbol', {'textDocument': {'uri': target_uri}})
                assert 'target' in json.dumps(inspected), inspected
            assert target_uri not in ls.open_file_buffers, 'Target must be closed before edit'
            # An unrelated-file request is an ordered protocol barrier after didClose.
            ls.server.send_request('textDocument/documentSymbol', {'textDocument':{'uri':caller_uri}})
            # Atomic replacement also changes the inode and need not preserve mtime ordering.
            temporary = root/'replacement.php'
            temporary.write_text(updated)
            temporary.replace(root/'Target.php')
            ls.server.send_notification('workspace/didChangeWatchedFiles', {'changes':[{'uri':target_uri,'type':2}]})
            with ls.open_file('Caller.php'):
                # Wait on an observable updated cross-file index, without opening Target.
                deadline = time.monotonic() + 10
                while True:
                    refs = ls.server.send_request('textDocument/references', {'textDocument':{'uri':caller_uri},
                        'position':{'line':0,'character':caller.index('target()')},
                        'context':{'includeDeclaration':True}})
                    target_refs = [x for x in (refs or []) if x['uri'] == target_uri]
                    if target_refs and target_refs[0]['range']['start']['character'] >= updated.index('target()'):
                        break
                    if time.monotonic() >= deadline:
                        raise AssertionError(f'Updated cross-file index not ready: {refs}')
                    time.sleep(.05)
                edit = ls.server.send_request('textDocument/rename', {'textDocument':{'uri':caller_uri},
                    'position':{'line':0,'character':caller.index('target()')},'newName':'renamed'})
            assert target_uri not in ls.open_file_buffers, 'Query must never reopen target'
            changes = {x['textDocument']['uri']:x['edits'] for x in edit['documentChanges']}
            actual = changes[target_uri][0]['range']['start']
            expected = {'line':0,'character':updated.index('target()')}
            result = {'target_open_before_query':False,'target_reopened_before_query':False,
                      'original_sha256':digest(original),'disk_sha256':digest(updated),
                      'expected_codepoint_position':expected,'actual_codepoint_position':actual,
                      'edit':edit,'status':'pass' if actual == expected else 'fail','control':'external_nonbmp' if external else 'healthy_unchanged'}
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
            assert actual == expected, f'Closed target converted using stale text: {actual} != {expected}'
            return result
        finally:
            ls.stop()


def run_direct(evidence):
    """Same event sequence against Mago, asserting native UTF-16 coordinates."""
    from lsp_client import LspClient
    with tempfile.TemporaryDirectory(prefix='mago-closed-direct-') as directory:
        root = Path(directory)
        initial = '<?php class CloseTarget { /* éé */ public function target(): int { return 7; } }\n'
        updated = initial.replace('éé','🧪')
        caller = '<?php function use_target(CloseTarget $x): int { return $x->target(); }\n'
        (root/'Target.php').write_text(initial)
        (root/'Caller.php').write_text(caller)
        (root/'mago.toml').write_text('version = "1"\nphp-version = "8.5"\n[source]\npaths = ["."]\n')
        client = LspClient([os.environ.get('MAGO_BINARY','mago'),'language-server'],root,evidence)
        try:
            client.initialize()
            uri = (root/'Target.php').as_uri()
            client.open('Target.php')
            client.request('textDocument/documentSymbol',{'textDocument':{'uri':uri}})
            client.notify('textDocument/didClose',{'textDocument':{'uri':uri}})
            client.request('textDocument/documentSymbol',{'textDocument':{'uri':(root/'Caller.php').as_uri()}})
            (root/'Target.php').write_text(updated)
            client.notify('workspace/didChangeWatchedFiles',{'changes':[{'uri':uri,'type':2}]})
            client.open('Caller.php')
            edit = client.request('textDocument/rename',{'textDocument':{'uri':(root/'Caller.php').as_uri()},
                'position':{'line':0,'character':caller.index('target()')},'newName':'renamed'})
            changes = {x['textDocument']['uri']:x['edits'] for x in edit['documentChanges']}
            actual = changes[uri][0]['range']['start']
            prefix = updated[:updated.index('target()')]
            expected = {'line':0,'character':sum(1 + (ord(ch)>0xffff) for ch in prefix)}
            assert actual == expected,(actual,expected)
            return {'status':'pass','wire_utf16':actual,'codepoints':len(prefix)}
        finally:
            client.close()


async def run_mcp(root,evidence):
    """Public Serena REPL reference+rename after closing/external replacement.

    The inspected target is the caller file; references originate in the other
    declaration file. No caller open occurs before that cross-file LSP response.
    Both generated fixtures are removed in finally, including on failure.
    """
    from mcp_client import connect
    root,evidence = Path(root),Path(evidence)
    evidence.mkdir(parents=True,exist_ok=True)
    results = {'adapter_external':run(),'adapter_healthy':run(False),'direct':run_direct(evidence/'direct')}
    declaration = 'semantic/ClosedTarget.php'
    target = 'semantic/ClosedCaller.php'
    decl_text = '<?php namespace ClosedState; class ClosedTarget { public function target(): int { return 7; } }\n'
    original = '<?php namespace ClosedState; function invoke(ClosedTarget $x): int { /* éé */ return $x->target(); }\n'
    updated = original.replace('éé','🧪')
    for relative in (declaration,target):
        assert not (root/relative).exists(),f'Fixture would overwrite {relative}'
    try:
        (root/declaration).write_text(decl_text)
        (root/target).write_text(original)
        async with connect(root,evidence/'mcp',extra_env={'POC_EVIDENCE':str(evidence),'POC_TRACE':'1'}) as repl:
            inspected = await repl.code(f's.lsp.find_symbol("invoke",relative_path={target!r},include_body=True)')
            assert 'invoke' in inspected,inspected
            # Establish the filesystem notifier baseline without revisiting target.
            await repl.code(f's.lsp.find_referencing_symbols("ClosedTarget/target",{declaration!r})')
            replacement = root/'semantic/closed-replacement.tmp'
            replacement.write_text(updated)
            replacement.replace(root/target)
            code = ('import json\n' +
                f'json.dumps([{{"file":x.get_relative_path(),"line":x.line,"character":x.character}} for x in s.lsp.find_referencing_symbols("ClosedTarget/target",{declaration!r}).references])')
            output = await repl.code(code)
            answer = json.loads(output)
            expected = [{'file':target,'line':0,'character':updated.index('target()')}]
            assert answer == expected,(answer,expected)
            # The adapter trace proves that reference conversion selected disk
            # while the target stayed closed. A later symbol-context lookup may
            # open it AFTER conversion; that cannot mask this assertion.
            traces = list(evidence.glob('document-state-*.jsonl'))
            assert len(traces) == 1,traces
            events = [json.loads(x) for x in traces[0].read_text().splitlines()]
            requests = [i for i,x in enumerate(events) if x.get('event') == 'request' and x.get('method') == 'textDocument/references']
            assert requests,events
            begin = requests[-1]
            end = next(i for i in range(begin+1,len(events)) if events[i].get('event') == 'response_converted' and events[i].get('method') == 'textDocument/references')
            during = [x for x in events[begin:end+1] if x.get('uri') == (root/target).as_uri()]
            assert during and all(not x.get('open') for x in during),during
            assert all(x.get('event') != 'textDocument/didOpen' for x in during),during
            assert any(x.get('selected_sha256') == digest(updated) for x in during),during
            (evidence/'closed-target-reference-state.json').write_text(json.dumps(during,indent=2)+'\n')
            renamed = await repl.code(f's.lsp.rename_symbol("ClosedTarget/target",{declaration!r},"renamed")')
            assert (root/target).read_text() == updated.replace('target()','renamed()'),renamed
            assert (root/declaration).read_text() == decl_text.replace('target()','renamed()'),renamed
            fresh = await repl.code(f's.lsp.find_symbol("ClosedTarget/renamed",relative_path={declaration!r})')
            assert 'renamed' in fresh,fresh
            results['mcp'] = {'status':'pass','expected_reference':expected,'actual_reference':answer,
                              'renamed_exact_text':True,'fresh_semantic_query':True,
                              'original_sha256':digest(original),'disk_sha256':digest(updated)}
        (evidence/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
        return results
    finally:
        for relative in (declaration,target,'semantic/closed-replacement.tmp'):
            (root/relative).unlink(missing_ok=True)


if __name__ == '__main__':
    import asyncio
    if os.environ.get('POC_STATE_MCP') == '1':
        asyncio.run(run_mcp(Path('/app'),Path(os.environ.get('POC_EVIDENCE','/evidence'))/'document-state'))
    else:
        run()
