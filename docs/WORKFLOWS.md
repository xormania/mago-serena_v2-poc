# Development workflows

Use this guide after [Getting started](GETTING-STARTED.md). Examples assume the `dev` workspace is running; replace `dev` consistently with another workspace ID when needed. Edit its host application at `workspaces/dev/app/`. Keep the checked-in `app/` fixture intact.

## Analyze and format PHP

Mago provides PHP analysis, linting, supported fixes, formatting, structural checks and syntax-tree inspection. Native checks analyze `src/` and `tests/`, using installed `vendor/` declarations as context.

```sh
./bin/mago --run dev -- analyze --reporting-format json
./bin/mago --run dev -- lint --reporting-format json
./bin/mago --run dev -- format --check src/Form/Type/TagsInputType.php
./bin/mago --run dev -- guard --structural --reporting-format json
./bin/mago --run dev -- cst --json --names src/Form/Type/TagsInputType.php
```

The fixture has existing analysis/lint findings. Exit `1` and a diagnostic report are different from failure to execute a tool. Native stdout/stderr, invocation, tool identity and exit are retained under `artifacts/dev/mago/invocations/`.

To apply formatting or fixes, name the intended PHP files explicitly, then inspect the changes:

```sh
./bin/mago --run dev -- format src/Form/Type/TagsInputType.php
./bin/mago --run dev -- lint --fix src/Form/Type/TagsInputType.php
./bin/mago --run dev -- format --check src/Form/Type/TagsInputType.php
./bin/poc exec --run dev -- php vendor/bin/phpunit
```

Fix availability depends on the reported rule. A fix command can complete without changing a finding that has no applicable fix. The wrapper rejects directories and implicit source scopes for writing commands. `./bin/poc quality --run dev` records analysis, lint, structural checks and a formatting check of the selected form service; it does not format the entire application. PHPStan and PHP-CS-Fixer are optional historical comparisons through `/opt/poc/docker/check --legacy-comparison`, outside the default PHP workflow.

## Navigate and edit semantically

[Connect an agent client](AGENT-CLIENTS.md) to `bin/serena-mcp` for the selected workspace. Serena's Model Context Protocol (MCP) server exposes its persistent Python REPL; the registered Mago adapter supplies Language Server Protocol (LSP) operations.

Call `initial_instructions`, retain the returned session token and use it for `serena_repl`. In that session, request the current facade contract with this cell:

```python
s.info("lsp")
```

Then discover symbols and references before modifying source. For example:

```python
s.lsp.find_symbol("PostRepository/findLatest", relative_path="src/Repository/PostRepository.php", include_body=True)
```

```python
s.lsp.find_referencing_symbols("PostRepository/findLatest", "src/Repository/PostRepository.php")
```

Use the actual returned contract for rename and editing operations. Only the cell's final expression returns tool content; variables persist within that REPL session. Requery after a mutation because retained symbol objects can contain old source text. Check the resulting diff and application tests independently. Known semantic defects and recovery limits are described in [Troubleshooting](TROUBLESHOOTING.md) and the [capability reference](CAPABILITIES.md).

The agent's native filesystem tools see `workspaces/dev/app/...`; container commands see `/app/...`. The REPL runs with the container process's privileges. Its API and read-only flags guide the agent; they do not create an operating-system security boundary.

## Inspect Symfony services and runtime data

AI Mate and the Symfony/Monolog extensions are installed through the declared development overlay. Preparation also compiles dev metadata, exports a container reference and writes selected-workspace instructions:

```sh
./bin/poc mate-prepare --run dev
./bin/mate --run dev -- tools:list --format=json
./bin/mate --run dev -- tools:inspect symfony-service-detail --format=json
./bin/mate --run dev -- tools:call symfony-service-detail \
  --id='App\Repository\TagRepository' --context=inspection-dev --format=json
```

`mate-prepare` installs the locked overlay into this disposable application, may replace only recognized original/overlay Composer files, and clears the dev cache. It archives bounded existing profiles/logs before clearing. Preserve relevant failed-request observations before intentionally refreshing. Edits to source, dependencies or compiled metadata invalidate compiled inspection and enriched analysis; repeat preparation explicitly when those facts need to be current.

For an ordinary Console view of the same application:

```sh
./bin/poc exec --run dev -- php bin/console debug:container 'App\Repository\TagRepository' --env=dev
./bin/poc exec --run dev -- php bin/console debug:router --env=dev
```

### Analyze with compiled Symfony wiring

After preparation, use the Symfony analysis profile:

```sh
./bin/mago --run dev --profile symfony \
  --symbol 'App\Repository\TagRepository' -- analyze --reporting-format json
```

