# Mago LSP external analyzer candidate

This candidate connects configured external analyzer workers to Mago's native
workspace analysis and exposes its semantic dependency graph through Serena's
Mago backend. It is an unpublished source patch on experimental Mago
`46df50c96d93d0ac3655c116c375574277cf0b30`.

**Validation status: pending.** The implementation and proof are being prepared.
The contract below describes the candidate design; no passing candidate run is
claimed by this draft. Candidate patch digest, executable hash, proof commands,
retained evidence and actual results must be filled from the completed runs.

## Three separate claims

| Claim | Required observation |
| --- | --- |
| Workers start and complete | Worker startup/protocol evidence and completed supported hooks |
| Contributions enter current server analysis | A native server graph result changes under independently specified extension/binding/source controls |
| Serena exposes a contribution | A real host MCP request through Serena's REPL and configured Mago backend returns that same server data |

A startup marker or completion attestation proves only the first claim. The
CLI observer reads Mago's final graph, but does not establish an LSP or Serena
result. A graph response must also be fresh after edits and metadata reloads;
retaining an old edge is not successful analysis.

## Matched baseline and candidate

| Component | Identity |
| --- | --- |
| Upstream Mago base | `46df50c96d93d0ac3655c116c375574277cf0b30`, executable version `1.58.2` |
| Composer Mago SDK | Exact same source revision, package version `1.58.2`, MANA `2.1` |
| Wiring extension | `28c3f54065b71fe046a7474ced401aeadc941b0f`, explicit PHP worker backend |
| Serena | `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3` |
| Symfony Demo | `8d2e2ef75c3e18df173d8bf2379a14abb58c4c31`, declared PoC overlay |
| Candidate patch and executable | Pending completed reproducible build |

The candidate leaves the SDK files and worker protocol unchanged. Stable Mago
`1.59.0` / MANA `2.2` is a different compatibility matrix and must not be
substituted for this source/SDK pair. Build provenance must identify the base,
applied patch, compiler, Cargo lock and live executable; a version string alone
cannot distinguish the candidate from the baseline.

The original [CLI/LSP comparison](upstream/mago-lsp-extension-hosts.md) remains
attributed to the unpatched base. There, CLI analysis starts the worker and
observes a concrete Registry dependency, while LSP initialization serves normal
native symbols without starting that worker.

## Native integration and lifecycle

The workspace loader attaches the existing native `ExternalAnalyzerHandle` to
its `PluginRegistry` before initial analysis. The existing incremental analysis
service executes the supported scan, before-analysis and after-analysis hooks
against the workspace's in-memory file database. It consumes the worker's real
contributions alongside native results. It does not run the enriched CLI as an
LSP substitute.

One handle belongs to a workspace generation. Subsequent edits reuse that
handle; they do not start a worker pool for every query or keystroke. Open-buffer
contents enter the same database used for analysis and worker source requests,
so unsaved-content support must be established by different disk/buffer bytes in
the focused proof. A disk-only observation cannot establish that property.

The native service replaces analysis results between generations. A failed
analysis invalidates semantic availability, and semantic requests refuse until
a successful analysis. A failed configuration or metadata rebuild marks the
retained workspace as failed so requests cannot describe its previous graph as
the new configuration. File-local document symbols and formatting can remain
available while semantic analysis is unavailable.

A successful workspace reload creates the new registry/worker state and drops
the previous state. Disabling/re-enabling an extension host or changing its
command takes effect through that reload. Workspace removal and server shutdown
release workspace-owned worker pools; shutdown does this before waiting for
`exit`. Existing worker request and shutdown timeouts bound protocol waits and
cleanup. Their configured values and observed failure/recovery behavior belong
in the retained proof.

Each workspace owns its configuration, database, registry and workers. No shared
service graph is introduced. Independent-workspace controls must establish that
a changed binding or failed worker in one workspace leaves the other result
unchanged.

## Metadata freshness and recovery

The wiring extension loads a compiled Symfony reference at worker startup.
Exporting a new reference does not by itself replace a live worker's cached
facts. A valid refreshed export must be followed by a workspace reload or an
explicit server restart before querying the updated binding.

The PoC candidate uses Mago's existing `[language-server].restart-on` facility
for the wiring reference and worker configuration paths. A watched-file event
for one of those paths schedules a debounced full workspace rebuild. This is a
reload contract, not per-request incremental export discovery. Clients that do
not deliver the relevant watched-file event must explicitly restart the server.
`mate-prepare` remains the trusted host operation for compiling/exporting/sealing
current Symfony facts after intentional source or metadata changes.

A worker failure during an existing analysis makes semantic requests fail;
a later supported edit/save or valid workspace reload may retry. If initial
workspace loading fails, the existing bootstrap can leave that workspace
unloaded. Correcting the configuration then requires a process restart or
removing and re-adding the workspace. There is no claim of unlimited transparent
worker restart or recovery without an input/state change.

## Agent-visible data

