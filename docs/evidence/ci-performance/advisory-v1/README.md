# Historical CI performance observations

These are retained observations downloaded on 2026-10-29, before artifact expiry.
They are not synthetic fault cases or model replies. No provider call was made
while collecting them. Each `observed-<run>.json` binds run/attempt/tested checkout,
workflow head, runner image, image identity, native gate inventories and GitHub
job/step timestamps to its original Actions artifact. It also records retrieval
commands, original byte counts and SHA-256 digests, selected line numbers, and
selection rules. No complete build output, vendor tree or Rust target is retained.

| Observation | Warm PR #6 | First merged master |
| --- | --- | --- |
| Run | [40798696741](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40798696741) | [40799634539](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40799634539) |
| Attempt / job | 1 / 123201305754 | 1 / 123204359865 |
| Event / cache ref | pull_request / refs/pull/6/merge | push / refs/heads/master |
| Tested checkout | 60c578e1ab69d80deee263e78a241f857d9befe3 | 6a4d2ed6234d724c67d3755285fe66c12b89fbbc |
| Workflow head | 8dc3158f654159b23900345fcd07989b48aa62ef | 6a4d2ed6234d724c67d3755285fe66c12b89fbbc |
| Run wall, GitHub API | 464 s | 1,158 s |
| Captured image build | 47.548 s | 651.353 s |
| Baseline / candidate compile layer | cached / cached | cached / executed |
| Executed candidate, BuildKit RUN | unknown duration (cached) | 570.7 s |
| Cargo release report | none (cached) | 9m 30s; 253 `Compiling` entries |
| Five captured verification phases, sum | 381.369 s | 469.772 s |
| Cache manifest import / export, BuildKit | 0.1 / 5.5 s | 0.3 / 25.3 s |
| Runner image | ubuntu-24.04, 20261025.353.1 | ubuntu-24.04, 20261025.353.1 |

`steps-<run>.jsonl` is the original bounded command ledger. Historical elapsed
values used wall-clock subtraction; new capture uses a monotonic clock. GitHub
API step durations are rounded to seconds and differ slightly from captured
command timings. Run wall time includes work beyond these phases and must not be
presented as their sum. Queue, setup, collection, artifact upload and post-action
cleanup are separately recoverable from the retained job timestamps.

`build-<run>.log` contains selected original BuildKit lines in original order,
without timestamp decoration, for parser regression tests. `timestamped-<run>.txt`
retains corresponding GitHub log records and checkout/runner observations for
correlation. Compilation duration comes from BuildKit/Cargo output, not the
buffered outer timestamps. The cold log deliberately retains the baseline
`CACHED` followed by repeated headers, downloads/extraction and `DONE 17.1s`:
that duration is layer materialization, not compilation. Most candidate compile
entries are omitted from the compact excerpt; their count was measured against
the complete original build member before omission and recorded in metadata.

[comparison.json](comparison.json) records matching Git object IDs for Dockerfile,
patch, locks, configuration, build helper and workflow between the PR merge
checkout and merged master. The 603.805 s build delta explains about 87% of the
694 s total run delta. This comparison establishes an explained first cold
candidate population across a cache-visibility boundary. It does not establish a
recurring cache failure. The 88.403 s verification sum difference has no
established cause from these two observations. Cold and warm samples do not
supply a valid verification regression baseline.

GitHub [restricts cache visibility by branch/ref](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching#restrictions-for-accessing-a-cache),
including PR merge-ref caches. Docker's [GHA backend follows those access restrictions](https://docs.docker.com/build/cache/backends/gha/#scope),
and its [cache mounts are not persisted in the GitHub Actions cache by default](https://docs.docker.com/build/ci/github-actions/cache/#cache-mounts).
A cached unmodified executable layer consequently does not establish the presence
of Cargo intermediates needed to compile a new patched candidate. Master's
successful export is observed; accessible future cache presence remains subject
to visibility, eviction and export validity.

The bounded master history query at the recorded retrieval time found no newer
unchanged-master run after 40799634539. Warm reuse on that master SHA remains
unverified. Final PR measurements, when added, concern their identified PR cache
regime and do not resolve that master question by implication.

To reproduce retrieval while retained:

```sh
gh api repos/xormania/mago-serena_v2-poc/actions/runs/40799634539
gh api repos/xormania/mago-serena_v2-poc/actions/jobs/123204359865
gh run view 40799634539 --job 123204359865 --log
gh api repos/xormania/mago-serena_v2-poc/actions/runs/40799634539/artifacts
# Use the exact nonexpired poc-evidence artifact ID from that inventory;
# read only ci/step-attempts.jsonl, ci/build-plan.json, ci/build-attempt-1.log,
# ci/image.iid and declared gate inventories from its bounded ZIP.
```

The PR counterpart uses job 123201305754 and run 40798696741. Artifact IDs,
source-member digests and selected source line numbers are recorded per
observation. The two build excerpts also run locally without GitHub credentials
through the historical performance tests. Mock provider tests are separately
identified by `transport: mock`; they demonstrate contract behavior, not live
model causal accuracy. This reporting work alone establishes no speed improvement.
