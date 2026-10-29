"""Trusted consumer: fetch one bounded ZIP and parse JSON without extracting files."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from jev import MAX_PACKET, NoRedirect, canonical, validate_packet, parse_json
ZIP_LIMIT = 200000


def read_archive(raw, expected):
    if len(raw) > ZIP_LIMIT:
        raise ValueError('Compressed artifact bound exceeded')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or entries[0].filename != 'diagnosis-input.json':
            raise ValueError('Unexpected artifact members')
        info = entries[0]
        if (info.file_size > MAX_PACKET or info.compress_size > ZIP_LIMIT or info.flag_bits & 1
                or ((info.external_attr >> 16) & 0o170000) == 0o120000):
            raise ValueError('Unsafe artifact entry')
        with archive.open(info) as stream:
            packet = parse_json(stream.read(MAX_PACKET+1))
    return validate_packet(packet, expected)


def validate_source_association(packet, source, repo, opener, token):
    """Bind separately supplied metrics to the actual producing run and ref."""
    if 'performance' not in packet:
        return  # Legacy packet compatibility; no new API requirement.
    observation = packet['performance']
    context = observation['context']
    timestamps = []
    for name in ('created_at', 'updated_at'):
        text = source.get(name)
        if text is None:
            continue  # Minimal legacy-style API fixtures have no complete wall interval.
        if not isinstance(text, str) or len(text) > 40:
            raise ValueError('Invalid producing run timestamp')
        timestamps.append(datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(timezone.utc).timestamp())
    if len(timestamps) == 2:
        lower, upper = timestamps
        if lower > upper or not lower-60 <= observation['observed_unix'] <= upper+60:
            raise ValueError('Performance observation is outside the producing run interval')
        for phase in observation['phases']:
            started = phase['started_unix']
            if started is not None and not lower-60 <= started <= upper+60:
                raise ValueError('Performance phase is outside the producing run interval')
    event = source.get('event')
    if context['event'] != event:
        raise ValueError('Performance event differs from producing run')
    if event in {'push', 'workflow_dispatch'}:
        if (packet['ci']['source_sha'] != source['head_sha']
                or context['ref'] != 'refs/heads/'+source.get('head_branch', '')):
            raise ValueError('Performance source/ref differs from producing run')
    elif event == 'pull_request':
        pulls = source.get('pull_requests', [])
        if not isinstance(pulls, list) or len(pulls) > 20:
            raise ValueError('Invalid producing PR inventory')
        numbers = [row.get('number') for row in pulls if isinstance(row, dict)]
        if any(type(number) is not int or number < 1 for number in numbers):
            raise ValueError('Invalid producing PR identity')
        if not re.fullmatch(r'refs/pull/[1-9][0-9]*/merge', context['ref']):
            raise ValueError('Invalid performance PR ref')
        if numbers and context['ref'] not in {'refs/pull/'+str(number)+'/merge' for number in numbers}:
            raise ValueError('Performance ref differs from producing PR')
        # GitHub workflow_run identifies the PR head while checkout tests the
        # merge. Verify that exact merge contains that head; never execute it.
        tested = packet['ci']['source_sha']
        if tested != source['head_sha']:
            request = urllib.request.Request(f'https://api.github.com/repos/{repo}/git/commits/{tested}', headers={
                'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
                'X-GitHub-Api-Version':'2022-11-28'})
            with opener.open(request, timeout=15) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError('Source association API bound exceeded')
            commit = parse_json(raw)
            parents = commit.get('parents') if isinstance(commit, dict) else None
            if (not isinstance(commit, dict) or commit.get('sha') != tested
                    or not isinstance(parents, list) or len(parents) != 2
                    or any(not isinstance(row, dict) for row in parents)
                    or not any(row.get('sha') == source['head_sha'] for row in parents)):
                raise ValueError('Performance PR merge source association failed')
    else:
        raise ValueError('Unsupported performance producer event')


def download(event, output, token, *, opener=None):
    source = event['workflow_run']
    repo = event['repository']['full_name']
    if not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or source['head_repository']['full_name'] != repo:
        raise ValueError('Foreign repository')
    run_id, attempt, sha = str(source['id']), source['run_attempt'], source['head_sha']
    expected = {'run_id':run_id,'attempt':attempt,'workflow_head_sha':sha}
    if not run_id.isdigit() or type(attempt) is not int or not re.fullmatch('[0-9a-f]{40}',sha) or attempt < 1:
        raise ValueError('Invalid source identity')
    opener = opener or urllib.request.build_opener(NoRedirect())
    headers = {'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    url = f'https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100'
    with opener.open(urllib.request.Request(url,headers=headers),timeout=15) as response:
        raw = response.read(1000001)
    if len(raw) > 1000000:
        raise ValueError('Artifact inventory bound exceeded')
    listing = parse_json(raw)
    if (not isinstance(listing, dict) or type(listing.get('total_count')) is not int
            or not 0 <= listing['total_count'] <= 100
            or not isinstance(listing.get('artifacts'), list)
            or len(listing['artifacts']) != listing['total_count']
            or any(not isinstance(row, dict) for row in listing['artifacts'])):
        raise ValueError('Artifact inventory pagination required or invalid; refuse incomplete listing')
    name = f'jev-input-{run_id}-{attempt}'
    artifacts = [row for row in listing['artifacts'] if row.get('name') == name and not row.get('expired')]
    if not artifacts:
        return None
    if len(artifacts) != 1 or type(artifacts[0].get('id')) is not int or artifacts[0].get('size_in_bytes',ZIP_LIMIT+1) > ZIP_LIMIT:
        raise ValueError('Duplicate or oversized diagnosis artifact')
    aid = artifacts[0]['id']
    request = urllib.request.Request(f'https://api.github.com/repos/{repo}/actions/artifacts/{aid}/zip',headers=headers)
    try:
        response = opener.open(request,timeout=15)
    except urllib.error.HTTPError as exc:
        if exc.code != 302:
            raise
        location = exc.headers.get('Location','')
        exc.close()
        parsed = urlparse(location)
        if (parsed.scheme != 'https' or parsed.username or parsed.password
                or not any((parsed.hostname or '').endswith('.'+suffix) for suffix in ('blob.core.windows.net','actions.githubusercontent.com','githubusercontent.com'))):
            raise ValueError('Unexpected artifact download location')
        # The short-lived signed download URL gets no GitHub Authorization header.
        response = opener.open(urllib.request.Request(location),timeout=15)
    with response:
        raw = response.read(ZIP_LIMIT+1)
    packet = read_archive(raw,expected)
    validate_source_association(packet, source, repo, opener, token)
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(canonical(packet)+b'\n')
    return packet


def main():
    p = argparse.ArgumentParser(); p.add_argument('--out',required=True); args = p.parse_args()
    event = parse_json(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    result = download(event,args.out,os.environ['GH_TOKEN'])
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:
        output.write('found='+('true' if result is not None else 'false')+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
