"""Real PHP-worker/LSP controls, run inside one owned disposable application.

The observer records debug graph snapshots. Only mago/symbolReferences responses
are used to assert server-visible facts. No diagnostic or reference is invented.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from lsp_client import LspClient, LspError

OWNER = r'App\Repository\TagRepository'
REGISTRY = r'Doctrine\Bundle\DoctrineBundle\Registry'
ALTERNATE = r'App\LspProof\AlternateRegistry'
PATH = 'src/Repository/TagRepository.php'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(out):
    root = Path('/app')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    config, source, services = (root/p for p in ('mago.toml', PATH, 'config/services.yaml'))
    reference = root/'.mago/container-reference.dev.json'
    alternate = root/'src/LspProof/AlternateRegistry.php'
    wrapper = root/'.mago/lspext-worker.py'
    originals = {p: p.read_bytes() for p in (config, source, services, reference)}
    assert not alternate.exists() and not wrapper.exists()
    result = {'status': 'fail', 'controls': {}, 'limits': [
        'Graph edges have no locations and are not navigable references or calls.',
        'Compiled metadata is explicitly exported; watched reference/config changes reload workers.',
        'Source edits do not compile Symfony metadata automatically.',
    ]}
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    os.environ['POC_WIRING_OBSERVATION'] = str(out/'observer.json')
    os.environ['POC_WIRING'] = '1'
    os.environ['MAGO_LOG'] = 'trace'
    starts = out/'worker-starts.jsonl'
    wrapper.write_text('import os,sys,json\nfrom pathlib import Path\n'
                       f'with Path({str(starts)!r}).open("a") as f: f.write(json.dumps({{"pid":os.getpid()}})+"\\n")\n'
                       'os.execvpe(sys.argv[1],sys.argv[1:],os.environ)\n')

    def configure(enabled=True, broken=False):
        command = ['python', str(wrapper), 'env', 'MAGO_EXTENSION_BACKEND=php',
                   'MAGO_SYMFONY_WIRING_ATTESTATION=1', 'php', '-d', 'display_errors=stderr',
                   '-d', 'memory_limit=1G', '.mago/extensions.php']
        if broken:
            command = ['/lspext/no-such-worker']
        config.write_text('extends = ".mago/wiring.toml"\n'
                          '[language-server]\nrestart-on = [".mago/container-reference.dev.json", ".mago/extensions.php"]\n'
                          '[extension-hosts.php]\nworking-directory = "."\nworkers = 1\n'
                          'request-timeout-ms = 10000\nshutdown-timeout-ms = 2000\n'
                          f'enabled = {str(enabled).lower()}\ncommand = {json.dumps(command)}\n')
        (out/('config-broken.toml' if broken else 'config-on.toml' if enabled else 'config-off.toml')).write_bytes(config.read_bytes())

    def retain(name, value):
        result['controls'][name] = value
        (out/(name+'.json')).write_text(json.dumps(value, indent=2)+'\n')

    def graph(client):
        return client.request('mago/symbolReferences', {
            'textDocument': {'uri': source.as_uri()}, 'symbol': OWNER, 'member': '__construct'})

    def bodies(answer):
        return {r['target']['symbol'].lower() for r in answer['references'] if r['kind'] == 'body'}

    def wait_graph(client, predicate, timeout=45):
        deadline = time.monotonic()+timeout
        last = None
        while time.monotonic() < deadline:
            try:
                last = graph(client)
                if predicate(last):
                    return last
            except LspError as exc:
                last = str(exc)
            time.sleep(.15)
        raise AssertionError(('graph did not settle', last))

    def changed(client, path):
        client.notify('workspace/didChangeWatchedFiles', {'changes': [{'uri': path.as_uri(), 'type': 2}]})

    def worker_pids():
        return [json.loads(line)['pid'] for line in starts.read_text().splitlines()] if starts.exists() else []

    def alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def shutdown(client):
        pids = worker_pids()
        client.request('shutdown', None, timeout=15)
        deadline = time.monotonic()+5
        while any(alive(pid) for pid in pids) and time.monotonic() < deadline:
            time.sleep(.05)
        assert not any(alive(pid) for pid in pids), ('orphan worker', pids)
        # Check before exit: shutdown itself owns worker cleanup.
        client.notify('exit', None)
        client.process.wait(timeout=5)
        client.log.close()
        client.stderr.close()

    def cli(name, enabled):
        configure(enabled)
        report = subprocess.run(['mago', '--workspace', '/app', '--threads', '1',
                                 'analyze', '--reporting-format', 'json'], capture_output=True, timeout=120)
        (out/(name+'.stdout.json')).write_bytes(report.stdout)
        (out/(name+'.stderr')).write_bytes(report.stderr)
        assert report.returncode in (0, 1), report.stderr.decode()[-3000:]
        issues = json.loads(report.stdout)['issues']
        attestation = [i for i in issues if i.get('code') == 'byte-kitsune/symfony-wiring/analysis-attestation']
        assert len(attestation) == int(enabled)
        observed = json.loads((out/'observer.json').read_text()) if enabled else None
        if enabled:
            assert any(r['kind'] == 'Body' and r['target'] == REGISTRY.lower()
                       for r in observed['dependency_references']), observed['dependency_references']
        retain(name, {'native_exit': report.returncode, 'attestations': attestation,
                      'observer': observed, 'issue_count': len(issues)})

    def export(name):
        commands = [
            ['php', 'bin/console', 'cache:clear', '--env=dev', '--no-interaction'],
            ['php', 'bin/console', 'debug:container', '--env=dev', '--format=json', '--no-interaction', '--types'],
            ['php', 'bin/console', 'debug:container', '--env=dev', '--format=json', '--no-interaction'],
        ]
        for index, command in enumerate(commands):
            response = subprocess.run(command, env={**os.environ, 'APP_ENV': 'dev', 'APP_DEBUG': '1'},
                                      capture_output=True, timeout=120)
            (out/(name+f'-console-{index}.stderr')).write_bytes(response.stderr)
            assert response.returncode == 0, response.stderr.decode()[-3000:]
            if index:
                # Raw full Console views may contain scalars; they remain private state.
                Path('/state/lspext-'+('types' if index == 1 else 'services')+'.json').write_bytes(response.stdout)
        command = ['php', 'vendor/byte-kitsune/mago-symfony-wiring/bin/create-container-reference.php',
                   '--types=/state/lspext-types.json', '--services=/state/lspext-services.json',
                   '--autoload=/app/vendor/autoload.php']
        response = subprocess.run(command, capture_output=True, timeout=120)
        assert response.returncode == 0, response.stderr.decode()[-3000:]
        reference.write_bytes(response.stdout)
        ref = json.loads(response.stdout)
        selected = {key: ref['definitions'][key] for key in (OWNER, 'doctrine', 'lspext.registry')
                    if key in ref['definitions']}
        retain(name+'-export', {'argv': commands+[command], 'sha256': sha(reference),
                               'definitions': selected, 'source_sha256': ref['source_sha256']})
        # Independent Symfony service inspection, separate from extension's exported map.
        for service_id in (OWNER, 'lspext.registry') if alternate.exists() else (OWNER, 'doctrine'):
            response = subprocess.run(['php', 'bin/console', 'debug:container', service_id,
                                       '--env=dev', '--format=json'],
                                      capture_output=True, timeout=120)
            assert response.returncode == 0, response.stderr.decode()[-3000:]
            (out/(name+'-'+service_id.rsplit('\\', 1)[-1]+'.json')).write_bytes(response.stdout)
        return ref

    client = None
    try:
        cli('cli-on', True)
        cli('cli-off', False)
        configure(False)
        client = LspClient(['mago', '--threads', '1', 'language-server'], root, out/'direct')
        identity = client.initialize()
        assert identity['capabilities']['experimental']['symbolReferencesProvider'] is True
        client.open(PATH)
        off = graph(client)
        assert REGISTRY.lower() not in bodies(off), off
        retain('extension-off', off)
        configure(True)
        changed(client, config)
        on = wait_graph(client, lambda g: REGISTRY.lower() in bodies(g))
        retain('extension-on', on)
        pids_before_edit = worker_pids()
        original_source = source.read_text()
        # A constructor-owner rename exists only in the open buffer. The extension
        # must see that buffer, whose owner has no compiled binding, not the disk owner.
        unsaved = original_source.replace('class TagRepository', 'class UnsavedTagRepository')
        assert unsaved != original_source
        client.notify('textDocument/didChange', {'textDocument': {'uri': source.as_uri(), 'version': 2},
                                               'contentChanges': [{'text': unsaved}]})
        no_old_owner = wait_graph(client, lambda g: REGISTRY.lower() not in bodies(g))
        assert source.read_text() == original_source
        assert worker_pids() == pids_before_edit, 'Source edit launched duplicate workers'
        retain('unsaved-source-replaced', {'old_owner': no_old_owner, 'disk_sha256': sha(source),
                                          'buffer_sha256': hashlib.sha256(unsaved.encode()).hexdigest(),
                                          'worker_pids': worker_pids()})
        client.notify('textDocument/didChange', {'textDocument': {'uri': source.as_uri(), 'version': 3},
                                               'contentChanges': [{'text': original_source}]})
        retain('unsaved-source-restored', wait_graph(client, lambda g: REGISTRY.lower() in bodies(g)))

        active = [pid for pid in worker_pids() if alive(pid)]
        assert len(active) == 1, active
        # A dead idle worker may be replaced before checkout. Force the real
        # extension's next analysis hook to fail on malformed metadata in that
        # replacement; this is a labelled failure injection, not a binding fact.
        healthy_reference = reference.read_bytes()
        reference.write_bytes(b'{invalid compiled-reference failure control')
        os.kill(active[0], signal.SIGKILL)
        time.sleep(.1)
        client.notify('textDocument/didChange', {'textDocument': {'uri': source.as_uri(), 'version': 4},
                                               'contentChanges': [{'text': original_source+'\n// worker failure control\n'}]})
        try:
            try:
                old = graph(client)
            except LspError as exc:
                incremental_failure = str(exc)
            else:
                raise AssertionError(('failed extension returned a completed graph', old))
        finally:
            reference.write_bytes(healthy_reference)
        assert 'analy' in incremental_failure.lower(), incremental_failure
        retain('analysis-worker-failure', {'killed_owned_worker': active[0], 'error': incremental_failure,
                                            'logs': client.notifications[-8:]})
        client.notify('textDocument/didChange', {'textDocument': {'uri': source.as_uri(), 'version': 5},
                                               'contentChanges': [{'text': original_source}]})
        retain('analysis-worker-recovery', wait_graph(client, lambda g: REGISTRY.lower() in bodies(g)))

        alternate.parent.mkdir()
        alternate.write_text('<?php\nnamespace App\\LspProof;\nclass AlternateRegistry extends \\Doctrine\\Bundle\\DoctrineBundle\\Registry {}\n')
        services.write_bytes(originals[services]+b'\n    lspext.registry:\n        parent: doctrine\n        class: App\\LspProof\\AlternateRegistry\n        autowire: false\n        autoconfigure: false\n    App\\LspProof\\AlternateRegistry:\n        alias: lspext.registry\n    App\\Repository\\TagRepository:\n        arguments:\n            $registry: "@lspext.registry"\n')
        ref = export('changed-binding')
        assert ref['definitions'][OWNER]['arguments'][0] == 'lspext.registry'
        assert ref['definitions']['lspext.registry']['class'] == ALTERNATE
        changed(client, reference)
        rebound = wait_graph(client, lambda g: ALTERNATE.lower() in bodies(g) and REGISTRY.lower() not in bodies(g))
        retain('changed-binding', rebound)
        services.write_bytes(originals[services])
        alternate.unlink()
        alternate.parent.rmdir()
        export('restored-binding')
        changed(client, reference)
        restored = wait_graph(client, lambda g: REGISTRY.lower() in bodies(g) and ALTERNATE.lower() not in bodies(g))
        retain('restored-binding', restored)

        configure(True, broken=True)
        changed(client, config)
        deadline = time.monotonic()+40
        failure = None
        while time.monotonic() < deadline:
            try:
                graph(client)
            except LspError as exc:
                failure = str(exc)
                if 'reload failed' in failure.lower() or 'external' in failure.lower():
                    break
            time.sleep(.15)
        assert failure and 'worker' in failure.lower(), failure
        retain('worker-failure', {'error': failure, 'logs': client.notifications[-8:]})
        configure(True)
        changed(client, config)
        retain('worker-recovery', wait_graph(client, lambda g: REGISTRY.lower() in bodies(g)))
        configure(False)
        changed(client, config)
        retain('disabled-after-analysis', wait_graph(client, lambda g: REGISTRY.lower() not in bodies(g)))
        configure(True)
        changed(client, config)
        retain('reenabled-after-analysis', wait_graph(client, lambda g: REGISTRY.lower() in bodies(g)))
        isolated = out/'isolation-workspace'
        isolated.mkdir()
        (isolated/'a.php').write_text('<?php namespace App\\Repository; class TagRepository { public function __construct(\\DateTimeImmutable $clock) {} }\n')
        (isolated/'mago.toml').write_text('version = "1"\n[source]\npaths = ["a.php"]\n')
        client.notify('workspace/didChangeWorkspaceFolders', {'event': {
            'added': [{'uri': isolated.as_uri(), 'name': 'lspext-independent'}], 'removed': []}})
        independent = client.request('mago/symbolReferences', {
            'textDocument': {'uri': (isolated/'a.php').as_uri()}, 'symbol': OWNER, 'member': '__construct'})
        assert REGISTRY.lower() not in bodies(independent)
        assert any(r['kind'] == 'signature' and r['target']['symbol'].lower() == 'DateTimeImmutable'.lower()
                   for r in independent['references']), independent
        unchanged = graph(client)
        assert REGISTRY.lower() in bodies(unchanged)
        retain('workspace-isolation', {'independent': independent, 'original': unchanged})
        client.notify('workspace/didChangeWorkspaceFolders', {'event': {
            'added': [], 'removed': [{'uri': isolated.as_uri(), 'name': 'lspext-independent'}]}})
        shutdown(client)
        client = None
        retain('shutdown', {'worker_pids': worker_pids(), 'all_exited': True})
        client = LspClient(['mago', '--threads', '1', 'language-server'], root, out/'restart')
        client.initialize()
        retain('restart', wait_graph(client, lambda g: REGISTRY.lower() in bodies(g)))
        shutdown(client)
        client = None
        result['status'] = 'pass'
        result['identity'] = {'version': subprocess.check_output(['mago', '--version'], text=True).strip(),
                              'binary_sha256': sha(Path('/usr/local/bin/mago')),
                              'runtime': json.loads(Path('/opt/toolchain-runtime.json').read_text())}
        return result
    finally:
        if client:
            client.close()
        for path, content in originals.items():
            path.write_bytes(content)
        alternate.unlink(missing_ok=True)
        if alternate.parent.exists():
            alternate.parent.rmdir()
        wrapper.unlink(missing_ok=True)
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1]), indent=2))
