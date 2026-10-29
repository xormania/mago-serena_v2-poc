# Mago LSP extension configuration and reference

The default Docker build includes this repository's Mago external-analyzer patch
and Serena graph-query patch. With explicit workspace configuration, the server
runs the wiring worker during native LSP analysis and exposes dependency graph
results through Serena. The ordinary workspace configuration still uses native
PHP analysis until enrichment is selected.

Use [setup](GETTING-STARTED.md) and [agent connection](AGENT-CLIENTS.md) first.
This page documents the experimental interface, opt-in configuration, lifecycle,
and retained validation. The upstream base is pinned in
[the toolchain lock](../toolchain.lock.json); `mago-baseline` preserves the
unpatched comparison executable. The graph interface is a repository extension,
not an established upstream API.

## Recorded integration checks

| Claim | Observation |
| --- | --- |
| Workers start and complete | Real PHP worker startup, supported hooks and final CLI/LSP observer output |
| Contributions enter current server analysis | Native `mago/symbolReferences` responses change under off/on, unsaved-source and real exported binding controls |
| Serena exposes a contribution | Fourteen agent-selected REPL cells (15 MCP tool calls) through Serena's REPL return the candidate's graph and verify off/on, changed and restored bindings |

A startup marker or completion attestation alone proves only the first claim.
The CLI observer reads Mago's final graph; LSP protocol responses establish the
second claim. The [adaptive transcript and result](evidence/lsp-extensions/agent/result.json)
establish the third without substituting a scripted replay.

## Build inputs and recorded identities

| Component | Identity |
| --- | --- |
| Upstream Mago base | `46df50c96d93d0ac3655c116c375574277cf0b30`, executable version `1.58.2` |
| Mago patch SHA-256 | `ca955e0db6023a997fe708d46d3bd0b92e6dd91237aee7c206f13768effdea11` |
| Recorded patched executable SHA-256 | `5cfaa051b9cb23f63cbcd8ec1703538c1f2789ff21ad068b239678631f701e46` |
| Recorded baseline executable SHA-256 | `78565cd890a50be3b5a12994edd191930a5c16cdf682047dcb20f4f14549a255` |
| Composer Mago SDK | Same exact source revision, package version `1.58.2`, MANA `2.1` |
| Wiring extension | `28c3f54065b71fe046a7474ced401aeadc941b0f`, explicit PHP worker backend |
| Serena base | `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3` |
| Serena REPL patch SHA-256 | `57385a9e49d8a490e696f49b3c62d16e8685703d9531899372a3c41a28270051` |
| Recorded patched Serena facade SHA-256 | `438e52fc79044efa5264e84638190a68a5d5be4ed18f9e2f698f7a49e10d184e` |
| Symfony Demo | `8d2e2ef75c3e18df173d8bf2379a14abb58c4c31`, declared PoC overlay |
| Recorded direct and adaptive investigation image | `sha256:3cc2d1c9f074c1377d103a90d3287a8bb04c7af0e909dd2f0b85b7243cdd7ef1` |

The [Mago patch](../patches/mago-lsp-extensions.patch),
[Serena patch](../patches/serena-symbol-references.patch), Dockerfile and
[toolchain lock](../toolchain.lock.json) make the build reproducible. The Docker
build applies the Mago patch to the exact base and verifies that the Cargo lock,
Composer SDK and MANA protocol files are unchanged. Rust is
`1.99.0 (b940084d7 2026-09-28)`; the Cargo lock SHA-256 is
`f5468183e5440ccacff66b06f7b444f15641caf89d9533057a03e4f280a28e1d`.
The patched build stage defaults to two jobs for its additional compilation.
`/usr/local/bin/mago-baseline` retains
the unmodified executable alongside `/usr/local/bin/mago`; build argument
`MAGO_LSP_EXTENSIONS=0` selects the unpatched executable as the primary binary.

Build the patched development image and optional focused native regression
tests with distinct tags:

```sh
export POC_IMAGE=mago-serena-poc:lsp-workers-example
docker build --build-arg MAGO_BUILD_JOBS=2 -t "$POC_IMAGE" .
docker build --target mago-candidate-tests --build-arg MAGO_BUILD_JOBS=2 -t "${POC_IMAGE}-rust-tests" .
docker run --rm "${POC_IMAGE}-rust-tests" cat /mago-native-tests.log
```

