# Serena: honor full-document synchronization for semantic edits

Status: confirmed against current upstream; local issue/discussion draft only.
No issue or PR has been posted and no Serena pin or source has been changed.

## Current-upstream check

On 2026-10-27 the connected GitHub read API resolved `oraios/serena` `main` to
`9e1cced0c34ed48d668e179f7c56c77b4d14a3e3`, exactly the retained PoC pin.
The API's `src/solidlsp/ls.py` blob was
`5321030caa72a2087c8040f19e6e98dc6012e324`. Its installed Docker source SHA-256
was `49c03a1dcaa73d7af9077573c328ab5739bf39a2218c31a0a331c7215adca665`, matching
the checkout. The installed distribution's `direct_url.json` identifies that
same Git revision. This was a live rerun against current-upstream bytes, not a
claim based only on the historical PoC result.

Evidence: [resolved tip](../evidence/strengthening/serena-upstream-tip.json),
[actual reproduction](../evidence/strengthening/serena-fullsync-current.json),
and [selected didChange frames](../evidence/strengthening/serena-fullsync-frames.txt).
Full attempt artifacts remain in
`artifacts/dev/upstream-fullsync-current-20261027/fullsync-reproduction/`.

## Proposed issue title and body

**SolidLSP emits ranged didChange edits to a full-sync language server**

Using a registered external SolidLSP backend for Mago, a semantic edit leaves the
language server indexing the old method. Mago advertises
`textDocumentSync: {openClose: true, change: 1, save: true, ...}`. The shared
`insert_text_at_position` and `delete_text_between_positions` paths nevertheless
emit ranged didChange notifications. The same operations, input and server work
when the external backend translates those notifications into the updated full
document text.

Versions: Serena `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3` (`main` on
2026-10-27, distribution `2.1.1.dev0`); Mago experimental server
`46df50c96d93d0ac3655c116c375574277cf0b30`; Python 3.12.12; Linux. Mago's
`1.58.2` display version alone does not identify this experimental server.

Reproduction in the pinned PoC development container:

```sh
./bin/poc up
./bin/poc exec -- python - < tests/integration/repro_fullsync.py
```

The complete reproduction is
[`tests/integration/repro_fullsync.py`](../../tests/integration/repro_fullsync.py).
It creates a temporary project containing only:

```php
<?php class SyncProbe { public function value(): int { return 7; } }
```

It starts a real Mago stdio process, opens the file using SolidLSP, replaces
`value` with `renamed` through the actual shared delete/insert methods, then asks
Mago for document symbols. A second real process repeats the scenario with the
external adapter's full-document bridge. No server response is mocked and no
model participates.

Observed negative control: the unbridged transport sends a ranged deletion at
columns 40–45 and a ranged insertion at column 40; document symbols still contain
`value`. This is the intended fault, with a successfully initialized live server
and completed semantic requests. It is not a setup failure.

Observed healthy control: the bridge sends full document text with increasing
versions 1 and 2; document symbols contain `renamed` with the expected selection
range at columns 40–47. The reproduction asserts both observations, so an
unexpected outcome fails the probe.

Expected behavior: a backend advertising full document synchronization receives
full text after each semantic edit. Incremental backends should retain their
current ranged-edit behavior. The original Mago response is consistent with its
advertised sync contract; this evidence does not establish a Mago defect.

Is a shared synchronization policy appropriate for external backends, or should
external registrations explicitly own this adaptation? The current public
transport extension point permits a local workaround. We would prefer to agree
on that ownership before proposing changes to the common transport/startup
contract.

## Contribution scope and next validation

Serena's [contribution guidance](https://github.com/oraios/serena/blob/9e1cced0c34ed48d668e179f7c56c77b4d14a3e3/CONTRIBUTING.md)
requires practical observed problems and asks for discussion before broader
changes, especially beta work. The minimal live reproduction establishes the
problem. A shared policy would affect many backend initialize paths, which
currently hold capabilities in different forms; this draft therefore recommends
an issue/discussion with the reproduction first, rather than an unvalidated
cross-backend patch. A focused fix may follow maintainer agreement.

A proposed upstream behavior test should use an external backend or controlled
LSP peer and exercise the ordinary edit API. Its independent assertions should
cover full-sync number/object capability forms, full resulting text and
increasing versions, plus an incremental-sync healthy control. It should not
assert helper names, scan implementation spelling, or couple to cache layout.
After a source/test patch, run the upstream-prescribed `poe format`,
`poe type-check`, and affected `poe test` suites; supply a concise changelog entry
if required by release scope. New SolidLSP files use SPDX MIT. The CLA and any
submission remain the user's actions. No upstream source patch or full upstream
test suite is claimed here.

## Related work and compatibility

- [Serena #1726](https://github.com/oraios/serena/pull/1726) is merged and its
  merge commit `0a3226377aa952c0a13a0239ab443287dcdda59c` is an ancestor of the
  retained/current pin. It adds external filesystem polling before cross-file
  semantic operations; it does not negotiate incremental versus full didChange
  payloads. It remains enabled in the PoC.
- [Serena #2132](https://github.com/oraios/serena/pull/2132) is merged and its
  merge commit `a8059c11ea4cb319359b2f95bb4ef92b792bce8d` is also an ancestor.
  It repairs high-level symbol-cache contamination, a different cache from the
  PoC transport's document text. No duplicate fix is proposed for that issue.
- [Serena #2115](https://github.com/oraios/serena/pull/2115), head
  `a258552b6a194115330b50bf802a1952f55aa988`, was still an open draft when checked.
  It addresses UTF-16 conversion in edit helpers, not full-document sync. Its
  coordinate assumptions need reconciliation with this PoC's conversion of all
  request/response wire positions to code points; adopting it unchanged could
  convert some positions twice. It was inspected, not cherry-picked.
- [xormania/serena #6](https://github.com/xormania/serena/pull/6) supplies useful
  independent newline/property and deliberate-regression methodology. It is an
  open test PR, not a full-sync fix.
- [xormania/serena #7](https://github.com/xormania/serena/pull/7) is an open
  documentation/settings-manifest PR, not a complete application-manifest
  verifier. Its independent review warned against implementation-scanning tests;
  that warning informed the behavior-focused test proposal above. The PoC's
  complete file manifest independently verifies observable filesystem contents.

A bounded read-only search for full-sync/textDocumentSync/full-document work
found related versioning PR #2009 and other backend-specific work, but establishes
no claim that all possible duplicates have been ruled out. Recheck the target tip,
issues and contribution guidance immediately before submission.
