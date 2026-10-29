### Jev advisory

Status: **nothing_to_diagnose**; transport: **live**; provider requests: 0.
Source verdict and check statuses are independent of this advisory.

## CI performance (advisory)

[Producer run 40810928800 / attempt 1](https://github.com/xormania/mago-serena_v2-poc/actions/runs/40810928800/attempts/1) · pull_request · refs/pull/7/merge

Tested source: `0ec6a393dbbf6e437f2759da7c5e87129bf7d6a8`; workflow head: `db0f44ae4cc092cf3be3c5b2399e786edb310aae`.
Runner: {"arch": "X64", "class": "ubuntu-latest", "environment": "github-hosted", "image": "ubuntu24", "image_version": "20261026.354.1", "os": "Linux"}; platform: linux/amd64.

| Phase / attempt | Native status | Duration |
| --- | --- | --- |
| dependencies / 1 | pass | 1.894s |
| fast / 1 | pass | 4.945s |
| build / 1 | pass | 43.331s |
| acceptance / 1 | pass | 95.877s |
| slice1 / 1 | pass | 110.567s |
| slice2 / 1 | pass | 66.693s |
| slice3 / 1 | pass | 74.209s |
| lsp_extensions / 1 | pass | 65.128s |

Captured wall span: 471.379s; sum of recorded command durations: 462.644s.
Full job wall / queue / setup / cleanup: unavailable / unavailable / unavailable / unavailable.

| BuildKit work | Outcome | RUN/layer duration | Compile RUN duration |
| --- | --- | --- | --- |
| baseline | cached | unavailable | unavailable |
| candidate | cached | unavailable | unavailable |
| import | success | 0.400s | unavailable |
| export | success | 6.100s | unavailable |

Cached-layer download/extraction durations are not compilation; import success does not prove layer reuse.
Compile fingerprint: `1fab14170542b0e3875d61159781e8bf4b26c7858ab87ce1e50d4db7067c26f0`.
Mago source pin, patch bytes, compile-stage Docker instructions/base, effective ARGs and platform; excludes docs, runtime/test stages, repository SHA and timestamps.
Effective compile inputs: {"build_args": {"MAGO_BUILD_JOBS": "2", "MAGO_LSP_EXTENSIONS": "1", "MAGO_REV": "46df50c96d93d0ac3655c116c375574277cf0b30"}, "coverage": "Mago source pin, patch bytes, compile-stage Docker instructions/base, effective ARGs and platform; excludes docs, runtime/test stages, repository SHA and timestamps.", "docker_compile_instructions_sha256": "1e9116bfa387c0a80fe96ab5fd5e6b5e35e7d5fc89b3373f22be1faa7cb48ff0", "patch_sha256": "ca955e0db6023a997fe708d46d3bd0b92e6dd91237aee7c206f13768effdea11", "platform": "linux/amd64", "rust_base": "rust:1.99.0-bookworm@sha256:114c7a4425406451c2866b6aafe69fe29b1b298832db1277d411ac73c82d04d6"}.
Gate inventory: {"definitions_sha256": "7e6225c68db0edfc75b2c8230fe5f853a9cf9234d6766e9db9bf5c968eabf64e", "gates": [{"expected_checks": 31, "id": "acceptance"}, {"expected_checks": 9, "id": "slice1"}, {"expected_checks": 12, "id": "slice2"}, {"expected_checks": 14, "id": "slice3"}, {"expected_checks": 19, "id": "lsp_extensions"}]}.

**Deterministic classification:** warm_reuse, insufficient_evidence.
Comparison compatibility: unavailable/incomparable; missing_baseline.

Jev performance eligibility: **no**. No supported actionable performance signal; zero performance provider requests are needed.
A single comparison is an observation, not a statistical performance guarantee. Native acceptance results are independent.

**Missing evidence / limits:**
- No bounded, identified prior observation is available.

<details><summary>Bounded BuildKit evidence</summary>

**performance.build.baseline**

<pre>#30 [mago 4/4] RUN --mount=type=cache,target=/usr/local/cargo/registry     --mount=type=cache,target=/src/target     --mount=type=secret,id=proxy_ca     if [ -s /run/secrets/proxy_ca ] [...] #30 CACHED</pre>

**performance.build.candidate**

<pre>#46 [mago-candidate 2/3] RUN --mount=type=cache,target=/usr/local/cargo/registry     --mount=type=cache,target=/src/target     --mount=type=secret,id=proxy_ca     cp /mago /mago-baseli [...] #46 CACHED</pre>

**performance.build.import**

<pre>#15 importing cache manifest from gha:4124431879427473276 #15 DONE 0.4s</pre>

**performance.build.export**

<pre>#60 exporting to GitHub Actions Cache #60 DONE 6.1s</pre>

</details>


Jev did not run: no failed/blocked check or supported actionable performance signal.
