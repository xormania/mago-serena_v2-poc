# Continuous integration

The **Pinned Serena + Mago PoC** workflow builds the pinned development image,
runs the test suite, and retains results on success and failure. The required
job is named `acceptance`. A separate **Jev advisory diagnosis** workflow can
suggest a diagnosis from the recorded results; it cannot change acceptance.

For local checks, see [testing](TESTING.md). For everyday development, start
with [getting started](GETTING-STARTED.md) and the [workflow guide](WORKFLOWS.md).

## Find a run and its results

Open the repository's [Actions page](https://github.com/xormania/mago-serena_v2-poc/actions)
and select **Pinned Serena + Mago PoC**. The `acceptance` job shows the native
command outcomes and a readable performance summary. Its artifacts are:

| Artifact | Contents | Retention |
| --- | --- | --- |
| `poc-evidence-<run>-<attempt>` | Available `artifacts/` tree: logs, application/test results, runtime identities, performance reports, and failed attempts | 14 days |
| `jev-input-<run>-<attempt>` | Bounded `diagnosis-input.json` for the advisory consumer | 7 days |

Performance reports are under `artifacts/ci/performance.json` and
`artifacts/ci/performance.md`. The producer's command ledger is
`artifacts/ci/step-attempts.jsonl`. Individual application checks retain their
own result files; use the recorded run/workspace identities when following a
failure into those directories. The [command reference](COMMANDS.md) describes
`poc report` for local run directories.

