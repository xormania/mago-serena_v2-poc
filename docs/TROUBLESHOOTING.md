# Troubleshooting

Start with the affected run ID and its `artifacts/<id>/` directory. Preserve
source changes, databases, profiler records, and logs before resetting an
application. A failed check's detailed output is more useful than its final
summary alone.

| Symptom | Inspect | Supported response |
| --- | --- | --- |
| Docker CLI missing or daemon inaccessible | `docker info`, `docker compose version` | Install/start Docker and Compose v2; give the invoking user access. Host launchers require POSIX user/group APIs. |
| `fast` asks for a virtual environment | Host `.venv/`, `uv sync` output | Run `uv sync --frozen --python 3.12.12`; Node must also be on PATH for Actions helper tests. |
| Image unavailable with `--no-build` | Selected run's `run.json`; `artifacts/<id>/build.log` | Build that exact image. Use a consistent tag, or create a new workspace for a different image. |
| `POC_IMAGE differs from the selected run image` | Saved `image` field in `workspaces/<id>/run.json` | Restore the saved selection or use a new run ID; do not silently retarget the existing run. |
| Installed code inventory differs | `executed-identity.stderr`, image and source records | Rebuild the image from the checkout containing the adapter/tests/config being exercised. |
| Unknown run or ownership mismatch | Run spelling and `workspaces/<id>/run.json` | Select a run belonging to this checkout. Use `up` or `agent-task` to create a new owned workspace. |
| Service stopped | `./bin/poc doctor --run <id>` | After preserving data/settings, restart using `up --run <id> --no-build`; it reruns setup and resets databases and `.env.local`. |
| HTTP readiness timeout | `artifacts/<id>/setup.log`, Compose logs | Diagnose the first dependency, setup, database, or boot error. Check the selected host port rather than assuming every run uses 8000. |
| MCP client cannot initialize | Client stderr, absolute launcher path, selected service/run | Follow [Agent clients](AGENT-CLIENTS.md); run the launcher with `--help`, then check service readiness. MCP stdout must contain protocol data only. |
| Native analysis/lint exits 1 | Retained Mago report | Existing fixture findings are expected; inspect findings and compare the relevant baseline. Exit 1 alone does not mean the launcher failed. |
| Symfony-enriched analysis rejected as stale | Preparation report and wrapper message | Preserve failed-request observations, then explicitly run `mate-prepare --run <id>` and retry. Source/dependency changes invalidate compiled facts. |
| Workers installed but no enriched LSP dependencies | Workspace-root `mago.*`, effective extension configuration, prepared metadata | Use [Mago LSP extensions](MAGO-LSP-EXTENSIONS.md). A root configuration takes precedence over launch-time fallback; the patched binary alone does not enable workers. |
| Closed external edit gives stale ranges or rename error | Exact source changes and protocol trace | Re-query symbols; for the documented byte-length-changing declaration defect, restart the server and query again. Restart is a workaround for the tested pin. |
| Missing profiler token | Actual HTTP headers/status, application logs | A failure before profiling begins may have no token. Preserve earlier recorded profiles; do not associate an unrelated newest profile with this request. |
| `verify-agent` rejects a transcript | `agent-verification.log`, original native JSONL | Check Codex event format and required semantic operations for the rename task. Connectivity alone does not establish parser support or task correctness. |
| Acceptance report rejects missing/stale artifacts | `results.json`, `run-plan.json`, metadata, original artifact directories | Retain complete outputs, including the companion run; investigate mismatch rather than editing result records to pass. |

## Inspect the selected service

Read its Compose project name from `workspaces/<id>/run.json`. Substitute that
name in the following commands:

```sh
docker compose -p <project-name> logs --no-color php
docker compose -p <project-name> port php 8000
```

Use these from the repository root so Compose reads `compose.yaml`. Logs and
published-port inspection use the existing project's labels. Public launchers
supply the correct bind paths and configuration when executing commands.

## Preserve runtime observations before refresh

Mate's recorded profiler and log reads can remain available after edits or a
failed application boot. They describe recorded requests, not current health.
Compiled service inspection and Symfony-enriched Mago analysis require fresh
metadata. A refresh may clear profiler/cache state; capture the failed response,
its token, relevant profile collectors, and matching log records first. See
[Workflows](WORKFLOWS.md).

## Build and network failures

Read the first failed step in `build.log` or `setup.log`. Builds need registry,
source, Composer, Python, Rust, and asset downloads. Corporate proxies may need
separate host and build CA trust; see [Getting started](GETTING-STARTED.md#proxy-certificates).
Do not disable TLS verification. An expected cold compile can be much slower than
a cache hit; [CI](CI.md) explains how to read measured timings without assuming a
regression from incomparable runs.
