# Recorded upstream investigations

> **Historical record.** This ledger records inspected revisions, local fixes, candidate patches, and draft upstream reports. Read each entry with its recorded evidence; its operating instructions do not define current contributor policy, and a draft does not establish publication. See [Contributing](CONTRIBUTING.md) and [current capabilities](CAPABILITIES.md).

## Original report

This is review material for xormania; nothing has been posted upstream. A passing
known-defect control means the fault and its healthy comparison were observed,
not that the affected feature works. Jev supplies no evidence for these claims.
Deterministic protocol responses, independent assertions and original application
tests are the evidence. Latest inspection: 2026-10-27.

## Shared revision and reproduction contract

| Input | Exact revision / identity |
| --- | --- |
| Reviewed PoC | `41729d30d23459de1ba53023051eb55894fb33b9` |
| Hardened PoC and adapter | Execution commit, dirty content, source and installed hashes in each run's `metadata.json`, `executed-identity.json`, `image-identity.json`; reviewable [validation index](evidence/strengthening/validation.json) |
| Serena | `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3`; also current upstream main on inspection ([API/source evidence](evidence/strengthening/serena-upstream-tip.json)) |
| Mago | `46df50c96d93d0ac3655c116c375574277cf0b30`; also current experimental next-server on inspection; main `95a25d686a2b584c387326e466d6ead8c885465d` was not built |
| Symfony Demo | `8d2e2ef75c3e18df173d8bf2379a14abb58c4c31`, original locks/tests plus declared timestamp adaptation |
| Runtime | PHP 8.5.12, Rust 1.99.0, Python 3.12.12; exact image/tool identities in the validation index |

All candidates below use this matrix unless explicitly marked source-only or
historical. Targeted pre-commit executions identify dirty adapter/probe hashes
in [their identity record](evidence/strengthening/adapter-reproduction-identity.json).
The final rebuilt-image run is recorded separately; targeted `docker cp` runs
are not represented as immutable image execution.

Build prerequisites and commands are in [README](../README.md). Tiny PHP probes,
protocol clients and new tests were authored in this PoC and use its MIT license.
They do not vendor the Demo. Serena remains GPL-3.0-or-later and Mago MIT OR
Apache-2.0; installing those projects retains their licenses. Direct Mago probes
need only ordinary Python 3, the adjacent `lsp_client.py` and `trace.py` helpers,
and the tested experimental binary. Adapter probes additionally need the pinned
SolidLSP environment. Temporary fixtures clean up after execution; evidence is
written outside them.

## U01 — Honor full document synchronization in SolidLSP

- **Observed / importance:** current pinned/current-main SolidLSP emits ranged
  didChange for insert/delete even though Mago advertises `change: 1`. The real
  unbridged server continues reporting `value`; our full-document bridge reports
  `renamed`. Small ASCII input isolates synchronization from Unicode/state issues.
- **Expected / actual contract:** LSP [TextDocumentSyncKind.Full](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocumentSyncKind)
  requires complete document content. A general client policy belongs at the
  SolidLSP transport/edit boundary; Mago need not accept unadvertised incremental
  edits. The current common edit path lacks capability-based selection. Current
  upstream bytes and the live response are verified, not inferred from old docs.
- **Attribution / revisions:** confirmed Serena/SolidLSP compatibility defect;
  shared revisions above. Mago behavior is a valid server control, not blamed.
- **Reproduction / evidence:** [tiny script](../tests/integration/repro_fullsync.py),
  `./bin/poc exec -- python - < tests/integration/repro_fullsync.py`;
  [current live result](evidence/strengthening/serena-fullsync-current.json),
  [selected didChange frames](evidence/strengthening/serena-fullsync-frames.txt).
  Full source, command, guidance and exact identities are in the
  [draft issue/compatibility report](upstream/serena-full-sync.md).
