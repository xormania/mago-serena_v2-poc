"""Standalone direct-Mago probe for external edits changing prefix byte length.

No adapter or Serena is involved. Exit 0 means the recorded expected fault and
healthy restart control were both observed; this is diagnostic evidence, not a
claim that the external update works. Run inside the pinned PoC image.
"""
import json
import os
from pathlib import Path
import tempfile

from lsp_client import LspClient


def reproduce(evidence):
    evidence = Path(evidence)
    evidence.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mago-span-') as directory:
        root = Path(directory)
        original = '<?php class CloseTarget { public function target(): int { return 7; } }\n'
        updated = original.replace('public function','/* 🧪 */ public function')
        caller = '<?php function use_target(CloseTarget $x): int { return $x->target(); }\n'
        (root/'Target.php').write_text(original)
        (root/'Caller.php').write_text(caller)
        (root/'mago.toml').write_text('version = "1"\nphp-version = "8.5"\n[source]\npaths = ["."]\n')
        target_uri,caller_uri=(root/'Target.php').as_uri(),(root/'Caller.php').as_uri()
        params = {'textDocument':{'uri':caller_uri},'position':{'line':0,'character':caller.index('target()')}}
        expected = sum(1+(ord(ch)>0xffff) for ch in updated[:updated.index('target()')])
        result={'expected_utf16_column':expected,'mago_source':'46df50c96d93d0ac3655c116c375574277cf0b30'}
        for stage in ('warm_external_edit','fresh_process_control'):
            client=LspClient([os.environ.get('MAGO_BINARY','mago'),'language-server'],root,evidence/stage)
            try:
                client.initialize()
                if stage == 'warm_external_edit':
                    client.open('Target.php')
                    client.request('textDocument/documentSymbol',{'textDocument':{'uri':target_uri}})
                    client.notify('textDocument/didClose',{'textDocument':{'uri':target_uri}})
                    # Ordered barrier ensures didClose completed against original disk.
                    client.request('textDocument/documentSymbol',{'textDocument':{'uri':caller_uri}})
                    (root/'Target.php').write_text(updated)
                    client.notify('workspace/didChangeWatchedFiles',{'changes':[{'uri':target_uri,'type':2}]})
                client.open('Caller.php')
                refs=client.request('textDocument/references',{**params,'context':{'includeDeclaration':True}})
                target=[x for x in refs if x['uri']==target_uri]
                assert len(target)==1,refs
                column=target[0]['range']['start']['character']
                stage_result={'actual_utf16_column':column,'matches_source':column==expected}
                try:
                    edits=client.request('textDocument/rename',{**params,'newName':'renamed'})
                    stage_result['rename']={'status':'ok','edits':edits}
                except Exception as exc:
                    stage_result['rename']={'status':'error','error':str(exc)}
                result[stage]=stage_result
            finally:
                client.close()
        assert not result['warm_external_edit']['matches_source'],result
        assert result['warm_external_edit']['rename']['status']=='error',result
        assert 'out of date' in result['warm_external_edit']['rename']['error'],result
        assert result['fresh_process_control']['matches_source'],result
        assert result['fresh_process_control']['rename']['status']=='ok',result
        result['outcome']='expected_negative_with_healthy_control'
        (evidence/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return result


if __name__=='__main__':
    reproduce(Path(os.environ.get('POC_EVIDENCE','/evidence'))/'mago-external-spans')
