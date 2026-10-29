"""Bounded, key-free baseline lookup performed only by the trusted consumer.

Artifacts are observations, never policy. Search at most 20 prior successful
producer runs and download at most three exact-attempt packets, without extraction.
Prefer the same event/ref, then default-branch push history. A cache index is only
availability evidence, not proof that any particular layer remains recoverable.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import re
import tempfile
import time
import urllib.parse
import urllib.request

from download_inputs import download
from jev import NoRedirect, parse_json
from performance import validate_observation

MAX_RUNS = 20
MAX_DOWNLOADS = 3
MAX_AGE_S = 7 * 86400
MAX_API_BYTES = 1_000_000


def _json(opener, url, token):
    request = urllib.request.Request(url, headers={
        'Authorization': 'Bearer '+token, 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'})
    with opener.open(request, timeout=15) as response:
        raw = response.read(MAX_API_BYTES+1)
    if len(raw) > MAX_API_BYTES:
        raise ValueError('Performance history API bound exceeded')
    value = parse_json(raw)
    if not isinstance(value, dict):
        raise ValueError('Invalid performance history API response')
    return value


def _epoch(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('Invalid history timestamp')
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).timestamp()


def source_timing(event, token, *, opener=None):
    """Read the completed attempt's job timing, unavailable to a live producer.

    Values come from the Actions API, whose second resolution differs from the
    monotonic command ledger. Setup sums named setup actions; cleanup sums post
    actions. Neither is substituted for the full job wall duration.
    """
    opener = opener or urllib.request.build_opener(NoRedirect())
    source, repo = event['workflow_run'], event['repository']['full_name']
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)
            or source.get('head_repository', {}).get('full_name') != repo
            or type(source.get('id')) is not int or type(source.get('run_attempt')) is not int):
        raise ValueError('Invalid source timing identity')
    result = {'status': 'unavailable', 'resolution_s': 1, 'job_wall_s': None,
              'queue_s': None, 'setup_s': None, 'cleanup_s': None}
    try:
        jobs = _json(opener, f"https://api.github.com/repos/{repo}/actions/runs/{source['id']}/attempts/{source['run_attempt']}/jobs?per_page=20", token)
        rows = jobs.get('jobs')
        if not isinstance(rows, list) or len(rows) > 20 or jobs.get('total_count') != len(rows):
            raise ValueError('Incomplete source job inventory')
        acceptance = [row for row in rows if row.get('name') == 'acceptance']
        if len(acceptance) != 1:
            return result
        job = acceptance[0]
        def duration(start, end):
            elapsed = _epoch(end)-_epoch(start)
            if not 0 <= elapsed <= 31*86400:
                raise ValueError('Invalid source timing range')
            return elapsed
        steps = job.get('steps')
        if not isinstance(steps, list) or len(steps) > 100:
            raise ValueError('Invalid source step inventory')
        setup, cleanup = 0, 0
        for row in steps:
            name = row.get('name', '')
            if (name == 'Set up job' or name.startswith(('Run actions/checkout@', 'Run astral-sh/setup-uv@', 'Run docker/setup-buildx-action@', 'Run ./.github/actions/cache-runtime'))):
                setup += duration(row['started_at'], row['completed_at'])
            elif name.startswith('Post ') or name == 'Complete job':
                cleanup += duration(row['started_at'], row['completed_at'])
        queue_start = source.get('run_started_at') if source['run_attempt'] > 1 else source['created_at']
        result.update(status='observed', job_id=job.get('id'),
                      job_wall_s=duration(job['started_at'], job['completed_at']),
                      queue_s=duration(queue_start, job['started_at']) if queue_start else None,
                      setup_s=setup, cleanup_s=cleanup)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        result.update(status='timing_lookup_failed', exception_type=type(exc).__name__)
    return result


def lookup_baseline(packet, event, token, *, opener=None, now=None):
    """Return (trusted-selection wrapper or None, bounded selection audit).

    Incomplete/expired/legacy history means comparison unavailable, never a paid
    retry. Network/schema failures are surfaced in the audit and consumer summary.
    """
    source = event['workflow_run']
    repo = event['repository']['full_name']
    default = event['repository']['default_branch']
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)
            or source.get('head_repository', {}).get('full_name') != repo):
        raise ValueError('Foreign performance history source')
    now = time.time() if now is None else now
    audit = {'strategy': 'newest compatible same event/ref, then default push; 20 runs/3 downloads/7 days',
             'runs_examined': 0, 'downloads_attempted': 0, 'rejections': [], 'status': 'comparison_unavailable'}
    opener = opener or urllib.request.build_opener(NoRedirect())
    fallback = None
    try:
        listing = _json(opener, f'https://api.github.com/repos/{repo}/actions/workflows/poc.yml/runs?status=success&per_page={MAX_RUNS}', token)
        runs = listing.get('workflow_runs')
        if not isinstance(runs, list) or len(runs) > MAX_RUNS:
            raise ValueError('Invalid bounded history inventory')
        candidates = []
        current_started = _epoch(source['created_at'])
        for run in runs:
            audit['runs_examined'] += 1
            if (not isinstance(run, dict) or type(run.get('id')) is not int
                    or type(run.get('run_attempt')) is not int or run['run_attempt'] < 1):
                raise ValueError('Invalid history identity')
            same = (run.get('event') == source.get('event') and run.get('head_branch') == source.get('head_branch'))
            trusted_default = run.get('event') == 'push' and run.get('head_branch') == default
            if not (same or trusted_default) or str(run['id']) == packet['ci']['run_id']:
                continue
            created = _epoch(run.get('created_at'))
            if not 0 <= now-created <= MAX_AGE_S or created >= current_started:
                continue
            if (run.get('conclusion') != 'success' or run.get('status') != 'completed'
                    or str(run.get('path', '')).split('@', 1)[0] != '.github/workflows/poc.yml'
                    or run.get('repository', {}).get('full_name') != repo
                    or run.get('head_repository', {}).get('full_name') != repo
                    or not re.fullmatch(r'[0-9a-f]{40}', run.get('head_sha', ''))):
                continue
            candidates.append((not same, -created, run))
        for _, _, run in sorted(candidates, key=lambda row: row[:2]):
            if audit['downloads_attempted'] >= MAX_DOWNLOADS:
                break
            audit['downloads_attempted'] += 1
            reason = 'same event/ref' if run['event'] == source.get('event') and run['head_branch'] == source.get('head_branch') else 'default branch push'
            try:
                with tempfile.TemporaryDirectory(prefix='jev-baseline-') as directory:
                    previous = download({'repository': event['repository'], 'workflow_run': run}, Path(directory)/'packet.json', token, opener=opener)
                if previous is None or 'performance' not in previous:
                    audit['rejections'].append({'run_id': str(run['id']), 'reason': 'missing, expired or legacy performance artifact'})
                    continue
                observation = validate_observation(previous['performance'], previous['ci'])
                current = packet['performance']
                # Prefer a compatible sample. A final incompatible observation is
                # still useful to explain changed inputs or a visibility boundary.
                compatible = all(observation.get(key) == current.get(key) for key in ('inventory',))
                prior_context, current_context = observation.get('context', {}), current.get('context', {})
                compatible = compatible and prior_context.get('runner') == current_context.get('runner')
                compatible = compatible and observation.get('fingerprint') == current.get('fingerprint')
                wrapper = {'observation': observation, 'selection_reason': reason+'; bounded newest prior successful observation',
                           'cache_entry': {'accessible': False, 'observed_at_unix': now, 'source': 'github_cache_inventory'}}
                if compatible:
                    scope = current_context.get('cache_scope')
                    ref = prior_context.get('ref')
                    visible = ref in {current_context.get('ref'), 'refs/heads/'+default}
                    if visible and isinstance(scope, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', scope):
                        query = urllib.parse.urlencode({'key': 'index-'+scope, 'ref': ref, 'per_page': 20})
                        cache = _json(opener, f'https://api.github.com/repos/{repo}/actions/caches?{query}', token)
                        entries = cache.get('actions_caches')
                        if not isinstance(entries, list) or len(entries) > 20:
                            raise ValueError('Invalid bounded cache inventory')
                        wrapper['cache_entry']['accessible'] = any(
                            row.get('ref') == ref and str(row.get('key', '')).startswith('index-'+scope+'-')
                            and type(row.get('id')) is int
                            and _epoch(row.get('created_at')) <= current_started for row in entries)
                    audit.update(status='baseline_selected', selected_run_id=str(run['id']), selection_reason=wrapper['selection_reason'])
                    return wrapper, audit
                audit['rejections'].append({'run_id': str(run['id']), 'reason': 'runner, inventory or compile inputs differ'})
                if fallback is None:
                    fallback = wrapper
            except (ValueError, KeyError, TypeError, OSError) as exc:
                audit['rejections'].append({'run_id': str(run['id']), 'reason': 'unavailable or invalid evidence', 'exception_type': type(exc).__name__})
        if fallback is not None:
            audit.update(status='incomparable_baseline_selected', selected_run_id=fallback['observation']['ci']['run_id'])
            return fallback, audit
    except (ValueError, KeyError, TypeError, OSError) as exc:
        audit.update(status='history_lookup_failed', exception_type=type(exc).__name__)
    return None, audit