- **Existing work:** [PR 2115](https://github.com/oraios/serena/pull/2115) concerns
  UTF-16, not this ASCII synchronization fault. Merged
  [1726](https://github.com/oraios/serena/pull/1726) supplies external notifications;
  it does not select full content for client edits. No claim of exhaustive issue
  discovery is made.
- **Smallest contribution / readiness:** ready for issue/discussion plus native
  regression test. A shared correction should preserve incremental backends and
  handle both forms of sync capability. Recommend maintainer agreement before a
  patch across backend startup policies. Our adapter workaround is already tested;
  no universal upstream patch is included.

## U02 — Additional Unicode/newline/state coverage for PR 2115

- **Observed / importance:** codepoint and UTF-16 columns differ after non-BMP
  characters; only CR, LF and CRLF are LSP line endings. Closed-file transitions
  add a separate choice of conversion text. These interact during cross-file
  references and WorkspaceEdits, beyond a single open-buffer insertion test.
- **Expected / actual:** seeded independent index-scanning properties assert both
  coordinates and exact insert/delete/WorkspaceEdit text for ASCII, BMP, astral
  characters, Unicode separators, empty lines and EOF. Deliberate identity,
  LF-only and off-by-one converter faults fail the same assertions; healthy
  helpers pass. Disk reads normalize CR/CRLF to LF, while wire buffers preserve
  their text; Linux Serena writes normalize to native LF.
- **Attribution / revisions:** coverage contribution; no new upstream Unicode
  defect asserted from our own adapter bug. Shared pinned/current-main revisions.
- **Reproduction / evidence:** `./bin/poc fast`, [position properties](../tests/fast/test_positions.py),
  [state tests](../tests/fast/test_document_state.py), [actual adapter/MCP probe](../tests/integration/state_repro.py),
  and the [coverage draft](upstream/unicode-state-coverage.md). Native Mago wire
  column 51 and adapter column 50 are equivalent after the same astral prefix.
- **Existing work:** 2115 is open/draft, inspected at
  `a258552b6a194115330b50bf802a1952f55aa988`; its proposed edit-boundary conversion
  overlaps our transport conversion and cannot be stacked blindly.
  [xormania/serena PR 6](https://github.com/xormania/serena/pull/6), head
  `6f8f838551e3982ce6b442c0bec9f8cfb019dfec`, supplies the independent newline
  property approach. This supplements their case coverage and requires an A/B
  run on the proposed upstream branch before claiming compatibility.
- **Smallest contribution / readiness:** existing work we can help validate.
  Offer the fixtures/properties and a report of coordinate conventions first;
  port to upstream test style after maintainer agreement. Validation of 2115's
  actual patch remains pending.

## U03 — Closed-document text-cache invalidation (our adapter)

- **Observed / importance:** inspect Target, close it, externally replace `éé`
  with `🧪`, then rename from Caller without reopening Target. Equal UTF-8 prefix
  byte lengths isolate this from U04. The reviewed adapter retained old text:
  Python column 51 instead of 50. Native Mago returned correct UTF-16 column51.
- **Expected / actual:** after didClose, closed-file range translation must use
  current disk text. Open buffers use transmitted text, including unsaved text
  over an externally changed/deleted disk file. Creation, deletion, atomic
  replacement and restart follow the explicit [architecture](ARCHITECTURE.md)
  policy. Fixed adapter reads closed files afresh and preserves full sync.
- **Attribution / revisions:** confirmed **our adapter**, reviewed PoC41729d3;
  same pinned Mago/Serena, fixed content hashes in the execution records. No
  upstream cache fault is inferred. Merged
  [Serena 2132](https://github.com/oraios/serena/pull/2132) fixes high-level symbol
  cache mutation, a different cache. 1726 is present and provides the watched
  events used in our public REPL test.
- **Reproduction / evidence:** `./bin/poc exec -- python /opt/poc/tests/integration/state_repro.py`;
  [before](evidence/strengthening/adapter-state-before.txt),
  [after](evidence/strengthening/adapter-state-after.txt), and the final acceptance's
  `document-state/closed-target-reference-state.json` prove disk/transmitted hashes
  and no didOpen before the cross-file response. The public MCP path also checks
  exact semantic rename text and a fresh query.
  [The committed closed-target state excerpt](evidence/strengthening/adapter-closed-target-reference-state.json)
  also retains the hash/closed-state proof from targeted execution.
- **Smallest contribution / readiness:** fixed locally. Upstream value is a
  regression fixture/documentation example for external adapters, not an issue
  alleging Serena owns our cache. Recommend sharing with U02 after reviewing its
  overlap.

## U04 — Mago external changes leave cross-file spans stale

- **Observed / importance:** direct LSP, without adapter or Serena, returns stale
  declaration column40 after adding `/* 🧪 */ ` before a closed declaration;
  expected UTF-16 column51. Rename refuses with `-32803`, "index is out of date".
  A fresh server over exactly those edited files returns51 and valid edits.
- **Contract / attribution:** watched-file updates should refresh semantic spans.
  Confirmed Mago behavior on current experimental next-server; an old byte-span
  mapping through new source is a hypothesis, not proven root cause. The failure
  is not attributed to Serena or to our corrected cache. Main branch untested.
- **Reproduction / evidence:**
  `./bin/poc exec -- python /opt/poc/tests/integration/repro_mago_external_spans.py`;
  [stdlib-only two-file reproduction](../tests/integration/repro_mago_external_spans.py),
  [fault + fresh-process control](evidence/strengthening/mago-external-spans.json),
  [selected actual protocol frames](evidence/strengthening/mago-external-span-frames.json),
  [draft issue, guidance and environment](upstream/mago-external-spans.md).
  The script asserts the expected fault **and** healthy control; exit0 does not
  claim the external update works. Explicit restart is the observed recovery.
- **Existing work:** supplements experimental
  [Mago PR2555](https://github.com/carthage-software/mago/pull/2555); bounded searches
  found no matching report. Check again before posting.
- **Smallest contribution / readiness:** ready to discuss as a reproducible issue
  and native LSP regression test. Diagnose/update workspace registry spans before
  proposing a patch; no Mago source change is included. A failing test must target
  refreshed positions, not merely accept the known refusal.

## U05 — Positive Symfony Demo / Mago compatibility report

- **Observed / importance:** real MCP → Serena REPL → Mago resolves Demo
  repository/controller declarations, exactly the PHP caller, Doctrine vendor
  definitions, and interface implementation families. Semantic Demo rename
  `findLatest` → `findLatestPublished` changes exactly the declaration and caller;
  independent re-query and original Symfony tests verify behavior.
- **Expected / actual:** core supported navigation/edit/diagnostic operations pass
  with the full-sync/UTF-16 bridge. Exact file/range/text oracles and original test
  identities support this, rather than advertised capabilities alone. Open rename
  documents have versions; closed documents may have null versions. Normal
  documentChanges handling is observed; adverse stale WorkspaceEdit versions and
  alternate changes form have not been separately exercised live.
- **Attribution / revisions:** positive cross-project compatibility evidence using
  the shared pins and original Demo provenance. Our adapter supplies protocol
  adaptation; U04 remains an explicit limitation.
- **Reproduction / evidence:** `POC_TRACE=1 ./bin/poc test`, [capability matrix](CAPABILITIES.md),
  [findings](FINDINGS.md), [validation index](evidence/strengthening/validation.json),
  original [rename diff](evidence/rename.diff) and retained per-run logs/JUnit.
- **Existing work:** useful downstream evidence for Mago2555 and Serena's
  [external backend guide](https://github.com/oraios/serena/blob/9e1cced0c34ed48d668e179f7c56c77b4d14a3e3/docs/03-special-guides/external_language_server_registration.md).
  Complements them; no claim of a built-in supported Mago backend or full editor
  feature coverage.
- **Smallest contribution / readiness:** ready compatibility report, with the
  limitations attached. [Draft](upstream/mago-compatibility.md). A native Mago
  backend is an integration opportunity requiring upstream maintenance agreement,
  not a deliverable or dependency upgrade in this PoC.

## U06 — Reusable lifecycle and rename-failure protocol fixtures

- **Observed / importance:** collision rename refuses without changes; explicit
  restart changes PID and restores queries. Killing a genuinely in-flight server
  produces a bounded intelligible error; a between-request death instead triggers
  Serena's automatic recovery. REPL exceptions preserve edits already executed.
- **Expected / actual:** refusals leave bytes unchanged; partial execution is
  observed before recovery. These are lifecycle contracts and useful integration
  tests, not defects. No cancellation, timeout exhaustion or arbitrary rename
  failure class is inferred from server-death/collision tests.
- **Attribution / revisions:** compatible Mago and Serena behavior at shared pins;
  protocol fixture opportunity. [Fixtures](../fixtures/semantic/Calculator.php),
  [real MCP assertions](../tests/integration/run.py), bounded per-run transcripts
  and `restart_and_death`/`invalid_rename` result rows provide evidence.
- **Existing work / smallest contribution:** supplements Mago2555/Serena backend
  testing. Reusable standalone fullsync and U04 scripts already exist; extracting
  death/collision into native upstream tests is promising but needs maintainer
  test-style alignment. Cancellation remains explicitly unexercised.

## U07 — Whole application and evidence verification (PoC only)

- **Observed / importance:** the old selected-directory verifier accepted a
  correct rename with weakened root PHPUnit config; old report accepted an empty
  checks array. Both could create misleading acceptance claims.
- **Expected / actual:** full application metadata/bytes and exact original test
  identities are verified against read-only external baselines; required run-bound
  inventory rejects incomplete, skipped, duplicate/stale/wrong-run results.
- **Attribution / revisions:** confirmed local fixture/verifier/harness defects at
  PoC41729d3, fixed by hardened verifier/evidence code. Not Mago/Serena bugs.
- **Evidence / prior work:** [verifier before](evidence/strengthening/verifier-before.json),
  [after](evidence/strengthening/verifier-after.json), [report before](evidence/strengthening/report-before.json),
  [fast verifier tests](../tests/fast/test_verifier.py) and
  [inventory mutations](../tests/fast/test_evidence.py). The requested
  [xormania/serena7](https://github.com/xormania/serena/pull/7) is actually a
  language-server settings documentation manifest, not an application verifier.
  Its completeness principle is relevant; the underlying change is different.
- **Smallest contribution / readiness:** keep local; reusable fixture contract or
  testing note is useful to another consumer. No upstream bug report warranted.

## U08 — External-adapter documentation and integration opportunities

- **Observed / importance:** the public entry point supports this backend without
  a Serena fork. Configuration alone does not provide full-sync selection,
  position conversion or closed-file text policy. Those responsibilities should
  be visible to external-backend authors.
- **Expected / actual / attribution:** documentation opportunity, not a demonstrated
  additional defect. Shared pinned/current code and all above protocols apply.
- **Reproduction / evidence / existing work:** real registered `mago` backend,
  [architecture](ARCHITECTURE.md), [source](../adapter/src/serena_mago/server.py), U01–U03,
  and Serena's existing external-language-server guide. Complements rather than
  replaces that guide; account for PR2115 before documenting a permanent boundary.
- **Smallest contribution / readiness:** draft a short backend-author checklist:
  selected encoding, negotiated sync kind, notification/cache ownership, versioned
  edits, fresh cross-file oracles and restart. Promising documentation contribution;
  finalize after U01/2115 boundary decisions. No submission prepared as an API promise.

## U09 — Native LSP external analyzer lifecycle and dependency graph candidate

- **Baseline / attribution:** experimental Mago
  `46df50c96d93d0ac3655c116c375574277cf0b30`, matched SDK `1.58.2`/MANA `2.1`,
  wiring extension `28c3f54065b71fe046a7474ced401aeadc941b0f`, PHP backend.
  The corrected matched control starts/completes the CLI worker and observes its
  concrete Registry Body dependency; unpatched LSP serves native symbols without
  worker startup. This remains a named-source server omission, not a general
  extension/Serena incompatibility.
- **Harness correction:** a folder's own `mago.toml` overrides launch `--config`.
  The earlier launch-config-only slice probe did not prove matched effective LSP
  configuration. Historical snapshots remain intact; the new probe temporarily
  installs the same instrumented configuration at the workspace root, restores
  original bytes and independently reproduces the omission. See the
  [corrected baseline and configuration](evidence/lsp-extensions/baseline/index.json).
- **Implemented candidate:** the [native patch](../patches/mago-lsp-extensions.patch)
  attaches existing external analyzer state to each workspace registry, loads
  initialization stubs and uses the native incremental pipeline. Worker lifetime
  follows workspace generations and shutdown. Failed analysis/reload refuses
  stale semantic results. The separate `mago/symbolReferences` request returns
  actual typed dependency edges; the adapter and
  [small Serena facade patch](../patches/serena-symbol-references.patch) forward
  those results without a CLI fallback. The edge has no source span, runtime-call
  meaning or per-edge provider provenance. Class/function/member queries are the
  intended scope; top-level case-sensitive constants are not demonstrated.
- **Proof / boundaries:** [19 real-worker/direct-LSP controls and four focused
  Rust tests](evidence/lsp-extensions/native/index.json) pass. They cover unsaved
  contents without duplicate startup, real compiled changed/restored bindings,
  analysis and worker-command failure/recovery, host disable/re-enable,
  shutdown/restart and independent folder isolation. The [adaptive host MCP
  investigation](evidence/lsp-extensions/agent/result.json) has 14 agent-selected REPL cells (15 MCP tool calls)
  calls and four true off/on/change/restoration flags; the original 53 tests and
  120 assertions pass with source/test identities. The [minimal real-SDK
  regression](upstream/lsp-extensions-repro/README.md) independently compares the
  two executables. Broad semantic acceptance (31 checks), slices 1/2 (9/12 checks), and the
  strengthened native-plus-Serena gate pass on the [final image](evidence/lsp-extensions/acceptance/summary.json).
- **Identities / freshness:** base and SDK/protocol are unchanged. Mago patch
  SHA-256 `ca955e0db6023a997fe708d46d3bd0b92e6dd91237aee7c206f13768effdea11`,
  executable SHA-256 `5cfaa051b9cb23f63cbcd8ec1703538c1f2789ff21ad068b239678631f701e46`.
  Fresh compiled metadata requires export plus a configured `restart-on`
  watched-file reload or explicit server restart; source edits do not recompile
  Symfony metadata. The [compatibility record](evidence/lsp-extensions/compatibility.json)
  verifies actual SDK header/package sources. The [diagnostic comparison](evidence/lsp-extensions/diagnostic-comparison.json)
  shows identical complete 35-native-Issue sets for baseline and candidate off/on
  across 46 files; enabled reports add one real attestation. The historical
  30-diagnostic/34-source-file record remains unchanged. Initial load failure requires process restart or folder
  remove/re-add. [The focused document](MAGO-LSP-EXTENSIONS.md) records exact
  patches/build identities, opt-in config, observations and limits.
- **Upstream readiness:** local reviewable patch and regression fixture; no
  upstream publication or acceptance. The historical external-span finding is
  separate. [Draft](upstream/mago-lsp-extension-hosts.md).

Slice 1 also extends U05 with a positive compiled-wiring compatibility report:
Mate confirms `TagsInputType → TagRepository → doctrine/Registry`, while the
existing wiring package adds the repository-to-concrete-Registry Body edge to
Mago's final graph. Off/on, unresolved-binding and restored controls distinguish
the extension contribution from native signature references. The selected
service's direct concrete edge is unchanged because Mago suppresses a redundant
Body edge when its Signature reference already exists. No runtime call or
universal Symfony/ORM coverage is inferred. See [slice adoption](SLICE-1.md).

The [slice-2 command task](SLICE-2.md) extends this positive U05 evidence to a
new Maker-generated service. Compiled Console/Mate facts bind
`TagsCountCommand::$tags` to the existing `TagRepository`; the public CLI analyzes
the new command and test and observes its native Signature reference plus the
repository's extension-supplied concrete Registry Body reference. The retained
adaptive MCP exercise and scripted acceptance replay are separately attributed.
That baseline slice-2 run adds feature-workflow evidence under the same pins
without changing its LSP worker-start boundary. The later U09 candidate is
tracked separately and does not retroactively change that result.

The [slice-3 request task](SLICE-3.md) adds runtime integration evidence with
Mate and the official Symfony/Monolog extensions at `0.15.0`. Its stale-profiler
reproduction is attributed to this PoC's `matelib.call()` freshness guard: it
applied the compiled-service lifetime to recorded request/log data. The local
correction separates those policies and keeps compiled reads guarded. The
injected invalid ORM field and expected absence of a pre-boot profile are task
controls, not upstream defects. No additional upstream defect or submission is
established by this slice; the source-semantic/CLI wiring results leave U09
with its existing pin-specific attribution.

## Prioritized handoff

| Priority / category | Candidate | Recommendation and deliverable |
| --- | --- | --- |
| Ready to discuss | U04 | Mago external-span issue with [tiny repro, frames and healthy control](upstream/mago-external-spans.md) |
| Ready to discuss | U01 | SolidLSP full-sync policy, [current-code live reproduction and draft](upstream/serena-full-sync.md) |
| Ready to share | U05 | [Positive Symfony compatibility report](upstream/mago-compatibility.md), with U04 and unexercised features attached |
| Local candidate ready for review | U09 | Native worker lifecycle, typed graph exposure and real CLI/LSP/Serena controls; [unpublished draft](upstream/mago-lsp-extension-hosts.md) and [results/limits](MAGO-LSP-EXTENSIONS.md) |
| Existing work to validate | U02 | [Additional Unicode/state properties](upstream/unicode-state-coverage.md) for2115 and xormania6; actual PR-branch A/B still pending |
| Promising, more evidence/design | U06, U08 | Native lifecycle/collision tests and backend-author docs; cancellation/new API promises remain unproven |
| Confined to our PoC | U03, U07 | Fixed adapter cache, whole-app verifier and report integrity; share tests without misattributing ownership |

Before posting, recheck upstream status and duplicate searches. Serena's guidance
routes bugs/improvements through maintainer discussion and asks for a reproducible
case; Mago's contribution guide similarly asks for discussion and regression
tests. The linked drafts record the inspected guidance and required future native
checks. Merging, upstream branches, issues and submissions remain with xormania.
