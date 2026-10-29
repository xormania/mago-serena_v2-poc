# Advisory Jev diagnosis

## Performance advisory contract and rollout

Successful source runs now carry separately validated schema 1 `performance`
observations inside the existing schema 1 packet. `allowed_probes` remains exactly
the legacy failure-probe map. The current default-branch consumer at
`6a4d2ed6234d724c67d3755285fe66c12b89fbbc` accepts the optional new field, validates
the original packet contract and continues its failure-only eligibility behavior.
The candidate consumer accepts both old packets without performance data and new
packets. New policy, performance choices and eligibility are owned by trusted
consumer code, never taken from producer-supplied probe options or an eligibility
flag. [CI reporting and policy](CI.md) documents exact metrics, thresholds,
fingerprint coverage, bounded baseline selection and comparison limitations.

The producer writes its deterministic report and readable Actions summary before
any provider decision. The candidate trusted consumer validates source/run/attempt
associations, observation schema, finite nonnegative numeric bounds (excluding
booleans), bounded inventories and evidence references, then performs bounded
history lookup and recomputes the report. Both its credential-free preparation
gate and the provider entry point accept an actual failed/blocked check **or** a
supported deterministic performance signal. The preparation gate writes the
trusted selected baseline locally; the provider step reads that file and
recomputes the second gate. No downloaded file is executed.

A healthy warm run needs zero calls, including when a fake key exists in local
tests. Explained cold population inside its budget stays visible and normally
needs zero calls. Missing/incomparable history alone cannot authorize diagnosis.
A substantial comparable verification slowdown, a configured absolute-budget
breach or supported unexpected recompilation can qualify a successful source
run. Failures and performance share one bounded request with failure evidence
priority; omitted performance fields are disclosed. Genuine check statuses and
expected-negative controls are retained. No timing check changes acceptance.

