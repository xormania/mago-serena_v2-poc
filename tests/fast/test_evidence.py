"""Deliberate evidence faults paired with a complete healthy control."""
import copy
import unittest

from evidence import REQUIRED, check_record, make_plan, result_document, validate


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan('run-a', {'source': 'trusted'})
        self.healthy = result_document(self.plan, [check_record(self.plan, n, 'pass', 'asserted') for n in REQUIRED])

    def test_healthy_complete(self):
        self.assertEqual(validate(self.healthy, self.plan), len(REQUIRED))

    def test_mutations_rejected(self):
        faults = []
        for name in ('missing', 'duplicate', 'skipped', 'failed', 'stale', 'wrong_run', 'missing_identity', 'inventory', 'all_missing'):
            value = copy.deepcopy(self.healthy)
            if name == 'missing': value['checks'].pop()
            elif name == 'duplicate': value['checks'].append(value['checks'][0])
            elif name == 'skipped': value['checks'][0]['status'] = 'not_exercised'
            elif name == 'failed': value['checks'][0]['status'] = 'fail'
            elif name == 'stale': value['checks'][0]['context_sha256'] = 'old'
            elif name == 'wrong_run': value['checks'][0]['run_id'] = 'another-run'
            elif name == 'missing_identity': del value['checks'][0]['attempt_id']
            elif name == 'inventory': value['inventory'].pop()
            elif name == 'all_missing': value['checks'] = []
            faults.append((name, value))
        for name, value in faults:
            with self.subTest(fault=name), self.assertRaises(AssertionError):
                validate(value, self.plan)

    def test_incomplete_cannot_pass_even_when_all_present_rows_pass(self):
        with self.assertRaises(AssertionError):
            validate({'checks': []}, self.plan)

    def test_plan_cannot_reduce_required_inventory(self):
        self.plan['inventory'].pop()
        with self.assertRaises(AssertionError):
            validate(self.healthy, self.plan)


if __name__ == '__main__':
    unittest.main()

class RetainedEvidenceTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from evidence import seal_artifacts, write_json
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.a, self.b = Path(self.temp.name)/'a', Path(self.temp.name)/'b'
        self.a.mkdir(); self.b.mkdir()
        runtime, runtime_metadata = runtime_control()
        self.metadata = {**runtime_metadata, 'source_manifest': {'adapter/src/serena_mago/server.py': {'sha256':'adapter-hash'}}}
        self.plan = make_plan('run-a', self.metadata)
        self.result = result_document(self.plan,[check_record(self.plan,n,'pass','asserted') for n in REQUIRED])
        records = {row['name']:row for row in self.result['checks']}
        images = []
        baselines = {}
        for directory,rid in ((self.a,'run-a'),(self.b,'run-a-b')):
            write_json(directory/'executed-identity.json', {**runtime, 'run_id':rid,'attempt_id':'1',
                'installed_files':{'adapter/src/serena_mago/server.py':'adapter-hash'},
                'installed_adapter':{'sha256':'adapter-hash'}})
            image = {'image_id':'sha256:image','container_id':rid}
            images.append(image)
            write_json(directory/'image-identity.json',image)
            write_json(directory/'application-baseline.json',{'app':rid})
            write_json(directory/'expected-suite.json',{'tests':rid})
            baselines[rid] = {trusted:hashlib.sha256((directory/name).read_bytes()).hexdigest()
                for name,trusted in (('application-baseline.json','application.json'),('expected-suite.json','expected-suite.json'))}
        records['executed_identity']['detail'] = images
        records['trusted_baseline']['detail'] = baselines
        self.result['evidence_manifest_sha256'] = seal_artifacts(self.a,self.b)

    def verify(self):
        from evidence import verify_artifacts
        verify_artifacts(self.a,self.b,self.result,self.metadata)

    def reseal(self):
        from evidence import seal_artifacts
        self.result['evidence_manifest_sha256'] = seal_artifacts(self.a,self.b)

    def test_complete_retained_control(self):
        self.verify()

    def test_missing_identity_rejected(self):
        (self.a/'executed-identity.json').unlink()
        with self.assertRaises(AssertionError): self.verify()

    def test_wrong_run_identity_rejected_even_if_resealed(self):
        import json
        from evidence import write_json
        path=self.b/'executed-identity.json'
        value=json.loads(path.read_text()); value['run_id']='wrong'
        write_json(path,value); self.reseal()
        with self.assertRaises(AssertionError): self.verify()

    def test_missing_installed_code_rejected_even_if_resealed(self):
        import json
        from evidence import write_json
        path=self.a/'executed-identity.json'
        value=json.loads(path.read_text()); value['installed_files']={}
        write_json(path,value); self.reseal()
        with self.assertRaises(AssertionError): self.verify()

    def test_changed_trusted_baseline_rejected_even_if_resealed(self):
        (self.a/'application-baseline.json').write_text('{}')
        self.reseal()
        with self.assertRaises(AssertionError): self.verify()

    def test_changed_image_rejected_even_if_resealed(self):
        from evidence import write_json
        write_json(self.b/'image-identity.json',{'image_id':'sha256:other','container_id':'run-a-b'})
        self.reseal()
        with self.assertRaises(AssertionError): self.verify()

    def test_modified_or_added_evidence_rejected(self):
        (self.a/'extra.log').write_text('unexpected')
        with self.assertRaises(AssertionError): self.verify()


