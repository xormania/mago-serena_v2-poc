
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
# Per-folder configuration takes precedence over launch options in this server.
# Select the same instrumented configuration explicitly at the workspace root.
workspace_config = root/'mago.toml'
workspace_original = workspace_config.read_bytes()
workspace_config.write_text('extends = '+json.dumps(str(probe_config))+'\n')
(out/'workspace-config.toml').write_bytes(workspace_config.read_bytes())
client = LspClient(['mago','--workspace','/app','--config',str(probe_config),'language-server'],root,out/'lsp')
try:
    identity = client.initialize()
    path = 'src/Form/Type/TagsInputType.php'; client.open(path)
    symbols = client.request('textDocument/documentSymbol',{'textDocument':{'uri':(root/path).as_uri()}})
    assert symbols, 'No selected service symbols; propagation probe is inconclusive'
    candidate = Path('/opt/mago-candidate-enabled').exists() and Path('/opt/mago-candidate-enabled').read_text().strip() == '1'
    graph = client.request('mago/symbolReferences', {
        'textDocument': {'uri': (root/'src/Repository/TagRepository.php').as_uri()},
        'symbol': r'App\Repository\TagRepository', 'member': '__construct'}) if candidate else None
    if candidate:
        assert any(r['kind'] == 'body' and r['target']['symbol'].lower() == r'doctrine\bundle\doctrinebundle\registry'
                   for r in graph['references']), graph
finally:
    client.close()
    workspace_config.write_bytes(workspace_original)
answer = {'status':'pass' if candidate else 'blocked','classification':'native graph propagation' if candidate else 'server propagation',
    'reason':('Candidate initializes native external hosts and exposes their real graph through mago/symbolReferences.' if candidate else 'Pinned LSP creates the native plugin registry without initializing configured external analyzer hosts.'),
    'config':str(config),'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
    'identity':{'version':version,'source':revision,'sdk_version':sdk['version'],'sdk_source':sdk['source']['reference']},
    'instrumented_config':str(probe_config),
    'cli':{'command':cli_command,'exit':cli.returncode,
        'worker_started':(out/'cli-worker-starts.txt').is_file(),
        'observer_ran':(out/'cli-observation.json').is_file(),'attestation':attestation},
    'lsp':{'initialization':identity,'symbols':symbols,'graph':graph,
        'worker_started':(out/'lsp-worker-starts.txt').exists(),
        'observer_ran':(out/'lsp-observation.json').exists()},
    'source_location':'src/language_server/workspace/loading.rs:89 at 46df50c96d93d0ac3655c116c375574277cf0b30'}
assert answer['lsp']['worker_started'] is candidate and answer['lsp']['observer_ran'] is candidate, 'Worker lifecycle does not match the selected candidate/control'
(out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer))
