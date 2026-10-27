# Capability evidence

Mago-first slice 1 adds calibrated native PHP checks, compiled Symfony wiring
and a real selected-service investigation. See [PHP evidence](MAGO-PHP.md),
[service semantics](SERVICE-SEMANTICS.md), [wiring](SYMFONY-WIRING.md) and the
[current adoption/result table](SLICE-1.md). These additions retain the historical
full-sync and stale-span findings at their original source pins.

Recorded 2026-10-27 with the exact pins in `toolchain.lock.json`. Hardened
validation is indexed in [strengthening/validation.json](evidence/strengthening/validation.json).
The original pre-hardening run remains in `docs/evidence/acceptance-results.json`.
“Wire” includes actual LSP requests/publications made by the adapter, retained
in the MCP stderr/protocol logs. A capability advertisement alone is never a pass.

| Feature | Mago advertises | Verified on LSP wire | Adapter | REPL | End-to-end result |
| --- | --- | --- | --- | --- | --- |
| Hierarchical document symbols and source/name ranges | Yes | Yes | Yes | Yes | pass: Demo declarations and exact source positions/bodies |
| References | Yes | Yes | Yes | Yes | pass: exact BlogController caller and renamed references |
| Definitions/declarations | Definition provider | Yes | Yes | Yes, find_declaration uses definition | pass: Demo and installed Doctrine declaration |
| Implementations/inheritance | Yes | Yes | Yes | Yes | pass: both Greeter implementations and inherited family rename |
| Semantic rename | Yes | Yes, documentChanges | Yes | Yes | pass: exact two-file Demo diff and unchanged original tests |
| Colliding rename | Request error | Yes | Yes | Yes | pass: useful error, unchanged file |
| Symbol body edit | Client operation | Full document changes | Yes | edit.replace_symbol_body | pass: exact source change, fresh query and PHP result |
| UTF-16 / non-BMP / CRLF positions | UTF-16 default | Yes | Codepoint conversion | Yes | pass: exact target after café/emoji on same line |
| Diagnostics | Push notifications; no pull provider | Yes | Push cache with empty clear publications | Yes | pass: exact introduced return-type range and restoration to baseline |
| External changes | Watched files and full document updates | Yes | Existing SolidLSP synchronization plus corrected closed-file text lifetime | Yes | Fresh body query and equal-byte-prefix cross-file closed-target cases pass; byte-length-changing declaration update exposes known Mago defect below |
| Server restart/death | Process lifecycle | Yes | Existing process manager | Yes | pass: PID changes, bounded in-flight error, explicit recovery |
| Full sync compatibility | change=1 | Yes; separate live reproduction | Full document bridge | Covered by edits/rename | pass; unbridged SolidLSP leaves old method indexed |
| REPL persistence/partial execution | Not an LSP capability | Real MCP sessions | Not applicable | Yes | pass: 42, independent session isolation, mutation before exception |
| Workspace/database isolation | Not an LSP capability | Not applicable | Separate processes/state | Separate services | pass: two fresh suites, cleanup of A preserves B |
| Backend identity and negative controls | mago-server initialize identity | Yes | Binary SHA check; no fallback | Startup errors observable | pass: missing/wrong executables rejected, wrong verifier expectation rejected |
| Real model-driven coding task | Not an LSP capability | Historical model MCP calls retained | Historical | Historical | Historical pass; not rerun after hardening; current deterministic MCP acceptance is separate |
| Hover | Yes | Yes, slice 1 | Existing request_hover | include_info=True on find_symbol/find_declaration | pass: selected method signature and generic vendor declaration |
| Completion/signature help | Yes | not_exercised | Generic transport available | No dedicated facade methods | not_exercised |
| Call/type hierarchy | Yes | Yes, slice 1 direct LSP | Generic transport available | No dedicated facade methods | Direct server pass: AbstractType supertype and inherited findAll outgoing call; REPL exposure remains unproven |
| Formatting/code actions | Yes | not_exercised | Generic transport available | No dedicated facade methods | not_exercised |
| Cancellation and timeout exhaustion | Not asserted | not_exercised | Bounded base requests | Not separately tested | not_exercised |
| Stale WorkspaceEdit version rejection / changes-form rename | Defensive adapter support / Mago negotiation | not_exercised as adverse/alternate cases | Implemented | Normal documentChanges path verified | not_exercised separately |

Serena's configured native line endings normalize CRLF to LF on Linux writes.
The position test records that normalization; it proves correct navigation and
edit coordinates, not byte-for-byte line-ending preservation. Retained symbol
objects can contain an old body; re-query after any mutation. Existing Demo
analyzer diagnostics are retained separately from deliberately introduced errors.
No zero-warning baseline or framework-specific analyzer correctness is claimed.

Hardened validation adds:

| Check | Evidence / interpretation |
| --- | --- |
| Closed file inspected, closed, externally replaced with non-BMP, queried from another file without reopen | Actual adapter/direct/MCP responses, state-event/hash proof, exact rename/requery; reviewed adapter failure reproduced before fix |
| Position/edit properties | Independent seeded oracle, ASCII/BMP/astral, LF/CRLF/CR, empty/EOF, selected converter mutations; deterministic fast tests |
| Entire application integrity | Complete external manifest including vendor, root config/manifests/locks/tests, types/modes/symlinks and narrow generated exclusions |
| Original suite execution | Trusted fixture method hashes plus exact class/method/dataset/file/line inventory; same-total fake, skipped, omitted and substituted results rejected |
| Execution/evidence identity | Source+dirty contents, exact installed code inventory, tool/source/lock pins, two actual image IDs, run/attempt/context and sealed artifact hashes; missing/stale/duplicate rows rejected |
| Mago closed external declaration span | **Known failure**, direct wire40 vs51 after byte-length-changing prefix; rename refuses -32803; fresh-process healthy control51 and rename succeeds. Expected-negative/control test pass does not repair this capability |
| Jev diagnosis | Merged default consumer active; actual four-call calibration: one accepted diagnosis, two abstentions, one invalid duplicate-reference response rejected. Exact model and usage retained; candidate reservation/reporting changes are not claimed live until merged. See JEV.md |

See [upstream candidates](UPSTREAM-CONTRIBUTIONS.md) for exact revisions, tiny
fixtures, protocol evidence, draft reports and contribution readiness.
