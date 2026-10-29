# Getting started

This environment runs Symfony Demo and PHP development tools in one Docker
service. Host scripts create editable workspaces and retain results. You can
use it without a model account or completing the included exercises.

## Requirements

Install Git, a host Python 3 interpreter, [uv](https://docs.astral.sh/uv/getting-started/installation/),
Node.js, and Docker Engine/Desktop with Compose v2. Docker must be running and
accessible to your user. Node is used by the fast tests for the repository's
Actions helper. The fast suite also reaches Docker CLI discovery in mocked
command paths, although it does not start containers. The locked host environment selects Python 3.12.12; CI uses
uv 0.12.8 and the Actions Node 24 runtime. `uv sync` can provision the selected
Python if necessary.

The launchers use POSIX user/group IDs, executable scripts, and bind mounts.
Ubuntu is the hosted test platform. On Windows, run inside WSL2 with Docker
integration. macOS provides the POSIX interfaces, but a separate macOS acceptance
run is not retained here. Native Windows Python is not a supported launcher
path. PHP, Composer, Mago, and Serena run in the image; host PHP and Rust are
not required.

The first image build compiles Rust and needs several GB of memory and disk;
allow several minutes. Network access is needed for image registries, GitHub,
PyPI, crates.io, Packagist, and the Demo's importmap/Sass downloads.

## Build and start

```sh
git clone https://github.com/xormania/mago-serena_v2-poc.git
cd mago-serena_v2-poc
uv sync --frozen --python 3.12.12
./bin/poc fast
./bin/poc up
./bin/poc doctor
```

`up` builds `mago-serena-poc:local`, creates `dev`, installs application
packages, initializes dev/test SQLite databases, and waits for HTTP readiness.
Open <http://localhost:8000/en/blog/>. Build/setup logs are in
`artifacts/dev/build.log` and `artifacts/dev/setup.log`.
The [fixture README](../app/README.md) describes the Demo's features and
upstream usage.

## Edit and inspect

| Host location | Container location | Purpose |
| --- | --- | --- |
| `app/` | Copied on creation | Checked-in fixture input; preserve it |
| `workspaces/dev/app/` | `/app` | Editable app, dependencies, caches, databases |
| `workspaces/dev/state/` | `/state` | Serena process/session state |
| `workspaces/dev/trusted/` | `/trusted`, read-only | Baselines created by task/acceptance preparation |
| `artifacts/dev/` | `/evidence` | Logs, reports, and retained output |

```sh
./bin/poc exec --run dev -- php vendor/bin/phpunit
./bin/poc mago --run dev -- analyze --reporting-format json
./bin/poc mate-prepare --run dev
./bin/mate --run dev -- tools:list --format=json
```

Mago reports existing fixture findings with native exit 1. See
[Workflows](WORKFLOWS.md) for lint, fixes, formatting, service-aware analysis,
and runtime inspection; see [Agent clients](AGENT-CLIENTS.md) for MCP setup.

## Reuse an image or select a workspace

After building the image, create a separate workspace without rebuilding:

```sh
./bin/poc up --run inspect --no-build
./bin/poc doctor --run inspect
```

Custom runs receive an automatically assigned HTTP host port. Read
`workspaces/inspect/run.json` for the Compose project name, then run
`docker compose -p <project-name> port php 8000`, substituting that name.
The default `dev` run uses port 8000.

`POC_IMAGE` selects an image when a run is created. Its choice is saved in
`run.json`; later conflicting overrides are rejected. Build the selected image
before commands that reuse it and keep the tag consistent throughout a scenario.
See [configuration reference](COMMANDS.md#workspace-and-image-configuration).

**Every `up`, including `up --no-build`, reruns setup.** It replaces dev/test
databases and `.env.local`, keeping existing application source. Save data,
local settings, and relevant runtime observations before repeating it.
Image-installed adapter/test changes require a rebuild.

## Stop and discard

```sh
./bin/poc down --run dev
```

This stops and removes the selected Compose service, keeping files and results.
After saving edits and data elsewhere, delete its disposable workspace with:

```sh
./bin/poc down --run dev --purge
```

This also removes dependencies, databases, and state; `artifacts/dev/` remains.
Cleanup targets a validated checkout-owned run, preserving unrelated services
and Docker caches.

## Proxy certificates

For a proxy requiring an additional CA, supply a combined public CA bundle:

```sh
docker buildx build --secret id=proxy_ca,src=/absolute/path/to/ca-bundle.pem \
  --load -t mago-serena-poc:local .
./bin/poc up --no-build
```

The secret is mounted only for source/dependency steps that request it. The
base-image package-install step may also need system trust if its mirror uses
that proxy. Host dependency installation needs appropriate host CA trust.
Keep TLS verification enabled. See [Troubleshooting](TROUBLESHOOTING.md).
