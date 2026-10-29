# Hosted CI performance and evidence

The Mago-first workflow has captured `slice1`, `slice2` and `slice3` steps after original
acceptance, using the same built image and separate fresh owned workspaces.
Slice 1 exercises native PHP calibration, real host MCP semantics, compiled
Mate/wiring-extension controls and the original PHPUnit identities. Slice 2
uses installed Maker, replays the declared tag-count task, checks its real
command and behavior tests, refreshes metadata, and invokes the public enriched
Mago path. Slice 3 correlates real HTTP responses with their profiler records,
replays the declared tag-filter repair, verifies historical profiler/log access
during a separate boot failure, and checks fresh recovery and regression tests.
Scripted slice replay is separate from the retained adaptive agent exercises
described in [SLICE-2.md](SLICE-2.md) and [SLICE-3.md](SLICE-3.md). Native whole-application findings
remain recorded rather than suppressed; this is a capability gate, not a claim
that every Demo diagnostic has been repaired. The original default container
check keeps Composer/Symfony validation; PHPStan/PHP-CS-Fixer require the explicit
`--legacy-comparison` option. Cache scope, event/concurrency policy and the
trusted default-branch Jev consumer are unchanged. No new calibration or local
provider key is involved.

The runtime stage uses the same candidate image as the earlier gates, in its own
application/database/state workspace. It runs once through `capture_step.py`;
native exits and nested `<stage>-error.txt` causes retain their original
run/attempt/source context. The collector accepts the declared `slice3` layout
under the same source, size and path checks as slices 1 and 2. Mocked tests cover
the runtime cause reaching the provider payload, foreign attempt rejection and
zero provider requests when all three slice results pass. The producer receives
no TypeSafe key; the trusted advisory consumer remains unchanged.

The combined LSP candidate also captures `lsp_extensions` after `slice3`.
Its fresh owned workspace verifies all 19 native worker controls and actual
host MCP/Serena on/off graph forwarding, then purges its application/state.
The [combined local validation](evidence/lsp-extensions/integration/validation.json)
at `7d7369cc87c64b3bd8d2d95749375f8954646c58` passes 178 fast tests, all 31
original checks, slices 1/2/3 at 9/12/14 stages and this focused LSP gate on one
verified image. These local results are separate from the hosted PR check.

Local parallel work can set `POC_IMAGE=mago-serena-poc:<session-tag>`. Compose,
launchers and the CI build helper honor that selection; unset or empty selection
keeps `mago-serena-poc:local`. Build and acceptance must use the same selection.
The selected run records the resolved configuration and actual image identity;
sharing the immutable image still leaves application/database/state directories
independent.

Local original acceptance on the slice-3 candidate image
`sha256:ff82c2ee2de6eedba1d5e93a6d62652a788998de0a22afec3bce802102eb40ec`
passed all **31 required checks** and **165 fast tests**. Both independent
application workspaces passed the exact original **53 tests / 120 assertions**.
The existing external-span reproduction remains labelled **EXPECTED NEGATIVE**;
its passing control does not claim that upstream behavior is fixed. Slice-specific
and hosted outcomes are reported separately in [SLICE-3.md](SLICE-3.md).

