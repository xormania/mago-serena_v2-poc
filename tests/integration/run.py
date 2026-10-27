"""Acceptance through real stdio MCP, Serena REPL and Mago. No model credentials."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback

from lsp_client import LspClient
from mcp_client import connect
from verifier import position, snapshot, verify_rename, verify_symbol

ROOT = Path(os.environ.get('POC_ROOT', '/app')).resolve()
EVIDENCE = Path(os.environ.get('POC_EVIDENCE', '/evidence')).resolve()
REPO = 'src/Repository/PostRepository.php'
BLOG = 'src/Controller/BlogController.php'
CALC = 'semantic/Calculator.php'
REL = 'semantic/Relationships.php'
POS = 'semantic/Positions.php'
CORE = ['direct_lsp', 'demo_symbols', 'cross_file_references', 'composer_navigation', 'demo_rename',
        'interface_inheritance', 'invalid_rename', 'semantic_body_edit', 'position_accuracy', 'diagnostics',
        'external_edit', 'repl_persistence', 'partial_execution', 'restart_and_death', 'negative_backend', 'negative_verifier']


class Results:
    def __init__(self):
        self.checks = {name: {'name':name,'status':'not_exercised','assertion':'Not reached'} for name in CORE}

    async def check(self, name, function):
        start = time.monotonic()
        try:
            assertion = await function()
            status = 'pass'
        except Exception as exc:
            status = 'fail'
            assertion = f'{type(exc).__name__}: {exc}'
            (EVIDENCE / f'{name}.traceback.txt').write_text(traceback.format_exc())
        self.checks[name] = {'name':name,'status':status,'assertion':assertion,
                             'elapsed_s':round(time.monotonic()-start,3),'evidence':str(EVIDENCE)}
        self.save()
        print(f'{status}: {name}: {assertion}', flush=True)

    def save(self):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE/'integration-results.json').write_text(json.dumps({'schema':1,'checks':list(self.checks.values())},indent=2)+'\n')


def php(code):
    return subprocess.check_output(['php','-r',code],cwd=ROOT,text=True,timeout=30).strip()


def suite(filename):
    with (EVIDENCE/filename).open('w') as log:
        result = subprocess.run(['php','vendor/bin/phpunit','--log-junit',f'/evidence/{filename}.xml'],cwd=ROOT,
                                stdout=log,stderr=subprocess.STDOUT,timeout=180)
    assert result.returncode == 0, f'PHPUnit exit {result.returncode}; see {filename}'


async def main():
    results = Results()
    results.save()
    before = snapshot(ROOT)
    fixture_before = {p:(ROOT/p).read_bytes() for p in (CALC,REL,POS)}
    async def direct():
        client = LspClient([os.environ.get('MAGO_BINARY','mago'),'language-server'],ROOT,EVIDENCE/'direct')
        try:
            identity = client.initialize()
            assert identity['serverInfo']['name'] == 'mago-server', identity
            client.open(REPO)
            symbols = client.request('textDocument/documentSymbol',{'textDocument':{'uri':(ROOT/REPO).as_uri()}})
            assert 'findLatest' in json.dumps(symbols)
            # Imported class identifier; expectation is an actual installed declaration.
            pos = position(ROOT, REPO, 'ServiceEntityRepository;')
            definition = client.request('textDocument/definition',{'textDocument':{'uri':(ROOT/REPO).as_uri()},'position':pos})
            (EVIDENCE/'direct-vendor-definition.json').write_text(json.dumps(definition,indent=2))
            assert 'vendor/doctrine/doctrine-bundle/src/Repository/ServiceEntityRepository.php' in json.dumps(definition), definition
            return 'initialize + hierarchical symbols + Doctrine vendor definition; raw wire and stderr retained'
        finally:
            client.close()
    await results.check('direct_lsp', direct)
    try:
        async with connect(ROOT,EVIDENCE/'mcp') as r:
            await r.code('s.info("lsp", "edit", "LspSymbolCollection", "LspReferenceCollection", "LspDiagnostics")')
            await r.code('import json\n'
                         'def symdata(x):\n'
                         '    return {"name":x.get_name_path(),"file":x.location.relative_path,"line":x.location.line,"column":x.location.column,"body":x.body}\n'
                         'def symbols(name, path):\n'
                         '    return [symdata(x) for x in s.lsp.find_symbol(name,relative_path=path,include_body=True).symbols]\n'
                         '"helpers ready"')
            async def data(expression):
                output = await r.code(f'json.dumps({expression})')
                try:
                    return json.loads(output)
                except ValueError:
                    raise AssertionError(output)

            async def demo():
                overview = await r.code(f's.lsp.get_symbols_overview({REPO!r},depth=2)')
                assert 'findLatest' in overview, overview
                repo = await data(f'symbols("PostRepository/findLatest",{REPO!r})')
                verify_symbol(repo, ROOT, REPO, 'findLatest(')
                verify_symbol(await data(f'symbols("BlogController/index",{BLOG!r})'), ROOT, BLOG, 'index(')
                return 'Demo overview, both declarations, exact name positions and source bodies verified independently'
            await results.check('demo_symbols',demo)

            async def references():
                actual = await data(f'[{{"file":x.get_relative_path(),"line":x.line,"character":x.character}} for x in s.lsp.find_referencing_symbols("PostRepository/findLatest",{REPO!r}).references]')
                expected = [{'file':BLOG,**position(ROOT,BLOG,'findLatest(')}]
                assert actual == expected, (actual,expected)
                return 'Exactly the pinned BlogController::index call, with independently derived position'
            await results.check('cross_file_references',references)

            async def vendor():
                answer = await r.code(f's.lsp.find_declaration({REPO!r},r"use Doctrine\\\\Bundle\\\\DoctrineBundle\\\\Repository\\\\(ServiceEntityRepository);")')
                assert 'vendor/doctrine/doctrine-bundle/src/Repository/ServiceEntityRepository.php' in answer, answer
                return 'Direct LSP and REPL resolve Doctrine declaration in the same vendor tree; vendor indexing enabled explicitly'
            await results.check('composer_navigation',vendor)

            async def persistence():
                await r.code('persisted_probe = 40\npersisted_probe')
                assert await r.code('persisted_probe + 2') == '42'
                async with connect(ROOT,EVIDENCE/'new-session') as fresh:
                    output = await fresh.code('persisted_probe')
                    assert 'NameError' in output or 'not defined' in output, output
                return 'Same-session variable yields 42; a new MCP process/session has no such variable'
            await results.check('repl_persistence',persistence)

            async def relationships():
                implementations = await data(f'[symdata(x) for x in s.lsp.find_implementations("Greeter/greet",{REL!r}).symbols]')
                assert {x['name'].split('/')[-2] for x in implementations} == {'FriendlyGreeter','LoudGreeter'}, implementations
                declaration = await r.code(f's.lsp.find_declaration({REL!r},r"greeter->(greet)\\(")')
                assert 'Greeter/greet' in declaration, declaration
                refs = await r.code(f's.lsp.find_referencing_symbols("Greeter/greet",{REL!r})')
                assert 'welcome' in refs, refs
                outcome = await r.code(f's.lsp.rename_symbol("Greeter/greet",{REL!r},"salute")')
                original = fixture_before[REL]
                assert (ROOT/REL).read_bytes() == original.replace(b'greet(',b'salute('), outcome
                assert php(f'require "{REL}"; echo PocFixture\\welcome(new PocFixture\\FriendlyGreeter());') == 'Hello World'
                (ROOT/REL).write_bytes(original)
                return 'Exact implementation family, declaration and reference; semantic rename updates family and calls; PHP behavior passes'
            await results.check('interface_inheritance',relationships)

            async def invalid():
                original = (ROOT/CALC).read_bytes()
                output = await r.code(f's.lsp.rename_symbol("Calculator/value",{CALC!r},"occupied")')
                assert (ROOT/CALC).read_bytes() == original, 'Colliding rename modified the fixture'
                assert any(x in output.lower() for x in ('error','exception','conflict','already','collision')), output
                return 'Colliding rename refused with feedback; file hash unchanged'
            await results.check('invalid_rename',invalid)
            # Even a failed negative check must not contaminate later scenarios.
            (ROOT/CALC).write_bytes(fixture_before[CALC])

            async def body():
                await r.code(f's.lsp.find_symbol("Calculator/value",relative_path={CALC!r},include_body=True)')
                replacement = 'public function value(): int\n    {\n        return 11;\n    }'
                output = await r.code(f's.edit.replace_symbol_body("Calculator/value",{CALC!r},{replacement!r})')
                assert (ROOT/CALC).read_bytes() == fixture_before[CALC].replace(b'return 7;',b'return 11;'), output
                assert php(f'require "{CALC}"; echo (new PocFixture\\Calculator())->value();') == '11'
                fresh = await data(f'symbols("Calculator/value",{CALC!r})')
                assert 'return 11;' in fresh[0]['body'], fresh
                (ROOT/CALC).write_bytes(fixture_before[CALC])
                return 'Only method body changed; fresh Mago query sees 11; PHP returns 11'
            await results.check('semantic_body_edit',body)

            async def positions():
                answer = await data(f'symbols("Positions/target",{POS!r})')
                verify_symbol(answer,ROOT,POS,'target(')
                output = await r.code(f's.lsp.rename_symbol("Positions/target",{POS!r},"renamed")')
                changed = (ROOT/POS).read_bytes()
                assert changed.replace(b'\r\n',b'\n') == fixture_before[POS].replace(b'\r\n',b'\n').replace(b'target(',b'renamed('), output
                assert php(f'require "{POS}"; echo (new PocFixture\\Positions())->renamed();') == 'old'
                (EVIDENCE/'position-line-endings.json').write_text(json.dumps({'input_crlf':fixture_before[POS].count(b'\r\n'),'output_crlf':changed.count(b'\r\n'),'output_lf':changed.count(b'\n')}))
                (ROOT/POS).write_bytes(fixture_before[POS])
                return 'Non-ASCII + non-BMP before target on same CRLF line: exact Python name column, semantic rename and PHP behavior correct; newline counts recorded'
            await results.check('position_accuracy',positions)

            async def diagnostics():
                original = fixture_before[CALC]
                baseline = await r.code(f's.lsp.get_diagnostics_for_file({CALC!r},min_severity=1)')
                (EVIDENCE/'diagnostics-baseline.txt').write_text(baseline)
                (ROOT/CALC).write_bytes(original.replace(b'return 7;',b'return "intentional_wrong_type";'))
                bad = await r.code(f's.lsp.get_diagnostics_for_file({CALC!r},min_severity=1)')
                (EVIDENCE/'diagnostics-introduced.txt').write_text(bad)
                errors = json.loads(bad)[CALC]['Error']['PocFixture/Calculator/value']
                introduced = [x for x in errors if x.get('code') == 'invalid-return-statement' and 'intentional_wrong_type' in x['message']]
                assert len(introduced) == 1, errors
                start = position(ROOT,CALC,'"intentional_wrong_type"')
                assert introduced[0]['range'] == {'start':start,'end':{**start,'character':start['character']+len('"intentional_wrong_type"')}}, introduced
                (ROOT/CALC).write_bytes(original)
                clear = await r.code(f's.lsp.get_diagnostics_for_file({CALC!r},min_severity=1)')
                (EVIDENCE/'diagnostics-cleared.txt').write_text(clear)
                assert clear == baseline, (baseline,clear)
                return 'Known invalid return type produces a file diagnostic; restoring contents clears it to the recorded baseline'
            await results.check('diagnostics',diagnostics)
            (ROOT/CALC).write_bytes(fixture_before[CALC])

            async def external():
                await r.code(f'stale_symbol = s.lsp.find_symbol("Calculator/value",relative_path={CALC!r},include_body=True).symbols[0]\nstale_symbol.body')
                (ROOT/CALC).write_bytes(fixture_before[CALC].replace(b'return 7;',b'return 17;'))
                current = await data(f'symbols("Calculator/value",{CALC!r})')
                assert 'return 17;' in current[0]['body'], current
                stale = await r.code('stale_symbol.body')
                (EVIDENCE/'stale-symbol.txt').write_text(stale)
                (ROOT/CALC).write_bytes(fixture_before[CALC])
                return 'Fresh query sees external edit; retained symbol behavior recorded; recovery always re-queries'
            await results.check('external_edit',external)

            async def partial():
                output = await r.code(f's.edit.replace_content({CALC!r},"return 7;","return 23;",mode="literal")\nraise RuntimeError("intentional partial execution")')
                assert 'intentional partial execution' in output, output
                assert b'return 23;' in (ROOT/CALC).read_bytes(), 'Mutation was not observed after exception'
                observed = await data(f'symbols("Calculator/value",{CALC!r})')
                assert 'return 23;' in observed[0]['body'], observed
                (ROOT/CALC).write_bytes(fixture_before[CALC])
                restored = await data(f'symbols("Calculator/value",{CALC!r})')
                assert 'return 7;' in restored[0]['body']
                return 'Cell mutates then raises; independent file and fresh semantic query observe mutation before recovery'
            await results.check('partial_execution',partial)

            async def rename():
                outcome = await r.code(f's.lsp.rename_symbol("PostRepository/findLatest",{REPO!r},"findLatestPublished")')
                files = verify_rename(before,ROOT,EVIDENCE)
                verify_symbol(await data(f'symbols("PostRepository/findLatestPublished",{REPO!r})'),ROOT,REPO,'findLatestPublished(')
                assert await data(f'symbols("PostRepository/findLatest",{REPO!r})') == []
                refs = await data(f'[{{"file":x.get_relative_path(),"line":x.line,"character":x.character}} for x in s.lsp.find_referencing_symbols("PostRepository/findLatestPublished",{REPO!r}).references]')
                assert refs == [{'file':BLOG,**position(ROOT,BLOG,'findLatestPublished(')}], refs
                suite('rename-phpunit.log')
                return f'Exact independent two-file diff; old symbol absent; new references correct; original PHPUnit suite passes: {files}'
            await results.check('demo_rename',rename)

            async def lifecycle():
                old = {p.name for p in EVIDENCE.glob('backend-*.json')}
                await r.code('s.lsp.restart_language_server()')
                answer = await data(f'symbols("Calculator/value",{CALC!r})')
                assert len(answer) == 1
                identities = [json.loads(p.read_text()) for p in EVIDENCE.glob('backend-*.json') if p.name not in old]
                assert identities, 'Restart did not launch a new observed Mago process'
                pid = identities[-1]['pid']
                # Kill during an actual request. Between calls Serena intentionally
                # detects a dead process and automatically restarts it.
                logs = list(Path(os.environ['SERENA_HOME']).glob('logs/**/*.txt'))
                offsets = {path:path.stat().st_size for path in logs}
                os.kill(pid,signal.SIGSTOP)
                start = time.monotonic()
                pending = asyncio.create_task(r.code(f's.lsp.find_referencing_symbols("Calculator/value",{CALC!r})'))
                deadline = time.monotonic() + 10
                sent = False
                try:
                    while time.monotonic() < deadline:
                        if any('Waiting for response to request' in path.read_text()[offset:] for path,offset in offsets.items()):
                            sent = True
                            break
                        await asyncio.sleep(0.02)
                finally:
                    os.kill(pid,signal.SIGKILL)
                output = await pending
                assert sent, 'Did not observe an in-flight LSP request before kill'
                elapsed = time.monotonic()-start
                assert elapsed < 100, elapsed
                assert any(x in output.lower() for x in ('error','exception','terminat','failed','not running')), output
                await r.code('s.lsp.restart_language_server()')
                recovered = await data(f'symbols("Calculator/value",{CALC!r})')
                assert len(recovered) == 1
                return f'Restart changes PID; SIGKILL yields intelligible failure in {elapsed:.2f}s; explicit restart restores query'
            await results.check('restart_and_death',lifecycle)
    except Exception:
        (EVIDENCE/'mcp-fatal.txt').write_text(traceback.format_exc())
        for check in results.checks.values():
            if check['status'] == 'not_exercised':
                check.update(status='blocked',assertion='MCP session unavailable; see mcp-fatal.txt')
    finally:
        for path, contents in fixture_before.items():
            (ROOT/path).write_bytes(contents)

    async def negative_backend():
        for binary in ('/definitely/missing/mago','/usr/bin/true'):
            suffix = 'missing' if 'missing' in binary else 'wrong'
            async with connect(ROOT,EVIDENCE/f'negative-{suffix}',extra_env={'MAGO_BINARY':binary}) as r:
                output = await r.code(f's.lsp.find_symbol("PostRepository/findLatestPublished",relative_path={REPO!r})')
                assert any(x in output.lower() for x in ('missing','mismatch','failed','error','exception')), output
        return 'Both missing executable and wrong executable fail backend startup visibly; no fallback'
    await results.check('negative_backend',negative_backend)

    async def negative_verifier():
        try:
            verify_symbol([{'file':REPO,'line':-99,'column':-99}],ROOT,REPO,'findLatest')
        except AssertionError:
            return 'Deliberately wrong symbol coordinates are rejected by independent verifier'
        raise AssertionError('Wrong expectation incorrectly passed')
    await results.check('negative_verifier',negative_verifier)
    results.save()
    return int(any(x['status'] != 'pass' for x in results.checks.values()))


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
