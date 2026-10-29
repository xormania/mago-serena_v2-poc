# Symfony development with Mago, Serena, and AI Mate

A reproducible Docker environment for exploring PHP source, inspecting Symfony
services, and diagnosing requests with coding agents. It includes a pinned
Symfony Demo application, Mago's PHP tools, Serena's semantic Model Context
Protocol (MCP) server, AI Mate inspection tools, and independent checks.

Use it for development in a disposable application or for reproducing the
included coding exercises. The integration is experimental: the image includes
repository patches to Mago and Serena. See [capabilities](docs/CAPABILITIES.md)
for supported paths and the scope of their verification.

## Get started

Install Git, a host Python 3 interpreter, [uv](https://docs.astral.sh/uv/getting-started/installation/),
Node.js for fast tests, and Docker with Compose v2. Host launchers use POSIX user
and group IDs; use Linux or a Linux environment such as WSL2. Hosted acceptance
runs on Ubuntu. See [setup requirements](docs/GETTING-STARTED.md) for platform,
network, and proxy details.

```sh
git clone https://github.com/xormania/mago-serena_v2-poc.git
cd mago-serena_v2-poc
uv sync --frozen --python 3.12.12
./bin/poc fast
./bin/poc up
./bin/poc doctor
```

The first build compiles Rust software and downloads dependencies; allow several
minutes and several GB of memory and disk. No model account or API key is needed
for setup and deterministic checks. Open <http://localhost:8000/en/blog/>.

Edit `workspaces/dev/app/`, mounted at `/app` in the container. The checked-in
`app/` directory is fixture input. **Every `up` invocation runs setup again,
replacing the workspace's dev/test databases and `.env.local`.** Save data and
local settings before repeating it.

## Use the tools

```sh
./bin/poc mago --run dev -- analyze --reporting-format json
./bin/poc exec --run dev -- php vendor/bin/phpunit
./bin/poc mate-prepare --run dev
./bin/mate --run dev -- tools:list --format=json
```

Mago retains native findings and exits; the fixture has existing analysis/lint
findings, so analysis can exit 1 while producing a valid report. See
[daily workflows](docs/WORKFLOWS.md) for lint, fixes, scoped formatting,
service-aware analysis, profiler/log inspection, and request repair.

Connect an agent using [`bin/serena-mcp`](docs/AGENT-CLIENTS.md), an absolute
launcher path, and the selected run ID. Model, reasoning, and permission settings
belong to your native client. The transcript verifier currently reads Codex
JSONL for the rename exercise; client connection and task verification have
separate support requirements.

## Checks and exercises

Build the image with `up` before container-based checks.

| Purpose | Command |
| --- | --- |
| Fast properties, verifier faults, and mocked provider tests | `./bin/poc fast` |
| Original application and real MCP/LSP integration without a model | `./bin/poc test` |
| Analyze a PHP service with Symfony wiring and behavior checks | `./bin/poc slice1` |
| Generate and verify a Symfony console command | `./bin/poc slice2` |
| Diagnose and repair a failed HTTP request | `./bin/poc slice3` |

The numbered command names identify existing exercises; users can select them
independently. See [testing and results](docs/TESTING.md) for the LSP extension
checks, output locations, and differences between replays and agent sessions.

```sh
./bin/poc down --run dev          # Stop the service; retain files.
# After saving edits and data elsewhere:
./bin/poc down --run dev --purge  # Delete the workspace; retain artifacts/dev/.
```

## Documentation

- [Documentation index](docs/index.md), [Getting started](docs/GETTING-STARTED.md), and [Troubleshooting](docs/TROUBLESHOOTING.md).
- [Commands and configuration](docs/COMMANDS.md), [Workflows](docs/WORKFLOWS.md), and [Agent clients](docs/AGENT-CLIENTS.md).
- [Capabilities](docs/CAPABILITIES.md), [Symfony coverage](docs/RUNTIME-COVERAGE.md), and [Architecture](docs/ARCHITECTURE.md).
- [Contributing](docs/CONTRIBUTING.md), [CI](docs/CI.md), and [Sources and licenses](docs/PROVENANCE.md).

The default build contains a patched Mago LSP; Symfony extension contributions
still require explicit workspace configuration. The [extension reference](docs/MAGO-LSP-EXTENSIONS.md)
describes opt-in and baseline differences. A known external-edit span defect
has a reproduced failure and restart workaround. Passing its expected-failure
check does not establish that the defect is fixed.
