# Serena v2 REPL + experimental Mago LSP

New Symfony work follows the [Mago-first roadmap](docs/ROADMAP.md): Mago owns
PHP analysis, lint, safe fixes and scoped formatting; Serena supplies semantic
navigation and Mate supplies compiled-container facts. Slice 1 investigates the
existing [`TagsInputType` service](docs/SERVICE-SEMANTICS.md). [Slice 2](docs/SLICE-2.md)
generates and verifies `app:tags:count` in a disposable task workspace. The
original rename/application acceptance below remains independently runnable.

```sh
./bin/poc slice1                         # Fresh combined service proof, then cleanup
./bin/poc up --run inspect --no-build
./bin/poc mago --run inspect -- analyze --reporting-format json
./bin/poc quality --run inspect          # Native exits/findings retained; may be nonclean
./bin/poc mate-prepare --run inspect     # Locked overlay + explicit dev metadata refresh
./bin/poc mago-enriched --run inspect --symbol 'App\Form\Type\TagsInputType' -- analyze --reporting-format json
./bin/mate --run inspect -- tools:list --format=json
./bin/serena-mcp --run inspect            # MCP stdio for this exact workspace
./bin/poc down --run inspect
./bin/poc slice2                        # Fresh Maker/task replay and behavior/wiring proof
```

Run the initial `./bin/poc up` below to build the image before `slice1`.
Host launchers work from another directory and require/select an owned run.
Formatting requires explicit PHP paths. The combined proof passes only when its
PHP, semantics, compiled-wiring and behavioral controls pass; it does not label
the Demo's existing native findings clean. Raw reports and failing attempts are
retained under `artifacts/<run-id>/`. The legacy formatter/analyzer remain an
explicit historical comparison via `poc exec --run <id> --
/opt/poc/docker/check --legacy-comparison`, outside the default workflow.

Enriched CLI analysis requires current prepared Symfony metadata. After editing
source, run `mate-prepare` explicitly before analyzing again. Native diagnostics
and exits remain visible: existing application findings return 1; rejected
preparation returns 3 with a refresh instruction. The CLI extension's graph and
execution evidence are separate from Serena/LSP results. See the exact
[public analysis contract](docs/SYMFONY-WIRING.md) and the
[feature task and adaptive agent evidence](docs/SLICE-2.md).

A pinned Symfony Demo fixture, Docker development service, external SolidLSP
adapter, and acceptance harness proving **MCP → Serena REPL → Mago → PHP source**.

The hardened harness verifies the whole disposable application, exact original
test identities, document state and run-bound evidence. It exercises real
MCP → Serena REPL → Mago without a model. A separate historical Codex run completed
the semantic rename; it has **not been rerun after hardening**. A direct-Mago
external-edit span defect remains documented with a healthy restart control.
See [findings](docs/FINDINGS.md), [capabilities](docs/CAPABILITIES.md), and the
[prioritized contribution ledger](docs/UPSTREAM-CONTRIBUTIONS.md).

Prerequisites: Linux/macOS/WSL with Python 3, Git, Docker Engine or Desktop,
Compose v2, and network access to image registries, GitHub, PyPI, crates.io,
Packagist and the Demo's asset downloads. The initial Rust build takes several
minutes and needs several GB of memory and disk. No model credentials are needed
for automated acceptance.

```sh
uv sync --frozen --python 3.12.12
./bin/poc fast             # Properties, verifier/evidence faults and mocked Jev; no Docker/key
./bin/poc up               # Build, provision fresh dev copy, wait for HTTP
./bin/poc doctor           # Fixture, Docker, toolchain and dependency checks
./bin/poc test             # Two independent baselines + real MCP acceptance
./bin/poc report <run-id>  # Read recorded results; missing checks cannot pass
./bin/poc down             # Stop dev; add --purge to discard its workspace
```

