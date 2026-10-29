# Recorded HTTP diagnosis and repair

> **Historical record.** This report retains a particular adaptive session, scripted replay, and wrapper development history. Its images, tokens, counts, and initial failures are run-specific. Use [Workflows](WORKFLOWS.md) for current runtime inspection and [Testing](TESTING.md) for result interpretation.

## Original report

Recorded profiler and log reads remain available after source changes and even
when the application cannot compile. Compiled service facts and Symfony-enriched
Mago still require explicit, fresh preparation. The actual coding session used
those runtime observations and Serena REPL → Mago source queries to repair one
real Symfony Demo request; deterministic acceptance is a separate replay.

The [local exact-image validation](evidence/slice3/integration/validation.json)
passes: **165 fast tests**, **31 original acceptance checks**, **9 slice-1**,
**12 slice-2** and **14 slice-3 stages**. The
[artifact manifest](evidence/slice3/integration/manifest.json) retains selected
reports, identities and complete task manifests. Slice 3's final task delta is
exactly its new regression test. Its replay suite discovers 54 tests / 135
assertions, including the unchanged original 53 / 120 and new 1 / 15. The first
13/14 attempt is also retained: its only failure was the then-absent adaptive
evidence index; a fresh run after the index was ready passed all stages.

The declared [task contract](../fixtures/slice3/task.json) changes the tag lookup
in `BlogController::index` from the mapped `name` field to invalid `label` in an
owned disposable app. `/en/blog/?tag=lorem` then fails with a real Doctrine
`UnrecognizedField` exception. The healthy contract is HTTP 200 and the expected
filtered post count, independently checked against SQLite. Randomized fixture
associations can yield no posts for a particular fixed tag; the new regression
selects a tag from a persisted post and asserts nonempty, correctly tagged
results. The repair restores the controller's original bytes. The sole final
application task addition is `tests/Controller/BlogTagFilterTest.php`; every
original test/configuration remains unchanged.

## Fresh adaptive evidence

The [retained artifact index](evidence/slice3/fresh-agent/index.json) binds 108
bounded artifacts, including actual MCP requests/results, adaptive decisions,
raw HTTP headers and command invocations, collector/log outputs, complete native
reports, JUnit inventories and complete initial/final application manifests.
[Decisions](evidence/slice3/fresh-agent/chronology.json) and
[the actual MCP trace](evidence/slice3/fresh-agent/mcp/mcp.jsonl) retain exploratory
errors as well as the successful semantic method edit. This is an integration
exercise performed by the current coding agent, not a blinded benchmark.

| Observation | Exact request token | Result |
| --- | --- | --- |
| Healthy control | `702a12` | HTTP 200, uniquely marked tag request |
| Diagnosed failure | `f50b98` | HTTP 500, exact marker/URL/time matched in profile and structured logs |
| Fresh recovery | `7bf144` | HTTP 200, new marker/token, own profile and SQL collector |

The agent read installed Mate schemas, profiler list/detail and exception,
`db` and logger collectors; searched Monolog by marker, structured request URI
and exception/time; inspected compiled `TagRepository` binding; and used
`server-info` to identify Mate's own PHP runtime. The exception collector located
`BlogController.php:57`. Actual Serena/Mago queries resolved inherited Doctrine
`findOneBy`, `TagRepository` and the `Tag` entity's mapped `name` property. The
agent then used `s.edit.replace_symbol_body` on the previously retrieved method.
Independent hashes confirm exact restoration of the original controller.

The failed `db` collector contains **zero SQL queries**: invalid ORM criteria
fail before SQL execution. The recovered request records **four queries**. The
same-second Monolog route record contains the unique URI marker; the following
critical record contains the actual exception. Retained source-file/line/time
metadata and the profiler's logger collector support this correlation without
assuming the newest profile belongs to the request.

The first request immediately after injection still returned 200 before the
changed source became visible; both attempts are retained. An earlier actual
failure `d61d3f` reproduced the old wrapper's stale-source rejection. During
wrapper development an explicit preparation bootstrapped the independent runtime
marker and archived those profile/log bytes before `cache:clear`. Its subsequent
live-profile absence is retained accurately. The final diagnosis uses newly
captured `f50b98`, without a refresh between its request and runtime reads.

Ordinary editing created/refined the new test because it had no existing symbol.
Initial native reports found three analyzer and three lint findings in that
new test. A real repository instance assertion and consistent `static::`
assertions resolved them, without suppressions. Native safe fixes applied no
changes; scoped formatting was stable. The final complete diagnostic multisets
match the measured candidate-overlay baseline: **35 analyzer / 125 lint findings**,
both native exit **1**, zero new/removed findings and no finding on the new test.
These numbers were remeasured; the older slice numbers were not assumed.

