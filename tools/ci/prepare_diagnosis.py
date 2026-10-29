"""Trusted, key-free gate and durable reservation for one diagnostic source attempt.

The workflow serializes a source identity. This gate checks earlier reservations,
then the workflow uploads a new immutable reservation BEFORE exposing TypeSafe's
key. A failed or interrupted provider step remains reserved; there is no automatic
provider retry. Downloaded artifacts are inspected as data only.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jev import MAX_PACKET, NoRedirect, canonical, diagnose, parse_json, performance_report, validate_packet

MAX_API_BYTES = 1_000_000
_BASELINE_UNSET = object()


def api_json(opener, url, token):
    request = urllib.request.Request(url, headers={
        'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28'})
    with opener.open(request, timeout=15) as response:
        raw = response.read(MAX_API_BYTES+1)
    if len(raw) > MAX_API_BYTES:
        raise ValueError('Reservation API response exceeds bound')
    return parse_json(raw)


def prior_reservation(repo, name, default_branch, token, *, opener=None):
    """Only reservations owned by this trusted consumer/default branch count."""
    opener = opener or urllib.request.build_opener(NoRedirect())
    query = urllib.parse.urlencode({'name':name, 'per_page':100})
    listing = api_json(opener, f'https://api.github.com/repos/{repo}/actions/artifacts?{query}', token)
    if type(listing.get('total_count')) is not int or listing['total_count'] > 100:
        raise ValueError('Reservation inventory incomplete; refuse a provider call')
    rows = listing.get('artifacts')
    if not isinstance(rows, list) or len(rows) > 20 or len(rows) != listing['total_count']:
        raise ValueError('Invalid reservation inventory')
    for artifact in rows:
        if artifact.get('name') != name:
            continue
        owner = artifact.get('workflow_run', {}).get('id')
        if type(owner) is not int or owner <= 0:
            raise ValueError('Reservation owner missing')
        run = api_json(opener, f'https://api.github.com/repos/{repo}/actions/runs/{owner}', token)
        path = str(run.get('path', '')).split('@',1)[0]
        if (path == '.github/workflows/jev.yml' and run.get('head_branch') == default_branch
                and run.get('event') in {'workflow_run','workflow_dispatch'}
                and run.get('repository', {}).get('full_name') == repo):
            # Expiry does not authorize another call. Name/owner are enough;
            # this code never downloads or executes the reservation's contents.
            return {'artifact_id':artifact.get('id'), 'consumer_run_id':owner,
                    'artifact_expired':bool(artifact.get('expired'))}
    return None


def prepare(event, packet_path, control_dir, output_dir, reservation_dir, context, token, *, opener=None, baseline=_BASELINE_UNSET):
    repo = event['repository']['full_name']
    default = event['repository']['default_branch']
    trusted = context['trusted_sha']
    consumer = str(context['run_id'])
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)
            or not re.fullmatch(r'[0-9a-f]{40}',trusted) or not consumer.isdigit()
            or type(context['attempt']) is not int or context['attempt'] < 1):
        raise ValueError('Invalid trusted execution context')
    record = {'schema':1, 'trusted_revision':trusted, 'consumer_run_id':consumer,
              'consumer_attempt':context['attempt'], 'provider_needed':False,
              'reservation_written':False}
    control_dir, output_dir, reservation_dir = map(Path,(control_dir,output_dir,reservation_dir))
    control_dir.mkdir(parents=True,exist_ok=False)
    if context['attempt'] > 1:
        # An Actions rerun is not authorization to repeat a potentially billed
        # request, even if its earlier reservation artifact has since expired.
        record['status']='consumer_rerun_suppressed'
        output_dir.mkdir(parents=True,exist_ok=False)
        (output_dir/'gate-result.json').write_bytes(canonical(record)+b'\n')
        (control_dir/'result.json').write_bytes(canonical(record)+b'\n')
        return record
    if context['event_name'] == 'workflow_dispatch':
        if event.get('inputs', {}).get('calibration') not in (True,'true'):
            raise ValueError('Manual calibration not explicitly authorized')
        # A rerun of this dispatch must not authorize another four requests.
        name = f'jev-reservation-calibration-{consumer}'
        record.update(kind='calibration', tested_source_revision=trusted,
                      calibration_fixture_sha256=hashlib.sha256(Path(__file__).with_name('calibration.json').read_bytes()).hexdigest())
    elif context['event_name'] == 'workflow_run':
        source = event['workflow_run']
        source_id, attempt = str(source['id']), source['run_attempt']
        if source.get('head_repository', {}).get('full_name') != repo:
            raise ValueError('Foreign source repository')
        if not source_id.isdigit() or type(attempt) is not int or attempt < 1:
            raise ValueError('Invalid source attempt')
        record.update(source_run_id=source_id,source_attempt=attempt,
                      source_conclusion=source.get('conclusion'))
        if source.get('conclusion') in {'cancelled','skipped'}:
            # Superseded PR runs are deliberately cancelled by acceptance's
            # concurrency policy. That is not a new paid diagnosis request.
            record['status']='source_'+source['conclusion']
            output_dir.mkdir(parents=True,exist_ok=False)
            (output_dir/'gate-result.json').write_bytes(canonical(record)+b'\n')
            (control_dir/'result.json').write_bytes(canonical(record)+b'\n')
            return record
        if packet_path is None or not Path(packet_path).is_file():
            record.update(status='missing_evidence', source_run_id=source_id, source_attempt=attempt,
                          expected_artifact=f'jev-input-{source_id}-{attempt}')
            (output_dir).mkdir(parents=True,exist_ok=False)
            (output_dir/'gate-result.json').write_bytes(canonical(record)+b'\n')
            (control_dir/'result.json').write_bytes(canonical(record)+b'\n')
            return record
        packet_file = Path(packet_path)
        if packet_file.is_symlink() or packet_file.stat().st_size > MAX_PACKET:
            raise ValueError('Invalid bounded packet file')
        packet = validate_packet(parse_json(packet_file.read_bytes()),{
            'run_id':source_id,'attempt':attempt,'workflow_head_sha':source['head_sha']})
        record.update(kind='producer',source_run_id=source_id,source_attempt=attempt,
                      tested_source_revision=packet['ci']['source_sha'])
        report = None
        if 'performance' in packet:
            from performance import render_summary
            if baseline is _BASELINE_UNSET:
                from performance_history import lookup_baseline, source_timing
                baseline, lookup = lookup_baseline(packet, event, token, opener=opener)
                lookup['source_timing'] = source_timing(event, token, opener=opener)
            else:
                lookup = {'status':'explicit_trusted_baseline' if baseline else 'explicit_no_baseline'}
            if baseline is not None:
                (control_dir/'baseline.json').write_bytes(canonical(baseline)+b'\n')
            report = performance_report(packet, baseline)
            record['performance_history'] = lookup
            record['performance_classifications'] = report['classifications']
            record['performance_eligible'] = report['provider_eligible']
            (control_dir/'performance-report.json').write_bytes(canonical(report)+b'\n')
            summary = render_summary(report)+'\nHistory lookup: `'+str(lookup.get('status', 'recorded'))+'`.\n'
            if lookup.get('source_timing'):
                completed = lookup['source_timing']
                summary += ('Completed source timing from trusted GitHub metadata: '+
                            ', '.join(name+'='+str(completed.get(name)) for name in
                                      ('job_wall_s', 'queue_s', 'setup_s', 'cleanup_s'))+
                            ' seconds; status `'+str(completed.get('status', 'recorded'))+'`; API resolution '+
                            str(completed.get('resolution_s', 'unknown'))+' seconds.\n')
            (control_dir/'performance-summary.md').write_text(summary)
            if os.environ.get('GITHUB_STEP_SUMMARY'):
                with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as stream:
                    stream.write(summary)
        if not any(row['status'] in {'fail','blocked'} for row in packet['checks']) and not (report and report['provider_eligible']):
            # Supplying key='' prevents even an environment lookup. Healthy runs
            # retain their ordinary evidence without receiving TypeSafe's key.
            result = diagnose(packet, output_dir, key='', live=True, baseline=None if baseline is _BASELINE_UNSET else baseline)
            record.update(status=result['status'])
            (control_dir/'result.json').write_bytes(canonical(record)+b'\n')
            return record
        name = f'jev-reservation-source-{source_id}-{attempt}'
    else:
        raise ValueError('Unsupported diagnostic event')
    prior = prior_reservation(repo,name,default,token,opener=opener)
    record['reservation_name'] = name
    if prior:
        record.update(status='duplicate_suppressed',prior_reservation=prior)
        output_dir.mkdir(parents=True,exist_ok=False)
        (output_dir/'gate-result.json').write_bytes(canonical(record)+b'\n')
    else:
        record.update(status='reservation_required',provider_needed=True,reservation_written=True)
        reservation_dir.mkdir(parents=True,exist_ok=False)
        (reservation_dir/'reservation.json').write_bytes(canonical(record)+b'\n')
    (control_dir/'result.json').write_bytes(canonical(record)+b'\n')
    return record


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--packet'); parser.add_argument('--control',required=True)
    parser.add_argument('--out',required=True); parser.add_argument('--reservation',required=True)
    args=parser.parse_args()
    event=parse_json(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())
    context={'trusted_sha':os.environ['JEV_TRUSTED_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],
             'attempt':int(os.environ['GITHUB_RUN_ATTEMPT']),'event_name':os.environ['GITHUB_EVENT_NAME']}
    try:
        record=prepare(event,args.packet,args.control,args.out,args.reservation,context,os.environ['GH_TOKEN'])
    except Exception as exc:
        directory=Path(args.out); directory.mkdir(parents=True,exist_ok=True)
        (directory/'gate-error.json').write_bytes(canonical({
            'status':'reservation_check_failed','exception_type':type(exc).__name__,
            'provider_request_attempted':False})+b'\n')
        raise RuntimeError('Diagnostic reservation could not be verified; no provider call authorized') from None
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
        output.write('provider_needed='+('true' if record['provider_needed'] else 'false')+'\n')
        output.write('reservation_name='+record.get('reservation_name','')+'\n')
        output.write('status='+record['status']+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
