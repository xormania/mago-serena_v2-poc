# Mago-first Symfony development

Revision 4, 28 October 2026. This roadmap supersedes the original
[implementation handoff](IMPLEMENTATION-PLAN.md) for new work. The original
fixture, semantic rename evidence, CI caching and trusted Jev workflow remain.
The slice-3 runtime work starts from merged PR #4 at
`88abf50d747f0e2f02905bb23d3701c18d00b2c5`. Runtime diagnosis and the parallel
LSP worker workstream use separate Git worktrees, image tags and disposable
applications/databases/state. The runtime proof uses the existing enriched CLI.

| Slice | Intended proof | Scope |
| --- | --- | --- |
| 1: understand and analyze | Explain `App\Form\Type\TagsInputType` through Mago checks and Serena semantics, enriched with compiled Symfony wiring | Implemented: native PHP/semantics and CLI wiring pass; LSP worker propagation blocked. See [evidence/adoption](SLICE-1.md) |
| 2: generate and change | Use installed Maker to create `app:tags:count`, semantically edit it, run Mago and verify execution and tests | Implemented: fresh adaptive agent and exact-image replay pass; CLI wiring demonstrated, existing LSP boundary retained. See [task and evidence](SLICE-2.md) |
| 3: diagnose and repair | Correlate one failing request with Mate runtime evidence, inspect and repair through Mago, verify a fresh request and regression test | Implemented: adaptive real-request diagnosis and semantic repair; deterministic acceptance is separately recorded in [slice 3](SLICE-3.md). The [coverage inventory](RUNTIME-COVERAGE.md) separates exercised and remaining workflows. |

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

The ordinary public CLI bridge is `./bin/poc mago-enriched --run <run>
--symbol '<class>' -- analyze --reporting-format json`. It requires explicit
`mate-prepare` after source/dependency changes and retains native findings and
exits with extension/graph evidence. The native `mago` command remains available
for comparison. Slice 2 declares only its new command and test as task changes;
original fixture integrity, original suite identities and existing semantic
acceptance remain independent gates. A scripted replay does not establish a
fresh adaptive agent run.

Slice 3 separates historical profiler/log reads from compiled-service freshness.
Runtime evidence remains readable during stale-source and boot-failure controls;
compiled service inspection and enriched analysis still require explicit
preparation. The selected tag-filter task restores the existing controller and
declares one new regression test. This request path does not establish complete
Symfony development coverage: migrations, new forms/security, browser behavior
and broader environment repair remain follow-on work.

Keep exact executable/source/SDK/extension identities together. Stable 1.59.0
uses a different worker protocol from the experimental 1.58.2 pin. Do not update
one side silently. Historical full-sync and stale-span findings remain
attributable to their original tested pins; restart is a recovery, not a fix.

Upstream opportunities belong in the [contribution ledger](UPSTREAM-CONTRIBUTIONS.md)
with small reproductions, controls, source identities and workaround costs.
Prepare drafts only. No upstream messages, merge, new paid calibration or
local TypeSafe key is required for this work.