The recorded comparison with Mago `1.59.0` / MANA `2.2` used a different
compatibility matrix; it is not a statement about the latest upstream release.
A version string alone cannot distinguish the tested baseline from the patch. Live
backend checks retain the executable hash, patch identities and loaded Serena
facade. The [installed compatibility record](evidence/lsp-extensions/compatibility.json)
checks the actual SDK MANA 2.1 header, package source identities and Mate/Symfony
extension `0.15.0`. [Read-only upstream refs](evidence/lsp-extensions/baseline/upstream-refs.json)
identify the experimental branch at the time of that inspection.

## Effective configuration and opt-in

The ordinary application-root `mago.toml` remains native. Enrichment is explicitly
selected in an owned disposable application's **workspace-root** configuration.
Mago loads a folder's own `mago.*` before a launch-time `--config` fallback; passing
only `--config .mago/wiring.toml` does not override an existing root `mago.toml`.

This precedence exposed a flaw in the earlier launch-config-only propagation
probe: it did not prove matched effective CLI/LSP configuration. Its historical
investigation evidence remains attributed to that run. The corrected probe temporarily
installs a workspace-root config extending the same instrumented worker config,
then restores the original bytes. The [corrected matched baseline](evidence/lsp-extensions/baseline/index.json)
still demonstrates CLI startup/contribution and the unpatched LSP omission.
The independent [minimal real-SDK regression](upstream/lsp-extensions-repro/README.md)
corroborates both baseline and candidate behavior.

After building the image above, use the same exported `POC_IMAGE` in a
dedicated disposable environment:

```sh
./bin/poc up --run lspext-example --no-build
./bin/poc mate-prepare --run lspext-example
cp docs/evidence/lsp-extensions/agent/agent-config-on.toml workspaces/lspext-example/app/mago.toml
# Include the intentional root-config change in fresh prepared state:
./bin/poc mate-prepare --run lspext-example
./bin/serena-mcp --run lspext-example
```

The [reviewed root configuration](evidence/lsp-extensions/agent/agent-config-on.toml)
extends `.mago/wiring.toml`, selects one PHP worker and watches the compiled
reference and extension entrypoint. Its worker command sets
`POC_WIRING_OBSERVATION=/evidence/agent-observer.json`, required by this PoC's
included debug observer. That artifact is separate from the agent's server
response. Intentional configuration/source changes can require preparation
refresh before another freshness-guarded CLI read.

## Native lifecycle and freshness

The workspace loader attaches the existing native `ExternalAnalyzerHandle` to
its `PluginRegistry` before initial analysis. Initialization stubs enter the
in-memory database before the analysis service's baseline is constructed, as in
the CLI pipeline. The existing incremental service executes supported scan,
before-analysis and after-analysis hooks and consumes their real contributions.
It does not run the enriched CLI behind the LSP interface.

One handle belongs to a workspace generation. Open-buffer edits reuse it. The
unsaved-source control changes the constructor owner only in the buffer, records
different disk/buffer hashes and removes the old owner's dependency; restoring
the buffer restores the edge without launching duplicate workers. Native
analysis and worker source requests use the same in-memory database.

The native service replaces analysis results between generations. A failed
analysis invalidates semantic availability. A failed configuration/metadata
rebuild marks the retained workspace as failed, preventing semantic queries from
presenting the previous graph as current. File-local document symbols and
formatting can remain available. The failure control combines an owned worker
kill with deliberately malformed reference input so the replacement's next
analysis hook actually fails; restoring valid input and editing the buffer
recovers. A separate missing-worker-command control attributes reload failure to
the external worker and recovers after valid configuration reload.

A successful reload replaces the workspace registry and workers. Disabling and
re-enabling the host removes and restores its contribution. Native shutdown
releases the workers before `exit`; all recorded owned worker PIDs exit. A fresh
server restores the current graph. A second folder containing the same owner
name but a different signature stays isolated from the Symfony folder.
The focused configuration uses a 10-second request timeout, 2-second shutdown
timeout and one worker.

