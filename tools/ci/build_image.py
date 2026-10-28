"""CLI BuildKit cache policy; stdout/stderr remain captured by capture_step.py.

GHA stores the immutable RUN result layers, not RUN --mount=type=cache contents.
The Mago stage copies its binary/identity/licenses out of its cache mounts before
the RUN completes, so importing that layer skips compilation on another runner.
Docker's branch access rules still apply to this stable image scope: a PR can
read its merge-ref cache and its base/default branch, not another PR's cache.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess

CACHE_SCOPE = 'mago-serena-linux-amd64-v1'


def build_command(env=None):
    # Keep this scope independent of adapter/tests/docs changes. Docker's own
    # content-addressed layer keys invalidate changed toolchain inputs correctly.
    env = os.environ if env is None else env
    cache = f'type=gha,version=2,scope={CACHE_SCOPE},timeout=5m'
    image = env.get('POC_IMAGE') or 'mago-serena-poc:local'
    return ['docker', 'buildx', 'build', '--load', '--tag', image,
            '--progress', 'plain', '--metadata-file', 'artifacts/ci/build-metadata.json',
            '--iidfile', 'artifacts/ci/image.iid', '--cache-from', cache,
            '--cache-to', cache+',mode=max', '.']


def build_plan(env):
    if env.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('CI cache build requires GitHub Actions; local builds use ./bin/poc up')
    for name in ('ACTIONS_RESULTS_URL', 'ACTIONS_RUNTIME_TOKEN'):
        if not env.get(name):
            raise ValueError('GitHub cache runtime is unavailable; check the pinned runtime helper step')
    if (not re.fullmatch(r'[0-9a-f]{40}', env.get('GITHUB_SHA',''))
            or not env.get('GITHUB_RUN_ID','').isdigit()
            or not env.get('GITHUB_RUN_ATTEMPT','').isdigit()):
        raise ValueError('Missing build source/run identity')
    # No URL/token values or environment dump: BuildKit consumes credentials from
    # the environment and receives no secret-bearing command arguments.
    return {'schema':1, 'source_sha':env['GITHUB_SHA'], 'run_id':env['GITHUB_RUN_ID'],
            'attempt':int(env['GITHUB_RUN_ATTEMPT']), 'event':env.get('GITHUB_EVENT_NAME'),
            'ref':env.get('GITHUB_REF'), 'cache':{'backend':'gha','version':2,'scope':CACHE_SCOPE,
                'export_mode':'max','timeout':'5m','export_errors_fatal':True,
                'cache_mounts_persisted':False}, 'command':build_command(env)}


def main():
    plan = build_plan(os.environ)
    directory = Path('artifacts/ci')
    directory.mkdir(parents=True, exist_ok=True)
    plan['buildx_version'] = subprocess.check_output(['docker','buildx','version'], text=True).strip()
    plan['docker_version'] = subprocess.check_output(['docker','version','--format','{{.Client.Version}} / {{.Server.Version}}'], text=True).strip()
    (directory/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    return subprocess.run(plan['command'], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
