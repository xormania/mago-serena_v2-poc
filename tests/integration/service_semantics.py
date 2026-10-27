"""Replay selected-service queries through the real host MCP launcher.

This is deterministic acceptance. The separate agent-investigation transcript
records the agent's adaptive cells; neither is an autonomous coding benchmark.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'bin'))
from poclib import execute, load, require_running
from mcp_client import connect

SERVICE = 'src/Form/Type/TagsInputType.php'
DEPENDENCY = 'src/Repository/TagRepository.php'
CALLER = 'src/Form/PostType.php'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def position(root, path, needle):
    content = (root / path).read_text()
    assert content.count(needle) == 1, (path, needle)
    prefix = content[:content.index(needle)]
    return {'line': prefix.count('\n'), 'character': len(prefix.rsplit('\n', 1)[-1])}


DIRECT_PROBE = r'''
from pathlib import Path
import json,sys
sys.path.insert(0, '/opt/poc/tests/integration')
from lsp_client import LspClient
root = Path('/app')
evidence = Path(sys.argv[1])
path = 'src/Form/Type/TagsInputType.php'
source = (root/path).read_text()
def params(needle):
    assert source.count(needle) == 1
    prefix = source[:source.index(needle)]
    return {'textDocument': {'uri': (root/path).as_uri()}, 'position': {
        'line': prefix.count('\n'),
        'character': len(prefix.rsplit('\n',1)[-1].encode('utf-16-le'))//2}}
client = LspClient(['mago', 'language-server'], root, evidence)
try:
    identity = client.initialize()
    assert identity['serverInfo']['name'] == 'mago-server', identity
    client.open(path)
    types = client.request('textDocument/prepareTypeHierarchy', params('TagsInputType extends'))
    assert len(types) == 1 and types[0]['name'] == 'App\\Form\\Type\\TagsInputType', types
    parents = client.request('typeHierarchy/supertypes', {'item': types[0]})
    assert any(x['name'] == 'Symfony\\Component\\Form\\AbstractType' for x in parents), parents
    methods = client.request('textDocument/prepareCallHierarchy', params('buildView(FormView'))
    assert len(methods) == 1, methods
    outgoing = client.request('callHierarchy/outgoingCalls', {'item': methods[0]})
    assert any(x['to']['name'] == 'Doctrine\\ORM\\EntityRepository::findAll' for x in outgoing), outgoing
    answer = {'types': types, 'supertypes': parents, 'methods': methods, 'outgoing': outgoing}
    (evidence/'hierarchy.json').write_text(json.dumps(answer, indent=2)+'\n')
    print(json.dumps(answer))
finally:
    client.close()
'''


PROPAGATION_PROBE = r'''
from pathlib import Path
import hashlib,json,os,subprocess,sys,tomllib
sys.path.insert(0, '/opt/poc/tests/integration')
from lsp_client import LspClient
root = Path('/app')
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
version = subprocess.check_output(['mago', '--version'], text=True).strip()
revision = Path('/opt/mago-source.sha').read_text().strip()
assert version == 'mago 1.58.2' and revision == '46df50c96d93d0ac3655c116c375574277cf0b30', (version, revision)
lock = json.loads((root/'composer.lock').read_text())
sdk = next(x for x in lock['packages-dev'] if x['name'] == 'carthage-software/mago')
assert sdk['version'] == '1.58.2' and sdk['source']['reference'] == revision, sdk
config = root/'.mago/wiring.toml'
command = tomllib.loads(config.read_text())['extension-hosts']['php']['command']
wrapper = out/'worker-launch.py'
wrapper.write_text('import os,sys\nfrom pathlib import Path\n'
    'with Path(os.environ["POC_WORKER_LAUNCH"]).open("a") as f: f.write("worker-started\\n")\n'
    'os.execvpe(sys.argv[1],sys.argv[1:],os.environ)\n')
probe_config = out/'instrumented.toml'
probe_config.write_text('extends = "/app/.mago/wiring.toml"\n'
    '[extension-hosts.php]\nworking-directory = "/app"\n'
    'command = '+json.dumps(['python',str(wrapper),*command])+'\n')
environment = {**os.environ,'POC_WIRING':'1',
    'POC_WORKER_LAUNCH':str(out/'cli-worker-starts.txt'),
    'POC_WIRING_OBSERVATION':str(out/'cli-observation.json')}
cli_command = ['mago','--workspace','/app','--config',str(probe_config),'analyze','--reporting-format','json']
cli = subprocess.run(cli_command, env=environment, capture_output=True, text=True, timeout=120)
(out/'cli.stdout.json').write_text(cli.stdout); (out/'cli.stderr').write_text(cli.stderr)
issues = json.loads(cli.stdout)['issues']
attestation = [x for x in issues if x.get('code') == 'byte-kitsune/symfony-wiring/analysis-attestation']
assert attestation and (out/'cli-observation.json').is_file(), (cli.returncode, cli.stderr)
assert (out/'cli-worker-starts.txt').is_file(), 'CLI did not launch the instrumented worker'
os.environ.update({**environment,'POC_WORKER_LAUNCH':str(out/'lsp-worker-starts.txt'),
    'POC_WIRING_OBSERVATION':str(out/'lsp-observation.json')})
client = LspClient(['mago','--workspace','/app','--config',str(probe_config),'language-server'],root,out/'lsp')
try:
    identity = client.initialize()
    path = 'src/Form/Type/TagsInputType.php'; client.open(path)
    symbols = client.request('textDocument/documentSymbol',{'textDocument':{'uri':(root/path).as_uri()}})
    assert symbols, 'No selected service symbols; propagation probe is inconclusive'
finally:
    client.close()
answer = {'status':'blocked','classification':'server propagation',
    'reason':'Pinned LSP creates the native plugin registry without initializing configured external analyzer hosts.',
    'config':str(config),'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
    'identity':{'version':version,'source':revision,'sdk_version':sdk['version'],'sdk_source':sdk['source']['reference']},
    'instrumented_config':str(probe_config),
    'cli':{'command':cli_command,'exit':cli.returncode,
        'worker_started':(out/'cli-worker-starts.txt').is_file(),
        'observer_ran':(out/'cli-observation.json').is_file(),'attestation':attestation},
    'lsp':{'initialization':identity,'symbols':symbols,
        'worker_started':(out/'lsp-worker-starts.txt').exists(),
        'observer_ran':(out/'lsp-observation.json').exists()},
    'source_location':'src/language_server/workspace/loading.rs:89 at 46df50c96d93d0ac3655c116c375574277cf0b30'}
if answer['lsp']['worker_started'] or answer['lsp']['observer_ran']:
    raise AssertionError('LSP host behavior changed: investigate before reporting the old propagation blocker')
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer))
'''


def probe_extension_propagation(data):
    """Separate positive CLI execution from the pinned server's host omission."""
    require_running(data)
    assert (Path(data['app']) / '.mago/wiring.toml').is_file(), 'Prepare the framework overlay first'
    base = Path(data['evidence']) / 'service-semantics'
    out = base / ('propagation-' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    (out / 'probe.py').write_text(PROPAGATION_PROBE)
    relative = out.relative_to(Path(data['evidence']))
    response = execute(data, 'python', '-', str(Path('/evidence') / relative),
                       input=PROPAGATION_PROBE, text=True, capture_output=True, check=False)
    (out / 'probe.stdout').write_text(response.stdout)
    (out / 'probe.stderr').write_text(response.stderr)
    assert response.returncode == 0, f'Extension propagation probe failed: {response.stderr}'
    result = json.loads(response.stdout)
    result['evidence'] = str(out)
    (base / 'propagation-result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


async def _queries(data, evidence):
    app = Path(data['app'])
    # This deliberately launches the absolute host entry point from another cwd.
    command = [str(ROOT / 'bin/serena-mcp'), '--run', data['run_id']]
    answers = {}
    async with connect('/tmp', evidence / 'mcp', command=command) as repl:
        answers['contract'] = await repl.code('s.info("lsp.find_symbol", "lsp.find_declaration")')
        answers['service'] = await repl.code(
            f's.lsp.find_symbol("TagsInputType", relative_path={SERVICE!r}, include_body=True)')
        symbols = json.loads(answers['service'])
        assert len(symbols) == 1 and symbols[0]['relative_path'] == SERVICE, symbols
        assert 'private readonly TagRepository $tags' in symbols[0]['body'], symbols
        source = (app / SERVICE).read_text()
        assert symbols[0]['body'] in source, 'Returned body differs from selected workspace'

        answers['dependency'] = await repl.code(
            rf's.lsp.find_declaration({SERVICE!r}, r"readonly (TagRepository) \$tags", include_info=True)')
        dependency = json.loads(answers['dependency'])
        assert dependency['relative_path'] == DEPENDENCY, dependency
        assert '@template-extends ServiceEntityRepository<Tag>' in dependency['info'], dependency

        answers['method_hover'] = await repl.code(
            f's.lsp.find_symbol("TagsInputType/buildView", relative_path={SERVICE!r}, include_info=True)')
        hover = json.loads(answers['method_hover'])
        assert len(hover) == 1 and 'array<string, mixed> $options' in hover[0]['info'], hover
        assert '): void' in hover[0]['info'], hover

        answers['inherited_method'] = await repl.code(
            rf's.lsp.find_declaration({SERVICE!r}, r"tags->(findAll)\(", include_info=True)')
        inherited = json.loads(answers['inherited_method'])
        assert inherited['relative_path'] == 'vendor/doctrine/orm/src/EntityRepository.php', inherited
        assert 'list<' in inherited['info'], inherited

        answers['caller_declaration'] = await repl.code(
            rf's.lsp.find_declaration({CALLER!r}, r"add\(\x27tags\x27, (TagsInputType)::class", include_body=True)')
        assert json.loads(answers['caller_declaration'])['relative_path'] == SERVICE
        await repl.code('import json')
        answers['references'] = await repl.code(
            'json.dumps([{"file": x.get_relative_path(), "line": x.line, "character": x.character} '
            f'for x in s.lsp.find_referencing_symbols("TagsInputType", {SERVICE!r}).references])')
        references = json.loads(answers['references'])
        expected = [
            {'file': CALLER, **position(app, CALLER, 'App\\Form\\Type\\TagsInputType;')},
            {'file': CALLER, **position(app, CALLER, 'TagsInputType::class')},
        ]
        assert sorted(references, key=lambda x: (x['file'], x['line'])) == expected, (references, expected)

        answers['diagnostics'] = await repl.code(
            f's.lsp.get_diagnostics_for_file({SERVICE!r}, min_severity=4)')
        # Existing diagnostics remain evidence, never an assumed zero baseline.
        json.loads(answers['diagnostics'])
        answers['missing_symbol'] = await repl.code(
            f's.lsp.find_symbol("Slice1MissingService", relative_path={SERVICE!r})')
        assert json.loads(answers['missing_symbol']) == []
    (evidence / 'answers.json').write_text(json.dumps(answers, indent=2) + '\n')
    return {'reference_locations': references, 'inherited_definition': inherited['relative_path'],
            'hover_via_existing_facade': True, 'diagnostics': json.loads(answers['diagnostics'])}


def run_semantics(data):
    """Run real semantic acceptance for an already started, selected workspace."""
    require_running(data)
    base = Path(data['evidence']) / 'service-semantics'
    evidence = base / (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + uuid.uuid4().hex[:6])
    evidence.mkdir(parents=True)
    app = Path(data['app'])
    before = {path: digest(app / path) for path in (SERVICE, DEPENDENCY, CALLER)}
    result = {'schema': 1, 'run_id': data['run_id'], 'status': 'fail', 'evidence': str(evidence),
              'service': SERVICE, 'source_sha256': before,
              'verification': 'deterministic real MCP replay plus direct LSP hierarchy probes',
              'host_launcher': str(ROOT / 'bin/serena-mcp'), 'launcher_cwd': '/tmp',
              'probe_sha256': digest(Path(__file__))}
    try:
        wrong = subprocess.run([str(ROOT / 'bin/serena-mcp'), '--run', 'slice1-does-not-exist'],
                               cwd='/tmp', capture_output=True, text=True, timeout=15)
        (evidence / 'wrong-run.json').write_text(json.dumps({
            'exit': wrong.returncode, 'stdout': wrong.stdout, 'stderr': wrong.stderr}, indent=2) + '\n')
        assert wrong.returncode == 3 and not wrong.stdout and 'Unknown run' in wrong.stderr, wrong
        result['mcp'] = asyncio.run(_queries(data, evidence))
        relative = evidence.relative_to(Path(data['evidence']))
        direct = execute(data, 'python', '-', str(Path('/evidence') / relative / 'direct'),
                         input=DIRECT_PROBE, text=True, capture_output=True, check=False)
        (evidence / 'direct.stdout').write_text(direct.stdout)
        (evidence / 'direct.stderr').write_text(direct.stderr)
        assert direct.returncode == 0, f'Direct hierarchy probe exit {direct.returncode}; {direct.stderr}'
        result['direct_hierarchy'] = json.loads(direct.stdout)
        if (app / '.mago/wiring.toml').is_file():
            # Enrichment propagation is a separate result: successful native
            # navigation does not imply that this LSP starts external workers.
            result['extension_propagation'] = probe_extension_propagation(data)
        else:
            result['extension_propagation'] = {
                'status': 'not_exercised', 'reason': 'Framework overlay is not prepared in this run.'}
        after = {path: digest(app / path) for path in before}
        assert before == after, 'Semantic inspection unexpectedly modified application source'
        result['status'] = 'pass'
        return result
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        (base / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default='dev')
    parser.add_argument('--extension-propagation', action='store_true')
    args = parser.parse_args()
    function = probe_extension_propagation if args.extension_propagation else run_semantics
    print(json.dumps(function(load(args.run)), indent=2))


if __name__ == '__main__':
    main()