`poc test` repeats fast checks before starting containers and refuses stale
installed code/tool pins. Rebuild after changing the adapter or harness.
`POC_TRACE=1 ./bin/poc test` adds bounded hash/version document-state traces;
MCP/direct-LSP traces are always bounded and disclose truncation. Each invocation
gets its own evidence directory, preserving failed attempts. The known Mago
external-span diagnostic is an expected-negative test paired with a fresh-process
healthy control; its passing check does not claim that feature is fixed.

The Demo is at <http://localhost:8000/en/blog/>. The checked-in `app/` stays
unchanged: the editable dev copy is `workspaces/dev/app`, mapped to container
`/app`. Use `./bin/poc exec -- php vendor/bin/phpunit` for application commands.
`poc up --no-build` reuses the image. `up` resets databases in its selected
disposable workspace; retain edits/evidence before resetting an exercise.

Configure an MCP client with an **absolute** launcher path:

```json
{
  "mcpServers": {
    "serena": {
      "command": "/absolute/path/to/mago-serena_v2-poc/bin/serena-mcp",
      "args": []
    }
  }
}
```

The launcher works from another directory and with spaces in the checkout path.
Call `initial_instructions`, use its session token for `serena_repl`, and obtain
the live contract with `s.info("lsp")`. Only the cell's final expression returns
content. Variables persist within that session. Use the host's
`workspaces/<id>/app/...` paths for native file operations and `/app/...` inside
the container.

`./bin/poc agent-task` prepares a separate app with passing baseline tests and
prints the task, exact MCP configuration and container test command. Save the
authenticated harness's JSONL as `artifacts/<id>/agent-transcript.jsonl`, then run
`./bin/poc verify-agent <id>`. The supplied transcript verifier understands Codex
CLI `--json` events. It independently checks the exact source diff, semantic MCP
tool calls, a fresh semantic query and the original PHPUnit suite. Retain its
evidence, then `./bin/poc down --run <id> --purge` to discard the app. Other
harnesses need an equivalent transcript reader; they must not be called verified
without that evidence.

Results live in `artifacts/<id>/results.json` and `report.txt`, with runtime
identity, PHPUnit JUnit/logs, raw MCP/LSP transcripts, diagnostics, diffs and
failure tracebacks. Statuses are `pass`, `fail`, `blocked`, `not_exercised`.
Every inventory row must be present, unique, current and pass for exit0. Reports
also verify retained artifact hashes, installed code, actual image IDs, runtime
pins, and trusted baseline copies. Original test class/method/dataset/file/line
identities are compared; counts alone do not establish suite execution. Baselines
live outside `/app` and are read-only at `/trusted`. Real model execution is
reported separately and absent from deterministic CI.

`.github/workflows/poc.yml` runs fast checks before the image build and uploads
diagnostics on success and failure. The separate default-branch Jev consumer is
advisory, receives the TypeSafe key only in its diagnosis step, and never executes
artifact contents or suggested probes. Local tests use mocked provider responses.
The consumer is now registered on merged default `master`. Its four-call hosted
calibration produced one accepted diagnosis, two abstentions and one strictly
rejected duplicate-reference response. See [live Jev evidence and boundaries](docs/JEV.md)
and [CI cache/scheduling measurements](docs/CI.md). Unmerged diagnostic changes
remain separate from the trusted code actually used by those calls.

See [architecture](docs/ARCHITECTURE.md), the standalone [fixture contract](docs/FIXTURE-CONTRACT.md),
[provenance and licenses](docs/PROVENANCE.md), and [the implementation plan](docs/IMPLEMENTATION-PLAN.md).
`toolchain.lock.json`, `uv.lock`, and the original Composer/Cargo locks identify
the inputs. The experimental Mago version string alone is insufficient.

For a proxy requiring an extra CA, pass the combined public CA bundle using
`docker buildx build --secret id=proxy_ca,src=/path/to/bundle --load -t mago-serena-poc:local .`.
The CA is mounted only for networked source/dependency steps. Configure system
trust in the base-image package-install step if your package mirror requires
that CA too. Host credentials and the Docker socket are not mounted into the
development service.
