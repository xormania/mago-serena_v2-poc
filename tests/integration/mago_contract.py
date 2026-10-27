"""Calibrate installed Mago against one real service, preserving every native report."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'bin'))
from magolib import CONTEXT, SERVICE, prepare_mago, run_native, selected
from poclib import execute
from evidence import write_json
from verifier import expected_suite, verify_suite


def issues(row):
    value = json.loads((Path(row['evidence'])/'stdout').read_text())
    assert isinstance(value, dict) and isinstance(value.get('issues'), list), 'Mago did not emit a diagnostic report'
    return value['issues']


def primary(issue):
    return [a['span'] for a in issue.get('annotations', []) if a.get('kind') == 'Primary']


def on_service(report):
    return [i for i in report if any(a['file_id']['name'] == SERVICE for a in primary(i))]


def fingerprints(report):
    # Native parallel reporting order can vary. Compare complete diagnostic bodies.
    return Counter(json.dumps(i, sort_keys=True) for i in report)


def expected_issue(report, code, source, needle):
    offset = source.index(needle)
    line = source[:offset].count('\n')
    matches = [i for i in report if i.get('code') == code and any(
        a['file_id']['name'] == SERVICE and a['start']['line'] == line
        for a in primary(i))]
    assert len(matches) == 1, f'Expected one new {code} at {SERVICE}:{line+1}, got {matches}'
    return {'code': code, 'file': SERVICE, 'line': line+1, 'diagnostic': matches[0]}


def source_inventory(app):
    return {str(p.relative_to(app)): hashlib.sha256(p.read_bytes()).hexdigest()
            for root in ('src', 'tests') for p in sorted((app/root).rglob('*.php'))}


def classify_existing(report, tool):
    """Retain code and primary locations; categories are triage, not suppressions."""
    result = []
    for issue in report:
        code = issue['code']
        if tool == 'lint':
            if code in ('sensitive-parameter', 'no-literal-password'):
                category = 'Security policy finding; existing password/test-fixture usage needs contextual review.'
            elif code in ('too-many-methods', 'no-empty', 'no-boolean-flag-parameter'):
                category = 'Existing design/API convention; no framework failure inferred.'
            else:
                category = 'Existing coding-style/strictness convention; not adopted by rewriting the fixture.'
        elif 'UnicodeString' in issue['message']:
            category = 'Stringable coercion or array-element source-contract mismatch; review source types, not a proven missing framework feature.'
        elif code == 'incompatible-parameter-name':
            category = 'Source API contract: override parameter names differ; named-argument compatibility concern.'
        elif code in ('redundant-cast', 'redundant-docblock-type', 'redundant-logical-operation'):
            category = 'Existing redundant-source suggestion; no behavior repair required for this slice.'
        elif code in ('mixed-assignment', 'ambiguous-object-method-access', 'implicit-to-string-cast'):
            category = 'Dynamic Console/input/object type or implicit conversion; refinement not established.'
        elif code in ('possibly-null-argument', 'possible-method-access-on-null', 'possibly-null-operand'):
            category = 'Nullable lifecycle/repeated-getter reasoning; runtime invariant not supplied to Mago here.'
        elif code == 'possibly-false-operand':
            category = 'Potential source edge case: Reflection line API can return false; no isolated runtime reproduction.'
        else:
            category = 'Array/key/value/refinement or declared source contract; unconfirmed application risk, retained for review.'
        result.append({'code': code, 'level': issue['level'], 'message': issue['message'],
                       'locations': [{'file': p['file_id']['name'], 'line': p['start']['line']+1} for p in primary(issue)],
                       'classification': category, 'confirmed_tool_defect': False})
    return result


def calibrate(data):
    app = Path(data['app'])
    directory = Path(data['evidence'])/'mago'/('calibration-'+uuid.uuid4().hex)
    directory.mkdir(parents=True)
    original = (app/SERVICE).read_text()
    before = source_inventory(app)
    rows = []

    def command(name, argv, exits=(0,)):
        row = run_native(data, argv, directory=directory/name)
        rows.append(row)
        assert row['exit'] in exits, f'{name}: unexpected Mago exit {row["exit"]}; see {row["evidence"]}'
        return row

    def php(name, argv):
        result = execute(data, *argv, check=False, capture_output=True, text=True)
        (directory/(name+'.stdout')).write_text(result.stdout)
        (directory/(name+'.stderr')).write_text(result.stderr)
        write_json(directory/(name+'.invocation.json'), {'run_id': data['run_id'], 'argv': argv,
                                                       'exit': result.returncode, 'workspace': '/app'})
        assert result.returncode == 0, f'{name}: PHP check failed; see {directory}'
        return result

    def behavior(name):
        target = '/evidence/'+str(directory.relative_to(Path(data['evidence']))/(name+'.xml'))
        php(name, ['env', 'APP_ENV=test', 'APP_DEBUG=1', 'php', 'vendor/bin/phpunit',
                   '--configuration', 'phpunit.dist.xml', '--log-junit', target])
        expected = expected_suite(ROOT/'tests/fixtures/original-suite-list.xml', ROOT/'app')
        return verify_suite(expected, directory/(name+'.xml'))

    result = {'schema': 1, 'kind': 'installed_mago_service_calibration', 'run_id': data['run_id'],
              'service': r'App\Form\Type\TagsInputType', 'service_file': SERVICE,
              'context': list(CONTEXT), 'baseline': None, 'commands': rows, 'status': 'fail'}
    try:
        result['tool'] = prepare_mago(data)
        (directory/'healthy.php').write_text(original)
        write_json(directory/'source-before.json', before)
        config = command('effective-config', ['config'])
        listed = command('files', ['list-files', '--command', 'analyzer'])
        files = set((Path(listed['evidence'])/'stdout').read_text().splitlines())
        assert files == set(before), 'Mago host coverage differs from the real src/tests inventory'
        assert set(CONTEXT) <= files and files, 'Selected service/caller context missing'
        command('rules', ['lint', '--list-rules', '--json'])
        initial = command('initial-analyze', ['analyze', '--reporting-format', 'json'], exits=(0, 1))
        initial_lint = command('initial-lint', ['lint', '--reporting-format', 'json'], exits=(0, 1))
        healthy_analysis, healthy_lint = issues(initial), issues(initial_lint)
        trace = (Path(initial['evidence'])/'stderr').read_text()
        compiled = re.search(r'Compiled (\d+) source files', trace)
        analyzed = re.search(r'Analyzed (\d+) host files', trace)
        assert compiled and analyzed and int(analyzed[1]) == len(files) and int(compiled[1]) > len(files), 'Missing/empty actual native coverage'
        result['coverage'] = {'hosts': len(files), 'compiled_source_files': int(compiled[1]),
                              'host_manifest': str(directory/'files/stdout'),
                              'dependency_coverage': 'Actual native trace counts compiled host and vendor source files; builtin prelude enabled separately.',
                              'builtin_stubs': 'Enabled native precompiled prelude; excluded from the compiled-source count.'}
        vendor = {str(p.relative_to(app)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((app/'vendor').rglob('*.php')) if p.is_file()}
        write_json(directory/'available-vendor-php.json', vendor)
        result['coverage']['available_vendor_php_files'] = len(vendor)
        assert int(compiled[1]) == len(files)+len(vendor), 'Compiled dependency coverage differs from the declared PHP inventory'
        result['coverage']['vendor_inventory_limit'] = 'Available dependency file hashes; individual loaded vendor files are not enumerated by list-files.'
        result['initial'] = {'analyzer_exit': initial['exit'], 'lint_exit': initial_lint['exit'],
                             'analyzer_findings': len(healthy_analysis), 'lint_findings': len(healthy_lint),
                             'analyzer_codes': dict(Counter(i['code'] for i in healthy_analysis)),
                             'lint_codes': dict(Counter(i['code'] for i in healthy_lint)),
                             'service_analyzer': on_service(healthy_analysis), 'service_lint': on_service(healthy_lint),
                             'classification': 'Existing application findings retained; no baseline, ignores or source repairs.'}
        write_json(directory/'classified-analyzer.json', classify_existing(healthy_analysis, 'analyze'))
        write_json(directory/'classified-lint.json', classify_existing(healthy_lint, 'lint'))
        assert not on_service(healthy_analysis), 'Selected service has existing analyzer findings to classify'
        command('healthy-format', ['format', '--check', SERVICE])
        command('healthy-guard', ['guard', '--structural', '--reporting-format', 'json'])

        # Valid PHP but a concrete return type error; keep the full project context.
        defective = original.replace('return TextType::class;', 'return 42;')
        assert defective != original
        (app/SERVICE).write_text(defective)
        (directory/'type-defective.php').write_text(defective)
        php('type-valid-php', ['php', '-l', SERVICE])
        bad = issues(command('type-defect', ['analyze', '--reporting-format', 'json'], exits=(1,)))
        result['type_control'] = expected_issue(bad, 'invalid-return-statement', defective, '42;')
        assert fingerprints(bad) != fingerprints(healthy_analysis)
        (app/SERVICE).write_text(original)
        restored = issues(command('type-restored', ['analyze', '--reporting-format', 'json'], exits=(0, 1)))
        assert fingerprints(restored) == fingerprints(healthy_analysis), 'Restored source did not restore analysis'
        result['type_control']['restored'] = True

        defective = original.replace("        $view->vars['tags']", "        var_dump($options);\n        $view->vars['tags']")
        (app/SERVICE).write_text(defective)
        (directory/'lint-defective.php').write_text(defective)
        php('lint-valid-php', ['php', '-l', SERVICE])
        bad_lint = issues(command('lint-defect', ['lint', '--reporting-format', 'json'], exits=(1,)))
        result['lint_control'] = expected_issue(bad_lint, 'no-debug-symbols', defective, 'var_dump')
        (app/SERVICE).write_text(original)
        restored_lint = issues(command('lint-restored', ['lint', '--reporting-format', 'json'], exits=(0, 1)))
        assert fingerprints(restored_lint) == fingerprints(healthy_lint), 'Restored source did not restore lint'
        result['lint_control']['restored'] = True

        defective = original.replace('$this->tags->findAll();', '($this->tags->findAll());')
        (app/SERVICE).write_text(defective)
        detected = issues(command('fix-before', ['lint', '--reporting-format', 'json', SERVICE], exits=(0, 1)))
        expected_issue(detected, 'no-redundant-parentheses', defective, "$view->vars['tags'] = (")
        command('safe-fix', ['lint', '--only', 'no-redundant-parentheses', '--fix', '--fail-on-remaining', SERVICE])
        fixed = (app/SERVICE).read_text()
        (directory/'safe-fix.diff').write_text(''.join(difflib.unified_diff(defective.splitlines(True), fixed.splitlines(True),
                                                                        fromfile='injected-parentheses', tofile='safe-fix')))
        assert fixed == original, 'Safe fix changed more than the injected redundant parentheses'
        after_fix = issues(command('fix-after', ['lint', '--reporting-format', 'json', SERVICE], exits=(0, 1)))
        assert not any(i['code'] == 'no-redundant-parentheses' for i in after_fix)
        result['safe_fix'] = {'rule': 'no-redundant-parentheses', 'safe_default': True, 'diff': str(directory/'safe-fix.diff'),
                              'restores_exact_source': True, 'unfixable_lint_control': 'no-debug-symbols has no automatic fix; removed explicitly.'}

        # The declared Guard rule checks a real Symfony form extension contract.
        defective = original.replace(' extends AbstractType', '')
        (app/SERVICE).write_text(defective)
        bad_guard = issues(command('guard-violation', ['guard', '--structural', '--reporting-format', 'json'], exits=(1,)))
        selected_guard = on_service(bad_guard)
        expected_issue(bad_guard, 'must-extend', defective, 'final class TagsInputType')
        assert len(selected_guard) == 1, 'Unexpected Guard findings on selected service'
        result['guard'] = {'allowed': True, 'violating': selected_guard, 'purpose': 'Registered form retains Symfony AbstractType contract.'}
        (app/SERVICE).write_text(original)
        command('guard-restored', ['guard', '--structural', '--reporting-format', 'json'])

        # A whitespace-only variant must be noticed, fixed, stable and behavior preserving.
        result['behavior_before'] = behavior('phpunit-before-format')
        defective = original.replace('return TextType::class;', 'return   TextType::class ;')
        (app/SERVICE).write_text(defective)
        command('format-detected', ['format', '--check', SERVICE], exits=(1,))
        assert (app/SERVICE).read_text() == defective, 'Read-only formatter check changed source'
        command('format-diff', ['format', '--dry-run', SERVICE], exits=(1,))
        command('format-applied', ['format', SERVICE])
        formatted = (app/SERVICE).read_text()
        assert formatted == original, 'Formatting changed more than the whitespace-only variant'
        command('format-stable', ['format', '--check', SERVICE])
        command('format-second', ['format', SERVICE])
        assert (app/SERVICE).read_text() == formatted
        result['behavior_after'] = behavior('phpunit-after-format')
        assert result['behavior_before'] == result['behavior_after'], 'Original suite identities/assertions changed after formatting'
        result['format'] = {'detected_exit': 1, 'restored_exact_source': True, 'second_pass_stable': True,
                            'behavior_unchanged': True, 'scope': SERVICE}

        cst = command('cst', ['cst', '--json', '--names', SERVICE])
        tree = json.loads((Path(cst['evidence'])/'stdout').read_text())['program']
        assert tree['errors'] == [] and bytes(tree['source_text']).decode() == original
        namespace = tree['statements']['nodes'][1]['value']
        statements = namespace['body']['value']['statements']['nodes']
        classes = [node['value'] for node in statements if node['type'] == 'Class']
        assert len(classes) == 1
        declaration = classes[0]
        class_name = bytes(declaration['name']['value']).decode()
        extends = bytes(declaration['extends']['types']['nodes'][0]['value']['value']).decode()
        methods = {bytes(node['value']['name']['value']).decode(): node['value']
                   for node in declaration['members']['nodes'] if node['type'] == 'Method'}
        parameter = methods['__construct']['parameter_list']['parameters']['nodes'][0]
        parameter_name = bytes(parameter['variable']['name']).decode()
        parameter_type = bytes(parameter['hint']['value']['value']['value']).decode()
        parameter_modifiers = [node['type'] for node in parameter['modifiers']['nodes']]
        assert class_name == 'TagsInputType' and extends == 'AbstractType'
        assert parameter_name == '$tags' and parameter_type == 'TagRepository'
        assert parameter_modifiers == ['Private', 'Readonly']
        assert set(methods) == {'__construct', 'buildForm', 'buildView', 'getParent'}
        result['cst'] = {'status': 'used', 'purpose': 'Verify class, inheritance spelling, promoted parameter and method names in the native lossless CST; retain method bodies.',
                         'bytes': len(original.encode()), 'parse_errors': tree['errors'], 'raw': str(Path(cst['evidence'])/'stdout'),
                         'declaration': {'class': class_name, 'extends_local_name': extends,
                                         'constructor_parameter': parameter_name, 'parameter_local_type': parameter_type,
                                         'promoted_modifiers': parameter_modifiers, 'methods': list(methods)}}

        # Invoke the actual public launcher from another working directory.
        argv = [str(ROOT/'bin/mago'), '--run', data['run_id'], '--', 'list-files', '--command', 'analyzer']
        routed = subprocess.run(argv, cwd='/tmp', capture_output=True, text=True)
        (directory/'foreign-cwd.stdout').write_text(routed.stdout)
        (directory/'foreign-cwd.stderr').write_text(routed.stderr)
        assert routed.returncode == 0 and set(routed.stdout.splitlines()) == files, 'Public launcher routed to wrong workspace'
        wrong = subprocess.run([str(ROOT/'bin/mago'), '--run', 'missing-mago-slice', '--', 'analyze'],
                               cwd='/tmp', capture_output=True, text=True)
        (directory/'missing-run.stdout').write_text(wrong.stdout)
        (directory/'missing-run.stderr').write_text(wrong.stderr)
        assert wrong.returncode == 3 and not wrong.stdout and 'Unknown run' in wrong.stderr
        escaped = subprocess.run([str(ROOT/'bin/mago'), '--run', data['run_id'], '--', 'analyze', '--workspace', '/tmp'],
                                 cwd='/tmp', capture_output=True, text=True)
        (directory/'wrong-workspace.stderr').write_text(escaped.stderr)
        assert escaped.returncode == 3 and not escaped.stdout and 'selected by the run' in escaped.stderr
        result['routing'] = {'foreign_cwd': 'pass', 'missing_run_exit': wrong.returncode, 'workspace_override_exit': escaped.returncode}
        # A PHP filename must not mask a directory or an implicit whole-app fix.
        # These run the public entry point and must fail before starting Mago.
        scoped_rejections = {}
        for name, arguments in (
            ('format-directory-mix', ['format', SERVICE, '.']),
            ('format-absolute-mix', ['format', SERVICE, '/app/'+SERVICE]),
            ('format-parent-mix', ['format', SERVICE, '../outside.php']),
            ('format-help-operand', ['format', SERVICE, '.', '--', '--help']),
            ('lint-unscoped-fix', ['lint', '--fix']),
            ('analyze-unscoped-fix', ['analyze', '--fix']),
            ('lint-fix-directory-mix', ['lint', '--fix', '--only', 'no-redundant-parentheses', SERVICE, '.']),
            ('analyze-variable-option', ['analyze', '--fix', '--only', 'invalid-return-statement', SERVICE]),
        ):
            response = subprocess.run([str(ROOT/'bin/mago'), '--run', data['run_id'], '--', *arguments],
                                      cwd='/tmp', capture_output=True, text=True, timeout=30)
            (directory/(name+'.stdout')).write_text(response.stdout)
            (directory/(name+'.stderr')).write_text(response.stderr)
            assert response.returncode == 3 and not response.stdout, name+': unsafe scope was accepted'
            assert 'explicit existing workspace-relative PHP file targets only' in response.stderr, name+': unhelpful scope error'
            assert source_inventory(app) == before, name+': rejected invocation changed application source'
            scoped_rejections[name] = {'argv': arguments, 'exit': response.returncode, 'source_unchanged': True}
        result['routing']['scoped_write_rejections'] = scoped_rejections
        assert source_inventory(app) == before, 'Calibration left application source changes'
        result['status'] = 'pass'
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        (app/SERVICE).write_text(original)
        result['source_restored'] = source_inventory(app) == before
        result['evidence'] = str(directory)
        write_json(directory/'result.json', result)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    outcome = calibrate(selected(args.run))
    print(json.dumps(outcome, indent=2))
