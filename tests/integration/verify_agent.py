"""Verify a model-driven transcript separately from deterministic acceptance."""
import asyncio
import json
import os
from pathlib import Path
from mcp_client import connect
from verifier import load_snapshot, verify_rename, verify_suite


async def main():
    evidence = Path(os.environ['POC_EVIDENCE'])
    trusted = Path(os.environ.get('POC_TRUSTED', '/trusted'))
    changed = verify_rename(load_snapshot(trusted / 'application.json'), '/app', evidence)
    suite = verify_suite(json.loads((trusted / 'expected-suite.json').read_text()), evidence / 'agent-phpunit.xml')
    transcript = evidence/'agent-transcript.jsonl'
    assert transcript.is_file(), 'Missing real-agent transcript; save the authenticated harness JSONL here'
    calls = []
    for line in transcript.read_text().splitlines():
        event = json.loads(line)
        item = event.get('item', {})
        if (event.get('type') == 'item.completed' and item.get('status') == 'completed'
                and not item.get('error') and item.get('type') == 'mcp_tool_call'
                and 'serena_repl' in item.get('tool','')):
            if 'rename_symbol' in item.get('arguments',{}).get('code',''):
                assert 'Successfully renamed' in json.dumps(item.get('result')), 'Model rename call did not succeed'
            calls.append(item.get('arguments',{}).get('code',''))
    assert any('find_symbol' in code for code in calls), 'No semantic symbol lookup in model tool calls'
    assert any('find_referencing_symbols' in code for code in calls), 'No semantic reference lookup in model tool calls'
    assert any('rename_symbol' in code and 'findLatestPublished' in code for code in calls), 'No REPL semantic rename in model tool calls'
    async with connect('/app',evidence/'independent-agent-requery') as r:
        await r.code('s.info("lsp")')
        old = await r.code('len(s.lsp.find_symbol("PostRepository/findLatest",relative_path="src/Repository/PostRepository.php").symbols)')
        new = await r.code('len(s.lsp.find_symbol("PostRepository/findLatestPublished",relative_path="src/Repository/PostRepository.php").symbols)')
        refs = await r.code('s.lsp.find_referencing_symbols("PostRepository/findLatestPublished","src/Repository/PostRepository.php")')
        assert old == '0' and new == '1' and 'BlogController/index' in refs, (old,new,refs)
    verify_rename(load_snapshot(trusted / 'application.json'), '/app', evidence)
    (evidence/'agent-result.json').write_text(json.dumps({'status':'pass','assertion':'Complete application manifest + original PHPUnit identities + real model MCP semantic operations + independent fresh semantic requery','semantic_tool_calls':len(calls),'changed':changed,'original_suite':suite},indent=2))


asyncio.run(main())