The existing four typed choice questions can select trusted performance choices:
expected cold population, cache visibility/reuse concern, compilation cost, slow
verification, or insufficient evidence. Supporting answers cite supplied metrics
or comparison evidence IDs; strict validation requires supporting evidence and
rejects unsupported choices, missing/duplicate references, malformed probabilities
and a wrong model. Permitted next diagnostics are suggestions only. Jev cannot
execute a probe, change workflow configuration, approve a run or prove a root
cause. `setup_environment` continues to mean an intended check could not execute.
Jev answers questions about supplied structured state; it has not independently
inspected GitHub history or arbitrary repository files, consistent with the
[TypeSafe System One contract](https://docs.typesafe.ai/api/system-one).

The consumer renders deterministic metrics separately from a validated Jev
hypothesis in `summary.md` and the job summary, states live/mock transport and
explains no-request/missing-credential outcomes. `performance-report.json` retains
its recomputed metrics; gate artifacts retain baseline selection and reservations.
These remain advisory, including provider transport/validation failures. They
cannot turn a failing source run green.

`workflow_run` still checks out the actual default branch into `trusted`, records
its checkout SHA and uses isolated Python. This PR's candidate consumer is not
automatically exercised by PR producer completion. Hosted PR runs therefore prove
the new producer with the currently merged consumer; candidate performance
eligibility, typed provider integration and both-direction packet rollout are
validated with mocked replies. New trusted performance behavior requires a merge
and a later default-branch execution before any hosted/live claim. No candidate
checkout receives the TypeSafe secret, and no new live calibration or paid fault
run is part of this work. The existing at-most-one reservation-before-key request,
no retry, durable duplicate suppression, cancellation/rerun behavior, response
bounds, redaction, pinned `jev-1.14.0` model and failure priority remain in place.

All three CLI entry points explicitly add their resolved trusted `tools/ci`
directory to the import path: `python -I` excludes the script directory as well
as ignoring `PYTHONPATH`. The provider entry point needs this for its performance
siblings even though the key-free gate already imported them successfully in
another process. Subprocess regressions invoke the actual isolated provider CLI
from an unrelated directory containing hostile sibling-module names, with empty
credentials. They cover warm packets, successful performance signals, failed
checks carrying performance data, and the four-case calibration path, making zero
provider requests. The calibration regression is a keyless CLI smoke test, not a
new live calibration.

[Actual retained cold/warm observations](evidence/ci-performance/advisory-v1/README.md)
are distinct from synthetic fault tests and mock provider responses. Mocked useful
answers prove integration behavior, not the model's causal accuracy. The following
sections retain historical activation and calibration evidence from earlier PRs;
those live calls did not run this candidate implementation.

PR1 merged into default `master` at
`262e06d00024ab4ff2c025ce2b52a2ff49f65715`. Both workflows are registered and
active. The old explanation that the consumer exists only on a PR branch is no
longer applicable. The CI follow-up uses a fresh branch from that merged revision.

## Automatic activation: registration versus name matching

The first merged default-branch producer
[40489054256](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40489054256)
completed successfully, but **no automatic Jev run was created**. This was neither
a skipped diagnostic job nor a healthy evidence-only run. The registered consumer
used `workflows: [Pinned Serena + Mago PoC]`: GitHub interprets these names as glob
patterns, where `+` repeats the preceding character. It does not literally match
the producer's plus sign. The candidate uses the single-quoted pattern
`'Pinned Serena \+ Mago PoC'` and includes a focused old/fixed matching regression.
This follows [GitHub's documented workflow-name filter contract](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_runworkflows).

A branch-only two-space display-name control in representative run40492209788
did **not** trigger the listener; the existing workflow's registered default name
remained the literal-plus name. That failed probe is retained as an observation.

A separate temporary registered workflow with the two-space name then supplied
an actual healthy, credential-free trigger control. Source
[40493337758](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40493337758)
at `15c4ba5c5d921b38b366015367c19bf381c18d50` triggered real automatic consumer
[40493363925](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40493363925).
The consumer executed trusted default revision262e06d, downloaded the bounded
packet successfully and recorded **`nothing_to_diagnose`, zero provider calls**.
Its response file is empty, with no HTTP status, returned model or usage.
This is observed healthy workflow-control evidence, **not application acceptance**.
[Source/trusted identities and sanitized outputs](evidence/ci-performance/healthy-consumer-verification-40493363925.json)
make that distinction reviewable. The temporary workflow is removed from the final
tree and its registration disabled after observation; its [source snapshot](evidence/ci-performance/trigger-control.workflow.txt)
remains evidence. It did not duplicate the expensive acceptance job.

The final producer name is restored to `Pinned Serena + Mago PoC`. This isolates
the registered-name matching defect and demonstrates that the existing consumer's
artifact/condition/permission/healthy-data path works. The corrected literal-plus
listener and new reservation/reporting code become trusted only when this PR
reaches the default branch. Their post-merge execution remains to be observed;
the successful old-code control does not substitute for it.

Workflow registration, job status, evidence-only operation and validated provider
outcomes are inspected separately. Manual calibration proves provider access;
it does not by itself prove the broken automatic filter or unmerged repair works.
[The classification record](evidence/ci-performance/activation-classification.json)
distinguishes never-triggered, skipped-job (not observed), evidence-only, rejected
provider-response and completed-diagnosis cases. No provider HTTP/transport failure
was observed in the four-call calibration; the rejected case returned HTTP200.

## Observed live calibration

The single authorized calibration ran on GitHub Actions in
[40489607174](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40489607174).
It made exactly **four live requests**, with no provider retries, using the
existing Actions secret. All returned HTTP200 and exact model `jev-1.14.0`.
There was **one accepted diagnosis, two abstentions and one rejected response**.
Sanitized requests/responses, models, usage, latency and source identities are
retained under [live calibration evidence](evidence/ci-performance/live-calibration-40489607174/)
and its [summary](evidence/ci-performance/live-calibration-summary.json).
No key was retrieved locally. Local provider tests remain mocked.

The actual trusted code and calibration fixture revision for those calls is
`262e06d00024ab4ff2c025ce2b52a2ff49f65715`. This is **not** live validation of the
new PR's unmerged reservation/reporting changes. Recorded defect/healthy inputs
are replays; the ambiguous timeout control is synthetic. No fresh defect
execution or production calibration/diagnostic-accuracy claim follows.

| Case | Live outcome | Latency | Input / output tokens |
| --- | --- | --- | --- |
| Closed-file defect replay | Response rejected: `support_1=e2` and `support_2=e2` violate distinct-reference validation | 0.233480s | 1649 / 242 |
| Root-configuration defect replay | `application_integrity`, supporting `e1`, suggested `verify_run_identity` | 0.093961s | 1521 / 225 |
| Healthy replay | Abstained: `unknown`, `none` probe | 0.102696s | 1526 / 220 |
| Synthetic ambiguous control | Abstained: `unknown`, `none` probe | 0.128364s | 1394 / 219 |

The closed-file provider selected the plausible layer and probe but repeated the
support ID. Local deterministic replay of the retained response reproduces
`ValueError: Duplicate supporting reference`; strict rejection is preserved.
The existing workflow completed green because diagnosis is advisory and its CLI
did not signal rejected case outcomes. Candidate code now records the validation
reason, explicit attempt count and per-case calibration summary, and returns
nonzero for rejected responses while keeping the source verdict independent.
No further live calibration requests are authorized in this iteration.

Total available usage was6090input/906output tokens. The dated public input-price
estimate is USD0.00025578; the provider returned no cost/invoice, so actual billed
cost remains unknown. A useful-looking hypothesis is not proof of causal accuracy.

## Local validation

```sh
./bin/poc fast
# Just the provider/collector/security-boundary cases:
python3 -m unittest discover -s tests/fast -p test_jev.py -v
# Slice producer/collector regression and mocked provider payload:
python3 -m unittest discover -s tests/fast -p test_jev_slice.py -v
```

These tests require no API key. They cover useful diagnosis, abstention, missing
credentials, timeout, provider failure, malformed/wrong-model/incomplete replies,
unsupported excerpt/probe references, redaction, bounds, immutable attempts,
recovered failures, and artifact validation. Provider results from these tests
are explicitly marked `transport: mock`.

## Producer and trusted consumer

`.github/workflows/poc.yml` runs locked Python setup, fast tests, the image build,
and Docker acceptance through `tools/ci/capture_step.py`. The wrapper returns the
command's original exit status and writes one immutable log per step/attempt plus
`artifacts/ci/step-attempts.jsonl`. It does not retry. An explicit second attempt
uses another number and retains the first. Logs are capped at 1 MiB and disclose
truncation. Setup Action failures that precede a captured command are reported as
setup observations; they cannot earn credit for reproducing an intended defect.

An `always()` collector writes a bounded `diagnosis-input.json`. Its schema binds
the producing GitHub run ID, run attempt and tested checkout SHA. It separately
records the workflow head SHA: on pull requests the tested merge commit differs
from the PR head commit. The consumer binds the workflow head to its event while
retaining the actual tested merge identity; it never substitutes one for the other. Each excerpt has a stable
ID, step, attempt and truncation flag. Internal failed attempt ledgers, including
recovered attempts, contribute excerpts with their original run/context identity.
The collector retains at most 20 excerpts (1,600 bytes each), 12 outer step rows
and 20 harness run directories; omitted counts are explicit. The full available
harness evidence is uploaded separately on success and failure. Producer code
has no TypeSafe credential.

The collector also understands the declared slice layouts:
`artifacts/<run>/slice{1,2,3}/attempt-*/results.json`, each attempt's `source.json`
and named `<stage>-error.txt`. The root `slice{1,2,3}-result.json` is a latest-attempt
mirror and never creates another observation. When one captured slice wrapper
failed, its nested stage excerpts augment that same failed check; the wrapper
and its cause are not counted as independent failures. A recovered wrapper still
retains earlier nested failures as failed observations. Multiple failed wrapper
attempts retain stage provenance without guessing a parent from unrelated
counters. Earlier failed attempts survive a
later successful attempt. Slice observations identify the owned run, attempt
directory, source revision/context digest and failing stage; their numeric
attempt is the stage's `step_attempt` (one unless the producer records otherwise).
The producer's actual reason and sanitized traceback tail reach the packet even
when the console excerpt only contains `fail: symfony_wiring` and cleanup.

Only those declared files are read. Source documents are limited to 16 MiB,
results to 1 MiB, traces to 1 MiB, and each slice to 20 attempt directories.
The existing global 20-excerpt/48,000-byte packet bounds still apply. Source
revision, context hash, run/workspace, optional explicit attempt ID, stage
inventory/status and mirrored-result mismatches reject collection rather than
silently attributing evidence to the wrong run. Relative `--root artifacts`
resolves to the producer's absolute evidence paths. The
[local contract proof](evidence/jev-slice-contract/result.json) records the
pre-fix omission and repaired real-collector payload with a mocked provider;
it contains no live request or new calibration.
The [integration correlation proof](evidence/jev-slice-contract/final-correlation/result.json)
retains the final one-check/two-excerpt packet and mocked provider payload after
the wrapper/stage correlation adjustment.
Slice 3 extends that same collector contract to runtime diagnosis stages. Its
mocked regressions retain a failed request's stage reason and original context
in the provider payload, reject a foreign attempt, and observe zero provider
requests for healthy slices. No live calibration or consumer trust change is
part of this extension.

`.github/workflows/jev.yml` consumes completed runs on a fresh runner. It checks
out diagnosis code from the repository's default branch, records the **actual
checkout SHA**, and invokes isolated Python (`-I`). It never checks out or executes
the tested revision. `download_inputs.py` downloads only the exact run/attempt's
named artifact with the Actions token. It limits the compressed ZIP to 200,000
bytes, requires exactly one `diagnosis-input.json` member, caps its uncompressed
size at 48,000 bytes, rejects symlinks/unexpected members, and reads JSON in memory
without extraction. Duplicate JSON fields/non-finite numbers, foreign run/SHA,
missing identities and duplicate/invalid references are refused. Artifact text is
untrusted data, including any instructions inside it.

The TypeSafe secret appears only in the diagnosis step's environment:

```yaml
env:
  TYPESAFE_API_KEY: ${{ secrets.TYPESAFE_API_KEY }}
```

No application/test container, Docker build, command argument, producer or
artifact receives that key. Only the fixed TypeSafe endpoint gets an Authorization
header; redirects are refused. Request and response evidence removes the exact
key plus credential-like fields, bearer strings and URL credentials. The script
does not log headers or raw exceptions containing provider data. Redaction is
bounded best-effort for arbitrary evidence; do not intentionally place secrets
in source/logs. Full application artifacts are credential-free test outputs,
not a place to store credentials.

This workflow adapts the independent producer/consumer pattern in
[UXor PR 132](https://github.com/xormania/uxor/pull/132), inspected at
`2a5c9bab65bf12402eee0d0b0203d753969da55c`: a source workflow uploads data and a
later default-branch consumer runs trusted diagnostic code. The producer never
calls a branch-controlled reusable workflow with the key.

GitHub requires this consumer and its trusted tools on the **default branch**.
That requirement is now satisfied by merged PR1, as the actual calibration proves.
New changes in a follow-up PR remain unexecuted by the trusted consumer until
merged. Automatic runs check out default-branch diagnosis code and record the
tested source revision separately. Manual calibration is also restricted to the
default branch. The existing repository secret suffices; repository-secret
visibility does not independently prevent a writer from creating another
secret-reading workflow. Restricting that broader permission requires repository
policy or an environment-only secret restricted to a protected branch. No secret
or repository policy was changed here.

## Provider contract and retained evidence

The fixed provider is TypeSafe, endpoint
`https://api.typesafe.ai/v1/systemone`, exact requested model `jev-1.14.0` (not a
moving alias). Its model identity and current input-only list price were checked
against the [official model reference](https://docs.typesafe.ai/models) on
2026-10-27. Each assessment makes at most **one request**, with a 15-second socket
timeout, a 58,000-byte request bound and a 65,536-byte response bound. The workflow
also bounds the entire diagnosis step to two minutes. There is no blanket retry.

Four typed choice questions return a failure-layer or performance hypothesis, up to
two supporting supplied excerpt/metric/comparison IDs, and one next diagnostic
step from trusted options.
`unknown`/`none` are explicit outcomes. Exact model, complete question inventory,
option membership, confidence/probability values when supplied, distinct excerpt
references and supporting evidence are validated. A useful hypothesis without a
supporting excerpt is rejected. This validates references and structure; it does
not establish that the hypothesis is correct.

A fresh output directory contains:

- `request.json`: sanitized exact request body; its SHA is in the result.
- `response.txt`: bounded sanitized provider response, even if malformed.
- `result.json`: source/run identity, actual trusted checkout/code hashes,
  endpoint/model/configuration, live/mock route, status, diagnosis, latency,
  available token usage/provider cost, input list-price estimate, and truncation.

Missing usage stays unknown. List-price estimates use USD 0.042 per million
input tokens and free output tokens from the dated model reference; these are
not invoices. Actual billing remains unknown unless separately available. Failed
responses retain available usage too. Prior attempts cannot be overwritten.

With no failed/blocked observation and no supported actionable performance signal,
normal CI writes `nothing_to_diagnose` without a request, even when a key exists.
Explained cold population and missing history alone do not qualify. Missing keys produce
`missing_credentials`. Jev cannot change source check results, suppress required
tests, approve a run, or execute its proposed probe. Consumer failure affects
only the advisory consumer and never changes the producing workflow's verdict.

## Explicit calibration and duplicate prevention

For a future explicitly authorized calibration, manually dispatch **Jev advisory
diagnosis** on the default branch with `calibration: true`. This is a bounded mode:
**at most four requests, one attempt per case**. It uses the trusted
`tools/ci/calibration.json` fixture:

| Case | Origin | Interpretation |
| --- | --- | --- |
| Closed-file position defect | Frozen excerpts/hashes of actual pre-fix adapter/Mago reproduction | Known-defect replay |
| Root PHPUnit configuration omission | Frozen excerpts/hashes of actual legacy verifier acceptance | Known-defect replay |
| Correct closed-file coordinates | Frozen excerpts/hashes of actual repaired adapter control | Healthy replay |
| Timeout without causal evidence | Clearly marked synthetic incomplete observation | Ambiguous control |

Each case records its kind/origin; these are **replays, not fresh defect
executions**. The expected-layer labels are frozen in the separate plan and are
not sent in model-visible packets. The request includes only the supplied
observations and probe choices. Calibration records its plan before calls,
actual request/response/model/usage/latency and statuses per case. Healthy and
ambiguous controls deliberately exercise the abstention path. This small chosen
set is not a production accuracy or confidence-calibration estimate.

The follow-up adds a key-free evidence/reservation gate before the provider step.
Healthy evidence writes `nothing_to_diagnose` with zero provider requests and
never receives the TypeSafe key. Missing evidence and duplicate suppression have
explicit gate artifacts. A failure needing diagnosis first checks bounded Actions
metadata for a previous reservation owned by the default-branch Jev workflow,
then uploads an immutable reservation before the key-bearing step. API lookup or
reservation upload failure prevents a call. Artifact contents are never executed.

Ordinary reservations are keyed by producer run ID and attempt. Calibration
reservations use their dispatch run ID, independent of rerun attempt. Consumer
reruns are suppressed even if an older marker has expired; failed/interrupted
provider attempts remain reserved rather than retried. Reservations are retained
for90days. Concurrency serializes matching source attempts; it is not treated as
durable duplicate prevention by itself. A new explicit calibration dispatch is a
new authorization decision and must respect its own four-call budget.

Sanitized output names include consumer run/attempt to retain rerun suppression
evidence without immutable-artifact name collisions. The gate and provider outputs
record trusted-code and tested-source/fixture revisions separately. Candidate
reservation/reporting behavior has mocked/local and PR fast-test coverage; the
four actual live calls above used the existing merged implementation.

The [independent v1 review](https://github.com/xormania/xorchestrate/blob/cfa3549490ee9db1c3e6cad918523cd854902e51/experiments/jev_failure_correlation/INDEPENDENT_REVIEW.md)
and [v2 methodology review](https://github.com/xormania/xorchestrate/blob/cfa3549490ee9db1c3e6cad918523cd854902e51/experiments/jev_failure_correlation_v2/reviews/methodology-review.md)
from [xorchestrate PR 7](https://github.com/xormania/xorchestrate/pull/7) were
inspected. They report that confident wrong answers and misleading detection
credit remain possible; selection agreement alone does not prove probe utility,
and the structured comparator resolved cases that Jev did not. This PoC keeps
deterministic checks authoritative, requires an actual target assertion for
reproduction credit, retains setup failures separately, and makes no usefulness,
production calibration, cost-effectiveness or live-execution claim from mocks.
