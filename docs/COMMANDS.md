# Command and configuration reference

Run these commands from the repository root. Host launchers also work from other directories when invoked by absolute path. `./bin/poc --help` and the individual launchers' `--help` show the implemented parser. Start with [Getting started](GETTING-STARTED.md) for installation and [Development workflows](WORKFLOWS.md) for examples.

## Environment commands

| Command | Arguments and defaults | Effect and prerequisites |
| --- | --- | --- |
| `./bin/poc up` | `--run ID` defaults to `dev`; `--no-build` skips building | Creates or selects a workspace, builds its image unless skipped, starts the PHP service, runs application setup and waits for HTTP readiness. **Setup resets that workspace's dev/test databases**, including on repeated `up`. |
| `./bin/poc doctor` | `--run ID` defaults to `dev` | Requires a running selected workspace. Checks checked-in fixture integrity, Docker, selected backend registration, runtime identity and Composer platform requirements. |
| `./bin/poc exec` | `--run ID` defaults to `dev`; `-- COMMAND ARG...` required | Executes the argument array in the running PHP service with working directory `/app`; returns the child command's exit. |
| `./bin/poc down` | `--run ID` defaults to `dev`; optional `--purge` | Stops the selected checkout-owned Compose project. `--purge` also deletes its entire `workspaces/ID/` directory, including edits, dependencies, databases and state. `artifacts/ID/` remains. |

`up --no-build` still runs setup; it is not a resume-without-reset command. Preserve application edits and database contents before repeating setup. `down` without `--purge` preserves the workspace on disk, but a later `up` still resets its known databases. See [Troubleshooting](TROUBLESHOOTING.md) before resetting an environment to diagnose a fault.

## PHP and Symfony inspection commands

