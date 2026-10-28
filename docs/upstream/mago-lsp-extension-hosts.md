# Draft: native LSP external analyzer lifecycle and dependency graph

Prepared locally only; nothing posted upstream. This contains a native candidate
and real regression evidence on experimental Mago
`46df50c96d93d0ac3655c116c375574277cf0b30`. Full identities, opt-in configuration,
results and remaining limits are in [Mago LSP extensions](../MAGO-LSP-EXTENSIONS.md).

## Baseline and a corrected matched reproduction

The baseline executable reports `1.58.2`; its Composer SDK comes from the same
source SHA and uses MANA `2.1`. The Symfony wiring package is
`28c3f54065b71fe046a7474ced401aeadc941b0f`, using its explicit PHP backend, on the
PoC's declared Symfony Demo `8d2e2ef75c3e18df173d8bf2379a14abb58c4c31` overlay.

Prepare an owned disposable slice workspace, then run the corrected probe on
the unpatched executable:

```sh
.venv/bin/python tests/integration/service_semantics.py --run <run-id> --extension-propagation
```

The worker marker wrapper records startup, then executes the configured PHP
worker unchanged. The probe selects the same instrumented configuration at the
workspace root for CLI and LSP and restores the original configuration bytes.
This matters because a workspace's `mago.toml` overrides launch-time `--config`.
The earlier slice-1 launch-config-only probe did not establish matched effective
LSP configuration. Those historical artifacts are preserved below; the current
[corrected rerun](../evidence/lsp-extensions/baseline/index.json) independently
establishes the boundary:

1. CLI `analyze --reporting-format json` starts the worker, runs the final graph
   observer and returns the package's complete 46-file analysis attestation.
   Ordinary native application findings produce exit 1.
2. Unpatched LSP initializes and returns native service document symbols without
   starting the configured worker or completing the observer.

At that base, `src/language_server/workspace/loading.rs` creates the native
plugin registry without initializing external analyzers, while the CLI does
initialize them. This is a named-source integration omission. It does not imply
an SDK incompatibility or a Serena adapter startup fault.

The [minimal upstream regression](lsp-extensions-repro/README.md) removes Symfony
and the PoC adapter. A real SDK test plugin adds an explicitly declared test Body
edge and observes the final native graph. Both CLI variants pass; unpatched LSP
has no worker startup, while candidate LSP starts/completes the worker and returns
the test edge only when enabled. Its [retained results and frames](../evidence/lsp-extensions/minimal/index.json)
separately corroborate the matched fixture result.

## Candidate implementation and native data interface

The [source patch](../../patches/mago-lsp-extensions.patch) attaches the existing
`ExternalAnalyzerHandle` to the workspace's `PluginRegistry` before analysis and
loads external initialization stubs before constructing the analysis baseline.
The existing incremental service executes supported hooks against the current
in-memory file database and consumes their real contributions. Worker pools
belong to workspace generations and drop on replacement/removal and shutdown;
no enriched CLI runs behind the server interface.

The concrete Symfony constructor dependency has no source span. The candidate
adds a separate read-only `mago/symbolReferences` request returning actual
`{source, references: [{kind, target}]}` graph data. It does not fabricate ordinary
LSP reference locations, measured calls or per-edge provider attribution.
Class/function/member origins are the intended API scope; top-level
case-sensitive constants remain unproven. A
[small additive Serena REPL patch](../../patches/serena-symbol-references.patch)
and Mago adapter forwarding expose that supported server data as
`s.lsp.get_symbol_references(relative_path, symbol, member)`.

The exact source base, SDK `1.58.2` and MANA `2.1` remain unchanged. Mago patch
SHA-256 is `ca955e0db6023a997fe708d46d3bd0b92e6dd91237aee7c206f13768effdea11`;
executable SHA-256 is
`5cfaa051b9cb23f63cbcd8ec1703538c1f2789ff21ad068b239678631f701e46`.
The PoC Docker build retains the runnable unpatched binary and records both
identities, compiler, lock and applied patch. Stable `1.59.0`/MANA `2.2` is not
an interchangeable SDK/backend input.

## Proven behavior and freshness limits

[Four focused native Rust tests and 19 real-worker/direct controls](../evidence/lsp-extensions/native/index.json)
pass. Unsaved source removes/replaces the old graph contribution without changing
disk bytes or starting duplicate workers. A real changed Symfony service binding
and fresh package export replace Registry with AlternateRegistry after a watched
reference reload; a restored export removes the alternate edge. Extension
analysis failures and broken worker commands refuse stale graph queries and
recover after supported edits/reloads. Disable/re-enable, shutdown before exit,
restart and independent folder isolation pass.

The [real adaptive host MCP investigation](../evidence/lsp-extensions/agent/result.json)
uses 15 agent-selected Serena REPL calls. Healthy on, extension-off removal,
real exported changed binding and exact restoration all pass; the original
53 test identities and 120 assertions subsequently pass. This evidence is
separate from deterministic acceptance replay. Broad semantic acceptance and
slices 1/2 pass on their recorded image; final gate-strengthening results are
linked by the dedicated document.

Compiled references are worker-startup state. Refreshing an export requires a
full workspace reload through configured `restart-on` watched paths, or explicit
server restart. The direct proof sends the watched event; the adaptive agent
uses `mate-prepare` and explicit Serena restart. Source edits do not automatically
recompile Symfony metadata. Failed analysis/reload refuses old semantic data;
initial workspace load failure retains a narrower recovery contract of process
restart or removing/re-adding the folder. File-local native operations can remain
available while semantic analysis is invalid.

The [complete native Issue comparison](../evidence/lsp-extensions/diagnostic-comparison.json)
retains identical 35-Issue sets for baseline CLI and candidate off/on across 46
source/test files; enabled reports add one real completion note. The historical
30-native-diagnostic/34-source-file record remains unchanged. The [compatibility
record](../evidence/lsp-extensions/compatibility.json) checks installed source
identities and the actual MANA 2.1 SDK header. This patch neither suppresses
findings nor repairs the separately attributed historical external-span defect.

## Historical evidence (before the configuration correction)

These snapshots retain the original slice's tested identities and observations.
Their launch-config-only LSP invocation is not the current matched control:

- [Original result](../evidence/slice1/semantic-propagation-result.json) and [generated probe](../evidence/slice1/semantic-propagation-probe.py)
- [Instrumented config](../evidence/slice1/semantic-propagation-instrumented.toml), [wrapper](../evidence/slice1/semantic-propagation-worker-launch.py), [CLI starts](../evidence/slice1/semantic-propagation-cli-worker-starts.txt)
- [CLI graph](../evidence/slice1/semantic-propagation-cli-observation.json), [CLI report](../evidence/slice1/semantic-propagation-cli-report.json), [LSP frames](../evidence/slice1/semantic-propagation-lsp.jsonl), [stderr](../evidence/slice1/semantic-propagation-lsp.stderr)

Their [original hash index](../evidence/slice1/semantic-evidence-index.json) remains
unchanged. The corrected rerun, minimal SDK regression and native source establish
the worker omission without relying on that earlier harness assumption.