The wiring extension caches its compiled reference at startup. The direct proof
changes a real Symfony binding to `App\LspProof\AlternateRegistry`, clears the dev
cache and runs Console plus the package's actual reference exporter. Sending a
watched-file event for the refreshed reference triggers the configured
`restart-on` full workspace reload; the new target replaces the previous target.
Restoring and re-exporting removes the alternate target and restores Registry.
The adaptive agent uses real `mate-prepare` exports followed by explicit
`s.lsp.restart_language_server()` calls for the same transition.

This establishes export-plus-reload freshness. Source edits do not compile
Symfony metadata automatically, and clients must deliver the relevant watched
notification or explicitly restart. If initial workspace loading fails, the
existing bootstrap can leave that folder unloaded; recovery requires process
restart or removing/re-adding the folder. Recovery without any input/state
change and unlimited transparent worker restarts are not claimed.

## Agent-visible data

The demonstrated contribution is a semantic `body` dependency from
`App\Repository\TagRepository::__construct` to
`Doctrine\Bundle\DoctrineBundle\Registry`. The native `signature` reference to
`Doctrine\Persistence\ManagerRegistry` remains. The direct
`TagsInputType → TagRepository` signature already exists, so Mago suppresses a
redundant body edge there.

Dependency graph edges have no source spans. The candidate therefore exposes a
separate read-only `mago/symbolReferences` request, rather than inventing ordinary
`textDocument/references` locations or runtime call relationships:

```json
{
  "textDocument": {"uri": "file:///app/src/Repository/TagRepository.php"},
  "symbol": "App\\Repository\\TagRepository",
  "member": "__construct"
}
```

The result contains `source: {symbol, member}` and a sorted `references` array of
`{kind, target: {symbol, member}}`. Kinds are `body`, `signature`,
`overridden_member`, `function_like_return`, `property_read` and `property_write`.
An omitted member selects the owner-level origin. The URI selects the workspace;
class/function and known-method keys normalize to Mago's canonical identifiers.
The demonstrated API covers class/function/member graph origins; top-level
case-sensitive constants are unproven. The endpoint reads the completed native
`SymbolReferences`, without parsing PHP or attributing each edge to a plugin. On/off and changed/restored controls
establish this particular effect's extension provenance.

The server advertises `capabilities.experimental.symbolReferencesProvider: true`.
The adapter's `request_symbol_references` forwards the response without a CLI
fallback or result cache. The additive Serena facade exposes this public REPL
method. Import `json` in one cell, then evaluate the final expression in another:

```python
import json
```

```python
json.dumps(s.lsp.get_symbol_references(
    'src/Repository/TagRepository.php',
    r'App\Repository\TagRepository',
    '__construct',
))
```

The [real MCP transcript](evidence/lsp-extensions/agent/mcp.jsonl) includes the
agent's initial failed vendor-path assumption, directory discovery and corrected
query, followed by four true flags: healthy on, extension-off removal,
changed-binding replacement and exact restoration. The original independent
application suite then passes 53 test identities and 120 assertions with source
checksums retained. This is an adaptive investigation, not an autonomous coding
benchmark. Live backend identity validation remains enabled.

## Integration check and recorded results

```sh
.venv/bin/python tests/integration/lsp_extensions.py --fresh
```

This creates a fresh disposable environment using the selected image and
executes `lsp_extensions_probe.py`, matching CI. It temporarily changes source,
configuration, and compiled bindings, then restores them. To test an existing
prepared disposable environment instead, use `--run RUN`; intentional source or
configuration changes require a prior `mate-prepare` refresh. Both modes verify
resolved Compose image and
actual image ID through the existing installed-source/runtime identity contract,
and verifies real host MCP on/off graph forwarding with the native signature
preserved. This deterministic CI replay is separate from the adaptive session.
It then purges its owned environment even on failure. Bounded evidence remains in
`artifacts/`. The standalone upstream fixture needs only the real SDK autoloader,
PHP and the repository's stdlib LSP helper.

