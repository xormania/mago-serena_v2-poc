# Testing and results

Checks run in disposable applications copied from `app/`. Keep the checked-in
fixture intact. Build the image and install locked host dependencies using
[Getting started](GETTING-STARTED.md) before container-based checks.

## Select a check

| Command | What it establishes | Outputs |
| --- | --- | --- |
| `./bin/poc fast` | Properties, verifier/evidence fault controls, mocked CI/provider behavior; no Docker daemon or API key | `artifacts/fast/results.json` and console output |
| `./bin/poc test` | Two isolated application baselines, original test identities, real MCP/LSP operations, lifecycle, and verification controls without a model | Printed `test-…` run ID; `artifacts/<id>/results.json`, `report.txt`, logs and sealed artifacts, plus companion `<id>-b` |
| `./bin/poc slice1` | PHP analysis, semantic service inspection, compiled Symfony wiring, and behavior | `artifacts/<id>/slice1/…`; see printed run and reports |
| `./bin/poc slice2` | Generated tag-count command, declared changes, and independent application checks | `artifacts/<id>/slice2/…` |
| `./bin/poc slice3` | Injected HTTP failure, runtime observation, semantic repair, recovery, and new regression test | `artifacts/<id>/slice3/attempt-<uuid>/results.json` |
| `.venv/bin/python tests/integration/lsp_extensions.py --fresh` | Patched external-worker lifecycle and dependency contributions through native LSP and Serena | `artifacts/<id>/lsp-extensions/…`; printed summary |

The exercise names remain command identifiers; each report explains its own
acceptance contract. `slice1`, `slice2`, and `slice3` can take `--run <id>` and
`--keep-running`. Fresh IDs are preferable when testing; these commands prepare
and modify their own disposable applications. The LSP runner's `--fresh` selects
a new run and verifies its installed image/code. See [Commands](COMMANDS.md) for
the complete syntax.

```sh
./bin/poc fast
./bin/poc test
./bin/poc slice1
./bin/poc slice2
./bin/poc slice3
.venv/bin/python tests/integration/lsp_extensions.py --fresh
```

Tests retain failures as well as successful attempts. Most exercise services
are stopped automatically unless kept running; refer to their result and
cleanup records before deleting workspaces. [CI](CI.md) runs these checks on
GitHub-hosted Ubuntu and retains their artifacts.

Fast checks do not contact a Docker daemon, but mocked enriched-analysis paths
still resolve the Docker CLI name. Use the normal Docker installation from the
setup requirements. On a host intentionally lacking the CLI,
`POC_DOCKER=docker ./bin/poc fast` supplies only the executable name to those
intercepted subprocess calls; this does not validate Docker or containers.

## Read the results

For the original integration run, substitute the printed run ID:

```sh
./bin/poc report <run-id>
```

`report` validates the original acceptance plan, source context, required result
inventory, runtime/image identities, and retained artifact hashes. It does not
render every exercise format: inspect the exercise-specific JSON/report files
for those results.

| Status | Interpretation |
| --- | --- |
| `pass` | This named assertion executed successfully in the recorded context |
| `fail` | Its assertion or execution failed |
| `blocked` | An earlier failure prevented the required check |
| `not_exercised` | The check has no execution result |

Missing, duplicate, stale, foreign, or unexecuted required results prevent an
acceptance pass. Original PHPUnit identities are checked by class, method,
dataset, file, and line, with original source hashes. Counts alone do not prove
suite execution. The verifier also compares the entire covered application
manifest, including dependencies and configuration. Mutable cache/database
exclusions are defined in `tests/integration/verifier.py`.

Each task declares its allowed changes. The original semantic rename permits an
exact two-file diff; generation and request-repair exercises have their own
contracts and additional tests. The rename rule is not a general coding policy.

Mago's existing fixture findings remain visible with native exit 1. A quality
report can contain findings while a task's independent acceptance checks pass.
Conversely, absence of new findings does not establish application correctness.

The known external-edit span defect is tested with a reproduced failure and a
fresh-process healthy control. Passing that expected-failure check confirms the
observed defect; it does not establish that external edits are fully supported.
See [Capabilities](CAPABILITIES.md).

## Agent sessions and scripted replays

The deterministic integration runner makes real MCP/LSP calls without a model.
Exercise replays follow predefined operations and separately check application
outcomes. Retained adaptive sessions establish the decisions and calls made in
those particular sessions; replaying a task does not establish a new agent run.

To prepare a new rename task, run `./bin/poc agent-task`, follow the generated
instructions, retain the native transcript, and invoke `verify-agent` with its
printed run ID. The current transcript reader accepts Codex JSONL only. It also
checks the application, original tests, and a fresh independent semantic query.
See [Agent clients](AGENT-CLIENTS.md).

Historical agent evidence is indexed by task in the [documentation index](index.md#historical-results-and-reproductions).
The original rename was not rerun after verification strengthening. Later command,
request-repair, and LSP-extension investigations have separately retained agent
records; their scope must be read from their own indexes. Some original runner
metadata still uses historical labels such as `not_exercised_after_hardening`;
those fields describe that runner's separate-run inventory, not all later
experiments in the repository.

The request-repair replay reports 54 tests/135 assertions, while its adaptive
session reports 54/134. Randomized fixture associations explain the difference;
original identities remain fixed. Do not apply one recorded count to all runs.

## Evidence and diagnosis

`artifacts/<id>/` holds source/runtime metadata, raw MCP/LSP transcripts,
diagnostics, diffs, PHPUnit JUnit/logs, and error details. A prepared run's
`workspaces/<id>/trusted/` is mounted read-only at `/trusted`; original acceptance
also retains required baseline copies with its artifacts. Evidence survives
`down --purge`, which deletes the workspace.

Set `POC_TRACE=1` when creating acceptance environments for bounded hash/version
state traces. Protocol traces are bounded and report truncation. Preserve the
original evidence directory before repeating an investigation or clearing caches.
Jev's mocked tests and optional live CI diagnosis are advisory and do not change
these correctness assertions; see [Jev](JEV.md).
