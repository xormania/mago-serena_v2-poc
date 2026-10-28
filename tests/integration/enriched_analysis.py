#!/usr/bin/env python3
"""Public Symfony/Mago controls and explicit refresh on one owned disposable run."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'bin'))
from evidence import write_json
from framework_checks import run as framework_checks
from magolib import selected
from matelib import fresh


def run(data):
    directory = Path(data['evidence'])/'public-enriched'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    result = {'schema': 1, 'run_id': data['run_id'], 'status': 'fail', 'evidence': str(directory)}
    write_json(directory/'result.json', result)

    def public(name, args, expected):
        argv = [str(ROOT/'bin/poc'), *args]
        response = subprocess.run(argv, cwd='/tmp', capture_output=True, timeout=240)
        (directory/(name+'.stdout')).write_bytes(response.stdout)
        (directory/(name+'.stderr')).write_bytes(response.stderr)
        write_json(directory/(name+'.invocation.json'), {'argv': argv, 'cwd': '/tmp', 'exit': response.returncode})
        assert response.returncode == expected, name+': unexpected exit '+str(response.returncode)
        return response

    result['framework'] = framework_checks(data)
    original = fresh(data)
    source = Path(data['app'])/'src/Repository/TagRepository.php'
    content = source.read_bytes()
    try:
        source.write_bytes(content+b'\n// Intentional harmless change for the public metadata-refresh control.\n')
        stale = public('changed-source-rejected', ['mago-enriched', '--run', data['run_id'], '--',
                       'analyze', '--reporting-format', 'json'], 3)
        assert b'mate-prepare --run '+data['run_id'].encode() in stale.stderr and stale.stdout == b''
        public('explicit-refresh', ['mate-prepare', '--run', data['run_id']], 0)
        refreshed = fresh(data)
        assert refreshed['preparation_id'] != original['preparation_id']
        response = public('changed-source-analyzed', ['mago-enriched', '--run', data['run_id'],
                          '--symbol', r'App\Repository\TagRepository', '--',
                          'analyze', '--reporting-format', 'json'], 1)
        report = json.loads(response.stdout)
        assert any(issue['code'] == 'byte-kitsune/symfony-wiring/analysis-attestation' for issue in report['issues'])
        result['intentional_change_refresh'] = {'status': 'pass', 'preparation_id': refreshed['preparation_id'],
                                                 'native_exit': response.returncode}
    finally:
        source.write_bytes(content)
        public('restore-and-refresh', ['mate-prepare', '--run', data['run_id']], 0)
    fresh(data)
    result['status'] = 'pass'
    write_json(directory/'result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    print(json.dumps(run(selected(args.run)), indent=2))