The collector and uploads use `always()` so partial failures are retained where
possible. Cancellation can prevent collection itself. Missing output is missing
evidence, rather than a successful zero-duration check. GitHub-hosted artifacts
expire; committed [evidence indexes](index.md#historical-results-and-reproductions)
identify the selected records preserved in the repository.

## Events and scheduling

| Event | Behavior |
| --- | --- |
| Pull request, including documentation updates | Full `acceptance` job |
| Push to `master` | Full default-branch validation |
| Push to a feature branch | No duplicate push acceptance alongside its PR |
| Manual dispatch | Full acceptance on the selected ref |

Concurrency is scoped by workflow, event, and PR number or push ref. New updates
supersede earlier runs for that PR or push ref. Manual dispatches use their own
run ID, so independent manual validations and default-branch pushes are not
cancelled by a PR update. There are no documentation path filters. The job has
a 50-minute timeout and runs on `ubuntu-latest`.

## Checks run by acceptance

The workflow executes these phases in order. Container checks use the selected
source and the same built image, while application/database/state workspaces
remain independent.

| Phase | Entry point | Purpose |
| --- | --- | --- |
| Locked dependencies | `uv sync --frozen --python 3.12.12` | Install the pinned host Python environment |
| Fast checks | `./bin/poc fast` | Deterministic properties, verifier/evidence failures, CI policy, and mocked provider integration |
| Image build | `python3 tools/ci/build_image.py` | Build and load the pinned image using the Actions cache |
| Application and semantic integration | `./bin/poc test` | Original application suites, independent workspaces, real MCP/LSP behavior, and execution identity |
| PHP and service analysis | `./bin/poc slice1` | Native Mago checks, semantic inspection, compiled Symfony wiring, and application behavior |
| Generated feature | `./bin/poc slice2` | Maker-generated command, semantic changes, behavior tests, and enriched analysis |
| Request diagnosis and repair | `./bin/poc slice3` | HTTP/profiler/log correlation, semantic repair, runtime recovery, and regression tests |
| LSP extension integration | `.venv/bin/python tests/integration/lsp_extensions.py --fresh` | External analyzer worker lifecycle and actual Serena graph forwarding |

The command names retain their original numbering; the purposes above describe
what they do. These are scripted integration exercises. They do not launch a
new authenticated coding agent. Recorded agent sessions are indexed separately
in the [capability summary](CAPABILITIES.md).

`capture_step.py` returns each command's original exit status, writes an immutable
log per step/attempt, and does not retry. Existing whole-application Mago findings
remain visible; the acceptance criteria do not claim every Demo diagnostic has
been repaired. The known external-span defect has an expected-failure test and a
fresh-process healthy control. That test passing does not mean the defect is fixed.

## Build cache and image identity

[`tools/ci/build_image.py`](../tools/ci/build_image.py) uses Buildx with the GHA
cache API v2, `mode=max`, platform `linux/amd64`, and scope
`mago-serena-linux-amd64-v1`. The Actions job sets
`POC_IMAGE=mago-serena-poc:ci-<run>-<attempt>`. Build and acceptance use that same
selection and verify the actual image ID.

The cache scope does not include adapter, test, or documentation hashes. Docker's
content-based layer keys still invalidate changed inputs. The Mago compile
stages copy binaries, source/lock identities, and notices outside the cache mounts
before completing. Importing an unchanged intermediate RUN layer can therefore
skip compilation on another runner. The cache does **not** persist the Cargo
registry or `/src/target` cache-mount contents automatically.

A PR can read its merge-ref cache and its base/default-branch caches. Another
PR or `master` cannot import a cache available only under that PR's merge ref.
Without an accessible matching cache, initial population is expected to be cold.
A successful cache-manifest import alone does not establish that a matching
compile layer was restored.

The local [cache-runtime action](../.github/actions/cache-runtime/index.cjs)
exports only the Actions cache variables needed by Buildx and masks the
runtime token. It receives no TypeSafe key. Import/export errors remain visible
failures; the helper does not silently discard the configured cache policy.
The build plan, metadata, logs, and image ID are retained under `artifacts/ci/`.

Local builds do not need GitHub cache credentials and use `./bin/poc up`.
For a separate local image, set `POC_IMAGE=mago-serena-poc:<your-tag>` consistently
for build and workspace creation. An existing workspace retains its selected
image and rejects conflicting overrides. See [configuration](COMMANDS.md).

References: [Docker GHA backend](https://docs.docker.com/build/cache/backends/gha/),
[cache mounts](https://docs.docker.com/build/ci/github-actions/cache/), and
[GitHub cache visibility](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).

## Performance reporting and comparison

Timing is advisory. It cannot turn a passing acceptance check into a timing
failure or make a failed check pass. Reports retain partial runs, unavailable
measurements, and collection errors explicitly.

Observations include the GitHub run/attempt/event/ref, tested source and workflow
head, runner identity/image, platform, check definitions, command timings, and
bounded BuildKit evidence. Command durations use a monotonic clock. Command sums,
recorded wall span, job wall time, queue time, setup steps, and cleanup steps are
separate quantities. The producer cannot see completed job timings; the trusted
consumer supplements its report from the Actions API at one-second resolution.

BuildKit parsing follows declared vertices rather than fixed step numbers.
Compilation outcomes are `cached`, `executed`, `failed`, or `unknown`; cache
transfer outcomes are `success`, `failed`, or `unknown`. Cached layer extraction
time is not compilation time. Truncated or unrecognized logs leave unsupported
measurements unknown. A compile RUN includes bookkeeping as well as Cargo;
outer log timestamps do not measure the Cargo process precisely.

The compile fingerprint covers the Docker syntax directive and instructions in
the `mago` and `mago-candidate` stages, Rust base and Mago source pins, actual patch
bytes, effective compile arguments, and platform. Documentation, repository SHA,
timestamps, and downstream runtime/native-test stages do not feed those binaries
and are excluded. Check compatibility separately hashes the integration and test
runner definitions.

The producer applies absolute budgets without downloading history. The trusted
consumer validates observations and recomputes policy from its default-branch
code. It examines at most 20 prior successful producer runs from seven days,
downloads at most three exact-attempt packets without extracting them, and
prefers the newest compatible same-event/ref observation before default-branch
push history. Reports state the selected run/attempt/source, compatibility,
selection reason, and lookup errors. Missing, expired, legacy, or incompatible
records leave comparison unavailable.

| Policy in `tools/ci/performance.py` | Value |
| --- | --- |
| Warm image build budget | 180 seconds |
| Cold or unknown-cache image build budget | 900 seconds |
| Each verification phase budget | 300 seconds |
| Comparable verification slowdown | At least 1.5 times the baseline **and** at least 60 seconds longer |
| Maximum history age | Seven days |
| Maximum cache-availability observation age | Five minutes |

These conservative thresholds are diagnostic policy, not service guarantees.
Classifications are `warm_reuse`, `explained_cold_population`,
`unexpected_recompilation`, `slow_verification`, `absolute_budget_breach`, and
`insufficient_evidence`; several can apply.

Relative changes require compatible compile inputs, check definitions, platform,
runner identity/image, and cold/warm regime. Unexpected recompilation also needs
a matching successful export and fresh trusted cache inventory for an accessible
ref, with the relevant entry created during the selected baseline run and before
the source run. A newer export with different inputs can overwrite a scope.
Even a qualifying observation is a reason to investigate, not proof of eviction,
corruption, or another cause.

Warm success and explained cold population inside budget need no provider call.
Supported unexpected recompilation, comparable slowdown, or a budget breach can
qualify a successful run for the same single advisory request used for failures.
Missing history alone cannot qualify. Native failure evidence takes priority.
[Jev documentation](JEV.md) describes the credential gate, response validation,
and duplicate prevention.

## Pinned workflow dependencies

The workflow files are the authority for action revisions. The installed pins
include the following; these are not claims about the latest upstream releases.

| Action | Revision in the workflow |
| --- | --- |
| `actions/checkout` | `d23441a48e516b6c34aea4fa41551a30e30af803` (v6) |
| `astral-sh/setup-uv` | `94527f2e458b27549849d47d273a16bec83a01e9` (v7), uv `0.12.8` |
| `docker/setup-buildx-action` | `f87e5991a6d7451dcb8d9637bfbc97413f497069` (v4.4.1) |
| `actions/upload-artifact` | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` (v7.0.2) |

## Historical measurements

These selected observations belong to their recorded source revisions and
runner/image configurations. They are not new measurements of a documentation
update or statistical performance guarantees.

The original [baseline record](evidence/ci-performance/baseline.json) and
[measurement index](evidence/ci-performance/measurements.json) retain API step
and job timestamps, BuildKit logs, source/image identities, and provenance:

| Hosted run | Build | Application acceptance | Total | Mago layer |
| --- | --- | --- | --- | --- |
| [Baseline PR 40486178957](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40486178957) | 10m00s | 1m40s | 12m13s | Compiled |
| [Merged default 40489054256](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40489054256) | 9m37s | 1m40s | 11m54s | Compiled; no persistent cache |
| [Cache population 40490285225](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40490285225) | 11m15s | 1m36s | 13m37s | Compiled; export 78.9s |
| [Representative warm 40492209788](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40492209788) | 38s | 1m13s | 2m21s | Cached; export 3.9s |

The baseline compile RUN took 554.5 seconds; Cargo reported 9m13s. A same-head
feature-push [run 40485958869](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40485958869)
duplicated the earlier work (12m15s total, 9m59s build, 1m42s acceptance).
The warm representative build was 93.7% shorter and total time 80.8% shorter than
the baseline; against the merged default sample the differences were 93.4% and
80.3%. The initial population was slower, not faster. These samples used different
runners and changed diagnostic/test code; they passed the same 31 original
checks while fast tests grew from 104 to 122. They do not establish an unchanged
image benchmark. [Cold](evidence/ci-performance/excerpts-40490285225.txt) and
[warm](evidence/ci-performance/excerpts-40492209788.txt) excerpts retain the cache
observations. The original total uses job-level timestamps and includes overhead;
it should not be equated with a sum of captured command durations.

Later [performance advisory evidence](evidence/ci-performance/advisory-v1/README.md)
compares the actual PR #6 warm build (47.548 seconds) with the first-master cold
build (651.353 seconds). Their 603.805-second build difference explains about
87% of that total slowdown. Cache visibility explains the cold population;
recurring cache failure and the cause of slower verification were not established.
No newer unchanged-master warm run was available at that review. The reporting
change itself did not establish a speed improvement.

Selected local integration records, distinct from hosted measurements, are:

| Recorded revision | Result | Retained record |
| --- | --- | --- |
| `9e74151804e5e30f7b55d4e66cf09dd9ff0f7389` | 148 fast tests; 31 original checks; service/feature exercises at 9/12 stages; local concurrent durations 68.203s, 92.429s, 57.889s | [Feature integration](evidence/slice2/integration/validation.json) |
| Runtime candidate image `sha256:ff82c2ee2de6eedba1d5e93a6d62652a788998de0a22afec3bce802102eb40ec` | 165 fast tests; 31 original checks; both original suites at 53 tests / 120 assertions | [Runtime report](SLICE-3.md) |
| `7d7369cc87c64b3bd8d2d95749375f8954646c58` | 178 fast tests; 31 original checks; exercises at 9/12/14 stages; focused LSP integration | [Combined integration](evidence/lsp-extensions/integration/validation.json) |

For the full earlier chronology, the [pre-refresh CI document](https://github.com/xormania/mago-serena_v2-poc/blob/cf38cd43254acbe696b9fe104c0314daefcfaaca/docs/CI.md)
records the temporary trigger experiments and implementation branches. Current
workflow behavior is described above; [historical Jev observations](JEV.md#historical-live-observations)
identify which trusted code actually ran.
