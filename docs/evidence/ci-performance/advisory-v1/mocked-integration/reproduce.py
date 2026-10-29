"""Retain synthetic full-path integration evidence; never makes a live request.

Run from any directory with a full repository history available:
  python3 docs/evidence/ci-performance/advisory-v1/mocked-integration/reproduce.py
The old consumer is read with git show at the explicitly identified trusted SHA.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/'tools/ci'))
sys.path.insert(0, str(ROOT/'tests/fast'))
from jev import canonical
from test_jev import Provider, reply
from test_jev_performance import PerformanceContractTests

DEST = Path(__file__).resolve().parent
LEGACY = '6a4d2ed6234d724c67d3755285fe66c12b89fbbc'


def save(relative, value):
    path = DEST/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value)+b'\n')


def retain(directory, prefix, names):
    for name in names:
        target = DEST/prefix/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(directory/name, target)


def main():
    case = PerformanceContractTests()
    case.setUp()
    try:
        packet = case.produce(candidate='executed', build_s=1000)
        gate, gate_directory, _ = case.gate(packet, None)
        result, provider, directory = case.provider(packet, None)
        save('budget-breach/packet.json', packet)
        save('budget-breach/gate.json', gate)
        retain(gate_directory/'reservation', 'budget-breach', ['reservation.json'])
        retain(directory, 'budget-breach', ['request.json', 'response.txt', 'result.json', 'summary.md'])
        warm = case.produce()
        warm_gate, _, _ = case.gate(warm, None)
        warm_result, warm_provider, warm_directory = case.provider(warm, None)
        save('warm/gate.json', warm_gate)
        retain(warm_directory, 'warm', ['result.json', 'summary.md'])
        old_source = subprocess.check_output(['git', 'show', LEGACY+':tools/ci/jev.py'], cwd=ROOT)
        namespace = {'__name__':'trusted_legacy_jev', '__file__':str(ROOT/'tools/ci/jev.py')}
        exec(compile(old_source, 'legacy-'+LEGACY+'-jev.py', 'exec'), namespace)
        namespace['validate_packet'](packet)
        old_provider = Provider(reply())
        old_result = namespace['diagnose'](packet, case.root/'legacy-consumer', key='fake-key-never-live', opener=old_provider)
        legacy_packet = dict(warm)
        legacy_packet.pop('performance')
        new_legacy_result, legacy_provider, _ = case.provider(legacy_packet, None)
        files = sorted(set((ROOT/'tools/ci').glob('*.py')) | {ROOT/'tests/fast/test_jev_performance.py'})
        hashes = {path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        proof = {
            'schema':1,
            'origin':'Synthetic timing/cache faults and mocked TypeSafe replies; not historical measurements or live causal calibration.',
            'candidate_identity':{'kind':'file-content hashes before final commit', 'files':hashes,
                                  'content_sha256':hashlib.sha256(canonical(hashes)).hexdigest()},
            'budget_breach':{'checks':'all pass', 'gate_provider_needed':gate['provider_needed'],
                             'provider_calls':provider.calls, 'outcome':result['status'], 'transport':result['transport']},
            'warm':{'gate_provider_needed':warm_gate['provider_needed'], 'provider_calls':warm_provider.calls,
                    'outcome':warm_result['status']},
            'rollout':{'legacy_trusted_sha':LEGACY, 'legacy_consumer_file_sha256':hashlib.sha256(old_source).hexdigest(),
                       'new_packet_validated_by_actual_legacy_consumer':True,
                       'legacy_consumer_new_packet_outcome':old_result['status'],
                       'legacy_consumer_new_packet_provider_calls':old_provider.calls,
                       'new_consumer_legacy_packet_outcome':new_legacy_result['status'],
                       'new_consumer_legacy_packet_provider_calls':legacy_provider.calls,
                       'hosted_candidate_consumer_executed':False,
                       'limitation':'workflow_run continues to execute the trusted default-branch consumer until merge.'}}
        assert proof['budget_breach']['provider_calls'] == 1
        assert proof['warm']['provider_calls'] == old_provider.calls == legacy_provider.calls == 0
        save('proof.json', proof)
        print(json.dumps({key:proof[key] for key in ('budget_breach', 'warm', 'rollout')}, indent=2))
    finally:
        case.doCleanups()


if __name__ == '__main__':
    main()
