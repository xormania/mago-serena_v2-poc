"""Trusted consumer: fetch one bounded ZIP and parse JSON without extracting files."""
from __future__ import annotations
import argparse
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


def download(event, output, token, *, opener=None):
    source = event['workflow_run']
    repo = event['repository']['full_name']
    if not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or source['head_repository']['full_name'] != repo:
        raise ValueError('Foreign repository')
    run_id, attempt, sha = str(source['id']), int(source['run_attempt']), source['head_sha']
    expected = {'run_id':run_id,'attempt':attempt,'workflow_head_sha':sha}
    if not run_id.isdigit() or not re.fullmatch('[0-9a-f]{40}',sha) or attempt < 1:
        raise ValueError('Invalid source identity')
    opener = opener or urllib.request.build_opener(NoRedirect())
    headers = {'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    url = f'https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100'
    with opener.open(urllib.request.Request(url,headers=headers),timeout=15) as response:
        raw = response.read(1000001)
    if len(raw) > 1000000:
        raise ValueError('Artifact inventory bound exceeded')
    listing = parse_json(raw)
    if listing.get('total_count',101) > 100:
        raise ValueError('Artifact inventory pagination required; refuse incomplete listing')
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