Original identities: **53 tests / 120 assertions**. The new regression passes
**1 test / 14 assertions** in the fresh run; the combined suite discovers
**54 tests / 134 assertions**. Assertion counts can vary with randomized tag/post
associations, while identities remain fixed. The regression fails with the
actual invalid-field 500 and passes on the repair. The unchanged original suite
verifier checks an explicit projection of the full JUnit result separately.

The public enriched CLI ran after explicit final preparation, retained native
findings/exit, analyzed all **47** application/test hosts with vendor context,
and observed the wiring worker's concrete Registry Body edge. The fresh session
used immutable image `5192ec…` while the host wrapper was developed; preparation
records preserve its full image ID. Independent acceptance uses rebuilt final
candidate image `ff82c2…`. Initial/final manifests explicitly record the narrow
setup reconciliation of managed runtime instructions and lock JSON normalization
separately from the new test. Neither CLI result claims enriched LSP propagation.
The candidate has 9,871 vendor PHP files: baseline native analysis compiled 9,917
source files for 46 hosts; the new test raises those totals to 9,918 and 47.

## Runtime policy and dependency

`matelib.call()` previously called `fresh()` for almost every data read. That
full source/dependency/container check is appropriate for compiled service facts,
but prevented reading a failure's existing profile after a source edit.
The [focused real regression](evidence/slice3/runtime-policy/index.json) compares
the original wrapper's exit 3 with successful current public runtime reads.

The correction uses an exact installed-tool allowlist and a separate runtime
identity marker: selected run/workspace/container, fixed dev context and directory
configuration, regular paths and bounded files/bytes. Runtime calls never invoke
application warmup, Composer install or cache clearing. Invocation records label
observations historical and preserve request token/URL/time provenance. Unknown
or abbreviated data commands retain compiled freshness checks; only exact runtime
commands with recognized global flags take the runtime path. A compiled-service
abbreviation cannot bypass freshness. Tests cover missing/foreign contexts,
container ownership, missing runtime directories, bounds and option ambiguity.

An intentional `mate-prepare` archives bounded existing profiles/logs before
cache clearing. It preserves owner text outside managed instruction blocks while
refreshing discovery and skills. Raw archive files remain disposable; retained
public outputs and hashes are the review evidence.

The official `symfony/ai-monolog-mate-extension` is pinned to **0.15.0**, source
`d85a949ccc537f1a8be2fd2b02a1f0d6a5d5f25b`, compatible with the installed Mate
0.15 family. All previously locked package records are unchanged by this addition.
[Overlay provenance](../fixtures/mate/overlay.json) records exact constraints,
lock hashes and the solver-only handling of an existing Mime advisory; final
Composer policy remains unchanged. Mago, SDK, wiring and Serena source pins stay
unchanged.

A separate real missing-service control yields failed compilation and HTTP 500
**without a new profiler token**. Previously recorded profile/exception/log data
remain readable, while compiled-service inspection rejects stale preparation.
No profile is fabricated for this pre-profiler failure. The original defect's
profile and logs were preserved before any intentional refresh.

## Reproduction and replay

```sh
export POC_IMAGE=mago-serena-poc:s3-runtime-your-id
uv sync --frozen --python 3.12.12
docker buildx build --load -t "$POC_IMAGE" .
./bin/poc fast
./bin/poc test
./bin/poc slice1 --run s3-service-your-id
./bin/poc slice2 --run s3-command-your-id
./bin/poc slice3 --run s3-request-your-id --keep-running
# Explicit source-dependent refresh, only after preserving failed observations:
./bin/poc mate-prepare --run s3-request-your-id
./bin/poc mago-enriched --run s3-request-your-id \
  --symbol 'App\Repository\TagRepository' -- analyze --reporting-format json
# Existing findings deliberately retain native exit 1.
./bin/poc down --run s3-request-your-id --purge
```

Every new run records the resolved Compose image and verifies the actual image ID
before acceptance. The default image remains `mago-serena-poc:local`; selected
run image tags are persistent and conflicting overrides are rejected.

`slice3` replays a predefined fault/investigation/semantic repair and independently
checks actual requests, runtime correlation, boot failure, native diagnostic
bodies, explicit enriched refresh, original/new suites and complete final task
diff. It validates the retained adaptive trace and bound raw observations rather
than treating its own preselected calls as another agent success. Each attempt
is retained at `artifacts/RUN/slice3/attempt-UUID/results.json`, with source/context
identity and named stage errors. CI runs this once after existing gates and
retains bounded nested failure causes for advisory Jev; passing packets make
zero provider requests.

For a new adaptive exercise, use the [agent task instructions](slice3-agent-task.txt)
in another owned disposable app and retain its actual decisions and calls.
See the [coverage inventory](RUNTIME-COVERAGE.md) for installed, accessible,
exercised and blocked capabilities. Forms/security authoring, migrations,
environment repair and real browser/UI behavior remain follow-on work.
