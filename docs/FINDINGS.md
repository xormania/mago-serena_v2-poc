# Observed results

The pinned Docker integration and required acceptance matrix passed locally on
2026-10-27. Two independent fresh Symfony Demo copies/databases each passed
**53 tests, 120 assertions**. The semantic rename changed exactly
`src/Repository/PostRepository.php` and `src/Controller/BlogController.php`; the
renamed app passed the original suite. Composer validation, YAML/Twig/XLIFF and
translation linters, service/entity validation, PHP-CS-Fixer and PHPStan passed.
PHPStan uses `--memory-limit=512M`; the stock image's 128M limit was insufficient.

A separate authenticated **Codex CLI 0.164.0 / gpt-6.1-sol / xhigh** session used
six completed semantic REPL calls, including symbol lookup, caller/declaration
lookup, semantic rename and re-query. The external verifier checked its exact
diff, original PHPUnit result, transcript and a fresh independent MCP query.
The agent's disposable application is discarded after evidence capture; the
checked-in application remains unchanged.

Reviewable snapshots are in [docs/evidence](evidence/):

- [Acceptance results](evidence/acceptance-results.json), [runtime identity](evidence/runtime.json), and [exact rename diff](evidence/rename.diff).
- [Agent result](evidence/agent-result.json), [harness identity](evidence/agent-harness.json), [agent transcript](evidence/agent-transcript.jsonl), and [original tests](evidence/agent-phpunit.log).
- [Wrapper checks](evidence/wrapper-results.json): a real MCP query launched from `/tmp` with an actual checkout path containing spaces; the stopped service returned exit 3, actionable stderr and zero stdout.
- [Original timestamp failure](evidence/timestamp-baseline-php84.txt), reproduced before the one-line fixture adaptation.

Full per-run MCP/LSP traces, logs, JUnit, hashes, diagnostics and earlier failed
development runs remain in ignored `artifacts/`. Snapshot metadata records that
the implementation was uncommitted during execution, plus exact adapter/file
hashes; it does not claim the initial repository revision contains these changes.
The GitHub Actions workflow is supplied but was not remotely executed or published
in this session. Local Docker execution used the same entrypoint as CI.

# Integration finding useful to Serena

At Serena `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3`,
`SolidLanguageServer.insert_text_at_position` and
`delete_text_between_positions` emit ranged didChange messages. The pinned
Mago `46df50c96d93d0ac3655c116c375574277cf0b30` advertises full sync (`change=1`).
In a live minimal reproduction the unbridged path retained the old `value`
method after the client's in-memory edit to `renamed`; the bridged path returned
the new method. The adapter converts those updates to full document contents.
No Serena fork or upstream source patch was needed.

Reproduce against a running dev container:

```sh
./bin/poc exec -- python - < tests/integration/repro_fullsync.py
```

The PHP input is:

```php
<?php class SyncProbe { public function value(): int { return 7; } }
```

The script compares a stock SolidLSP transport with the external adapter using
two actual Mago processes, not mocks. It saves advertised sync, exact returned
symbols and a wire trace under `artifacts/dev/fullsync-reproduction/`.
[The captured result](evidence/fullsync-result.json) and
[selected protocol frames](evidence/fullsync-frames.txt) are suitable upstream
reproduction material. Attribution is to the client/server sync contract at the
adapter boundary; this does not establish that Mago should accept ranged updates
it never advertised.

# Findings useful to Mago and future consumers

Mago's real UTF-16 positions, hierarchical name/body ranges, Doctrine vendor
definitions, references, implementation relationships, colliding-rename errors,
and versioned documentChanges worked in this PoC. Preserve the exact source SHA
when reporting results: `mago 1.58.2` alone does not identify this experimental
server. The analyzer remained enabled. Pre-existing app diagnostics were not
suppressed, and passing tests do not establish the correctness of every analyzer
finding. No confirmed Mago integration defect requiring a source patch was found.

Serena automatically restarts a server that dies between requests. The death
test therefore kills an actual process during an observed in-flight LSP request,
asserts a bounded intelligible failure, and explicitly restarts/re-queries.
REPL exceptions do not roll back already completed edits; inspect hashes/diffs
and re-query before retrying a cell. Stale symbol objects are snapshots.

The [capability matrix](CAPABILITIES.md) distinguishes core passes from optional
features not exercised. CRLF normalization is visible, secondary editor features
are not proven through REPL, and cancellation/alternate edit shapes were not
separately exercised. OS package versions are recorded in the image; apt mirrors
are not snapshot-locked. This is a development PoC, with no deployment, MinSpec
migration, published upstream issues or merged changes.
