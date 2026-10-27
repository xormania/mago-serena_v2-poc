# Serena v2 REPL + experimental Mago LSP

A pinned Symfony Demo fixture, Docker development service, external SolidLSP
adapter, and acceptance harness proving **MCP → Serena REPL → Mago → PHP source**.

On 2026-10-27 the core matrix passed in Docker. Two independent fresh Demo
workspaces each passed **53 PHPUnit tests / 120 assertions**; the renamed app
passed the same suite. A separate authenticated Codex agent completed the
semantic rename and passed independent verification. See [findings](docs/FINDINGS.md)
and the [capability matrix](docs/CAPABILITIES.md) for evidence and limits.

Prerequisites: Linux/macOS/WSL with Python 3, Git, Docker Engine or Desktop,
Compose v2, and network access to image registries, GitHub, PyPI, crates.io,
Packagist and the Demo's asset downloads. The initial Rust build takes several
minutes and needs several GB of memory and disk. No model credentials are needed
for automated acceptance.

```sh
./bin/poc up               # Build, provision fresh dev copy, wait for HTTP
./bin/poc doctor           # Fixture, Docker, toolchain and dependency checks
./bin/poc test             # Two independent baselines + real MCP acceptance
./bin/poc report <run-id>  # Read recorded results; missing checks cannot pass
./bin/poc down             # Stop dev; add --purge to discard its workspace
```

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
Every required core row must pass for exit 0. Real model execution is reported
separately and is deliberately absent from CI. `.github/workflows/poc.yml` builds
the same pinned image and uploads evidence even after failures.

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
