"""Bounded performance observations and trusted, advisory comparison policy.

The producer supplies observations only. Consumers recompute classification with
their own POLICY and identified history; no artifact can authorize a request.
BuildKit vertex durations measure RUN/layer work, never buffered line timestamps.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

PHASES = ('dependencies', 'fast', 'build', 'acceptance', 'slice1', 'slice2', 'slice3', 'lsp_extensions')
VERIFICATION = ('acceptance', 'slice1', 'slice2', 'slice3', 'lsp_extensions')
MAX_OBSERVATION = 16000
MAX_LOG = 1024 * 1024
POLICY = {
    'version': 1, 'history_max_age_s': 7 * 86400,
    'cold_build_budget_s': 900, 'warm_build_budget_s': 180,
    'unknown_build_budget_s': 900, 'verification_budget_s': 300,
    'verification_relative_ratio': 1.5, 'verification_delta_s': 60,
    'cache_presence_max_age_s': 300,
}
HEX = re.compile(r'^[0-9a-f]{64}$')
IDENT = re.compile(r'^[A-Za-z0-9_.:-]{1,100}$')


def _matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _number(value, *, optional=False, maximum=31 * 86400):
    if value is None and optional:
        return
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError('Invalid performance measurement')


def _text(value, limit=200, *, optional=False):
    if value is None and optional:
        return
    if not isinstance(value, str) or len(value.encode()) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid performance identity text')


def _clean(value):
    # Import lazily: jev validates performance while loading its packet schema.
    from jev import sanitize
    return sanitize(value)


def parse_buildkit(raw, *, truncated=False):
    """Recognize only explicit vertices; cached extraction never means a compile.

    Changing vertex numbers and interleaving are normal. A truncated log needs
    actual Cargo execution output before an otherwise ambiguous DONE can count
    as execution. Import success never implies a compile layer cache hit.
    """
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    if not isinstance(raw, str) or len(raw.encode()) > MAX_LOG:
        raise ValueError('Build log bound exceeded')
    vertices = {}
    for line in raw.splitlines():
        match = re.search(r'(?:^|\s)#(\d+)\s+(.*)$', line)
        if not match:
            continue
        vertex, text = match.groups()
        state = vertices.setdefault(vertex, {'kind': None, 'cached': False, 'cargo': False,
                                             'failed': False, 'done': None, 'lines': {}})
        descriptor = re.match(r'\[([^]]+)\]\s+(.*)', text)
        kind = None
        if descriptor:
            stage, instruction = descriptor.groups()
            stage = stage.split()[0]
            if instruction.startswith('RUN ') and 'cargo build ' in instruction:
                if stage == 'mago':
                    kind = 'baseline'
                elif stage == 'mago-candidate':
                    kind = 'candidate'
        if re.search(r'^importing cache manifest from ', text):
            kind = 'import'
        elif re.search(r'^exporting (?:cache to|to GitHub Actions Cache)', text):
            kind = 'export'
        if kind:
            # Repeated descriptors are emitted during cached-layer extraction.
            if state['kind'] not in (None, kind):
                state['failed'] = True
            state['kind'] = kind
        if re.match(r'CACHED(?:\s|$)', text):
            state['cached'] = True
        if re.search(r'(?:^|\s)(?:Compiling \S|Finished [`\']?release|Finished `release`)', text):
            state['cargo'] = True
        if text.startswith('ERROR:') or re.match(r'(?:\d+(?:\.\d+)?\s+)?error(?:\[|:)', text):
            state['failed'] = True
        done = re.fullmatch(r'DONE(?:\s+(\d+(?:\.\d+)?)s)?', text)
        if done:
            state['done'] = float(done.group(1)) if done.group(1) is not None else None
            state['completed'] = True
        # A full Docker RUN can exceed the entire excerpt budget. Preserve the
        # outcome transitions rather than letting that declaration crowd them
        # out; a repeated cached extraction descriptor does not erase CACHED.
        if kind:
            state['lines']['descriptor'] = '#'+vertex+' '+text[:180]+(' [...]' if len(text) > 180 else '')
        for marker in ('CACHED', 'DONE', 'ERROR:'):
            if text.startswith(marker):
                state['lines'][marker] = '#'+vertex+' '+text[:120]
        if 'Finished ' in text:
            state['lines']['finished'] = '#'+vertex+' '+text[:120]
    result, evidence = {}, []
    for kind in ('baseline', 'candidate', 'import', 'export'):
        selected = [(vid, value) for vid, value in vertices.items() if value['kind'] == kind]
        row = {'outcome': 'unknown', 'duration_s': None, 'compile_duration_s': None,
               'vertex': None, 'evidence_ids': []}
        # Multiple candidate vertices cannot be attributed safely to one build.
        if len(selected) == 1:
            vid, state = selected[0]
            row['vertex'] = '#'+vid
            row['duration_s'] = state['done']
            if state['failed']:
                row['outcome'] = 'failed'
            elif kind in ('import', 'export'):
                row['outcome'] = 'success' if state.get('completed') else 'unknown'
            elif state['cached'] and state['cargo']:
                # Contradictory/reused vertex output cannot prove a cache hit.
                row['outcome'] = 'unknown'
            elif state['cached']:
                row['outcome'] = 'cached'
            elif state['cargo'] or (state.get('completed') and not truncated):
                row['outcome'] = 'executed'
            if kind in ('baseline', 'candidate') and row['outcome'] in ('executed', 'failed') and state['cargo']:
                row['compile_duration_s'] = state['done']
            elif kind in ('baseline', 'candidate') and row['outcome'] == 'executed':
                # This is the BuildKit RUN duration including bookkeeping, not
                # an independently measured inner cargo process duration.
                row['compile_duration_s'] = state['done']
            text = _clean('\n'.join(state['lines'].values()))
            clipped = text.encode()[:700].decode('utf-8', errors='ignore')
            eid = 'performance.build.'+kind
            evidence.append({'id': eid, 'text': clipped, 'truncated': len(text.encode()) > 700 or truncated})
            row['evidence_ids'] = [eid]
        result[kind] = row
    result['log_truncated'] = bool(truncated)
    return result, evidence


def compile_fingerprint(repo_root, *, platform='linux/amd64', build_args=None):
    """Fingerprint actual Mago compile inputs, excluding unrelated repo files.

    Covers syntax directive, all instructions in mago and mago-candidate stages
    (including pinned Rust base/source/default args), patch bytes, effective ARG
    values and platform. Native-test/runtime stages do not feed these binaries.
    """
    root = Path(repo_root)
    dockerfile = (root/'Dockerfile').read_text()
    marker = 'FROM mago-candidate AS mago-candidate-tests'
    if marker not in dockerfile:
        raise ValueError('Unrecognized Mago stage boundary')
    prefix = dockerfile.split(marker, 1)[0]
    if 'FROM mago AS mago-candidate' not in prefix or 'cargo build ' not in prefix:
        raise ValueError('Unrecognized Mago compile stages')
    instructions = '\n'.join(line for line in prefix.splitlines()
                             if line.strip() and (not line.lstrip().startswith('#') or line.startswith('# syntax=')))+'\n'
    defaults = dict(re.findall(r'^ARG ([A-Z0-9_]+)=(.*)$', prefix, re.M))
    supplied = {} if build_args is None else build_args
    if not isinstance(supplied, dict) or set(supplied) - set(defaults):
        raise ValueError('Unknown compile build argument')
    effective = {key: str(supplied.get(key, value)) for key, value in defaults.items()}
    for key, value in effective.items():
        _text(value, 200)
    inputs = {'docker_compile_instructions_sha256': hashlib.sha256(instructions.encode()).hexdigest(),
              'patch_sha256': hashlib.sha256((root/'patches/mago-lsp-extensions.patch').read_bytes()).hexdigest(),
              'build_args': effective, 'platform': platform,
              'rust_base': next(line.split()[1] for line in prefix.splitlines() if line.startswith('FROM ')),
              'coverage': 'Mago source pin, patch bytes, compile-stage Docker instructions/base, effective ARGs and platform; excludes docs, runtime/test stages, repository SHA and timestamps.'}
    return {'sha256': hashlib.sha256(_canonical(inputs)).hexdigest(), 'inputs': inputs}


def _inventory(repo_root):
    # Source definitions distinguish changed gates even when their counts agree.
    root = Path(repo_root)
    files = sorted(list((root/'tests/integration').glob('*.py')) +
                   list((root/'bin').glob('*.py')) + [root/'bin/poc'])
    digest = hashlib.sha256()
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError('Unsafe gate definition')
        digest.update(path.relative_to(root).as_posix().encode()+b'\0'+path.read_bytes()+b'\0')
    return {'definitions_sha256': digest.hexdigest(),
            'gates': [{'id': name, 'expected_checks': count} for name, count in
                      (('acceptance', 31), ('slice1', 9), ('slice2', 12), ('slice3', 14), ('lsp_extensions', 19))]}


def collect_observation(root, rows, ci, env=None, step_outcomes=None):
    env = os.environ if env is None else env
    root = Path(root)
    repo_root = Path(env.get('GITHUB_WORKSPACE', Path(__file__).resolve().parents[2]))
    phases = []
    if len(rows) > 100:
        raise ValueError('Performance ledger bound exceeded')
    for phase in PHASES:
        attempts = [row for row in rows if row.get('step') == phase]
        if len(attempts) > 10:
            raise ValueError('Performance phase attempt bound exceeded')
        if not attempts:
            outcome = (step_outcomes or {}).get(phase, {}).get('outcome')
            phases.append({'id': phase, 'attempt': 1,
                           'status': {'cancelled': 'cancelled', 'skipped': 'not_exercised', 'failure': 'fail'}.get(outcome, 'missing'),
                           'elapsed_s': None, 'started_unix': None})
        for row in attempts:
            phases.append({'id': phase, 'attempt': row['attempt'], 'status': row['status'],
                           'elapsed_s': row.get('elapsed_s'), 'started_unix': row.get('started_unix')})
    builds = [row for row in rows if row.get('step') == 'build' and row.get('log')]
    build, evidence = parse_buildkit('')
    if builds:
        # The last outer attempt is reported; other timings remain in phases.
        row = max(builds, key=lambda value: value['attempt'])
        name = f"build-attempt-{row['attempt']}.log"
        path = root/'ci'/name
        if row['log'] != name or path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_LOG:
            raise ValueError('Unsafe performance build log')
        build, evidence = parse_buildkit(path.read_bytes(), truncated=row.get('log_truncated', False))
    from build_image import PLATFORM
    platform = PLATFORM
    fingerprint = compile_fingerprint(repo_root, platform=platform)
    now = time.time()
    measured = [row for row in phases if row['elapsed_s'] is not None and row['started_unix'] is not None]
    start = min((row['started_unix'] for row in measured), default=None)
    end = max((row['started_unix']+row['elapsed_s'] for row in measured), default=None)
    observation = {
        'schema': 1, 'ci': dict(ci), 'observed_unix': now,
        'context': {'event': env.get('GITHUB_EVENT_NAME', 'unknown'), 'ref': env.get('GITHUB_REF', 'unknown'),
                    'runner': {'os': env.get('RUNNER_OS', 'unknown'), 'arch': env.get('RUNNER_ARCH', 'unknown'),
                               'environment': env.get('RUNNER_ENVIRONMENT', 'unknown'),
                               'class': env.get('PERFORMANCE_RUNNER_CLASS', 'ubuntu-latest' if env.get('GITHUB_ACTIONS') == 'true' else 'unknown'),
                               'image': env.get('ImageOS', 'unknown'), 'image_version': env.get('ImageVersion', 'unknown')},
                    'platform': platform, 'cache_scope': 'mago-serena-linux-amd64-v1'},
        'fingerprint': fingerprint, 'inventory': _inventory(repo_root), 'phases': phases,
        'timing': {'captured_wall_s': round(end-start, 3) if start is not None else None,
                   'step_sum_s': round(sum(row['elapsed_s'] for row in phases if row['elapsed_s'] is not None), 3),
                   'queue_s': None, 'setup_s': None, 'cleanup_s': None, 'job_wall_s': None},
        'build': build, 'evidence': evidence,
    }
    return validate_observation(_clean(observation), ci)


def validate_observation(value, expected_ci=None):
    if type(value) is not dict or type(value.get('schema')) is not int or value['schema'] != 1 or len(_canonical(value)) > MAX_OBSERVATION:
        raise ValueError('Invalid or oversized performance observation')
    if set(value) != {'schema', 'ci', 'observed_unix', 'context', 'fingerprint', 'inventory', 'phases', 'timing', 'build', 'evidence'}:
        raise ValueError('Unexpected performance fields')
    ci = value['ci']
    if (not isinstance(ci, dict) or not isinstance(ci.get('run_id'), str) or not ci['run_id'].isdigit()
            or len(ci['run_id']) > 30 or type(ci.get('attempt')) is not int or not 1 <= ci['attempt'] <= 10000
            or any(not _matches(r'[0-9a-f]{40}', ci.get(key)) for key in ('source_sha', 'workflow_head_sha'))
            or (expected_ci is not None and any(ci.get(key) != val for key, val in expected_ci.items()))):
        raise ValueError('Foreign or invalid performance run identity')
    _number(value['observed_unix'], maximum=4102444800)
    context = value['context']
    if not isinstance(context, dict) or set(context) != {'event', 'ref', 'runner', 'platform', 'cache_scope'}:
        raise ValueError('Invalid performance context')
    for key in ('event', 'ref', 'platform', 'cache_scope'):
        _text(context[key], 300)
    runner = context['runner']
    if not isinstance(runner, dict) or set(runner) != {'os', 'arch', 'environment', 'class', 'image', 'image_version'}:
        raise ValueError('Invalid runner identity')
    for text in runner.values():
        _text(text)
    fingerprint = value['fingerprint']
    if not isinstance(fingerprint, dict) or set(fingerprint) != {'sha256', 'inputs'} or not _matches(HEX, fingerprint.get('sha256')):
        raise ValueError('Invalid compile fingerprint')
    inputs = fingerprint['inputs']
    if not isinstance(inputs, dict) or set(inputs) != {'docker_compile_instructions_sha256', 'patch_sha256', 'build_args', 'platform', 'rust_base', 'coverage'}:
        raise ValueError('Invalid fingerprint inputs')
    for key in ('docker_compile_instructions_sha256', 'patch_sha256'):
        if not _matches(HEX, inputs.get(key)):
            raise ValueError('Invalid compile input digest')
    if (not isinstance(inputs['build_args'], dict) or not 1 <= len(inputs['build_args']) <= 10
            or any(not _matches(r'[A-Z0-9_]{1,60}', key) for key in inputs['build_args'])):
        raise ValueError('Invalid compile build arguments')
    for text in inputs['build_args'].values():
        _text(text)
    for key in ('platform', 'rust_base', 'coverage'):
        _text(inputs[key], 500)
    if hashlib.sha256(_canonical(inputs)).hexdigest() != fingerprint['sha256'] or inputs['platform'] != context['platform']:
        raise ValueError('Mismatched compile fingerprint')
    inventory = value['inventory']
    if (not isinstance(inventory, dict) or set(inventory) != {'definitions_sha256', 'gates'}
            or not _matches(HEX, inventory.get('definitions_sha256'))
            or not isinstance(inventory['gates'], list) or not 1 <= len(inventory['gates']) <= 20):
        raise ValueError('Invalid performance gate inventory')
    gate_ids = set()
    for row in inventory['gates']:
        if (not isinstance(row, dict) or set(row) != {'id', 'expected_checks'} or not _matches(IDENT, row.get('id'))
                or row['id'] in gate_ids or type(row.get('expected_checks')) is not int or not 1 <= row['expected_checks'] <= 1000):
            raise ValueError('Invalid performance gate')
        gate_ids.add(row['id'])
    phases = value['phases']
    if not isinstance(phases, list) or not 1 <= len(phases) <= 80:
        raise ValueError('Invalid performance phases')
    seen = set()
    for row in phases:
        if (not isinstance(row, dict) or set(row) != {'id', 'attempt', 'status', 'elapsed_s', 'started_unix'}
                or row.get('id') not in PHASES or type(row.get('attempt')) is not int or not 1 <= row['attempt'] <= 10
                or (row['id'], row['attempt']) in seen
                or row.get('status') not in {'pass', 'fail', 'blocked', 'not_exercised', 'missing', 'cancelled'}):
            raise ValueError('Invalid performance phase identity')
        seen.add((row['id'], row['attempt']))
        _number(row['elapsed_s'], optional=True)
        _number(row['started_unix'], optional=True, maximum=4102444800)
        if row['status'] in {'missing', 'not_exercised', 'cancelled'} and row['elapsed_s'] is not None:
            raise ValueError('Missing/cancelled phase has a duration')
    timing = value['timing']
    if not isinstance(timing, dict) or set(timing) != {'captured_wall_s', 'step_sum_s', 'queue_s', 'setup_s', 'cleanup_s', 'job_wall_s'}:
        raise ValueError('Invalid performance timing')
    for duration in timing.values():
        _number(duration, optional=True)
    if timing['step_sum_s'] is not None and abs(timing['step_sum_s']-sum(row['elapsed_s'] or 0 for row in phases)) > .01:
        raise ValueError('Mismatched performance duration sum')
    evidence = value['evidence']
    if not isinstance(evidence, list) or len(evidence) > 8:
        raise ValueError('Invalid performance evidence bound')
    ids = set()
    for row in evidence:
        if (not isinstance(row, dict) or set(row) != {'id', 'text', 'truncated'} or not _matches(IDENT, row.get('id'))
                or row['id'] in ids or not isinstance(row.get('text'), str) or len(row['text'].encode()) > 700
                or type(row.get('truncated')) is not bool):
            raise ValueError('Invalid performance evidence reference')
        ids.add(row['id'])
    build = value['build']
    if not isinstance(build, dict) or set(build) != {'baseline', 'candidate', 'import', 'export', 'log_truncated'} or type(build['log_truncated']) is not bool:
        raise ValueError('Invalid performance build inventory')
    for key in ('baseline', 'candidate', 'import', 'export'):
        row = build[key]
        choices = {'unknown', 'failed', 'success'} if key in ('import', 'export') else {'unknown', 'failed', 'cached', 'executed'}
        if (not isinstance(row, dict) or set(row) != {'outcome', 'duration_s', 'compile_duration_s', 'vertex', 'evidence_ids'}
                or row['outcome'] not in choices or not isinstance(row['evidence_ids'], list)
                or len(row['evidence_ids']) > 2 or any(eid not in ids for eid in row['evidence_ids'])
                or (row['vertex'] is not None and not _matches(r'#\d{1,6}', row['vertex']))):
            raise ValueError('Invalid BuildKit observation')
        _number(row['duration_s'], optional=True)
        _number(row['compile_duration_s'], optional=True)
        if row['outcome'] in {'cached', 'unknown'} and row['compile_duration_s'] is not None:
            raise ValueError('Unsupported compilation duration')
    return value


def assess(observation, baseline=None, policy=None):
    """Apply trusted policy. History wrappers are constructed by trusted lookup.

    Recompilation needs compatible recent history, prior export, a visible ref
    and a fresh positive cache inventory observation. That supports a diagnostic
    concern; it does not prove eviction, corruption or another root cause.
    """
    current = validate_observation(observation)
    policy = copy.deepcopy(POLICY if policy is None else policy)
    if set(policy) != set(POLICY):
        raise ValueError('Unknown performance policy')
    for value in policy.values():
        _number(value, maximum=31 * 86400)
    report = {'schema': 1, 'observation': current, 'baseline': None,
              'classifications': [], 'signals': [], 'provider_eligible': False,
              'comparison': {'compatible': False, 'configuration_compatible': False, 'reasons': [], 'deltas': []}, 'missing': [], 'policy': policy}
    compare = report['comparison']
    previous, wrapper = None, {}
    if baseline is not None:
        wrapper = baseline if isinstance(baseline, dict) and 'observation' in baseline else {'observation': baseline}
        previous = validate_observation(wrapper['observation'])
        reason = wrapper.get('selection_reason', 'identified prior observation')
        _text(reason, 500)
        report['baseline'] = {'ci': previous['ci'], 'selection_reason': reason,
                              'context': previous['context'], 'observed_unix': previous['observed_unix'],
                              'cache_regime': previous['build']['candidate']['outcome']}
        age = current['observed_unix']-previous['observed_unix']
        if not 0 < age <= policy['history_max_age_s']:
            compare['reasons'].append('stale_or_nonprior_baseline')
        if current['inventory'] != previous['inventory']:
            compare['reasons'].append('different_gate_inventory')
        if current['fingerprint']['sha256'] != previous['fingerprint']['sha256']:
            compare['reasons'].append('changed_compile_inputs')
        if (current['context']['runner'] != previous['context']['runner']
                or any(v == 'unknown' for v in current['context']['runner'].values())):
            compare['reasons'].append('different_or_unknown_runner')
        if current['context']['platform'] != previous['context']['platform']:
            compare['reasons'].append('different_platform')
        if current['context']['cache_scope'] != previous['context']['cache_scope']:
            compare['reasons'].append('different_cache_scope')
        compare['compatible'] = not compare['reasons']
        compare['configuration_compatible'] = compare['compatible']
    else:
        compare['reasons'].append('missing_baseline')
        report['missing'].append('No bounded, identified prior observation is available.')

    def classification(name):
        if name not in report['classifications']:
            report['classifications'].append(name)

    def signal(kind, details, ids=None):
        classification(kind)
        report['signals'].append({'kind': kind, 'details': details, 'evidence_ids': ids or []})

    candidate = current['build']['candidate']
    cold = any(current['build'][key]['outcome'] == 'executed' for key in ('baseline', 'candidate'))
    warm = all(current['build'][key]['outcome'] == 'cached' for key in ('baseline', 'candidate'))
    current_phases = {name: [p for p in current['phases'] if p['id'] == name] for name in PHASES}
    for row in current['phases']:
        if row['elapsed_s'] is None:
            report['missing'].append(row['id']+': duration unavailable ('+row['status']+').')
    if candidate['outcome'] == 'unknown':
        report['missing'].append('Candidate compile layer outcome is unknown; cache import is not layer reuse evidence.')

    prior_ref = previous['context']['ref'] if previous else ''
    visibility_boundary = (bool(re.fullmatch(r'refs/pull/\d+/merge', prior_ref))
                           and current['context']['ref'] != prior_ref)
    explained = bool(cold and previous and (
        'changed_compile_inputs' in compare['reasons'] or visibility_boundary))
    if explained:
        classification('explained_cold_population')
        report['missing'].append('Cold population is explained by changed inputs or ref visibility; recurring cache failure is not established.')
    if cold and compare['compatible'] and previous:
        entry = wrapper.get('cache_entry', {})
        observed = entry.get('observed_at_unix')
        # Trusted lookup happens after collection and validates that the cache
        # entry predates the source run. The observation may therefore be later
        # than this producer's timestamp.
        fresh = type(observed) in (int, float) and math.isfinite(observed) and abs(current['observed_unix']-observed) <= policy['cache_presence_max_age_s']
        if (previous['build']['export']['outcome'] == 'success'
                and previous['build']['candidate']['outcome'] in {'cached', 'executed'}
                and entry.get('accessible') is True and entry.get('source') == 'github_cache_inventory' and fresh):
            signal('unexpected_recompilation', 'Matching recent exported inputs and a currently visible cache entry support investigating recompilation; no root cause is proven.', candidate['evidence_ids'])
        else:
            report['missing'].append('Matching inputs alone do not establish a currently accessible reusable layer (visibility, export and eviction remain relevant).')

    # Absolute budgets remain usable without history; these are advisory signals.
    build_budget = policy['cold_build_budget_s'] if cold else policy['warm_build_budget_s'] if warm else policy['unknown_build_budget_s']
    for row in current['phases']:
        if row['status'] != 'pass' or row['elapsed_s'] is None:
            continue
        budget = build_budget if row['id'] == 'build' else policy['verification_budget_s'] if row['id'] in VERIFICATION else None
        if budget is not None and row['elapsed_s'] > budget:
            signal('absolute_budget_breach', f"{row['id']} {row['elapsed_s']:.3f}s exceeds configured {budget:.3f}s advisory budget.", candidate['evidence_ids'] if row['id'] == 'build' else [])
    if previous and compare['compatible']:
        previous_phases = {name: [p for p in previous['phases'] if p['id'] == name] for name in PHASES}
        same_regime = current['build']['candidate']['outcome'] == previous['build']['candidate']['outcome'] and current['build']['baseline']['outcome'] == previous['build']['baseline']['outcome']
        if not same_regime:
            compare['reasons'].append('different_cache_regime_for_timing')
            compare['compatible'] = False
        else:
            for name in ('build',)+VERIFICATION:
                now, old = current_phases[name], previous_phases[name]
                if len(now) != 1 or len(old) != 1 or any(row['status'] != 'pass' or row['elapsed_s'] is None for row in now+old):
                    continue
                before, after = old[0]['elapsed_s'], now[0]['elapsed_s']
                delta = after-before
                ratio = after/before if before > 0 else None
                compare['deltas'].append({'phase': name, 'baseline_s': before, 'current_s': after,
                                          'delta_s': round(delta, 3), 'ratio': round(ratio, 4) if ratio is not None else None})
                if name in VERIFICATION and ratio is not None and ratio >= policy['verification_relative_ratio'] and delta >= policy['verification_delta_s']:
                    signal('slow_verification', f'{name} increased {delta:.3f}s ({ratio:.3f}x) under one compatible observation; cache causation is not established.')
    build_passes = current_phases['build']
    if (warm and build_passes and all(row['status'] == 'pass' and row['elapsed_s'] is not None
                                     and row['elapsed_s'] <= build_budget for row in build_passes)
            and not any(row['kind'] == 'absolute_budget_breach' for row in report['signals'])):
        classification('warm_reuse')
    if not compare['compatible'] or not report['classifications'] or report['missing']:
        classification('insufficient_evidence')
    report['provider_eligible'] = bool(report['signals'])
    return report


def render_summary(report):
    """Readable deterministic facts before provider gating; Markdown is escaped."""
    def safe(value):
        return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('`', '&#96;').replace('\n', ' ')

    def duration(value):
        return 'unavailable' if value is None else f'{value:.3f}s'

    obs = report['observation']
    ci, context = obs['ci'], obs['context']
    url = f"https://github.com/xormania/mago-serena_v2-poc/actions/runs/{ci['run_id']}/attempts/{ci['attempt']}"
    lines = ['## CI performance (advisory)', '', f"[Producer run {ci['run_id']} / attempt {ci['attempt']}]({url}) · {safe(context['event'])} · {safe(context['ref'])}",
             '', f"Tested source: `{ci['source_sha']}`; workflow head: `{ci['workflow_head_sha']}`.",
             f"Runner: {safe(json.dumps(context['runner'], sort_keys=True))}; platform: {safe(context['platform'])}.",
             '', '| Phase / attempt | Native status | Duration |', '| --- | --- | --- |']
    for row in obs['phases']:
        lines.append(f"| {row['id']} / {row['attempt']} | {row['status']} | {duration(row['elapsed_s'])} |")
    timing = obs['timing']
    lines += ['', f"Captured wall span: {duration(timing['captured_wall_s'])}; sum of recorded command durations: {duration(timing['step_sum_s'])}.",
              f"Full job wall / queue / setup / cleanup: {duration(timing['job_wall_s'])} / {duration(timing['queue_s'])} / {duration(timing['setup_s'])} / {duration(timing['cleanup_s'])}.",
              '', '| BuildKit work | Outcome | RUN/layer duration | Compile RUN duration |', '| --- | --- | --- | --- |']
    for name in ('baseline', 'candidate', 'import', 'export'):
        row = obs['build'][name]
        lines.append(f"| {name} | {row['outcome']} | {duration(row['duration_s'])} | {duration(row['compile_duration_s'])} |")
    lines += ['', 'Cached-layer download/extraction durations are not compilation; import success does not prove layer reuse.',
              f"Compile fingerprint: `{obs['fingerprint']['sha256']}`.", safe(obs['fingerprint']['inputs']['coverage']),
              f"Effective compile inputs: {safe(json.dumps(obs['fingerprint']['inputs'], sort_keys=True))}.",
              f"Gate inventory: {safe(json.dumps(obs['inventory'], sort_keys=True))}.",
              '', '**Deterministic classification:** '+', '.join(report['classifications'])+'.']
    if report['baseline']:
        old = report['baseline']['ci']
        old_url = f"https://github.com/xormania/mago-serena_v2-poc/actions/runs/{old['run_id']}/attempts/{old['attempt']}"
        lines += [f"Comparison: [run {old['run_id']} / attempt {old['attempt']}]({old_url}), source `{old['source_sha']}`; {safe(report['baseline']['selection_reason'])}."]
    lines += ['Comparison compatibility: '+('compatible' if report['comparison']['compatible'] else 'unavailable/incomparable')+
              '; '+safe(', '.join(report['comparison']['reasons']) or 'matching runner, inputs and gate definitions')+'.']
    for delta in report['comparison']['deltas']:
        lines.append(f"- {delta['phase']}: {duration(delta['baseline_s'])} → {duration(delta['current_s'])}; delta {delta['delta_s']:+.3f}s; ratio {delta['ratio']}.")
    if report['signals']:
        lines += ['', '**Advisory signals:**']+[f"- {safe(row['details'])}" for row in report['signals']]
    lines += ['', f"Jev performance eligibility: **{'yes' if report['provider_eligible'] else 'no'}**. "+
              ('Trusted reservation, credentials and failure-evidence gates still apply; eligibility is not a provider call.' if report['provider_eligible'] else 'No supported actionable performance signal; zero performance provider requests are needed.'),
              'A single comparison is an observation, not a statistical performance guarantee. Native acceptance results are independent.']
    if report['missing']:
        lines += ['', '**Missing evidence / limits:**']+[f'- {safe(text)}' for text in report['missing']]
    if obs['evidence']:
        lines += ['', '<details><summary>Bounded BuildKit evidence</summary>', '']
        for row in obs['evidence']:
            lines += [f"**{row['id']}**"+(' (truncated)' if row['truncated'] else ''), '', '<pre>'+safe(row['text'])+'</pre>', '']
        lines += ['</details>']
    return '\n'.join(lines)+'\n'
