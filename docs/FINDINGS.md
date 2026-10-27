# CI follow-up after PR1 merged

The [CI performance report](CI.md) records the merged baseline, actual hosted
timings, restored BuildKit layers and duplicate-run removal. The default-branch
Jev consumer is now registered. Its [four-call live calibration](JEV.md) produced
one accepted diagnosis, two abstentions and one strictly rejected provider
response; sanitized evidence and exact trusted revision are retained. The
historical activation-pending statements below describe the original PR1 session,
not the current merged state. Unmerged follow-up diagnostic changes are not
claimed proven by those live calls. Upstream findings and source pins are retained.

# Hardened results

The strengthened rebuilt-image run passed **31/31 required checks** on
2026-10-27. It includes **96 deterministic fast tests**, genuine stdio
MCP → Serena REPL → Mago execution, two independent fresh Demo workspaces and the
semantic `findLatest` → `findLatestPublished` rename. All three application suite
executions passed **53 tests / 120 assertions**, with exact original
class/method/dataset/file/line identities verified. Complete application manifests
include root configuration, dependencies, unknown paths and relevant metadata.
The final post-scenario comparison matches the baseline plus the exact two-file
rename. Actual image/code/tool identities and artifact hashes are checked.

See the [validation index](evidence/strengthening/validation.json) for exact
source/run/image hashes, full evidence locations, and clean-checkout validation.
[Earlier attempts](evidence/strengthening/failed-attempts.json) are preserved and
not counted as reproducing the intended adapter/verifier defects. The first
identity parse exposed mixed Composer stderr; subsequent identity guards rejected
code edited after image builds. The full manifest also caught Serena's legitimate
first-start project.yml expansion. Real MCP initialization now canonicalizes that
state **before** sealing the external baseline; project configuration stays covered.

Confirmed before/after findings:

- The reviewed adapter returned Python column51 instead of50 after a closed
  target's equal-byte-length external non-BMP replacement. The corrected adapter
  returns50; direct Mago's equivalent UTF-16 column is51. Actual MCP reference and
  rename assertions plus hash/event evidence prove the target stayed closed.
- The reviewed verifier accepted an exact rename plus weakened root PHPUnit
  configuration. Whole-application verification rejects it and other root,
  dependency, test, file-type/mode, addition/deletion faults. Healthy controls pass.
- The reviewed report accepted an empty checks list. Required inventories now
  reject missing, duplicate, skipped, stale or foreign checks. Retained artifacts
  and their image/runtime/baseline content are also required and verified.
- Jev's mocked HTTP-error telemetry and calibration-bound review faults were
  reproduced and fixed. These provider tests are not live diagnosis results.

There are two independently assessable upstream findings. Current Serena main
still emits ranged changes to full-sync Mago, and the full-document bridge
remains necessary. A separate **direct-Mago** probe on current experimental
next-server finds stale cross-file declaration spans after a byte-length-changing
external edit: wire column40 versus expected51, then rename refusal -32803. A fresh
process returns51 and valid edits. This Mago limitation is **not fixed here**.
The required negative/control check asserts both outcomes without claiming the
affected feature passes. The equal-byte adapter reproduction isolates our cache
fault from that server issue.

[The contribution ledger](UPSTREAM-CONTRIBUTIONS.md) prioritizes both draft
reports, positive Symfony compatibility evidence, Unicode/property coverage for
existing PR2115, reusable fixtures and local-only fixes. Current tips, existing
PRs and contribution guidance were checked; no source pin changed and nothing was
submitted upstream. Cancellation, secondary editor APIs, adverse stale edit
versions and PR2115 branch compatibility remain unproven.

**Model-driven acceptance was not rerun after hardening.** The earlier authenticated
Codex run below remains historical evidence. Deterministic MCP execution is a
different check. **No live Jev request or live calibration ran locally.** The
trusted consumer requires default-branch activation; hosted workflow results and
provider behavior are pending. [Jev documentation](JEV.md) explains the boundary,
commands and bounded recorded/synthetic calibration controls.

# Historical results before hardening

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
finding. No confirmed Mago defect was found in that original run; the hardening
work above subsequently isolated an external-span defect directly against the
same experimental revision.

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
