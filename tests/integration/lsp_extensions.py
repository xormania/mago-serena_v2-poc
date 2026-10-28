#!/usr/bin/env python3
"""Run focused real-worker controls on one prepared, owned Symfony workspace."""
import argparse
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


def run(run_id, *, restore_preparation=True):
    data = selected(run_id)
    fresh(data)
    directory = Path(data['evidence'])/'lsp-extensions'
    directory.mkdir(parents=True, exist_ok=False)
    try:
        response = execute(data, 'python', '/opt/poc/tests/integration/lsp_extensions_probe.py',
                           '/evidence/lsp-extensions', capture_output=True, check=False)
        (directory/'probe.stdout').write_bytes(response.stdout)
        (directory/'probe.stderr').write_bytes(response.stderr)
        assert response.returncode == 0, response.stderr.decode()[-4000:]
        result = json.loads((directory/'result.json').read_text())
        assert result['status'] == 'pass'
        return result
    finally:
        # Restore original bytes and reseal the freshly compiled original container.
        if restore_preparation:
            prepare_mate(data)


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
