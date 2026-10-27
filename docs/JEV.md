# Advisory Jev diagnosis

This iteration implements a credential-free CI producer and a separate trusted
consumer. Local diagnosis and boundary tests use deterministic fixtures and
mocked responses. **No live TypeSafe request or live calibration has been run
for this iteration.** Workflow wiring is implemented; hosted activation and
provider behavior remain pending.

## Local validation

```sh
./bin/poc fast
# Just the provider/collector/security-boundary cases:
python3 -m unittest discover -s tests/fast -p test_jev.py -v
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

GitHub must have this consumer and its trusted tools on the **default branch**
before `workflow_run` can activate it. This branch alone does not activate the
consumer. Manual calibration is also restricted to the default branch. The
existing repository secret suffices for the supplied workflow; repository-secret
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

Four typed choice questions return a failure-layer hypothesis, up to two
supporting supplied excerpt IDs, and one next probe from supplied options.
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

With no failed/blocked observation, normal CI writes `nothing_to_diagnose`
without a request, even when a key exists. Missing keys produce
`missing_credentials`. Jev cannot change source check results, suppress required
tests, approve a run, or execute its proposed probe. Consumer failure affects
only the advisory consumer and never changes the producing workflow's verdict.

## Explicit calibration, pending live execution

After default-branch activation, manually dispatch **Jev advisory diagnosis** on
the default branch with `calibration: true`. This is an explicit bounded mode:
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

The [independent v1 review](https://github.com/xormania/xorchestrate/blob/cfa3549490ee9db1c3e6cad918523cd854902e51/experiments/jev_failure_correlation/INDEPENDENT_REVIEW.md)
and [v2 methodology review](https://github.com/xormania/xorchestrate/blob/cfa3549490ee9db1c3e6cad918523cd854902e51/experiments/jev_failure_correlation_v2/reviews/methodology-review.md)
from [xorchestrate PR 7](https://github.com/xormania/xorchestrate/pull/7) were
inspected. They report that confident wrong answers and misleading detection
credit remain possible; selection agreement alone does not prove probe utility,
and the structured comparator resolved cases that Jev did not. This PoC keeps
deterministic checks authoritative, requires an actual target assertion for
reproduction credit, retains setup failures separately, and makes no usefulness,
production calibration, cost-effectiveness or live-execution claim from mocks.