def runtime_control():
    from pathlib import Path
    import json
    root=Path(__file__).resolve().parents[2]
    lock=json.loads((root/'toolchain.lock.json').read_text())
    runtime=json.loads((root/'docs/evidence/runtime.json').read_text())
    actual={'runtime':runtime,'live_mago_binary_sha256':runtime['mago_binary_sha256'],
        'serena_direct_url':{'vcs_info':{'commit_id':lock['sources']['serena']}},
        'live_versions':{name:runtime[name] for name in ('php','python','uv','composer')}}
    if lock.get('candidates'):
        # Construct a current candidate unit-test fixture from the historical
        # version strings. This does not relabel retained historical evidence.
        runtime['lock'] = lock
        runtime['candidates'] = {name: {**candidate, 'enabled': True}
                                 for name, candidate in lock['candidates'].items()}
        runtime['mago_baseline_binary_sha256'] = 'baseline-unit-control'
        actual['live_mago_baseline_binary_sha256'] = 'baseline-unit-control'
        actual['live_serena_lsp_api_sha256'] = lock['candidates']['serena_symbol_references']['file_sha256']
    return actual,{'toolchain':lock}


class RuntimeIdentityTests(unittest.TestCase):
    def test_pinned_runtime_control(self):
        from evidence import validate_runtime
        validate_runtime(*runtime_control())

    def test_wrong_backend_or_dependency_or_version_refused(self):
        from evidence import validate_runtime
        for fault in ('mago_source_sha','cargo_lock_sha256','python_lock_sha256','mago_binary_sha256','serena','php'):
            actual,metadata=runtime_control()
            if fault in actual['runtime']:
                actual['runtime'][fault]='wrong'
            elif fault=='serena': actual['serena_direct_url']['vcs_info']['commit_id']='wrong'
            elif fault=='php': actual['live_versions']['php']='PHP 9.0.0'
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                validate_runtime(actual,metadata)

    def test_candidate_patch_selection_and_live_facade_are_required(self):
        from evidence import validate_runtime
        for fault in ('missing', 'disabled', 'patch', 'live_facade', 'baseline'):
            actual,metadata=runtime_control()
            if not metadata['toolchain'].get('candidates'):
                # Also exercise the candidate contract on the old baseline lock.
                candidates = {'mago_lsp_extensions': {'base': 'mago', 'patch_sha256': 'mago-patch'},
                              'serena_symbol_references': {'base': 'serena', 'patch_sha256': 'serena-patch',
                                                           'file_sha256': 'facade'}}
                metadata['toolchain'] = {**metadata['toolchain'], 'candidates': candidates}
                actual['runtime']['lock'] = metadata['toolchain']
                actual['runtime']['candidates'] = {name: {**candidate, 'enabled': True} for name,candidate in candidates.items()}
                actual['runtime']['mago_baseline_binary_sha256'] = 'baseline'
                actual['live_mago_baseline_binary_sha256'] = 'baseline'
                actual['live_serena_lsp_api_sha256'] = 'facade'
            validate_runtime(actual,metadata)
            if fault == 'missing': actual['runtime'].pop('candidates')
            elif fault == 'disabled': actual['runtime']['candidates']['mago_lsp_extensions']['enabled'] = False
            elif fault == 'patch': actual['runtime']['candidates']['mago_lsp_extensions']['patch_sha256'] = 'wrong'
            elif fault == 'live_facade': actual['live_serena_lsp_api_sha256'] = 'wrong'
            elif fault == 'baseline': actual['live_mago_baseline_binary_sha256'] = 'wrong'
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                validate_runtime(actual,metadata)
