"""Run-bound Mago commands with native reports and explicit, retained scope."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from poclib import ROOT, compose, environment, execute, load, require_running

sys.path.insert(0, str(ROOT/'tests/integration'))
from evidence import write_json

CONFIG = 'mago-php.toml'
SERVICE = 'src/Form/Type/TagsInputType.php'
CONTEXT = (SERVICE, 'src/Repository/TagRepository.php', 'src/Form/PostType.php',
           'src/Form/DataTransformer/TagArrayToStringTransformer.php')
MAGO_REV = '46df50c96d93d0ac3655c116c375574277cf0b30'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected(run_id):
    data = load(run_id)
    expected = ROOT/'workspaces'/run_id/'app'
    assert Path(data['app']) == expected and expected.is_dir() and not expected.is_symlink(), 'Invalid workspace path'
    require_running(data)
    result = execute(data, 'python3', '-c',
                     'import json,os;print(json.dumps({"run":os.environ.get("POC_RUN_ID"),"cwd":os.getcwd()}))',
                     capture_output=True, text=True)
    identity = json.loads(result.stdout)
    assert identity == {'run': run_id, 'cwd': '/app'}, 'Container belongs to another run/workspace'
    return data


def prepare_mago(data):
    """Install only the declared native-check config; never rewrite the LSP config."""
    source = ROOT/'fixtures/mago/mago.toml'
    target = Path(data['app'])/CONFIG
    if target.exists():
        assert sha(target) == sha(source), f'{CONFIG} was edited; preserve it and refresh explicitly'
    else:
        shutil.copy2(source, target)
    version = execute(data, 'mago', '--version', capture_output=True, text=True).stdout.strip()
    revision = execute(data, 'cat', '/opt/mago-source.sha', capture_output=True, text=True).stdout.strip()
    binary = execute(data, 'sha256sum', '/usr/local/bin/mago', capture_output=True, text=True).stdout.split()[0]
    assert version == 'mago 1.58.2' and revision == MAGO_REV, 'Unexpected Mago executable; rebuild the pinned image'
    assert (Path(data['app'])/'vendor/autoload.php').is_file(), 'Application dependencies absent; run poc up first'
    return {'config': '/app/'+CONFIG, 'config_sha256': sha(target), 'version': version,
            'revision': revision, 'binary_sha256': binary, 'php_target': '8.5', 'workspace': '/app',
            'composer_lock_sha256': sha(Path(data['app'])/'composer.lock')}


def validate_write_scope(data, argv):
    """Keep formatter/fixer operands explicit using the pinned CLI's option arity.

    Unknown options are refused for writing commands rather than guessed to be
    flags: a value-consuming option could otherwise hide an implicit whole-app
    source set. Read-only analyzer/linter commands retain the native interface.
    """
    command, args = argv[0], argv[1:]
    if command != 'format' and not (command in ('lint', 'analyze') and '--fix' in args):
        return
    message = 'Formatting/fixing requires explicit existing workspace-relative PHP file targets only'
    flags = {'--check', '-c', '--dry-run', '--diff', '-d'} if command == 'format' else {
        '--fix', '--fail-on-remaining', '--unsafe', '--potentially-unsafe',
        '--format-after-fix', '--fmt', '--dry-run', '--diff', '-d', '--sort',
        '--ignore-baseline', '--fail-on-out-of-sync-baseline',
    }
    values = set()
    if command in ('lint', 'analyze'):
        values = {'--reporting-format', '--reporting-target', '--minimum-fail-level', '-m',
                  '--minimum-report-level', '--retain-code'}
        if command == 'lint':
            flags |= {'--pedantic', '--semantics', '-s'}
            values |= {'--only', '-o'}
        else:
            flags |= {'--no-stubs', '--skip-ignores'}
            values |= {'--slow-file-warning-threshold-ms'}
            # Analyzer --only consumes one-or-more arguments in this pin. Treating
            # it like lint --only could mistake its values for source operands.
    paths, index, operands = [], 0, False
    while index < len(args):
        arg = args[index]
        if arg == '--' and not operands:
            operands = True
        elif arg.startswith('-') and not operands:
            if arg in ('--help', '-h'):
                return  # Native help does not execute the formatter/fixer.
            option, separator, value = arg.partition('=')
            if option in values:
                if not separator:
                    index += 1
                    if index >= len(args) or args[index].startswith('-'):
                        raise ValueError(message + '; missing value for ' + option)
                elif not value:
                    raise ValueError(message + '; missing value for ' + option)
            elif option not in flags or separator:
                raise ValueError(message + '; unsupported scoped option: ' + arg)
        else:
            paths.append(arg)
        index += 1
    if not paths:
        raise ValueError(message)
    app = Path(data['app']).resolve()
    for operand in paths:
        path = Path(operand)
        candidate = app / path
        if (path.is_absolute() or '..' in path.parts or path.suffix != '.php'
                or not candidate.is_file() or candidate.is_symlink()
                or not candidate.resolve().is_relative_to(app)):
            raise ValueError(message + '; rejected target: ' + operand)


def run_native(data, argv, *, directory=None, echo=False):
    """Do not collapse finding exits, invalid invocations, or tool failures into pass."""
    assert argv and argv[0] in ('analyze', 'lint', 'format', 'guard', 'cst', 'config', 'list-files',
                                'extension', 'fix', 'version', 'help'), 'Unsupported Mago command'
    forbidden = ('--workspace', '--config', '--php-version')
    assert not any(x.split('=', 1)[0] in forbidden for x in argv), 'Workspace/config/PHP target are selected by the run'
    validate_write_scope(data, argv)
    if argv[0] == 'fix':
        raise ValueError('Use a scoped lint/analyze --fix invocation and inspect its diff')
    identity = prepare_mago(data)
    directory = Path(directory) if directory else Path(data['evidence'])/'mago/invocations'/uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    command = compose(data, 'exec', '-T', '-w', '/app', 'php', 'env', 'MAGO_LOG=trace', 'mago',
                      '--workspace', '/app', '--config', identity['config'], '--php-version', '8.5',
                      '--colors', 'never', *argv)
    started = time.monotonic()
    result = subprocess.run(command, env=environment(data), capture_output=True)
    (directory/'stdout').write_bytes(result.stdout)
    (directory/'stderr').write_bytes(result.stderr)
    row = {'run_id': data['run_id'], 'host_workspace': data['app'], 'argv': command,
           'exit': result.returncode, 'elapsed_s': round(time.monotonic()-started, 6),
           'tool': identity, 'source_sha256': {p: sha(Path(data['app'])/p) for p in CONTEXT},
           'evidence': str(directory)}
    write_json(directory/'invocation.json', row)
    if echo:
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
    return row


def invoke(data, argv):
    return run_native(data, argv, echo=True)['exit']


def selected_symbols(symbols):
    symbols = list(symbols) if symbols else [r'App\Form\Type\TagsInputType', r'App\Repository\TagRepository']
    if (not 1 <= len(symbols) <= 8 or len(set(symbols)) != len(symbols)
            or any(not isinstance(name, str) or len(name) > 200
                   or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\\[A-Za-z_][A-Za-z0-9_]*)*', name)
                   for name in symbols)):
        raise ValueError('Supply one to eight distinct fully qualified class names with --symbol')
    return symbols


def enriched_identity(data):
    """Require the executable, installed SDK, extension and configs to agree."""
    app = Path(data['app'])
    for name in ('extensions.php', 'wiring.toml'):
        target = app/'.mago'/name
        assert target.is_file() and not target.is_symlink() and sha(target) == sha(ROOT/'fixtures/mago'/name), \
            'Enriched configuration differs from the declared fixture: '+name
    assert (app/CONFIG).is_file(), 'Native Mago configuration unprepared'
    identity = prepare_mago(data)
    installed = json.loads((app/'vendor/composer/installed.json').read_text())
    packages = {p['name']: p for p in installed['packages']}
    expected = {'carthage-software/mago': MAGO_REV,
                'byte-kitsune/mago-symfony-wiring': '28c3f54065b71fe046a7474ced401aeadc941b0f'}
    for name, revision in expected.items():
        package = packages.get(name, {})
        assert package.get('source', {}).get('reference') == revision, 'Installed '+name+' source does not match the pinned toolchain'
    return {**identity, 'config': '/app/.mago/wiring.toml',
            'config_sha256': sha(app/'.mago/wiring.toml'),
            'extension_config_sha256': sha(app/'.mago/extensions.php'),
            'sdk_source': expected['carthage-software/mago'],
            'extension_source': expected['byte-kitsune/mago-symfony-wiring'],
            'backend': 'php'}


def run_enriched(data, argv, *, symbols=(), directory=None, echo=False, wiring_enabled=True):
    """Run the real Mago extension host against explicitly prepared Symfony facts.

    JSON evidence distinguishes application findings from preparation/tool failure;
    stdout and stderr retain the native bytes and a completed process keeps its
    native exit. A preflight rejection never masquerades as a clean analysis.
    """
    from matelib import fresh
    from evidence import digest

    if not argv or argv[0] != 'analyze':
        raise ValueError('The Symfony profile accepts analyze; use the native profile for other commands')
    forbidden = {'--workspace', '--config', '--php-version'}
    if any(arg.split('=', 1)[0] in forbidden for arg in argv):
        raise ValueError('Workspace/config/PHP target are selected by the run')
    validate_write_scope(data, argv)
    symbols = selected_symbols(symbols)
    directory = Path(directory) if directory else Path(data['evidence'])/'mago/enriched'/uuid.uuid4().hex
    directory.mkdir(parents=True, exist_ok=False)
    row = {'schema': 1, 'kind': 'symfony_enriched_mago_analysis', 'run_id': data['run_id'],
           'host_workspace': data['app'], 'requested_argv': argv, 'symbols': symbols,
           'wiring_enabled': wiring_enabled, 'exit': 3, 'native_exit': None,
           'status': 'stale_preparation', 'preparation_id': None,
           'evidence': str(directory), 'observation': str(directory/'graph.json')}
    stdout, stderr = b'', b''
    started = time.monotonic()
    try:
        try:
            prepared = fresh(data)
            identity = enriched_identity(data)
        except (AssertionError, OSError, ValueError, KeyError) as exc:
            row['reason'] = str(exc)+'; refresh with ./bin/poc mate-prepare --run '+data['run_id']
            stderr = ('mago-enriched: '+row['reason']+'\n').encode()
            return row
        row.update(preparation_id=prepared['preparation_id'],
                   preparation_sha256=sha(Path(data['trusted'])/'mate-preparation.json'),
                   application_sha256=prepared['application_sha256'],
                   source_context_sha256=digest({'preparation': prepared, 'tool': identity}),
                   compiled_metadata=prepared['metadata'],
                   wiring_reference_sha256=prepared['wiring_reference_sha256'], tool=identity,
                   source_sha256={str(p.relative_to(Path(data['app']))): sha(p)
                                  for base in ('src', 'tests') for p in sorted((Path(data['app'])/base).rglob('*.php'))})
        observation = '/evidence/'+str((directory/'graph.json').relative_to(Path(data['evidence'])))
        command = compose(data, 'exec', '-T', '-w', '/app', 'php', 'env', 'MAGO_LOG=trace',
                          'POC_WIRING='+('1' if wiring_enabled else '0'),
                          'POC_WIRING_SYMBOLS='+json.dumps(symbols),
                          'POC_WIRING_OBSERVATION='+observation,
                          'mago', '--workspace', '/app', '--config', identity['config'],
                          '--php-version', '8.5', '--threads', '1', '--colors', 'never', *argv)
        row['argv'] = command
        process = subprocess.run(command, env=environment(data), capture_output=True)
        stdout, stderr = process.stdout, process.stderr
        row.update(exit=process.returncode, native_exit=process.returncode, status='tool_failure')
        # The observer is an after-analysis hook. Its graph demonstrates worker
        # execution even for native text/SARIF reports; JSON attestation is also
        # retained when requested. Do not reinterpret a worker crash as findings.
        path = directory/'graph.json'
        if process.returncode in (0, 1) and path.is_file() and not path.is_symlink():
            graph = json.loads(path.read_text())
            assert graph['observer'] == 'poc/wiring-observer' and graph['wiring_enabled'] is wiring_enabled
            assert set(graph['symbols']) == set(symbols), 'Observer returned different selected symbols'
            actual = {f['path'] for f in graph['files']}
            assert actual == set(row['source_sha256']), 'Enriched source/test coverage differs from the application'
            # The default JSON interface also exposes the wiring package's own
            # completion attestation, separate from this graph-only observer.
            if '--reporting-format=json' in argv or any(
                    arg == '--reporting-format' and argv[index+1:index+2] == ['json']
                    for index, arg in enumerate(argv)):
                report = json.loads(stdout)
                attestations = [issue for issue in report['issues']
                                if issue['code'] == 'byte-kitsune/symfony-wiring/analysis-attestation']
                assert len(attestations) == int(wiring_enabled), 'Wiring completion attestation differs'
                if wiring_enabled:
                    note = next((note for note in attestations[0]['notes']
                                 if note.startswith('extension-attestation: ')), '')
                    attestation = json.loads(note.removeprefix('extension-attestation: '))
                    assert attestation['complete'] is True and attestation['source_files'] == len(actual)
                    row['extension_attestation'] = attestation
            row['status'] = 'findings' if process.returncode else 'clean'
            row['analyzed_files'] = len(actual)
        else:
            row['reason'] = 'Mago did not complete its after-analysis observer; inspect native stderr'
        return row
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        row.update(status='tool_failure', reason=str(exc))
        if row['native_exit'] is None:
            stderr += ('mago-enriched: '+str(exc)+'\n').encode()
        return row
    finally:
        if row['status'] == 'tool_failure':
            # Preserve the raw native status separately. A successful native
            # process without its required extension evidence is a wrapper
            # failure, never shell success or an ordinary findings result.
            if row['exit'] in (0, 1):
                row['exit'] = 3
            stderr += ('mago-enriched: '+row.get('reason', 'Enriched analysis failed')
                       +' (native exit '+str(row['native_exit'])+')\n').encode()
        (directory/'stdout').write_bytes(stdout)
        (directory/'stderr').write_bytes(stderr)
        row['elapsed_s'] = round(time.monotonic()-started, 6)
        write_json(directory/'invocation.json', row)
        if echo:
            sys.stdout.buffer.write(stdout)
            sys.stderr.buffer.write(stderr)
            print('Enriched evidence: '+str(directory), file=sys.stderr)


def invoke_enriched(data, argv, **kwargs):
    return run_enriched(data, argv, echo=True, **kwargs)['exit']


def quality(data):
    """Return the real application findings; existing findings are not a clean run."""
    directory = Path(data['evidence'])/'mago'/('quality-'+uuid.uuid4().hex)
    directory.mkdir(parents=True)
    rows = [run_native(data, argv, directory=directory/name) for name, argv in (
        ('analyze', ['analyze', '--reporting-format', 'json']),
        ('lint', ['lint', '--reporting-format', 'json']),
        ('format', ['format', '--check', SERVICE]),
        ('guard', ['guard', '--structural', '--reporting-format', 'json']),
    )]
    result = {'schema': 1, 'kind': 'native_mago_application_quality', 'run_id': data['run_id'],
              'commands': rows, 'clean': all(row['exit'] == 0 for row in rows),
              'baseline': None, 'scope': 'All src/tests analyzed; vendor context; selected service formatted only.'}
    write_json(directory/'result.json', result)
    return result


def run_checks(data):
    from mago_contract import calibrate
    return calibrate(data)