| Command | Arguments and defaults | Results |
| --- | --- | --- |
| `./bin/poc mago` | Required `--run ID`; `-- MAGO_COMMAND ARG...` | Runs Mago with fixed selected workspace, native configuration and PHP 8.5 target. Equivalent to `./bin/mago --run ID --profile native -- ...`. |
| `./bin/poc quality` | Required `--run ID` | Runs analysis, lint, structural Guard checks and a formatting check of `TagsInputType.php`. Prints the recorded results; returns the highest command exit. This is not a whole-application formatting check. |
| `./bin/poc mate-prepare` | Required `--run ID` | Installs the locked development overlay and Mate configuration, refreshes discovery, clears dev cache and exports compiled Symfony metadata. Refuses to overwrite edited Composer manifests/locks or incompatible managed configuration. Archives bounded existing logs/profiles first. |
| `./bin/poc mago-enriched` | Required `--run ID`; repeatable `--symbol CLASS`; optional `--extension-off`; `-- analyze ARG...` | Requires fresh explicit Mate preparation. Retains native diagnostics and a graph observation. Default observed classes are `App\Form\Type\TagsInputType` and `App\Repository\TagRepository`; accept one to eight distinct class names. `--extension-off` compares analysis without the wiring contribution. |
| `./bin/mago` | Required `--run ID`; `--profile native` (default) or `--profile symfony`; `-- COMMAND ARG...` | The Symfony profile is equivalent to `poc mago-enriched` and accepts `analyze` only. `--symbol` and `--extension-off` require that profile. |
| `./bin/mate` | Required `--run ID`; `-- MATE_COMMAND ARG...` | Runs installed Mate in the selected dev container. Discovery, exact runtime inspection and compiled inspection have different freshness rules; see [Workflows](WORKFLOWS.md#inspect-symfony-services-and-runtime-data). |
| `./bin/serena-mcp` | `--run ID` defaults to `dev`; remaining arguments pass to Serena | Starts MCP over standard input/output in the selected running container, using Serena's REPL interface. Diagnostics go to stderr. No MCP HTTP endpoint is started. See [Agent clients](AGENT-CLIENTS.md). |

Native Mago accepts `analyze`, `lint`, `format`, `guard`, `cst`, `config`, `list-files`, `extension`, `version` and `help`. The wrapper refuses workspace, configuration and PHP-target overrides. Use `./bin/mago --run ID -- help` or command-specific native help for supported tool options.

Formatting and `lint/analyze --fix` require explicit existing workspace-relative `.php` file targets. Directories, absolute paths, parent paths, symlinks and unscoped fixes are rejected. The generic `fix` command is rejected; use scoped `lint --fix` or `analyze --fix` and inspect the diff. Writing commands also reject options whose argument scope the wrapper cannot validate. These are wrapper constraints, not claims about upstream Mago's interface.

## Checks and exercises

Build the selected image and install the host dependencies first. These commands do not select a model or launch an authenticated coding agent.

| Command | Arguments and defaults | What runs and where results are retained |
| --- | --- | --- |
| `./bin/poc fast` | No arguments | Deterministic properties, verifier and mocked-provider checks using `.venv/bin/python`; no Docker daemon or provider key. |
| `./bin/poc test` | `--run-prefix PREFIX` defaults to `test` | Fast tests followed by two isolated application baselines and real MCP/LSP acceptance, using an existing image. Creates unique run IDs; stops their containers and retains workspaces/evidence. Main result: `artifacts/ID/results.json`, `report.txt`, and a companion `ID-b` directory. |
| `./bin/poc report ID` | Required run ID | Reads the original acceptance result, verifies its required checks, context and artifact hashes, prints statuses and returns success only for a complete pass. This is not the reader for every exercise's nested result format. |
| `./bin/poc slice1` | Optional `--run ID`; `--keep-running` | Exercises PHP checks, semantic service inspection, compiled wiring and behavior. A missing ID creates a fresh unique workspace. |
| `./bin/poc slice2` | Optional `--run ID`; `--keep-running` | Generates and verifies the `app:tags:count` command in a disposable application, including semantic editing and independent behavior checks. |
| `./bin/poc slice3` | Optional `--run ID`; `--keep-running` | Replays failure injection, runtime inspection and repair of a real HTTP request with a regression test. |
| `./bin/poc agent-task` | No arguments | Prepares a unique `agent-*` workspace for the semantic rename task, verifies the baseline suite, and prints its instructions and exact launcher configuration. Leaves the workspace running for the operator's agent session. |
| `./bin/poc verify-agent ID` | Required prepared agent-task run ID | Verifies the task-specific application diff, original test identities, Codex JSONL tool-call transcript and fresh semantic requery. Requires the running selected container and `artifacts/ID/agent-transcript.jsonl`. |
| `.venv/bin/python tests/integration/lsp_extensions.py` | Exactly one of `--fresh` or `--run ID` | Focused native/Serena extension acceptance. `--fresh` prepares, checks and purges its own workspace; `--run` uses an already prepared owned workspace. See [LSP extension reference](MAGO-LSP-EXTENSIONS.md). |

The three `slice*` tokens are existing command names. Their task-oriented descriptions above explain their purpose. They modify disposable applications and retain attempt results beneath `artifacts/ID/sliceN/attempt-UUID/`. By default they stop the selected container and retain workspace files and evidence; `--keep-running` leaves the service running for inspection. Remove a finished workspace explicitly with `down --run ID --purge`. Use an unused ID for each exercise rather than an application containing work you intend to keep.

See [Testing and results](TESTING.md) for which outcomes each check establishes. `verify-agent`'s exact-diff rename policy belongs to that task; it is not a universal contract for application development.

## Workspace and image configuration

A run ID uses lowercase letters, digits and hyphens, starts with a letter or digit, and is at most 80 characters. `workspaces/ID/run.json` records its ownership, paths, Compose project, HTTP port and image selection.

| Setting | Meaning |
| --- | --- |
| `POC_IMAGE` | Image tag selected when a run is first created; defaults to `mago-serena-poc:local`. The selection is persisted. A later conflicting override is refused. Use a new workspace to choose a different image. |
| `POC_DOCKER` | Optional path to a Docker CLI executable. Normal discovery uses `PATH`, then the repository's `.cache/tools/docker/docker` fallback. The fallback also selects its local CLI-plugin directory. |
| `POC_TRACE=1` | Optional bounded adapter state tracing when creating acceptance workspaces. Raw MCP/LSP traces have their own bounds and truncation records. |
| `MAGO_LSP_EXTENSIONS` | Docker **build argument**, default `1`: applies the repository's Mago patch. `0` selects the unpatched executable as primary. This is separate from enabling an extension in workspace configuration. |
| `MAGO_BUILD_JOBS` | Docker build argument for the patched Mago compilation, default `2`. |

The launchers derive Compose mount paths, run/attempt IDs, UID/GID and published port from the run record and current host. They overwrite corresponding Compose environment values; manually setting `POC_APP`, `POC_STATE`, `POC_TRUSTED`, `POC_EVIDENCE_DIR`, `POC_PORT`, `POC_UID` or `POC_GID` is not a launcher configuration interface. The `dev` workspace initially requests localhost port 8000; named workspaces use Docker-assigned ports. Inspect `run.json` for Compose identity and query that project's `docker compose ... port php 8000` when you need its host URL.

| Host path | Container path | Purpose |
| --- | --- | --- |
| `app/` | Not edited by the public workflows | Checked-in fixture input |
| `workspaces/ID/app/` | `/app` | Editable application, dependencies, databases and dev cache |
| `workspaces/ID/state/` | `/state` | Serena/global process state |
| `workspaces/ID/trusted/` | `/trusted`, read-only | Host-owned baseline and preparation records |
| `artifacts/ID/` | `/evidence` | Retained invocations, reports, traces and results |

Native checks use `mago-php.toml`, copied from `fixtures/mago/mago.toml`. The application's root `mago.toml` configures the LSP. Prepared `.mago/wiring.toml` configures enriched CLI analysis; it does not automatically enable enriched LSP analysis. Workspace-root Mago configuration takes precedence over a launch-time config fallback. See the [extension configuration reference](MAGO-LSP-EXTENSIONS.md#effective-configuration-and-opt-in).

## Exits and statuses

A successful setup, check or report exits `0`. Native Mago analysis/lint may return `1` for findings already present in the fixture; the wrapper preserves native stdout, stderr and exit. `quality` can therefore return `1` even when the environment works correctly. Inspect the reports instead of treating every nonzero exit as a startup fault.

`bin/mago`, `bin/mate` and `bin/serena-mcp` use exit `3` for wrapper selection/preparation/runtime errors; parser usage errors use `2`. `poc mago-enriched` also uses `3` for rejected preparation or incomplete extension evidence, retaining a completed native process's exit separately. Other caught `bin/poc` errors exit `1`; child command failures retain their own native exit when returned directly.

Acceptance results use `pass`, `fail`, `blocked` and `not_exercised`. A missing, stale or unexecuted required check cannot produce a successful report. Enriched analysis invocation records distinguish `clean`, `findings`, `stale_preparation` and `tool_failure`; these are analysis states, not the acceptance status vocabulary.
