# Mago-first Symfony development

Revision 2, 27 October 2026. This roadmap supersedes the original
[implementation handoff](IMPLEMENTATION-PLAN.md) for new work. The original
fixture, semantic rename evidence, CI caching and trusted Jev workflow remain.
The starting branch is the existing `feat/mate-service-inspection`, based on
merged PR #2 at `e0a11fdf6e8bbc4c2e0e16840da0c62f5bb6913e`.

| Slice | Intended proof | Scope |
| --- | --- | --- |
| 1: understand and analyze | Explain `App\Form\Type\TagsInputType` through Mago checks and Serena semantics, enriched with compiled Symfony wiring | Implemented: native PHP/semantics and CLI wiring pass; LSP worker propagation blocked. See [evidence/adoption](SLICE-1.md) |
| 2: generate and change | Use installed Maker to create one command, semantically edit it, run Mago and verify execution and tests | Planned; no implementation in slice 1 |
| 3: diagnose and repair | Correlate one failing request with Mate runtime evidence, inspect and repair through Mago, verify a fresh request and regression test | Planned; no implementation in slice 1 |

Mago owns PHP analysis, lint, applicable fixes and formatting. Serena's actual
REPL/Mago path supplies source navigation. Mate supplies compiled framework
facts; the existing `Byte-Kitsune/mago-symfony-wiring` extension must be attempted
through Mago's supported worker APIs. PHPUnit and Symfony validation retain
their behavioral and runtime roles. PHPStan/PHP-CS-Fixer are historical
comparisons rather than duplicate default checks.

Slice 1 requires healthy, defective and restored controls, actual source and
dependency coverage, explicit PHP target, retained raw diagnostics and process
exits, formatter stability, and active extension evidence. Installation or a
zero analysis exit does not establish a framework contribution. A blocked
bridge leaves the combined result incomplete even when PHP controls pass.
CLI extension contribution and LSP/Serena propagation are separate claims.

Keep exact executable/source/SDK/extension identities together. Stable 1.59.0
uses a different worker protocol from the experimental 1.58.2 pin. Do not update
one side silently. Historical full-sync and stale-span findings remain
attributable to their original tested pins; restart is a recovery, not a fix.

Upstream opportunities belong in the [contribution ledger](UPSTREAM-CONTRIBUTIONS.md)
with small reproductions, controls, source identities and workaround costs.
Prepare drafts only. No upstream messages, merge, new paid calibration or
local TypeSafe key is required for this work.