The equivalent main entry point is `./bin/poc mago-enriched --run dev --symbol 'App\Repository\TagRepository' -- analyze --reporting-format json`. `--extension-off` supplies an explicit comparison without the wiring contribution. Native findings remain visible; inspect `artifacts/dev/mago/enriched/` for invocation, raw reports and graph observations. Exit `3` denotes rejected preparation or incomplete execution evidence, rather than a clean analysis result.

The standard image includes repository patches to Mago and Serena. This CLI profile selects its prepared wiring configuration explicitly. LSP enrichment requires a separate workspace-root configuration opt-in; follow [LSP extension configuration](MAGO-LSP-EXTENSIONS.md#effective-configuration-and-opt-in). Installing a patched executable alone does not enable the extension for every request.

### Diagnose a request with profiler data and logs

First make the request to the selected application's host URL and retain its URL, request time and response headers. The `dev` application is at `http://localhost:8000/en/blog/`. Use a unique query marker to distinguish your request from readiness checks. Read the exact response's `X-Debug-Token` header; do not select a profile merely because it is newest.

Inspect installed schemas before choosing additional parameters:

```sh
./bin/mate --run dev -- tools:inspect symfony-profiler-list --format=json
./bin/mate --run dev -- tools:inspect monolog-search --format=json
```

In the following examples, replace `REQUEST_MARKER` with your actual marker and `HEX6` with the actual six-character hexadecimal response token:

```sh
./bin/mate --run dev -- tools:call symfony-profiler-list \
  --context=inspection-dev --url=REQUEST_MARKER --limit=20 --format=json
./bin/mate --run dev -- tools:call symfony-profiler-get --token=HEX6 --format=json
./bin/mate --run dev -- resources:read symfony-profiler://profile/HEX6/exception --format=json
./bin/mate --run dev -- resources:read symfony-profiler://profile/HEX6/db --format=json
./bin/mate --run dev -- tools:call monolog-search \
  --term=REQUEST_MARKER --environment=dev --kernelContext=inspection-dev --limit=20 --format=json
./bin/mate --run dev -- tools:call server-info --format=json
```

Choose collectors actually present in that profile; a successful request may have no exception collector. Profiler records describe their recorded request. Monolog records include time, level, channel and structured context; correlate marker, exception and time. A boot failure can occur before profiling starts and yield no token. `server-info` describes Mate's own CLI PHP process, not the HTTP request's process.

Exact supported runtime reads remain available after a source edit or application boot failure, provided their selected-container runtime identity is valid. They do not silently refresh compiled state. Use exact command/tool names, `inspection-dev`, and limits from 1 to 100; Monolog reads also require `--environment=dev`. Unknown/abbreviated commands retain the compiled-freshness check. Raw output and the wrapper's observation metadata are retained under `artifacts/dev/mate/invocations/`.

## Generate a feature or investigate a repair

To discover installed Maker commands and their help:

```sh
./bin/poc exec --run dev -- php bin/console list make
./bin/poc exec --run dev -- php bin/console help make:command
```

Generation changes the editable application. Review generated code, apply the appropriate Mago checks and run the relevant behavior tests. The repository also provides reproducible exercises in fresh disposable applications:

| Goal | Command | Recorded example |
| --- | --- | --- |
| Inspect a form service, PHP diagnostics and compiled Symfony wiring | `./bin/poc slice1` | [Service analysis report](SLICE-1.md) |
| Generate and semantically edit a tag-count Console command | `./bin/poc slice2` | [Feature-generation report](SLICE-2.md) |
| Diagnose an HTTP failure through profiler/log data and repair its source | `./bin/poc slice3` | [Request-repair report](SLICE-3.md) |

These commands are scripted exercises with independent checks. Their retained agent-session evidence is separate from the new replay. Each selects a fresh ID by default, uses the existing selected image, and normally stops its container while retaining the workspace and results. To inspect the resulting application, choose an unused ID and keep it running:

```sh
./bin/poc slice3 --run request-repair-example --keep-running
```

Read its attempt reports in `artifacts/request-repair-example/slice3/`. When finished, preserve any desired edits and run `./bin/poc down --run request-repair-example --purge`. Preparing an exercise is not evidence of complete Symfony workflow coverage; see [Runtime coverage](RUNTIME-COVERAGE.md) for the demonstrated scope.

For a new authenticated semantic rename exercise, use `./bin/poc agent-task` and follow [Agent clients](AGENT-CLIENTS.md#verify-an-agent-driven-rename). For general checks and reporting, see [Testing and results](TESTING.md).
