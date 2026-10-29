# Development opportunities

The maintained [workflow guide](WORKFLOWS.md), [capabilities](CAPABILITIES.md),
and [coverage inventory](RUNTIME-COVERAGE.md) describe implemented functionality.
The original [implementation plan](IMPLEMENTATION-PLAN.md) and numbered
[service](SLICE-1.md), [command](SLICE-2.md), and [request-repair](SLICE-3.md)
reports are historical records, not setup instructions or a queue of pending work.

## Areas for future evaluation

These are known opportunities identified by the retained investigations. They
are not commitments to implement particular features or restrictions on using
the available tools.

| Area | Opportunity and existing reference |
| --- | --- |
| Upstream integration | Evaluate the repository patches against newer compatible Mago/Serena revisions using the [extension reference](MAGO-LSP-EXTENSIONS.md) and [contribution records](UPSTREAM-CONTRIBUTIONS.md). Preserve matched executable/SDK/protocol identities. |
| Semantic source tooling | Investigate the [external-declaration span defect](FINDINGS.md), wider completion/signature-help access, and currently unexercised edit/version/cancellation cases in [capabilities](CAPABILITIES.md). |
| Broader Symfony tasks | Add task evidence for migrations, form/security authoring, resource repair, and browser interactions as useful work arises. The [coverage inventory](RUNTIME-COVERAGE.md) identifies what existing exercises establish. |
| Agent clients and verification | Extend configuration and transcript support where needed, preserving the distinction between client connectivity, native execution records, and independent task verification. See [agent clients](AGENT-CLIENTS.md). |
| Runtime diagnosis | Evaluate additional requests, collectors, logging arrangements, and environment failures beyond the recorded tag-filter repair, with observations correlated to the actual request. |

Any new dependency or upstream comparison needs a deliberately selected compatible
configuration. Historical version comparisons describe their recorded inputs;
they do not identify the latest available upstream release. New evaluations
should retain their own configuration, outputs, and limitations.
