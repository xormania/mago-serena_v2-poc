"""Independent complete-manifest and original-suite mutation controls.

The list XML is a retained --list-tests-xml output from the pinned fixture.
JUnit controls below are synthetic: real execution is asserted by acceptance.
"""
import copy
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('poc_verifier', ROOT / 'tests/integration/verifier.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name, 'app')
        self.evidence = Path(self.tmp.name, 'evidence')
        shutil.copytree(ROOT / 'app', self.root)
        (self.root / '.serena').mkdir()
        (self.root / '.serena/project.yml').write_text('language_servers: [mago]\n')
        self.baseline = v.snapshot(self.root)
        for name in v.DEMO_RENAME:
            path = self.root / name
            path.write_bytes(path.read_bytes().replace(b'findLatest', b'findLatestPublished'))

    def accept(self):
        return v.verify_rename(self.baseline, self.root, self.evidence)

    def reject(self, mutate):
        mutate()
        with self.assertRaises(AssertionError):
            self.accept()

    def test_healthy_exact_rename(self):
        self.assertEqual(self.accept(), sorted(v.DEMO_RENAME))
        self.assertIn('findLatestPublished', (self.evidence / 'rename.diff').read_text())

    def test_root_phpunit_weakened_selection_rejected(self):
        path = self.root / 'phpunit.dist.xml'
        self.reject(lambda: path.write_text(path.read_text().replace('<directory>tests</directory>', '<directory>tests/Utils</directory>')))

    def test_serena_project_configuration_rejected(self):
        self.reject(lambda: (self.root / '.serena/project.yml').write_text('language_servers: [other]\n'))

    def test_composer_manifest_rejected(self):
        self.reject(lambda: (self.root / 'composer.json').write_text('{}'))

    def test_dependency_lock_rejected(self):
        self.reject(lambda: (self.root / 'composer.lock').write_text('{}'))

    def test_root_configuration_addition_rejected(self):
        self.reject(lambda: (self.root / 'phpunit.xml').write_text('<phpunit/>'))

    def test_test_weakened_rejected(self):
        path = self.root / 'tests/Controller/BlogControllerTest.php'
        self.reject(lambda: path.write_text(path.read_text().replace('assertResponseIsSuccessful()', 'assertTrue(true)')))

    def test_unexpected_hidden_addition_rejected(self):
        self.reject(lambda: (self.root / '.unexpected').write_text('hidden'))

    def test_unexpected_empty_directory_rejected(self):
        self.reject(lambda: (self.root / 'unexpected').mkdir())

    def test_source_deletion_rejected(self):
        self.reject(lambda: (self.root / 'public/index.php').unlink())

    def test_entrypoint_permissions_rejected(self):
        path = self.root / 'bin/console'
        self.reject(lambda: path.chmod(path.stat().st_mode ^ 0o111))

    def test_directory_permissions_rejected(self):
        path = self.root / 'tests'
        self.reject(lambda: path.chmod(0o777))

    def test_rename_source_permission_change_rejected(self):
        path = self.root / next(iter(v.DEMO_RENAME))
        self.reject(lambda: path.chmod(0o777))

    def test_identical_bytes_symlink_replacement_rejected(self):
        path = self.root / 'composer.json'
        destination = Path(self.tmp.name, 'copy.json')
        shutil.copy2(path, destination)
        def replace():
            path.unlink()
            path.symlink_to(destination)
        self.reject(replace)

    def test_symlink_directory_not_followed_and_target_change_rejected(self):
        path = self.root / 'link'
        path.symlink_to('/does/not/exist', target_is_directory=True)
        manifest = v.snapshot(self.root)
        self.assertEqual(manifest['entries']['link']['kind'], 'symlink')
        self.assertFalse(any(name.startswith('link/') for name in manifest['entries']))
        path.unlink()
        path.symlink_to('/another/missing/path', target_is_directory=True)
        self.assertNotEqual(manifest['entries']['link'], v.snapshot(self.root)['entries']['link'])

    def test_dependencies_are_covered(self):
        path = self.root / 'vendor/bin/phpunit'
        path.parent.mkdir(parents=True)
        path.write_text('trusted runner')
        # Return rename sources to their initial state before adding the dependency.
        for name in v.DEMO_RENAME:
            source = self.root / name
            source.write_bytes(source.read_bytes().replace(b'findLatestPublished', b'findLatest'))
        self.baseline = v.snapshot(self.root)
        for name in v.DEMO_RENAME:
            source = self.root / name
            source.write_bytes(source.read_bytes().replace(b'findLatest', b'findLatestPublished'))
        self.reject(lambda: path.write_text('exit success'))

    def test_generated_exclusions_are_narrow(self):
        for name in ('var/cache/test/x', '.serena/cache/state', '.phpunit.cache/test-results', '.git/index', 'data/database_test.sqlite-wal', 'config/reference.php'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'generated')
        self.accept()
        self.reject(lambda: (self.root / 'data/unexpected.sqlite').write_bytes(b'unauthorized'))

    def test_serialization_external_and_immutable(self):
        path = Path(self.tmp.name, 'trusted/application.json')
        v.save_snapshot(self.baseline, path, self.root)
        self.assertEqual(v.load_snapshot(path), self.baseline)
        with self.assertRaises(FileExistsError):
            v.save_snapshot(self.baseline, path, self.root)
        with self.assertRaisesRegex(AssertionError, 'outside'):
            v.save_snapshot(self.baseline, self.root / 'baseline.json', self.root)

    def test_unbound_baseline_source_rejected(self):
        manifest = copy.deepcopy(self.baseline)
        manifest['rename_sources_base64'][next(iter(v.DEMO_RENAME))] = 'd3Jvbmc='
        with self.assertRaisesRegex(AssertionError, 'Unbound'):
            v.verify_rename(manifest, self.root, self.evidence)

    def test_deliberate_legacy_fault_detected(self):
        # Execute the reviewed implementation, not a hand-written simulation.
        reviewed = (ROOT / 'tests/fixtures/reviewed_verifier.py').read_text()
        namespace = {}
        exec(compile(reviewed, '<reviewed verifier>', 'exec'), namespace)
        old_before = namespace['snapshot'](ROOT / 'app')
        self.evidence.mkdir()
        config = self.root / 'phpunit.dist.xml'
        config.write_text(config.read_text().replace('<directory>tests</directory>', '<directory>tests/Utils</directory>'))
        self.assertEqual(namespace['verify_rename'](old_before, self.root, self.evidence), sorted(v.DEMO_RENAME))
        with self.assertRaisesRegex(AssertionError, 'phpunit.dist.xml'):
            self.accept()


class OriginalSuiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.xml = Path(self.tmp.name, 'junit.xml')
        self.expected = v.expected_suite(ROOT / 'tests/fixtures/original-suite-list.xml', ROOT / 'app')
        self.tree = ET.Element('testsuites')
        self.suite = ET.SubElement(self.tree, 'testsuite', name='/app/phpunit.dist.xml', tests=str(len(self.expected['cases'])), errors='0', failures='0', skipped='0')
        for case in self.expected['cases']:
            cls, method = case['id'].split('::')
            method, marker, dataset = method.partition('#')
            name = method + (' with data set #' + dataset if marker else '')
            ET.SubElement(self.suite, 'testcase', {'class': cls, 'file': '/app/' + case['file'], 'name': name, 'line': str(case['line']), 'assertions': '1'})

    def verify(self):
        ET.ElementTree(self.tree).write(self.xml, encoding='utf-8', xml_declaration=True)
        return v.verify_suite(self.expected, self.xml)

    def test_healthy_exact_identity_control(self):
        self.assertEqual(self.verify()['tests'], 53)
        self.assertEqual(len(self.expected['source_sha256']), 13)
        self.assertTrue(any('#' in case['id'] for case in self.expected['cases']))

    def test_omitted_test_rejected_even_if_aggregate_unchanged(self):
        self.suite.remove(self.suite[0])
        with self.assertRaisesRegex(AssertionError, 'missing='):
            self.verify()

    def test_same_totals_wrong_identity_rejected(self):
        self.suite[0].set('name', 'testMadeUp')
        with self.assertRaisesRegex(AssertionError, 'identities differ'):
            self.verify()

    def test_duplicate_replacing_another_test_rejected(self):
        self.suite[0].attrib = dict(self.suite[1].attrib)
        with self.assertRaisesRegex(AssertionError, 'Duplicate'):
            self.verify()

    def test_wrong_dataset_rejected(self):
        self.suite[0].set('name', self.suite[0].get('name').replace('#0', '#999'))
        with self.assertRaisesRegex(AssertionError, 'identities differ'):
            self.verify()

    def test_named_dataset_uses_phpunit11_event_id_convention(self):
        # Synthetic named-dataset control: this pinned Demo currently uses only
        # numeric datasets. PHPUnit's TestMethod.id() joins named ones with #.
        name = 'named 🧪#"quoted"'
        base = self.expected['cases'][0]['id'].partition('#')[0]
        self.expected['cases'][0]['id'] = base + '#' + name
        self.expected['cases'].sort(key=lambda case: case['id'])
        method = base.split('::')[1]
        self.suite[0].set('name', method + ' with data set "' + name + '"')
        self.assertEqual(self.verify()['tests'], 53)

    def test_original_configuration_required(self):
        self.suite.set('name', '/app/weakened.xml')
        with self.assertRaisesRegex(AssertionError, 'configuration'):
            self.verify()

    def test_wrong_source_file_rejected(self):
        self.suite[0].set('file', '/app/tests/fake.php')
        with self.assertRaisesRegex(AssertionError, 'file/line'):
            self.verify()

    def test_wrong_source_line_rejected(self):
        self.suite[0].set('line', '9000')
        with self.assertRaisesRegex(AssertionError, 'file/line'):
            self.verify()

    def test_skipped_test_rejected(self):
        ET.SubElement(self.suite[0], 'skipped')
        with self.assertRaisesRegex(AssertionError, 'skipped'):
            self.verify()

    def test_failed_test_rejected(self):
        ET.SubElement(self.suite[0], 'failure')
        with self.assertRaisesRegex(AssertionError, 'failure'):
            self.verify()

    def test_empty_junit_cannot_pass(self):
        self.suite.clear()
        with self.assertRaises(AssertionError):
            self.verify()

    def test_zero_assertions_rejected(self):
        self.suite[0].set('assertions', '0')
        with self.assertRaisesRegex(AssertionError, 'no assertions'):
            self.verify()

    def test_changed_aggregate_rejected(self):
        self.suite.set('tests', '999')
        with self.assertRaisesRegex(AssertionError, 'aggregate'):
            self.verify()

    def test_missing_trusted_source_hashes_rejected(self):
        self.expected.pop('source_sha256')
        with self.assertRaisesRegex(AssertionError, 'trusted source hashes'):
            self.verify()

    def test_list_inventory_bound_to_original_methods(self):
        source = ROOT / 'tests/fixtures/original-suite-list.xml'
        changed = source.read_text().replace('testCreateUserNonInteractive', 'testInvented')
        path = Path(self.tmp.name, 'list.xml')
        path.write_text(changed)
        with self.assertRaisesRegex(AssertionError, 'trusted fixture'):
            v.expected_suite(path, ROOT / 'app')

    def test_list_omitting_original_method_rejected(self):
        tree = ET.parse(ROOT / 'tests/fixtures/original-suite-list.xml')
        for cls in tree.findall('.//{*}testClass'):
            for child in list(cls):
                if child.attrib.get('name') == 'testTransform':
                    cls.remove(child)
        path = Path(self.tmp.name, 'list.xml')
        tree.write(path)
        with self.assertRaisesRegex(AssertionError, 'omits'):
            v.expected_suite(path, ROOT / 'app')


if __name__ == '__main__':
    unittest.main()
