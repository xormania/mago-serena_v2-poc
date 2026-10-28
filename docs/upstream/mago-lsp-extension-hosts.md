# Draft: native LSP external analyzer lifecycle and dependency graph

Prepared locally only; nothing posted upstream.

The omission below is the retained unpatched-base reproduction. A native
candidate correction is now being prepared; its design and pending validation
are recorded separately in [Mago LSP extensions](../MAGO-LSP-EXTENSIONS.md).
Historical evidence is not a candidate result.

## Tested identities

- Mago experimental source `46df50c96d93d0ac3655c116c375574277cf0b30`, executable reports `mago 1.58.2`.
- Composer `carthage-software/mago` SDK `1.58.2` distributed from that same source SHA, not a broad constraint resolved to 1.59.
- `byte-kitsune/mago-symfony-wiring` source `28c3f54065b71fe046a7474ced401aeadc941b0f`, PHP worker backend; its native-backend candidates are outside this reproduction.
- Symfony Demo `8d2e2ef75c3e18df173d8bf2379a14abb58c4c31` with the declared development overlay and healthy dev compiled-container export.

## Reproduction

Prepare a selected slice workspace, then run:

```sh
.venv/bin/python tests/integration/service_semantics.py --run <run-id> --extension-propagation
```

The bounded probe inherits `/app/.mago/wiring.toml` and changes only the external
host launch command to prepend a small Python marker wrapper. The wrapper
records worker startup and executes the original command without modifying
its arguments or environment. Both CLI and LSP use that same inherited
configuration and `/app` workspace. The source and compiled reference remain
unchanged.

1. CLI `analyze --reporting-format json` starts the worker, creates the final
   graph observation, and returns the extension's
   `byte-kitsune/symfony-wiring/analysis-attestation` with `complete: true`.
   Native application findings make the CLI exit 1, independently of successful
   extension execution.
2. `language-server` initializes and returns the selected service's document
   symbols. No worker-start marker or final-graph observation is created.

Expected: honor configured external analyzer hosts, or explicitly report that
this experimental server does not support them. Actual: normal native analysis
and navigation silently proceed without starting those hosts.

## Attribution and bounds

At the tested source, `src/language_server/workspace/loading.rs:89` calls
`create_registry_with_plugins` for native plugins. The LSP path has no
`initialize_external_analyzer` or `start_external_analyzer` call, while
`src/commands/analyze.rs` initializes those hosts. Thus this is a server
integration omission at a named experimental pin. It does not establish a
universal Mago extension limitation, a worker-protocol incompatibility, or a
Serena adapter failure. No Mago Rust patch or binary update was made in this
slice. Adding external lifecycle support to the server also needs incremental
reanalysis and failure-handling tests, so it was not replaced with an adapter
that fabricates enriched answers.

At that baseline, the CLI framework bridge is the workaround. Its cost
is separate CLI inspection for enriched graph information; that information
cannot be assumed available in semantic editor queries. Existing full-sync
and stale-external-span findings remain separately attributed to their
original reproductions.

## Candidate correction (validation pending)

The candidate attaches Mago's existing `ExternalAnalyzerHandle` to the
workspace's `PluginRegistry` before initial analysis. The native incremental
analysis service then executes supported external hooks against its in-memory
database and consumes real contributions. Worker pools belong to one workspace
generation and are released on replacement/removal and shutdown. No enriched
CLI runs behind the server interface.

The concrete Symfony `body` dependency has no source span, so it cannot become
a faithful ordinary LSP reference location. The candidate adds a read-only
`mago/symbolReferences` request returning current native dependency edges and
their kinds, with no fabricated positions, runtime calls or edge provenance.
Serena exposes that supported response through a Mago backend method and an
additive patch to its pinned REPL API.

Compiled wiring references are worker-startup state. A valid refreshed export
requires a full workspace reload or server restart; the PoC uses existing
`restart-on` watched paths for the metadata/configuration. Clients must send the
relevant watched-file event or explicitly restart. A failed semantic analysis
or failed reload refuses graph queries instead of presenting old enriched
results as current. Initial workspace load failure retains the existing narrower
recovery contract: process restart or remove/re-add the workspace.

The exact upstream base remains `46df50c96d93d0ac3655c116c375574277cf0b30`,
executable/SDK `1.58.2`, MANA `2.1`; the patch does not change SDK/protocol files.
Candidate patch/build hashes, focused Rust results, direct worker controls,
adaptive host MCP/Serena result and original semantic/slice acceptance are
**pending**. See the dedicated document for the three separate claims and
required controls. Nothing in this section claims an upstream fix was accepted
or repairs the separate historical external-span defect.

## Retained evidence

- [Result and matched identities](../evidence/slice1/semantic-propagation-result.json)
- [Actual generated probe](../evidence/slice1/semantic-propagation-probe.py)
- [Instrumented configuration](../evidence/slice1/semantic-propagation-instrumented.toml) and [launch wrapper](../evidence/slice1/semantic-propagation-worker-launch.py)
- [CLI worker-start marker](../evidence/slice1/semantic-propagation-cli-worker-starts.txt), [observer graph](../evidence/slice1/semantic-propagation-cli-observation.json), and [full report](../evidence/slice1/semantic-propagation-cli-report.json)
- [LSP frames](../evidence/slice1/semantic-propagation-lsp.jsonl) and [server log](../evidence/slice1/semantic-propagation-lsp.stderr)

All snapshots are indexed with hashes in
[the semantic evidence index](../evidence/slice1/semantic-evidence-index.json).
Absence of an output file alone is not the argument: the working CLI control,
separate worker-start instrumentation, successful LSP requests and pinned
server source distinguish the layers.