The slice-2 integration starts from merged PR #3 at
`8f154f798d7cf9ae7cf3cb33b0b99352de99dec4`. Slice failures and earlier attempts
are collected from their nested result/error files, bound to the producing
source and run. [Jev's collector contract](JEV.md) explains the bounded,
credential-free failure path; the trusted consumer and native CI verdict retain
their existing roles. Measurements below describe the earlier cache follow-up;
the slice-2 run is recorded separately with its final validation evidence.

The [local exact-image validation](evidence/slice2/integration/validation.json)
at `9e74151804e5e30f7b55d4e66cf09dd9ff0f7389` passed 148 fast tests, all 31
original acceptance checks, nine slice-1 stages and 12 slice-2 stages. One cached
build produced the shared verified image; separate disposable runs executed
concurrently in 68.203s, 92.429s and 57.889s respectively. These are local gate
durations, not hosted CI measurements. The actual default-relative-root collector
then produced a healthy packet and the mocked provider boundary observed zero
calls. The integrated PR records its hosted workflow duration and artifact links
after the required run completes.

The CI follow-up starts from merged default-branch commit
`262e06d00024ab4ff2c025ce2b52a2ff49f65715`, on a new
`ci/cache-and-live-jev` branch. PR1's branch is not the baseline. Application,
Serena, Mago, dependency and image pins are retained, as are all 31 required
acceptance checks and fresh app/database/vendor/state isolation.

## Scheduling and cancellation

| Event | Acceptance |
| --- | --- |
| Pull request, including documentation updates | Full acceptance; check name remains `acceptance` |
| Push to `master` | Full default-branch validation |
| Push to a feature branch | No second push acceptance alongside its PR |
| Explicit workflow dispatch | Full acceptance on the selected ref |

Concurrency is keyed by workflow, event and PR number, or ref for push runs.
Explicit dispatches use their run ID. A newer update supersedes only that PR or
push ref. Other PRs, default-branch pushes and manual validations use different
groups. There are no path filters that leave required PR checks pending.

## Persistent cache, not persistent runner disks

`tools/ci/build_image.py` runs the ordinary Buildx CLI through the existing
`capture_step.py` collector. Import/export use GHA cache API v2 and the stable
scope `mago-serena-linux-amd64-v1`, with `mode=max`. Adapter, test and documentation
hashes do not split the cache scope. Docker's layer keys still invalidate changed
inputs, including a changed toolchain or source pin.

The pinned Mago stage does not depend on the adapter, tests or documentation.
Its compile RUN copies the binary, lock/source identity and license notices
outside its cache mounts before finishing. `mode=max` exports that intermediate
RUN result; a later runner can import it and skip compilation. GHA does **not**
persist `/src/target` or Cargo registry cache-mount contents by default. We make
no such claim and add no cache-mount extraction machinery.

GitHub cache visibility is limited to the current ref, PR base and default
branch. A PR writes its merge-ref cache, reusable by later runs of the same PR;
other PRs and `master` cannot import that PR-only cache. After this change merges,
the first `master` run populates a default-branch cache that later PRs can import.
An unrelated sibling branch's old cache cannot seed the new PR. The initial
population run therefore remains a cold build.

The local Node24 action `.github/actions/cache-runtime` exposes only the cache
runtime variables needed by a CLI build. It masks the ephemeral runtime token,
never prints values, and has no dependencies or network requests. No TypeSafe
key is supplied to this action, build arguments, the test environment or containers.
Cache import/export errors remain visible failures rather than silently running
without the intended policy. Logs, source/run/attempt cache plan, Buildx metadata
and image ID are uploaded with the existing acceptance evidence.

Primary cache documentation:
[Docker GHA backend](https://docs.docker.com/build/cache/backends/gha/),
[GitHub Actions cache mounts](https://docs.docker.com/build/ci/github-actions/cache/),
[GitHub cache visibility](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).

## Supported immutable actions

| Action | Verified version | Commit | Runtime |
| --- | --- | --- | --- |
| actions/checkout | v6 | `d23441a48e516b6c34aea4fa41551a30e30af803` | Node24 |
| docker/setup-buildx-action | v4.4.1 | `f87e5991a6d7451dcb8d9637bfbc97413f497069` | Node24 |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` | Node24 |

Releases and their `action.yml` runtimes were checked against the official action
repositories. The producer uses these updated pins now. The trusted Jev consumer
continues using default-branch workflow/code until this PR merges, so its old
upload-action warning is distinct from the candidate producer's runtime.

## Measurements

The [baseline evidence](evidence/ci-performance/baseline.json) uses GitHub run/job/
step timestamps and actual BuildKit logs. Baseline PR run
[40486178957](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40486178957)
took **12m13s total**, with **10m00s build** and **1m40s acceptance**. The Mago
compile RUN took554.5s; Cargo itself reported9m13s. Same-head push run
[40485958869](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40485958869)
duplicated that work: **12m15s total**, **9m59s build**, **1m42s acceptance**.
Both lacked persistent BuildKit import/export and emitted Node20 warnings.

The old cached workflow's historical run was also cold; its existence is not
warm-cache performance evidence. Before this follow-up there was no default-branch
BuildKit cache; old entries belonged to a sibling feature branch.

| Hosted run | Build | Full acceptance | Total | Mago layer |
| --- | --- | --- | --- | --- |
| Baseline PR40486178957 | 10m00s | 1m40s | 12m13s | Compiled |
| [Merged default40489054256](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40489054256) | 9m37s | 1m40s | 11m54s | Compiled; no persistent cache |
| [Cache population40490285225](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40490285225) | 11m15s | 1m36s | 13m37s | Compiled; cache export78.9s |
| [Representative40492209788](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40492209788) | 38s | 1m13s | 2m21s | **CACHED**; export3.9s |

These are actual measurements, indexed in
[measurements.json](evidence/ci-performance/measurements.json). Compared with the
baseline, the representative build was93.7% shorter and total time80.8% shorter.
Against the newly merged default run, reductions were93.4% and80.3% respectively.
The population run paid the initial export cost; it was not faster than baseline.
This is one population and one representative sample, not a statistical benchmark.
Total includes startup/queue/teardown; build/acceptance use step timestamps.

The representative commit changed diagnostic code, added18fast tests and updated
documentation. Both runs passed the identical31required checks, original fresh
application isolation and exact source/image verification; fast tests grew from104
to122. Runner IDs differed (`1000022680` versus `1000022682`). The warm log records
Mago's compile step24as`CACHED`, with24cached steps and no new Cargo compilation.
[Cold excerpts](evidence/ci-performance/excerpts-40490285225.txt) and
[warm excerpts](evidence/ci-performance/excerpts-40492209788.txt) preserve the
import/export and compile/cache assertions. Both new producer logs have no Node20
deprecation warnings. The representative image changed with the new tests, so this
was not acceptance against an unchanged stale image.

Head-SHA run inventories show exactly one PR acceptance for both measured commits,
with no feature-push acceptance. The temporary producer display-name control did
not alter the full acceptance inventory or warm-cache scope; the final candidate
restores its literal-plus display name. That control alone did not trigger the
existing default listener: the registered workflow still had its default-branch
plus name. A separate short registered-workflow diagnostic control then triggered
trusted consumer40493363925, which wrote `nothing_to_diagnose` with zero provider
calls. It is tracked in JEV.md and removed from the final tree. It never replaces
acceptance.
The temporary registered workflow was also disabled after the observation, so no
diagnostic probe remains active. Existing default consumer warnings and unmerged
gate deployment remain separately documented in JEV.md.

## Local and hosted commands

```sh
uv sync --frozen --python 3.12.12
./bin/poc fast
# Ordinary local image setup keeps its existing command; no GitHub cache credentials needed:
./bin/poc up
```

The fast suite also executes the tiny Node action with fake values, so Node is
required for those tests; Actions runners provide it. All provider tests remain
mocked and credential-free. CI runs fast checks before building, then executes
the entire application/MCP acceptance and always collects/uploads evidence.

See [Jev activation and live outcomes](JEV.md). Live provider calls are separate
from deterministic acceptance and cannot make a failing source run green.
