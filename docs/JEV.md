# Advisory CI diagnosis with Jev

Jev is an optional TypeSafe API integration that suggests a failure-layer or
performance hypothesis from bounded CI observations. The independent
**Jev advisory diagnosis** workflow consumes acceptance artifacts, validates
those observations, and decides whether a provider request is warranted.
Deterministic checks remain authoritative. Jev cannot run a proposed diagnostic,
change workflow configuration, approve a result, or make a failing test pass.

The implementation on `master` includes performance eligibility and durable
request reservations, merged in [PR #7](https://github.com/xormania/mago-serena_v2-poc/pull/7)
at `cf38cd43254acbe696b9fe104c0314daefcfaaca`. This describes available source
behavior. The [historical live observations](#historical-live-observations)
below identify the older trusted revisions that actually made recorded calls;
merging newer code does not establish that it has made a live request.

See [CI](CI.md) for performance policy and source artifacts, and
[testing](TESTING.md) for the independent acceptance checks.

## Read a diagnosis

On the [Actions page](https://github.com/xormania/mago-serena_v2-poc/actions),
open **Jev advisory diagnosis** for the producing acceptance run. Read its job
summary and the following artifacts:

| Artifact | Contents | Retention |
| --- | --- | --- |
| `jev-advisory-<source-run>-<source-attempt>-consumer-<run>-<attempt>` | Sanitized provider or no-request output | 14 days |
| `jev-gate-<consumer-run>-<consumer-attempt>` | Evidence-gate decision, trusted history lookup, selected baseline, and reservation checks | 14 days |
| Reservation artifact named by the gate | Immutable reservation written before a key-bearing step | 90 days |

A normal assessment directory contains `summary.md`, `result.json`,
`request.json`, and `response.txt`. `result.json` identifies the tested source,
actual trusted checkout/code hashes, requested/observed model, live/mock route,
request count, status, latency, available usage, and truncation. Request/response
files are sanitized; the response is retained even when malformed. A performance
assessment also retains recomputed `performance-report.json`. Gate outputs
include a readable `gate-summary.md` and, where applicable, a performance summary.

| Outcome | Interpretation |
| --- | --- |
| `nothing_to_diagnose` | No failed/blocked check or supported actionable performance signal; no request |
| `missing_credentials` | The assessment requires a provider but no key is available |
| `diagnosed` | A structurally valid supported hypothesis was returned; correctness still needs investigation |
| `abstained` | The provider selected an explicit unknown/insufficient-evidence outcome |
| `timeout`, `provider_failure`, `malformed_response` | The provider request or response validation failed |
| Gate suppression or reservation error | Read the gate artifact; a provider call is withheld |

A green advisory job is not application acceptance, proof that a diagnosis is
correct, or proof that a provider was called. Check `provider_request_attempts`,
transport, and per-case outcomes. The source workflow's verdict is independent.

## When a request is made

The current implementation accepts either an actual failed/blocked observation
or a supported deterministic performance signal. A successful source run can
qualify for unexpected recompilation, a compatible substantial verification
slowdown, or an absolute budget breach. Warm success, explained cold population
inside budget, and missing history alone do not qualify. [CI performance policy](CI.md#performance-reporting-and-comparison)
provides the exact thresholds and comparison rules.

The producer's schema 1 packet can contain optional performance observations
while retaining the original failure-probe map. Old packets without performance
remain supported. Trusted consumer code validates inputs and recomputes policy;
it never trusts a producer-supplied eligibility flag or provider authorization.
The credential-free gate and provider entry point both check eligibility. They
share one bounded request, with failure evidence prioritized if both failure and
performance information are present.

Before a request, the gate checks bounded Actions metadata for prior reservations
and uploads an immutable reservation. Lookup or upload failure prevents a call.
Ordinary reservations are keyed by producer run ID and attempt. Calibration uses
the dispatch run ID, independent of rerun attempt. Consumer reruns are suppressed
even if an older marker has expired, and an interrupted or failed request remains
reserved rather than being retried. Concurrency serializes matching attempts but
is not the durable duplicate-prevention mechanism.

## Workflow and credential boundaries

The producer, [`.github/workflows/poc.yml`](../.github/workflows/poc.yml), runs
without a TypeSafe key. Its `always()` collector writes a bounded JSON packet
and uploads it with the source run/attempt. The consumer,
[`.github/workflows/jev.yml`](../.github/workflows/jev.yml), listens for completed
producer runs from this repository. Its workflow-name filter escapes the literal
`+` in `Pinned Serena + Mago PoC`.

The consumer checks out `tools/ci` from the repository's default branch into
`trusted`, with persisted checkout credentials disabled. It records the actual
checkout SHA and invokes isolated Python (`-I`). It never executes the tested
revision or downloaded artifact contents. A pull request can change producer
observations, but its proposed diagnosis code is not loaded by the default-branch
consumer. After such a change merges, later consumer executions use the actual
then-current default revision and record it separately from the tested source.

`download_inputs.py` selects the exact source run/attempt's named artifact. It
caps compressed ZIP input at 200,000 bytes, requires exactly one
`diagnosis-input.json` member, caps that JSON at 48,000 bytes, rejects symlinks or
unexpected members, and reads JSON in memory without extraction. Duplicate fields,
non-finite numbers, foreign run/SHA identities, and invalid references are rejected.
Instructions embedded in logs are untrusted data.

Only the provider step receives the configured repository secret:

```yaml
env:
  TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}
```

The gate, build, tests, application containers, arguments, and artifacts do not
receive that key. The fixed TypeSafe endpoint receives its Authorization header;
redirects are refused. Output sanitization removes the exact key and recognized
credential fields, bearer strings, and URL credentials. Redaction is bounded
best-effort for arbitrary text; credentials must not be placed intentionally in
test outputs or source logs.

The consumer pattern constrains these workflows. A repository secret alone does
not stop a writer from creating a different secret-reading workflow; broader
restrictions require repository policy or an appropriately restricted environment
secret. No repository policy change is implied by using this integration.

All three CLI entry points resolve sibling imports from their actual trusted
`tools/ci` directory because isolated Python excludes the script directory and
ignores `PYTHONPATH`. The regressions exercise the actual provider CLI from an
unrelated directory with hostile sibling-module names and an empty key.

## Collected evidence and validation

The source packet binds run ID, run attempt, tested checkout SHA, and workflow
head SHA. On a PR, the tested merge SHA can differ from the workflow head; both
are retained rather than substituting one for the other. Each excerpt includes
an ID, step, attempt, and truncation flag. Earlier failures survive later success.

The collector reads only declared result layouts, including
`artifacts/<run>/slice{1,2,3}/attempt-*/results.json`, their `source.json`, and
named `<stage>-error.txt` files. A root `slice{1,2,3}-result.json` is a latest-attempt
mirror, not another observation. A failed wrapper and its nested stage cause
augment one check rather than being counted as independent failures.

| Collection bound | Limit |
| --- | --- |
| Outer captured log | 1 MiB, with disclosed truncation |
| Packet excerpts | 20, at most 1,600 bytes each |
| Outer step rows / test-run directories | 12 / 20 |
| Source documents / results / traces | 16 MiB / 1 MiB / 1 MiB |
| Attempt directories per exercise | 20 |
| Entire packet | 48,000 bytes |

Omitted counts are explicit. Source/context/run/attempt mismatches, invalid stage
inventories, and inconsistent mirrors reject collection. A setup failure is not
credit for reproducing an application defect. Full available test artifacts are
uploaded separately from this small packet.

[Collector regression records](evidence/jev-slice-contract/result.json) preserve
the former omission and repaired payload with a mock provider. The
[final correlation record](evidence/jev-slice-contract/final-correlation/result.json)
retains the one-check/two-excerpt result. These are local contract evidence, not
live requests or fresh model-accuracy measurements.

## Provider contract

The configured endpoint is `https://api.typesafe.ai/v1/systemone`, with exact
model `jev-1.14.0`. Each assessment makes at most one request, with a 15-second
socket timeout, 58,000-byte request bound, and 65,536-byte response bound. The
workflow bounds the provider step to two minutes. There is no automatic retry.

Four typed choice questions return a failure-layer or performance hypothesis,
up to two supporting supplied excerpt/metric/comparison IDs, and a proposed next
diagnostic from trusted options. `unknown` and `none` are explicit outcomes.
Validation checks model, question inventory, choice membership, supplied
confidence/probability ranges, distinct references, and required supporting
evidence. A performance hypothesis needs supplied performance evidence. This
validates structure and attribution; it does not prove causality or usefulness.

Available usage is preserved even on failed responses. Missing usage stays
unknown. The code's price reference is dated **27 October 2026**: USD 0.042 per
million input tokens with free output, from the [TypeSafe model reference](https://docs.typesafe.ai/models).
Its estimate is not an invoice or a claim about current pricing. Actual billed
cost remains unknown unless returned separately by the provider.

## Local checks and manual calibration

The normal [fast test suite](TESTING.md) requires no API key and uses mocked
provider responses. To focus on this integration after installing the locked
host environment:

```sh
./bin/poc fast
python3 -m unittest discover -s tests/fast -p test_jev.py -v
python3 -m unittest discover -s tests/fast -p test_jev_slice.py -v
```

Tests cover diagnosis, abstention, missing credentials, timeout, provider failure,
malformed/wrong-model/incomplete replies, unsupported references, redaction,
bounds, immutable attempts, recovered failures, reservations, and artifact
validation. Test outputs label mocked transport explicitly.

Manual **Jev advisory diagnosis** dispatch with `calibration: true` is a live
provider operation restricted by the workflow to the default branch. It makes
at most four requests, one attempt per case, using
[`tools/ci/calibration.json`](../tools/ci/calibration.json):

| Case | Kind |
| --- | --- |
| Closed-file position defect | Frozen known-defect reproduction excerpts/hashes |
| Root PHPUnit configuration omission | Frozen legacy verifier defect excerpts/hashes |
| Correct closed-file coordinates | Frozen repaired-adapter healthy control |
| Timeout without causal evidence | Synthetic ambiguous observation |

These are replays and one synthetic control, not fresh defect executions. The
expected labels remain in the separate plan and are not sent as provider input.
A plan is written before calls and each case retains request, response, model,
usage, latency, and outcome. This small selected set cannot estimate production
accuracy or confidence calibration. Ordinary documentation/test maintenance does
not require running it.

## Historical live observations

The following records describe the trusted implementation and fixtures used at
the time. Later merged reservation/performance code has local/mocked coverage;
these old calls do not establish its live execution.

### Recorded activation controls

The first merged producer [40489054256](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40489054256)
completed successfully without creating an automatic Jev run. The old listener
used an unescaped `+` in a glob pattern. A branch-only display-name change in
[40492209788](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40492209788)
also did not trigger the registered listener. These are never-triggered cases,
not skipped diagnostic jobs or evidence-only diagnoses.

A temporary registered source [40493337758](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40493337758)
at `15c4ba5c5d921b38b366015367c19bf381c18d50` triggered automatic consumer
[40493363925](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40493363925).
It ran trusted `262e06d00024ab4ff2c025ce2b52a2ff49f65715`, read the bounded packet,
and recorded `nothing_to_diagnose` with zero calls. Its response contained no
HTTP status, model, or usage. This was healthy workflow-control evidence, not
application acceptance. The temporary workflow was removed and its registration
disabled; its [source snapshot](evidence/ci-performance/trigger-control.workflow.txt)
and [sanitized identities/output](evidence/ci-performance/healthy-consumer-verification-40493363925.json)
remain recorded.

The [activation classification](evidence/ci-performance/activation-classification.json)
distinguishes absent triggers, evidence-only execution, rejected responses, and
completed diagnosis. A later recorded automatic consumer
[40815165257](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40815165257)
used trusted `6a4d2ed6234d724c67d3755285fe66c12b89fbbc` and made zero calls, as
recorded in [PR #7](https://github.com/xormania/mago-serena_v2-poc/pull/7).
That pre-merge consumer did not execute PR #7's proposed code.

### Recorded four-call calibration

[Run 40489607174](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40489607174)
made exactly four live requests using the Actions secret, no retries, trusted code
and fixture revision `262e06d00024ab4ff2c025ce2b52a2ff49f65715`, and exact model
`jev-1.14.0`. All returned HTTP 200. There was one accepted diagnosis, two
abstentions, and one rejected response:

| Case | Outcome | Latency | Input / output tokens |
| --- | --- | --- | --- |
| Closed-file defect replay | Rejected: repeated `e2` supporting reference | 0.233480 seconds | 1649 / 242 |
| Root-configuration defect replay | `application_integrity`, support `e1`, suggested `verify_run_identity` | 0.093961 seconds | 1521 / 225 |
| Healthy replay | Abstained: `unknown`, `none` | 0.102696 seconds | 1526 / 220 |
| Synthetic ambiguous control | Abstained: `unknown`, `none` | 0.128364 seconds | 1394 / 219 |

The [sanitized live artifacts](evidence/ci-performance/live-calibration-40489607174/)
and [summary](evidence/ci-performance/live-calibration-summary.json) retain these
observations. Local replay reproduces `ValueError: Duplicate supporting reference`
for the rejected response. The older workflow remained green because its advisory
CLI did not signal rejected per-case outcomes. The current implementation records
per-case reasons and returns nonzero for rejected calibration responses, while
leaving the producing workflow's verdict independent.

Total available usage was 6,090 input and 906 output tokens. The dated list-price
estimate was USD 0.00025578; the provider supplied no billed cost. No provider
HTTP/transport failure occurred in this four-call record. None of these outcomes
establish production diagnostic accuracy or prove that a suggested probe is useful.

The [independent v1 review](https://github.com/xormania/xorchestrate/blob/cfa3549490ee9db1c3e6cad918523cd854902e51/experiments/jev_failure_correlation/INDEPENDENT_REVIEW.md)
and [v2 methodology review](https://github.com/xormania/xorchestrate/blob/cfa3549490ee9db1c3e6cad918523cd854902e51/experiments/jev_failure_correlation_v2/reviews/methodology-review.md)
report that confident wrong answers and misleading detection credit remain
possible; selection agreement alone does not establish probe utility. Deterministic
checks and actual target assertions remain the basis for acceptance here.

The [pre-refresh Jev document](https://github.com/xormania/mago-serena_v2-poc/blob/cf38cd43254acbe696b9fe104c0314daefcfaaca/docs/JEV.md)
retains the full earlier rollout chronology and donor references. The current
workflow, request gates, and provider contract are described above.
