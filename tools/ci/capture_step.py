"""Credential-free step collector. Commands keep their original exit status; no retries."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from jev import PROBES, canonical, sanitize, validate_packet, parse_json
LOG_LIMIT = 1024 * 1024
SLICE_ATTEMPT_LIMIT = 20
SLICE_RESULT_LIMIT = 1024 * 1024
SLICE_SOURCE_LIMIT = 16 * 1024 * 1024


def _bounded_file(path, limit):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Invalid bounded slice evidence: '+path.name)
    with path.open('rb') as stream:
        raw = stream.read(limit+1)
    if len(raw) > limit:
        raise ValueError('Invalid bounded slice evidence: '+path.name)
    return raw


def _slice_excerpt(stage, reason, trace):
    # The producer's reason is authoritative. Tracebacks often end with the
    # useful frame/cause, well after both the console excerpt and their header.
    clean = sanitize(stage+': '+reason).encode()
    tail = sanitize(trace.decode('utf-8', errors='replace')).encode()
    limit = 900 if tail else 1500
    prefix = clean[:limit].decode('utf-8', errors='ignore')
    ending = tail[-(1500-len(prefix.encode())-1):].decode('utf-8', errors='ignore') if tail else ''
    return prefix+('\n'+ending if ending else ''), len(clean) > limit or len(tail) > len(ending.encode())


def _slice_failures(run_dir, source_sha):
    """Read only the two declared slice layouts, never crawl arbitrary artifacts.

    Latest-result files mirror an attempt; they are validated, not emitted as
    additional observations. Every retained retry remains a distinct attempt.
    """
    failures = []
    for slice_name in ('slice1', 'slice2'):
        directory = run_dir/slice_name
        summary = run_dir/(slice_name+'-result.json')
        if directory.is_symlink():
            raise ValueError('Invalid slice evidence directory')
        if not directory.exists():
            if summary.exists() or summary.is_symlink():
                raise ValueError('Slice summary has no attempt directory')
            continue
        attempts = sorted(directory.iterdir())
        if len(attempts) > SLICE_ATTEMPT_LIMIT:
            raise ValueError('Slice attempt directory bound exceeded')
        documents = {}
        for attempt_dir in attempts:
            if (attempt_dir.is_symlink() or not attempt_dir.is_dir()
                    or not re.fullmatch(r'attempt-[A-Za-z0-9_-]{1,80}', attempt_dir.name)):
                raise ValueError('Invalid slice attempt directory')
            result_path = attempt_dir/'results.json'
            if not result_path.exists() and not result_path.is_symlink():
                continue  # An interrupted attempt can have no published result.
            value = parse_json(_bounded_file(result_path, SLICE_RESULT_LIMIT))
            source = parse_json(_bounded_file(attempt_dir/'source.json', SLICE_SOURCE_LIMIT))
            context = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if (not isinstance(value, dict) or not isinstance(source, dict)
                    or value.get('schema') != 1 or value.get('kind') != 'mago_first_'+slice_name
                    or value.get('run_id') != run_dir.name
                    or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', run_dir.name)
                    or not isinstance(value.get('workspace'), str) or len(value['workspace']) > 1000
                    or value.get('source_context_sha256') != context
                    or source.get('revision') != source_sha
                    or not isinstance(source.get('run'), dict)
                    or source['run'].get('run_id') != run_dir.name
                    or source['run'].get('app') != value.get('workspace')
                    or value.get('evidence') != str(attempt_dir)
                    or value.get('attempt_id', attempt_dir.name) != attempt_dir.name):
                raise ValueError('Mismatched slice run, attempt or source identity')
            inventory, checks = value.get('inventory'), value.get('checks')
            if (not isinstance(inventory, list) or not isinstance(checks, list)
                    or not checks or len(checks) > 100 or len(inventory) != len(checks)
                    or any(not isinstance(row, dict) for row in checks)):
                raise ValueError('Invalid slice check inventory')
            names = [row.get('name') for row in checks]
            if (any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', name) for name in names)
                    or len(set(names)) != len(names) or inventory != names):
                raise ValueError('Invalid or duplicate slice stage')
            if (value.get('status') not in {'pass', 'incomplete'}
                    or (value['status'] == 'pass') != all(row.get('status') == 'pass' for row in checks)):
                raise ValueError('Mismatched slice aggregate status')
            for row in checks:
                if (any(row.get(key) != value.get(key) for key in ('run_id', 'workspace', 'source_context_sha256'))
                        or row.get('attempt_id', attempt_dir.name) != attempt_dir.name
                        or row.get('status') not in {'pass', 'fail', 'blocked', 'not_exercised'}):
                    raise ValueError('Mismatched slice stage identity/status')
                if row['status'] not in {'fail', 'blocked'}:
                    continue
                n = row.get('step_attempt', 1)
                if type(n) is not int or not 1 <= n <= 100:
                    raise ValueError('Invalid slice stage attempt')
                reason = row.get('reason', row.get('assertion', 'No stage reason recorded'))
                if not isinstance(reason, str):
                    raise ValueError('Invalid slice stage reason')
                provenance = {'run_id': run_dir.name, 'attempt_id': attempt_dir.name,
                              'context_sha256': context, 'source_sha': source_sha,
                              'step_attempt': n, 'stage': row['name'],
                              'source': result_path.relative_to(run_dir).as_posix()}
                trace_path = attempt_dir/(row['name']+'-error.txt')
                trace = _bounded_file(trace_path, LOG_LIMIT) if trace_path.exists() or trace_path.is_symlink() else b''
                text, truncated = _slice_excerpt(row['name'], reason, trace)
                failures.append((slice_name, row['status'], provenance, text, truncated))
            documents[str(attempt_dir)] = value
        if summary.exists() or summary.is_symlink():
            latest = parse_json(_bounded_file(summary, SLICE_RESULT_LIMIT))
            if (not isinstance(latest, dict) or not isinstance(latest.get('evidence'), str)
                    or documents.get(latest['evidence']) != latest):
                raise ValueError('Mismatched slice latest-result mirror')
    return failures


def capture(step, attempt, command, root):
    if not re.fullmatch('[a-z][a-z0-9_-]{0,39}', step) or not 1 <= attempt <= 10:
        raise ValueError('Invalid step or attempt')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f'{step}-attempt-{attempt}.log'
    started = time.time()
    count = 0
    with path.open('xb') as output:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            while block := process.stdout.read(4096):
                clean = sanitize(block.decode(errors='replace')).encode()
                sys.stdout.buffer.write(clean)
                sys.stdout.buffer.flush()
                if count < LOG_LIMIT:
                    output.write(clean[:LOG_LIMIT-count])
                count += len(clean)
            process.stdout.close()
            code = process.wait()
        except OSError as exc:
            output.write(f'Command setup failed: {type(exc).__name__}\n'.encode())
            code = 127
    row = {'step':step, 'attempt':attempt, 'command':sanitize(command), 'status':'pass' if code == 0 else 'fail',
           'exit_status':code, 'started_unix':started, 'elapsed_s':round(time.time()-started, 3),
           'log':path.name, 'log_truncated':count > LOG_LIMIT,
           'log_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    with (root/'step-attempts.jsonl').open('ab') as output:
        output.write(canonical(row)+b'\n')
    return code if code >= 0 else 128-code


def _excerpt(raw):
    text = raw.decode('utf-8', errors='replace')
    # Preserve a first causal-looking error and nearby lines, rather than only a final count.
    lines = text.splitlines()
    hit = next((i for i, line in enumerate(lines) if re.search(r'error|exception|assert|fail|mismatch|denied|missing|timeout', line, re.I)), max(0,len(lines)-10))
    selected = '\n'.join(lines[max(0,hit-2):hit+10])
    clean = sanitize(selected).encode()
    clipped = clean[:1500].decode('utf-8', errors='ignore')
    return clipped, len(clean) > 1500 or len(raw) > len(selected.encode())


def collect(root, output, *, run_id, attempt, source_sha, workflow_head_sha=None, step_outcomes=None):
    # Producers retain absolute owned evidence paths even when the CLI receives
    # its ordinary relative --root artifacts argument.
    root = Path(root).resolve()
    checks, excerpts = [], []
    seen = set()
    ledger = root/'ci/step-attempts.jsonl'
    rows = []
    if ledger.exists():
        if ledger.stat().st_size > 100000:
            raise ValueError('CI ledger bound exceeded')
        rows = [parse_json(line) for line in ledger.read_text().splitlines()]
    # Action-only setup failures still have a verdict even when no command logger ran.
    for step, outcome in (step_outcomes or {}).items():
        if outcome.get('outcome') == 'failure' and not any(row['step'] == step for row in rows):
            rows.append({'step':step, 'attempt':1, 'status':'fail', 'log':None,
                         'log_truncated':False, 'message':'GitHub Action failed before captured command execution; detailed action log not supplied.'})
    # Failures first; recovered failed attempts remain independent observations.
    rows.sort(key=lambda row: row.get('status') != 'fail')
    for row in rows[:12]:
        step, n = row['step'], row['attempt']
        if not re.fullmatch('[a-z][a-z0-9_-]{0,39}', step) or type(n) is not int or not 1 <= n <= 10 or (step,n) in seen:
            raise ValueError('Duplicate/invalid CI step attempt')
        seen.add((step,n))
        eid = f'{step}.attempt{n}'
        if row.get('log'):
            name = f'{step}-attempt-{n}.log'
            if row['log'] != name:
                raise ValueError('Invalid log reference')
            path = root/'ci'/name
            if path.is_symlink() or not path.is_file() or path.stat().st_size > LOG_LIMIT:
                raise ValueError('Invalid bounded step log')
            text, truncated = _excerpt(path.read_bytes())
        else:
            text, truncated = row['message'], False
        excerpts.append({'id':eid,'step':step,'attempt':n,'text':text,'truncated':truncated or row.get('log_truncated',False)})
        checks.append({'id':eid,'step':step,'attempt':n,'status':row['status'],'excerpt_ids':[eid]})
    # Include each failed internal attempt, even when a later check recovered.
    internal, slice_internal = [], []
    run_dirs = sorted(path for path in root.iterdir() if path.is_dir() and not path.is_symlink() and path.name not in {'ci','jev-input'})
    for run_dir in run_dirs[:20]:
        slice_internal.extend(_slice_failures(run_dir, source_sha))
        ledgers = [run_dir/name for name in ('step-attempts.jsonl','integration-attempts.jsonl')]
        present = False
        for path in ledgers:
            if not path.exists():
                continue
            present = True
            if path.is_symlink() or path.stat().st_size > 1000000:
                raise ValueError('Internal attempt ledger bound exceeded')
            for line in path.read_text().splitlines()[:1000]:
                row = parse_json(line)
                if row.get('status') in {'fail','blocked'}:
                    internal.append((run_dir,row))
        result = run_dir/'results.json'
        if not present and result.is_file() and not result.is_symlink() and result.stat().st_size <= 200000:
            data = parse_json(result.read_text())
            for row in data.get('checks',[]):
                if row.get('status') in {'fail','blocked'}:
                    internal.append((run_dir,{**row,'run_id':data.get('run_id',run_dir.name),'attempt_id':data.get('attempt_id','unknown')}))
    kept = 0
    for run_dir,row in internal:
        if len(excerpts) >= 20:
            break
        provenance = {k:row.get(k) for k in ('run_id','attempt_id','context_sha256','step_attempt')}
        name = str(row.get('name','unknown'))
        eid = 'internal.'+hashlib.sha256(canonical([provenance,name])).hexdigest()[:16]
        if eid in {x['id'] for x in excerpts}:
            raise ValueError('Duplicate internal failed attempt')
        assertion = str(row.get('assertion',''))
        trace = run_dir/(name+'.traceback.txt')
        if (re.fullmatch('[A-Za-z0-9_-]{1,80}',name) and trace.is_file() and not trace.is_symlink()
                and trace.stat().st_size <= LOG_LIMIT):
            assertion += '\n'+trace.read_text()
        text,truncated = _excerpt((name+': '+assertion).encode())
        n = row.get('step_attempt',1)
        if type(n) is not int or n < 1:
            raise ValueError('Invalid internal step attempt')
        excerpts.append({'id':eid,'step':'acceptance','attempt':n,'text':text,'truncated':truncated,'provenance':provenance})
        checks.append({'id':eid,'step':'acceptance','attempt':n,'status':row['status'],'excerpt_ids':[eid]})
        kept += 1
    slice_kept = 0
    # A failed stage carries the causal observation; blocked dependants follow
    # it, so they cannot use the excerpt budget before the actual failure.
    slice_internal.sort(key=lambda item: item[1] != 'fail')
    for slice_name, status, provenance, text, truncated in slice_internal:
        if len(excerpts) >= 20:
            break
        eid = 'internal.'+hashlib.sha256(canonical(provenance)).hexdigest()[:16]
        excerpts.append({'id': eid, 'step': slice_name, 'attempt': provenance['step_attempt'],
                         'text': text, 'truncated': truncated, 'provenance': provenance})
        checks.append({'id': eid, 'step': slice_name, 'attempt': provenance['step_attempt'],
                       'status': status, 'excerpt_ids': [eid]})
        slice_kept += 1
    packet = {'schema':1,'mode':'observed_ci','ci':{'run_id':str(run_id),'attempt':int(attempt),'source_sha':source_sha,'workflow_head_sha':workflow_head_sha or source_sha},
              'checks':checks,'excerpts':excerpts,'allowed_probes':PROBES,
              'collection':{'step_rows_omitted':max(0,len(rows)-12),'excerpt_limit':20,'internal_failed_attempts_omitted':len(internal)-kept+len(slice_internal)-slice_kept, 'run_directories_omitted':max(0,len(run_dirs)-20),
                            'note':'Bounded selected excerpts; full available per-step and harness evidence is a separate artifact.'}}
    validate_packet(packet)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(packet)+b'\n')
    return packet


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='mode',required=True)
    run = sub.add_parser('run'); run.add_argument('--step',required=True); run.add_argument('--attempt',type=int,default=1)
    run.add_argument('--out',default='artifacts/ci'); run.add_argument('command',nargs=argparse.REMAINDER)
    packet = sub.add_parser('collect'); packet.add_argument('--root',default='artifacts')
    packet.add_argument('--out',default='artifacts/jev-input/diagnosis-input.json')
    args = p.parse_args()
    if args.mode == 'run':
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        if not command:
            raise ValueError('No command supplied')
        return capture(args.step,args.attempt,command,args.out)
    event_path = Path(os.environ['GITHUB_EVENT_PATH'])
    if event_path.stat().st_size > 5000000:
        raise ValueError('GitHub event bound exceeded')
    event = parse_json(event_path.read_bytes())
    head = event.get('pull_request',{}).get('head',{}).get('sha',os.environ['GITHUB_SHA'])
    collect(args.root,args.out,run_id=os.environ['GITHUB_RUN_ID'],attempt=os.environ['GITHUB_RUN_ATTEMPT'],
            source_sha=os.environ['GITHUB_SHA'],workflow_head_sha=head,step_outcomes=parse_json(os.environ.get('STEP_OUTCOMES','{}')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