| Control | Observed result |
| --- | --- |
| Corrected matched CLI / baseline LSP | CLI starts/completes worker; LSP serves native symbols with no worker |
| Candidate CLI off/on | Same 35 native diagnostics and exit 1; on adds one completion attestation and the concrete graph edge |
| Native server extension off/on | Registry body edge absent/present; native ManagerRegistry signature preserved |
| Unsaved source / restoration | Old owner has no remaining references; disk differs from transmitted buffer; restoring buffer restores edge without duplicate startup |
| Real changed export / restored export | AlternateRegistry replaces Registry after watched reload; original target returns after restoration |
| Analysis failure / recovery | `-32803` analysis error; valid metadata and a later buffer edit recover |
| Worker-command failure / recovery | Attributed `-32803` reload error; valid configuration reload recovers |
| Disable/re-enable, shutdown/restart, folder isolation | Contributions removed/restored; all owned workers exit before `exit`; independent folder stays separate |
| Adaptive host MCP → Serena → candidate Mago | Fourteen selected REPL cells (15 MCP calls); all four binding/extension outcome flags true |
| Focused native Rust tests | Four pass, including unsaved graph, disabled analysis and failed-reload recovery |
| Original semantic acceptance and slices 1/2 | Original 31/31 checks; slice 1 9/9; slice 2 12/12, including original 53/120 and combined 55/124 PHPUnit results; final native-plus-MCP gate passes and purges its run |

The [broad acceptance summary](evidence/lsp-extensions/acceptance/summary.json)
records each actual run image. The [native result and index](evidence/lsp-extensions/native/index.json) retain
all 19 direct controls, exact configuration, complete LSP frames and CLI JSON,
with explicitly labelled 64-KiB stderr tails and original full-file digests.
The [minimal regression evidence](evidence/lsp-extensions/minimal/index.json)
separately proves real SDK startup and custom graph off/on behavior.

The [independent diagnostic comparison](evidence/lsp-extensions/diagnostic-comparison.json)
hashes complete sorted Issue objects: baseline CLI and candidate off/on have the
same 35 native diagnostics across 46 source/test files. Enabled reports have 36
total issues including the real completion attestation; disabled has 35. The
historical 30-native-diagnostic/34-source-file record has a different scope and
remains unchanged. Native findings remain findings; no diagnostic is manufactured
or suppressed to make enrichment pass. The separate historical external-span
defect remains attributed to its original
source and reproduction; this patch does not claim to repair it.

## Historical integration context

The retained direct and adaptive results use image `3cc2d1c9…`. Their
[acceptance evidence](evidence/lsp-extensions/acceptance/summary.json) identifies
the exact executable, image, and source revisions. The runtime-diagnosis and LSP
work were developed independently before their combined validation below;
references to an unmerged runtime branch in older reports describe that point
in development, not the current feature set.

The committed evidence indexes bound and hash the published review snapshots.
Some original full acceptance artifacts were retained only in the developer's
local checkout; those private paths are not prerequisites for building this
repository or using its integration checks.

## Recorded combined runtime and LSP validation

After runtime PR #5 merged, commit
`7d7369cc87c64b3bd8d2d95749375f8954646c58` reconciled the then-default branch
`73d7bb8886b8127d930a45252f4fd5d8c855e47d` with the LSP candidate. The workflow
retains both `slice3` and `lsp_extensions`, and the image-selection contract
retains run ownership and the default for an empty `POC_IMAGE`.

The [combined validation](evidence/lsp-extensions/integration/validation.json)
passes from a clean checkout on image
`sha256:7549c48b6259b12eb9698fb860560da6573a2233f61e3155ff880e988eafc7d6`:
178 fast tests, all 31 original acceptance checks, slices 1/2/3 at 9/12/14
stages, and all 19 native LSP controls plus real host MCP/Serena on/off
forwarding. Each gate verifies the selected image independently. The original
53 tests / 120 assertions remain preserved; slice 2 reports 55 / 124 and
slice 3 reports 54 / 135 combined. Native findings and the expected-negative
external-span control retain their existing interpretation.

The [bounded manifest](evidence/lsp-extensions/integration/manifest.json)
binds the retained gate results, image identities, JUnit and host forwarding
records. This is deterministic combined acceptance; the earlier adaptive
investigations remain separate evidence. Hosted CI results belong to PR #6
and are reported independently from these local gate durations.
