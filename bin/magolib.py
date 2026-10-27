"""Run-bound Mago commands with native reports and explicit, retained scope."""
import hashlib
import json
from pathlib import Path
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
