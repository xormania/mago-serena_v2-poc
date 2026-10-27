# Candidate Mago issue: external disk edits leave cross-file declaration spans stale

Status: prepared locally for xormania to review. No issue or upstream change has
been submitted. This is a direct LSP reproduction, independent of Serena and
the PoC adapter.

## Description

An externally edited, closed file can return a cross-file method declaration
reference at a stale span after `workspace/didChangeWatchedFiles(Changed)`.
Rename then refuses with `-32803`, saying the server index is out of date.
Starting a fresh server over the same edited files returns the correct range
and a valid rename WorkspaceEdit. No target reopening is used to obtain the
failing result.

Confirmed against experimental `next-server` commit
`46df50c96d93d0ac3655c116c375574277cf0b30`, reported version `1.58.2`, built with
Rust 1.99.0. On 2026-10-27, `git ls-remote` still identified that exact commit
as upstream `refs/heads/next-server`. The `main` tip was
`95a25d686a2b584c387326e466d6ead8c885465d`; that separate branch was not built
or claimed affected. Linux x86_64 Docker, UTF-16 LSP negotiation, PHP source
configuration 8.5, analyzer enabled.

## Reproduction

From this checkout with its pinned image built:

```sh
./bin/poc up --no-build
./bin/poc exec -- python /opt/poc/tests/integration/repro_mago_external_spans.py
```

For an upstream maintainer without Docker or Serena, put
`tests/integration/repro_mago_external_spans.py`, `lsp_client.py`, and `trace.py`
in one directory and run with ordinary Python 3 and the experimental binary:

```sh
MAGO_BINARY=/absolute/path/to/mago POC_EVIDENCE=/tmp/mago-span-evidence python3 repro_mago_external_spans.py
```

The client and trace helper use only the Python standard library. The script
creates two tiny files and `mago.toml` in a temporary directory, starts Mago
with `MAGO_EXPERIMENTAL_SERVER=1`, and cleans up that directory afterward.
Evidence survives in the chosen evidence directory. Exit 0 means the known
failure **and** healthy restart control were observed; it does not mean the
external update succeeded.

Initial `Target.php`:

```php
<?php class CloseTarget { public function target(): int { return 7; } }
```

`Caller.php`:

```php
<?php function use_target(CloseTarget $x): int { return $x->target(); }
```

The event order is initialize/initialized, didOpen(Target), documentSymbol(Target),
didClose(Target), documentSymbol(Caller) as an ordered barrier, externally write
Target, didChangeWatchedFiles(Target, Changed), didOpen(Caller), references from
the caller with `includeDeclaration=true`, then rename from that caller.
The external replacement introduces `/* 🧪 */ ` before `public function`:

```php
<?php class CloseTarget { /* 🧪 */ public function target(): int { return 7; } }
```

Expected declaration start: line 0, UTF-16 character **51** (Python codepoint
column 50). Observed warm-process declaration start: **40**. The original
source declaration was at ASCII column42; this suggests an old byte span is
being mapped through new source text, but that explanation is an inference,
not a proven root cause. A fresh process returns51 and accepts rename.

## Evidence and controls

- [Actual direct negative and fresh-process control](../evidence/strengthening/mago-external-spans.json).
- [Selected actual protocol frames](../evidence/strengthening/mago-external-span-frames.json).
- [PoC and reproduction source identity](../evidence/strengthening/adapter-reproduction-identity.json).

The adapter's own stale-text defect is separately isolated using an equal
UTF-8 byte-length prefix replacement (`éé` → `🧪`): Mago then returns the correct
wire position while the reviewed adapter produces Python column51 instead of50.
Those are distinct failures. The Mago report above does not depend on the
adapter fix and is not claimed fixed by it. Explicit server restart is the
observed recovery; do not blindly replay a partly applied edit.

## Existing work and contribution guidance checked

[The experimental language-server PR #2555](https://github.com/carthage-software/mago/pull/2555)
is the relevant existing feature discussion. Searches on 2026-10-27 for
`repo:carthage-software/mago "out of date"`, `incremental spans`, `stale`, and
`LSP external references` found no matching external declaration-span report.
This is a bounded duplicate check, not proof that no related work exists.

[CONTRIBUTING.md at the tested commit](https://github.com/carthage-software/mago/blob/46df50c96d93d0ac3655c116c375574277cf0b30/CONTRIBUTING.md)
asks contributors to discuss a change first, supply reproduction instructions,
and add regression tests for fixes. A future patch should use the native
workspace-registry/LSP integration tests and run `just test` plus `just check`.
The issue template asks for description, reproduction and environment; a web
Playground cannot model this multi-file LSP lifecycle. This draft supplies those
sections. No Mago patch, branch, or test-suite result is claimed here.
