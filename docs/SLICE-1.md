# Recorded PHP service investigation

> **Historical record.** This report describes the original service investigation and its tested inputs. Its blocked external-worker LSP observations concern that experiment; see [current capabilities](CAPABILITIES.md) and [patched LSP configuration](MAGO-LSP-EXTENSIONS.md) for subsequent implementation and opt-in. For routine use, follow [Workflows](WORKFLOWS.md).

## Original report

Mago is the default PHP analysis/lint/fix/format path. The existing
`App\Form\Type\TagsInputType` is explained through real Serena REPL/Mago
queries, calibrated native checks and compiled Symfony wiring consumed by the
existing wiring extension. The application fixture and original semantic rename
remain unchanged. The subsequent command-generation task is described in
[slice 2](SLICE-2.md); request diagnosis and repair are tracked in
[slice 3](SLICE-3.md).

The CLI framework bridge **passes**. External-worker propagation through the
pinned LSP remains **blocked**, with a positive CLI control and a reproduction.
This does not claim complete framework-aware editor navigation or a clean
whole-application native diagnostic report.

## Evidence and service explanation

- [Native PHP controls and classified findings](MAGO-PHP.md), including raw reports,
  enabled rules, effective configuration, coverage, defect restoration and diffs.
- [Actual agent investigation and independent semantic replay](SERVICE-SEMANTICS.md):
  declarations, dependency/vendor definitions, exact caller references and hover;
  direct server probes additionally exercise type/call hierarchies.
- [Compiled framework facts and extension contribution](SYMFONY-WIRING.md):
  matched SDK/package, active execution, off/on/invalid/restored controls and
  stale/absent metadata rejection.
- [Integrated result](evidence/slice1/integrated-result.json),
  [original acceptance](evidence/slice1/original-acceptance.json) and
  [validation index](evidence/slice1/validation.json).

`PostType` selects the tags field at `app/src/Form/PostType.php:69`.
`TagsInputType` extends `AbstractType`, declares readonly `TagRepository $tags`
at `app/src/Form/Type/TagsInputType.php:34`, chains collection/array/string
transformers in `buildForm`, supplies `findAll()` results to the view in
`buildView`, and returns Symfony `TextType::class` from `getParent`.
Mago resolves the inherited repository method into Doctrine vendor source.

Mate's compiled dev metadata confirms that constructor argument `tags` resolves
to service/class `App\Repository\TagRepository`. Its `registry` argument
resolves to service `doctrine`, class
`Doctrine\Bundle\DoctrineBundle\Registry`. Native Console corroborates the
selected bindings. The wiring extension adds a Body reference from
`TagRepository::__construct` to that concrete Registry in Mago's final graph.
The direct form-to-repository reference is already covered by a native Signature
edge and does not change. These are source/compiled dependency facts, not
measured runtime calls or proof that all services are reachable.

The combined overlay run analyzes all **46** source/test hosts with **9,864**
installed vendor PHP files: native trace reports **9,910** compiled source files;
precompiled builtin stubs are enabled separately. The initial **35 analyzer / 125
lint findings** remain visible. The selected service has no analyzer finding and
one existing `strict-types` warning. No broken-variant baseline or blanket
suppression is generated.

## Adoption decisions

| Capability | Actual Mago/extension result and evidence | Legacy tool | Disposition / remaining gap |
| --- | --- | --- | --- |
| PHP analysis | Valid-PHP return defect detected at line 57; complete diagnostic multiset restored; full caller/vendor context | PHPStan | Replacement for this workflow; historical comparison only. Existing findings require source-specific review; universal Symfony/ORM parity is unproven. |
| Lint and fix | Enabled debug rule detects line 52; safe redundant-parentheses fix restores exact healthy source | PHP-CS-Fixer overlap | Replacement. Debug-call removal has no automatic fix and remains explicit. |
| Formatting | Read-only check detects variant; native write restores exact source; second pass stable; original PHPUnit behavior unchanged | PHP-CS-Fixer | Replacement, scoped to named PHP files. No whole-Demo style migration. |
| Semantic inspection | Actual MCP/REPL definitions, caller references, hover and vendor declarations | None retained | Adopted. Type/call hierarchy proved directly, without claiming a dedicated REPL facade. |
| Structure | Native lossless CST and meaningful AbstractType Guard allowed/violating/restored control | None | Adopted for the selected question; no invented architecture policy. |
| Symfony facts inside analysis | Exact-source SDK + pinned wiring package contribute concrete Registry edge off/on; invalid binding removes it | No analyzer fallback | CLI bridge passes. The LSP does not start external workers at this pin; [draft reproduction](upstream/mago-lsp-extension-hosts.md). |
| Runtime/behavior | Mate compiled dev facts, Symfony validators and original PHPUnit identities | PHPUnit / native Console | Retained for distinct framework and behavior contracts. |

## Local commands

```sh
uv sync --frozen --python 3.12.12
docker buildx build --load -t mago-serena-poc:local .
./bin/poc test
./bin/poc slice1 --run slice1-acceptance --keep-running
./bin/poc quality --run slice1-acceptance
./bin/poc exec --run slice1-acceptance -- /opt/poc/docker/check --legacy-comparison
./bin/poc down --run slice1-acceptance
```

`quality` deliberately returns the native findings status **1** on the unchanged
Demo. `slice1` checks calibrated capabilities and binding contribution, retains
that nonclean snapshot, and separately reports blocked LSP propagation. It runs
host semantic checks with the locked `.venv` interpreter. Each slice attempt gets
its own source context, complete prepared-app manifest, raw tool invocations,
reports and PHPUnit identities; rejected requests and failed attempts remain.
Default `slice1` creates a fresh run and stops it; `--keep-running` explicitly
retains the selected workspace. Host commands use an absolute checkout-derived
root and work from another directory.

The original fast suite, 31 required container/semantic/behavior checks, exact
rename and full-sync/stale-span reproductions remain. CI adds the combined slice
after original acceptance without changing caching, scheduling or trusted Jev.
No local TypeSafe key, paid calibration, upstream message or merge is part of
this slice. The current local adaptive investigation demonstrates read-only
agent use, while deterministic acceptance independently asserts the results;
neither establishes a broader autonomous-development benchmark.
