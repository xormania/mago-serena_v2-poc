# Capabilities and limitations

This environment combines Mago PHP tooling, Serena semantic source tools, and
AI Mate's Symfony inspection tools against a pinned Symfony Demo application.
Use [the workflow guide](WORKFLOWS.md) for commands and
[testing and results](TESTING.md) to interpret a run. This page describes the
available paths and the scope of their retained verification.

## Tool and configuration boundaries

The default Docker build applies the repository's Mago external-analyzer patch
and Serena graph-query patch. The upstream Mago base and SDK remain pinned in
[the toolchain lock](../toolchain.lock.json); the image also retains the
unpatched `mago-baseline` executable. A version string alone does not distinguish
these binaries.

Ordinary Mago analysis and the default LSP workspace configuration use native PHP
analysis. Symfony enrichment is an explicit choice: the CLI uses
`mago-enriched` or `bin/mago --profile symfony`, while LSP enrichment requires an
appropriate workspace-root configuration. Both need prepared Symfony metadata.
See [compiled wiring](SYMFONY-WIRING.md) and
[LSP extension configuration](MAGO-LSP-EXTENSIONS.md#effective-configuration-and-opt-in).
The patched graph-query interface is a repository extension, not an upstream API.

## Available paths and verification scope

“Recorded” below means the linked retained run exercised that behavior. It does
not assert a new run on every later documentation revision. A server advertising
a capability, an installed package, and an exercised end-to-end workflow are
different observations.

| Capability | User-facing path | Verification and limits |
| --- | --- | --- |
| PHP analysis, linting, fixes, and formatting | `bin/mago`; `poc mago`; `poc quality` | [PHP checks](MAGO-PHP.md) record full application/test analysis with vendor declarations, introduced/restored defects, scoped fixes, and formatting stability. Existing Demo findings remain visible; no whole-project parity with other analyzers is claimed. |
| Symbols, definitions, references, and inheritance | Serena REPL through Mago LSP | [Semantic acceptance](evidence/strengthening/validation.json) records application/vendor declarations, exact source ranges, callers, and inherited rename behavior. |
| Rename and symbol-body editing | Serena REPL source operations | Recorded semantic acceptance checks exact task changes, fresh queries, and the original application tests. Exact-diff rules belong to their exercise. Re-query symbols after edits; retained symbol objects can contain an old body. |
| Hover and hierarchy | Serena hover; direct LSP hierarchy requests | [Service investigation](SERVICE-SEMANTICS.md) records hover through Serena and direct server call/type hierarchy. Completion, signature help, and dedicated hierarchy facade methods are not established by that exercise. |
| Diagnostics and document updates | LSP notifications and the adapter's full-document synchronization | Recorded controls introduce and remove a type error and check diagnostic clearing. Unicode/UTF-16 and newline coordinate tests establish edit positions; Linux writes normalize CRLF to LF rather than preserve bytes. |
| External edits and restart | Serena/Mago session and process lifecycle | Closed-file replacement, requery, process death, and explicit recovery are exercised. A separate byte-length-changing external-declaration span defect remains in the [known findings](FINDINGS.md). Its expected-failure test does not repair it. |
| Compiled Symfony service inspection | AI Mate service tools; enriched Mago CLI | [Wiring controls](SYMFONY-WIRING.md) record concrete service bindings and graph changes. Source/dependency/metadata changes require explicit preparation refresh. A dependency edge does not establish a runtime call. |
| Symfony graph contributions through LSP | Patched Mago server and Serena `get_symbol_references` | [Extension controls](MAGO-LSP-EXTENSIONS.md) record off/on, changed/restored binding, worker lifecycle, and real MCP forwarding. Enrichment needs workspace opt-in; metadata export plus reload/restart establishes freshness. The unpatched baseline omits external analyzers. |
| Profiler, exception, and log inspection | AI Mate Symfony and Monolog tools | [Request-repair evidence](SLICE-3.md) records exact request correlation, failure investigation, repair, and a fresh response. Historical observations remain readable during stale source or boot failure; they do not establish current application health. |
| Feature generation | Symfony Maker and ordinary source tools | [Command-generation evidence](SLICE-2.md) records one generated command, semantic changes, data-dependent behavior, and independent tests. It does not cover every Maker generator. |
| Workspace and test isolation | Selected disposable application, database, state, and Compose project | Original acceptance checks two independent suites and that cleaning one environment preserves the other. Results retain source/image/run identities and artifact hashes; see [architecture](ARCHITECTURE.md) and [testing](TESTING.md). |
| Agent-driven tasks | Native agent client connected to Serena; task-specific checks | Recorded sessions include the original rename, service investigation, command generation, request repair, and extension investigation. Each has its own revision/configuration and scope. The supplied general `verify-agent` transcript reader specifically understands Codex events for the rename exercise. See [agent clients](AGENT-CLIENTS.md). |

Formatting and code-action support advertised by the LSP is not the same claim
as the tested Mago CLI formatter. Adverse stale WorkspaceEdit versions,
alternate changes-form rename responses, and request cancellation/timeout
exhaustion are not separately established by normal rename success. Defensive
adapter code should not be described as exercised behavior without a matching
control.

## Recorded investigations

| Record | What it establishes |
| --- | --- |
| [Original semantic acceptance](evidence/acceptance-results.json) and [later verification](evidence/strengthening/validation.json) | Separate original and strengthened deterministic MCP/LSP/application runs. The original authenticated rename remains historical; it was not rerun by those deterministic checks. |
| [Service investigation](SLICE-1.md) | PHP tooling, semantic inspection, and compiled CLI wiring at that experiment's pins. Its original unpatched LSP limitation is superseded for the patched, explicitly configured path above. |
| [Command generation](SLICE-2.md) and [request repair](SLICE-3.md) | Distinct adaptive agent sessions and separate scripted replays; their source changes and result counts remain attached to each run. |
| [LSP extension investigation](MAGO-LSP-EXTENSIONS.md) | Matched upstream baseline versus repository patch, direct worker controls, and an adaptive graph investigation. |
| [Advisory CI diagnosis](JEV.md) | Jev's mocked and historical live provider observations, separate from application correctness and native agent execution. |

The [Symfony workflow coverage inventory](RUNTIME-COVERAGE.md) describes wider
framework areas such as migrations, forms/security, and browser behavior.
[Contribution records](UPSTREAM-CONTRIBUTIONS.md) retain revisions, reproductions,
and draft upstream material; they are not additional support guarantees.
