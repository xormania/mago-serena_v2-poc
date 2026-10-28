"""Cache policy controls; hosted layer reuse is measured separately in run logs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

from build_image import CACHE_SCOPE, build_command, build_plan

ROOT = Path(__file__).resolve().parents[2]


class BuildCacheTests(unittest.TestCase):
    def environment(self):
        return {'GITHUB_ACTIONS':'true','GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123',
                'GITHUB_RUN_ATTEMPT':'1','GITHUB_EVENT_NAME':'pull_request',
                'GITHUB_REF':'refs/pull/2/merge','ACTIONS_RESULTS_URL':'https://cache.invalid',
                'ACTIONS_RUNTIME_TOKEN':'fake-runtime-credential'}

    def test_import_export_same_stable_scope_and_complete_intermediate_layers(self):
        command=build_command()
        imported=command[command.index('--cache-from')+1]
        exported=command[command.index('--cache-to')+1]
        self.assertIn('type=gha', imported)
        self.assertIn('version=2', imported)
        self.assertIn('scope='+CACHE_SCOPE, imported)
        self.assertEqual(exported,imported+',mode=max')
        self.assertNotIn('ignore-error',exported)
        self.assertIn('--progress',command)
        self.assertEqual(command[command.index('--progress')+1],'plain')

    def test_plan_has_source_attempt_and_no_cache_or_provider_credentials(self):
        env=self.environment()
        env['TYPESAFE_API_KEY']='fake-provider-credential-not-used'
        plan=build_plan(env)
        self.assertEqual(plan['source_sha'],'a'*40)
        self.assertEqual(plan['attempt'],1)
        self.assertEqual(plan['ref'],'refs/pull/2/merge')
        raw=json.dumps(plan)
        self.assertNotIn('fake-runtime-credential',raw)
        self.assertNotIn('fake-provider-credential-not-used',raw)
        self.assertNotIn('https://cache.invalid',raw)

    def test_missing_runtime_cannot_silently_run_uncached(self):
        for key in ('ACTIONS_RESULTS_URL','ACTIONS_RUNTIME_TOKEN','GITHUB_SHA','GITHUB_RUN_ID'):
            env=self.environment();del env[key]
            with self.subTest(key=key),self.assertRaises(ValueError): build_plan(env)

    def test_scope_unchanged_for_other_source_commit_or_event(self):
        original=build_plan(self.environment())['cache']
        env=self.environment()
        env.update(GITHUB_SHA='b'*40,GITHUB_EVENT_NAME='push',GITHUB_REF='refs/heads/master')
        self.assertEqual(build_plan(env)['cache'],original)
        self.assertFalse(original['cache_mounts_persisted'])

    def test_build_selection_matches_compose_default_and_selected_session_tag(self):
        for selection, expected in ((None, 'mago-serena-poc:local'), ('', 'mago-serena-poc:local'),
                                    ('mago-serena-poc:s3-session', 'mago-serena-poc:s3-session')):
            env = self.environment()
            if selection is not None:
                env['POC_IMAGE'] = selection
            with self.subTest(selection=selection):
                command = build_plan(env)['command']
                self.assertEqual(command[command.index('--tag')+1], expected)


class AcceptanceSchedulingTests(unittest.TestCase):
    def workflow(self):
        # BaseLoader preserves YAML's "on" key instead of interpreting it as bool.
        return yaml.load((ROOT/'.github/workflows/poc.yml').read_text(),Loader=yaml.BaseLoader)

    def test_only_default_branch_pushes_and_pr_checks_are_scheduled(self):
        workflow=self.workflow()
        self.assertEqual(workflow['on']['push']['branches'],['master'])
        self.assertIn('pull_request',workflow['on'])
        self.assertIn('workflow_dispatch',workflow['on'])
        self.assertNotIn('paths',workflow['on']['pull_request'] or {})
        self.assertEqual(list(workflow['jobs']),['acceptance'])

    def test_supersession_is_scoped_to_same_pr_or_ref(self):
        concurrency=self.workflow()['concurrency']
        self.assertEqual(concurrency['cancel-in-progress'],'true')
        group=concurrency['group']
        self.assertIn('github.event.pull_request.number',group)
        self.assertIn('github.ref',group)
        self.assertIn('github.workflow',group)
        self.assertIn('github.event_name',group)
        self.assertIn('github.run_id',group)


class CacheRuntimeActionTests(unittest.TestCase):
    def test_exports_cache_allowlist_without_provider_credentials_or_value_logs(self):
        node=shutil.which('node')
        self.assertIsNotNone(node,'Node is needed to verify the local Node24 runtime action')
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'github-env'
            env={'GITHUB_ENV':str(output),'ACTIONS_RUNTIME_TOKEN':'fake-runtime-value',
                 'ACTIONS_RESULTS_URL':'https://cache.invalid/value',
                 'ACTIONS_UNRELATED_SECRET':'fake-unrelated-value',
                 'TYPESAFE_API_KEY':'fake-provider-value'}
            result=subprocess.run([node,str(ROOT/'.github/actions/cache-runtime/index.cjs')],
                                  env=env,text=True,capture_output=True,check=True)
            exported=output.read_text()
            self.assertEqual(set(line.split('=',1)[0] for line in exported.splitlines()),
                             {'ACTIONS_RUNTIME_TOKEN','ACTIONS_RESULTS_URL'})
            self.assertNotIn('fake-unrelated-value',exported)
            self.assertNotIn('fake-provider-value',exported)
            ordinary='\n'.join(line for line in result.stdout.splitlines() if not line.startswith('::add-mask::'))
            for value in env.values():
                self.assertNotIn(value,ordinary)

    def test_missing_or_multiline_runtime_refused_without_partial_export(self):
        node=shutil.which('node')
        self.assertIsNotNone(node)
        for change in ({'ACTIONS_RUNTIME_TOKEN':''},{'ACTIONS_RESULTS_URL':'url\nINJECTED=value'}):
            with tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/'github-env'
                env={'GITHUB_ENV':str(output),'ACTIONS_RUNTIME_TOKEN':'fake-runtime-value',
                     'ACTIONS_RESULTS_URL':'https://cache.invalid',**change}
                result=subprocess.run([node,str(ROOT/'.github/actions/cache-runtime/index.cjs')],
                                      env=env,text=True,capture_output=True)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