The demonstrated wiring contribution is a semantic `body` dependency from
`App\Repository\TagRepository::__construct` to
`Doctrine\Bundle\DoctrineBundle\Registry`. The constructor's native `signature`
reference to `Doctrine\Persistence\ManagerRegistry` remains. The direct
`TagsInputType → TagRepository` relationship already has a native signature
reference, so Mago suppresses a redundant body reference there.

These graph edges have no source spans. They cannot faithfully be returned as
ordinary navigable `textDocument/references` locations, rename edits or runtime
calls. The candidate adds a separate read-only native request,
`mago/symbolReferences`, with this shape:

```json
{
  "textDocument": {"uri": "file:///app/src/Repository/TagRepository.php"},
  "symbol": "App\\Repository\\TagRepository",
  "member": "__construct"
}
```

The response contains `source: {symbol, member}` and a sorted `references` array.
Each reference contains its native `kind` and `target: {symbol, member}`. Kinds
include `body`, `signature`, `overridden_member`, `function_like_return`,
`property_read` and `property_write`. An omitted member selects the symbol-level
origin. The URI selects the owning workspace. The endpoint normalizes class,
function and known method keys and returns Mago's native canonical lowercase
identifiers.

The endpoint reads the server's completed native `SymbolReferences`; it does not
parse PHP, invent edges, infer locations or attribute each edge to a plugin.
Extension provenance is demonstrated by matched off/on and changed/restored
controls. An empty graph result is not evidence of successful extension
execution by itself.

The server advertises `experimental.symbolReferencesProvider: true`. The adapter
forwards the custom response with `request_symbol_references`, without a CLI call
or result cache. A small deterministic patch to the pinned Serena source exposes
that backend method in the public REPL:

```python
s.info('lsp.get_symbol_references')
print(json.dumps(s.lsp.get_symbol_references(
    'src/Repository/TagRepository.php',
    r'App\Repository\TagRepository',
    '__construct',
)))
```

The actual returned bytes are pending the completed proof. The method preserves
live backend identity validation and errors; it does not reconstruct the
dependency from the CLI, compiled reference, source text or an observer artifact.

## Proof and results

The focused host entrypoint is:

```sh
POC_IMAGE=mago-serena-poc:lsp-workers-20261028b \
  .venv/bin/python tests/integration/lsp_extensions.py \
  --run lspext-20261028b-candidate
```

It selects an owned prepared disposable run and launches the in-container
`lsp_extensions_probe.py` helper. Bounded snapshots belong under
`docs/evidence/lsp-extensions/`; the completed evidence index is pending.
For a fresh owned application, metadata and state, the CI gate uses
`--fresh` instead of `--run`. It checks the resolved Compose image and actual
image ID against the selected tag, applies the existing installed-source/runtime
identity contract, and purges its owned environment even on failure. Source,
identity, bounded failure details and probe evidence remain under `artifacts/`.
Required controls are intentionally recorded before results:

| Control | Independent expected result | Candidate result |
| --- | --- | --- |
| Matched CLI / baseline LSP | CLI worker contribution; unpatched LSP omission | Pending rerun |
| Extension disabled / enabled | Concrete Registry body edge absent / present | Pending |
| Changed binding / restored binding | Previous concrete target removed; restored target returns | Pending |
| Unsaved source edit / restoration | Worker observes current buffer bytes; old contribution is removed/replaced | Pending |
| Valid refreshed metadata + reload | New export affects the next completed workspace generation | Pending |
| Worker failure / recovery | Attributed error; no stale successful graph; valid retry recovers | Pending |
| Shutdown / restart | Owned workers exit; fresh server responds with current facts | Pending |
| Independent workspaces | Changed/failing workspace does not contaminate the other | Pending |
| Host MCP → Serena REPL → candidate Mago | Real server graph reaches the adaptive agent | Pending |
| Native semantic acceptance and slices 1/2 | Existing independent assertions and original application test identities pass | Pending |

No Jev live call or new model benchmark is needed. Adaptive agent evidence and
deterministic acceptance replay must be identified separately. Existing native
application diagnostics remain findings with their actual content/exit status;
they are not suppressed to make enriched execution appear clean.

The historical external-span defect remains attributed to its original tested
source. This patch does not claim to repair that separate cause. Any changed
negative-control outcome must be explained by its actual tested response.

## Session A reconciliation

The small shared image-isolation commit selects
`image: ${POC_IMAGE:-mago-serena-poc:local}` and makes the CI build helper honor
the same environment selection. Launchers already forward it. Session B builds
and runs a unique `mago-serena-poc:lsp-workers-*` tag and scopes its mutable runs
to `lspext-*`; it does not retag or stop Session A resources.

Session B owns the Mago source patch, backend graph forwarding, focused proof
and this document. It does not require Session A's Mate runtime tools or Monolog
overlay. Combined-branch validation is pending unless both workstreams are merged
and checked on the actual integrated revision.
