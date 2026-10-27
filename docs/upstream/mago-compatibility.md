# Draft compatibility report: Mago LSP through Serena on Symfony Demo

The experimental `next-server` at `46df50c96d93d0ac3655c116c375574277cf0b30`
works through Serena `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3` with a small
external adapter. Official Symfony Demo `8d2e2ef75c3e18df173d8bf2379a14abb58c4c31`
supplies the real application and original tests. This is downstream integration
evidence, not a claim that Mago is a built-in supported Serena backend.

Real stdio MCP/REPL acceptance checks Demo repository/controller symbols and
independently derived source coordinates, the exact caller, Doctrine vendor
definitions, interface/inheritance implementations, semantic rename and re-query,
invalid collision refusal, exact body edits, non-BMP/newline positions, push
diagnostics and clearing, server restart/death and separate workspaces. The
renamed application runs the original full PHPUnit identities, not merely a
count threshold. The whole app manifest detects unrelated modifications.

The adapter translates codepoints↔UTF-16 and replaces SolidLSP ranged edits with
the full contents Mago advertised. Versioned documentChanges are validated; closed
documents may carry null versions. Normal edits work; hostile stale edit versions,
alternate changes form, cancellation, completion/hover/hierarchies/formatting and
code actions have not all been separately exercised live.

One direct Mago limitation is confirmed: external edits that change declaration
byte offsets can leave cross-file spans stale and make rename refuse. See the
[independent reproduction and healthy restart control](mago-external-spans.md).
That limitation accompanies this positive report. The fixed closed-file cache
fault belongs to our adapter. No model or Jev output establishes these facts.

Reproduce with `POC_TRACE=1 ./bin/poc test` after building the pinned image.
[Validation identities and exact results](../evidence/strengthening/validation.json),
[capabilities](../CAPABILITIES.md) and the [ledger](../UPSTREAM-CONTRIBUTIONS.md)
link all relevant artifacts. The original model-driven run is historical;
its rerun status is reported separately from deterministic MCP execution.

Suggested use: share this report in the experimental language-server PR2555,
then discuss which tiny cases belong in native integration tests. No upstream
submission or broader backend support commitment has been made.
