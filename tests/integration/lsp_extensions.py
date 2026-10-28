#!/usr/bin/env python3
"""Run focused real-worker controls on one prepared, owned Symfony workspace."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'bin'))
from matelib import selected, fresh, prepare_mate
from poclib import compose, docker, environment, execute, metadata, new_id, prepare, start, stop
from mcp_client import connect

OWNER = r'App\Repository\TagRepository'
REGISTRY = r'Doctrine\Bundle\DoctrineBundle\Registry'
MANAGER = r'Doctrine\Persistence\ManagerRegistry'
SOURCE = 'src/Repository/TagRepository.php'


async def run_serena(data, directory):
    """Check forwarding through real independent MCP sessions; no model replay claim."""
    directory = Path(directory)
    config = Path(data['app'])/'mago.toml'
    original = config.read_bytes()
    result = {'status': 'fail', 'kind': 'deterministic_real_host_mcp', 'controls': {},
              'launcher': str(ROOT/'bin/serena-mcp'), 'launcher_cwd': '/tmp'}
    try:
        for enabled in (True, False):
            state = 'on' if enabled else 'off'
            command = ['env', 'MAGO_EXTENSION_BACKEND=php', 'MAGO_SYMFONY_WIRING_ATTESTATION=1',
                       'POC_WIRING=1',
                       'POC_WIRING_OBSERVATION=/evidence/lsp-extensions/serena-observer.json',
                       'php', '-d', 'display_errors=stderr', '-d', 'memory_limit=1G', '.mago/extensions.php']
            config.write_text('extends = ".mago/wiring.toml"\n'
                              '[language-server]\nrestart-on = [".mago/container-reference.dev.json", ".mago/extensions.php"]\n'
                              '[extension-hosts.php]\nworking-directory = "."\nworkers = 1\n'
                              'request-timeout-ms = 10000\nshutdown-timeout-ms = 2000\n'
                              f'enabled = {str(enabled).lower()}\ncommand = {json.dumps(command)}\n')
            (directory/f'serena-config-{state}.toml').write_bytes(config.read_bytes())
            async with connect('/tmp', directory/f'mcp-{state}',
                               command=[str(ROOT/'bin/serena-mcp'), '--run', data['run_id']]) as repl:
                contract = await repl.code('s.info("lsp.get_symbol_references")')
                assert 'get_symbol_references' in contract, contract
                await repl.code('import json')
                raw = await repl.code(f'json.dumps(s.lsp.get_symbol_references({SOURCE!r}, {OWNER!r}, "__construct"))')
                answer = json.loads(raw)
                bodies = {edge['target']['symbol'].lower() for edge in answer['references'] if edge['kind'] == 'body'}
                signatures = {edge['target']['symbol'].lower() for edge in answer['references'] if edge['kind'] == 'signature'}
                assert answer['source']['symbol'].lower() == OWNER.lower(), answer
                assert MANAGER.lower() in signatures, ('native signature missing', answer)
                assert (REGISTRY.lower() in bodies) == enabled, ('extension graph forwarding mismatch', state, answer)
                result['controls'][state] = {'graph': answer, 'registry_body': REGISTRY.lower() in bodies,
                                             'manager_registry_signature': True}
        result['status'] = 'pass'
        return result
    except Exception as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)[-4000:]}
        raise
    finally:
        config.write_bytes(original)
        (directory/'serena-result.json').write_text(json.dumps(result, indent=2)+'\n')


def run(run_id, *, restore_preparation=True):
    data = selected(run_id)
    fresh(data)
    directory = Path(data['evidence'])/'lsp-extensions'
    directory.mkdir(parents=True, exist_ok=False)
    result = {'status': 'fail', 'run_id': run_id}
    try:
        response = execute(data, 'python', '/opt/poc/tests/integration/lsp_extensions_probe.py',
                           '/evidence/lsp-extensions', capture_output=True, check=False)
        (directory/'probe.stdout').write_bytes(response.stdout)
        (directory/'probe.stderr').write_bytes(response.stderr)
        assert response.returncode == 0, response.stderr.decode()[-4000:]
        result = json.loads((directory/'result.json').read_text())
        assert result['status'] == 'pass'
        result['serena'] = asyncio.run(run_serena(data, directory))
        return result
    except Exception as exc:
        result.update(status='fail', error={'type': type(exc).__name__, 'message': str(exc)[-4000:]})
        if (directory/'serena-result.json').is_file():
            result['serena'] = json.loads((directory/'serena-result.json').read_text())
        raise
    finally:
        # Restore original bytes and reseal the freshly compiled original container.
        try:
            if restore_preparation:
                prepare_mate(data)
        except Exception as exc:
            result.update(status='fail', restoration_error={'type': type(exc).__name__, 'message': str(exc)[-4000:]})
            raise
        finally:
            (directory/'host-result.json').write_text(json.dumps(result, indent=2)+'\n')


def run_fresh():
    """Exercise the selected immutable image, retaining evidence after scoped purge."""
    data = prepare(new_id('lspext-ci'))
    directory = Path(data['evidence'])
    record = {'schema': 1, 'kind': 'fresh_lsp_extensions', 'run_id': data['run_id'],
              'status': 'running', 'cleanup': 'pending', 'image': os.environ.get('POC_IMAGE') or 'mago-serena-poc:local'}

    def save():
        (directory/'fresh-result.json').write_text(json.dumps(record, indent=2)+'\n')

    save()
    try:
        source = metadata(data)
        (directory/'metadata.json').write_text(json.dumps(source, indent=2)+'\n')
        config = subprocess.check_output(compose(data, 'config', '--format', 'json'), env=environment(data), text=True)
        (directory/'compose-config.json').write_text(config)
        resolved = json.loads(config)['services']['php']['image']
        assert resolved == record['image'], 'Compose resolved a different selected image'
        expected_image = subprocess.check_output([docker(), 'image', 'inspect', '--format', '{{.Id}}', resolved], text=True).strip()
        record['expected_image_id'] = expected_image
        # Reuse the acceptance identity contract, including installed source and
        # candidate patch/runtime checks; never weaken it for the focused gate.
        capture_identity = runpy.run_path(str(ROOT/'bin/poc'))['capture_identity']

        def verify_image(selected_data):
            identity = capture_identity(selected_data, source)
            assert identity['image_id'] == expected_image, 'Running container does not use the selected image ID'
            record['image_id'] = identity['image_id']
            save()

        start(data, build=False, validate_image=verify_image)
        prepare_mate(data)
        result = run(data['run_id'], restore_preparation=False)
        record['status'] = 'pass'
        return result
    except Exception as exc:
        record.update(status='fail', error={'type': type(exc).__name__, 'message': str(exc)[-4000:]})
        raise
    finally:
        failed = sys.exc_info()[0] is not None
        try:
            logs = subprocess.run(compose(data, 'logs', '--no-color', '--tail', '200'), env=environment(data),
                                  capture_output=True, check=False)
            (directory/'container.log').write_bytes(logs.stdout[-65536:] + logs.stderr[-65536:])
        except Exception as exc:
            record['log_error'] = {'type': type(exc).__name__, 'message': str(exc)[-4000:]}
        try:
            stop(data, purge=True)
            record['cleanup'] = 'pass'
        except Exception as exc:
            record.update(cleanup='fail', cleanup_error={'type': type(exc).__name__, 'message': str(exc)[-4000:]})
            if not failed:
                record['status'] = 'fail'
                raise
        finally:
            save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--run', help='Use one already prepared, owned run')
    selection.add_argument('--fresh', action='store_true', help='Prepare and purge a fresh run using the selected image')
    args = parser.parse_args()
    print(json.dumps(run_fresh() if args.fresh else run(args.run), indent=2))
