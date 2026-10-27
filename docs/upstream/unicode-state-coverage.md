# Draft validation offer: Unicode, newline and cross-file state coverage

For Serena PR2115 discussion, not a claim that its draft has been tested here.
Inspected head: `a258552b6a194115330b50bf802a1952f55aa988` (open/draft).
The PoC currently runs Serena `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3` and Mago
`46df50c96d93d0ac3655c116c375574277cf0b30` through its external adapter.

We can offer independent properties that scan source indices and count astral
characters as two wire units, then assert exact text after insert/delete and
WorkspaceEdits. Cases include CR/LF/CRLF, empty lines/EOF, BMP and non-BMP, and
NEL/LS/PS that must remain text. Deliberately faulty converters fail the same
assertions. This follows xormania/serena6's independent-oracle approach without
claiming its patch was adopted.

The actual cross-file probe inspects and closes a file, externally replaces an
equal-UTF8-byte prefix with an emoji, and requests references/rename from another
file without reopening the target. Hash/version/event evidence verifies this
condition; the exact resulting text and fresh query are asserted through MCP.
The stale text cache was **our adapter's** bug and is fixed here. Mago's separate
byte-length-changing external-span finding has its own direct reproduction.

Run `./bin/poc fast` for properties; see `tests/integration/state_repro.py` for
actual adapter/direct/MCP comparisons and the contribution ledger U02/U03 for
evidence. New probe/test material is MIT; installed upstream sources retain their
licenses. No source pin was changed.

Before proposing a test port: run these assertions against PR2115 with a clearly
chosen coordinate boundary. Its edit-boundary conversion and our transport
conversion must not both transform the same position. Open-buffer-only tests do
not establish closed-file or external replacement correctness. Match upstream's
test framework and discuss that boundary with maintainers before a patch.
