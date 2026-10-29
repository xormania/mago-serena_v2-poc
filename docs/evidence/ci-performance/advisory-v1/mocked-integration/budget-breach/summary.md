### Jev advisory

Status: **diagnosed**; transport: **mock**; provider requests: 1.
Source verdict and check statuses are independent of this advisory.

## CI performance (advisory)

[Producer run 123 / attempt 2](https://github.com/xormania/mago-serena_v2-poc/actions/runs/123/attempts/2) · pull_request · refs/pull/7/merge

Tested source: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`; workflow head: `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.
Runner: {"arch": "X64", "class": "ubuntu-latest", "environment": "github-hosted", "image": "ubuntu24", "image_version": "synthetic-fixed-image", "os": "Linux"}; platform: linux/amd64.

| Phase / attempt | Native status | Duration |
| --- | --- | --- |
| dependencies / 1 | pass | 60.000s |
| fast / 1 | pass | 60.000s |
| build / 1 | pass | 1000.000s |
| acceptance / 1 | pass | 60.000s |
| slice1 / 1 | pass | 60.000s |
| slice2 / 1 | pass | 60.000s |
| slice3 / 1 | pass | 60.000s |
| lsp_extensions / 1 | pass | 60.000s |

Captured wall span: 1200.000s; sum of recorded command durations: 1420.000s.
Full job wall / queue / setup / cleanup: unavailable / unavailable / unavailable / unavailable.

| BuildKit work | Outcome | RUN/layer duration | Compile RUN duration |
| --- | --- | --- | --- |
| baseline | cached | unavailable | unavailable |
| candidate | executed | 570.700s | 570.700s |
| import | success | 0.800s | unavailable |
| export | success | 5.500s | unavailable |

Cached-layer download/extraction durations are not compilation; import success does not prove layer reuse.
Compile fingerprint: `1fab14170542b0e3875d61159781e8bf4b26c7858ab87ce1e50d4db7067c26f0`.
Mago source pin, patch bytes, compile-stage Docker instructions/base, effective ARGs and platform; excludes docs, runtime/test stages, repository SHA and timestamps.
Effective compile inputs: {"build_args": {"MAGO_BUILD_JOBS": "2", "MAGO_LSP_EXTENSIONS": "1", "MAGO_REV": "46df50c96d93d0ac3655c116c375574277cf0b30"}, "coverage": "Mago source pin, patch bytes, compile-stage Docker instructions/base, effective ARGs and platform; excludes docs, runtime/test stages, repository SHA and timestamps.", "docker_compile_instructions_sha256": "1e9116bfa387c0a80fe96ab5fd5e6b5e35e7d5fc89b3373f22be1faa7cb48ff0", "patch_sha256": "ca955e0db6023a997fe708d46d3bd0b92e6dd91237aee7c206f13768effdea11", "platform": "linux/amd64", "rust_base": "rust:1.99.0-bookworm@sha256:114c7a4425406451c2866b6aafe69fe29b1b298832db1277d411ac73c82d04d6"}.
Gate inventory: {"definitions_sha256": "7e6225c68db0edfc75b2c8230fe5f853a9cf9234d6766e9db9bf5c968eabf64e", "gates": [{"expected_checks": 31, "id": "acceptance"}, {"expected_checks": 9, "id": "slice1"}, {"expected_checks": 12, "id": "slice2"}, {"expected_checks": 14, "id": "slice3"}, {"expected_checks": 19, "id": "lsp_extensions"}]}.

**Deterministic classification:** absolute_budget_breach, insufficient_evidence.
Comparison compatibility: unavailable/incomparable; missing_baseline.

**Advisory signals:**
- build 1000.000s exceeds configured 900.000s advisory budget.

Jev performance eligibility: **yes**. Trusted reservation, credentials and failure-evidence gates still apply; eligibility is not a provider call.
A single comparison is an observation, not a statistical performance guarantee. Native acceptance results are independent.

**Missing evidence / limits:**
- No bounded, identified prior observation is available.

<details><summary>Bounded BuildKit evidence</summary>

**performance.build.baseline**

<pre>#9 [mago 3/3] RUN cargo build --locked --release -j 6 #9 CACHED</pre>

**performance.build.candidate**

<pre>#17 [mago-candidate 3/4] RUN cp /mago /mago-baseline &amp;&amp; cargo build --locked --release -j 2 #17 DONE 570.7s</pre>

**performance.build.import**

<pre>#3 importing cache manifest from gha:sample #3 DONE 0.8s</pre>

**performance.build.export**

<pre>#22 exporting cache to GitHub Actions Cache #22 DONE 5.5s</pre>

</details>


Jev hypothesis: `compilation_cost`; supplied evidence: `performance.metrics`.
Suggested next diagnostic step: `inspect_compile_profile` (not executed).
Jev answered typed questions about the supplied state; it did not independently inspect history or files.
