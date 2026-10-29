# Sources and licenses

## Sources and modifications

`toolchain.lock.json` records source commits, image digests, runtime versions,
lock hashes, and candidate patch identities. `uv.lock` resolves the pinned
Serena source and local adapter. The Dockerfile builds Mago from source and
installs Serena and the adapter in the same Python environment.

The default image applies `patches/mago-lsp-extensions.patch` to the pinned
experimental Mago source and `patches/serena-symbol-references.patch` to the
pinned Serena facade. It retains the unpatched Mago executable as
`mago-baseline`; build argument `MAGO_LSP_EXTENSIONS=0` selects that executable
as the primary Mago. These repository patches are not claims of upstream
publication. Extension contributions need explicit configuration; see
[Mago LSP extensions](MAGO-LSP-EXTENSIONS.md).

The separate [Mate overlay](../fixtures/mate/overlay.json) records its Composer
lock, Mate/Symfony/Monolog packages, Mago SDK source, and wiring extension. It
also records the required existing-package update and rationale. Installed
package licenses remain in vendor directories. PHP observer code in this
repository uses Mago's public SDK.

`app/` is an archive of official Symfony Demo commit
`8d2e2ef75c3e18df173d8bf2379a14abb58c4c31`. Its license, copyright headers,
original tests, manifests/locks, and environment seeds are preserved. The sole
source adaptation changes a fixture comment timestamp from future to past so
new comments sort correctly. Original/approved hashes and setup behavior are
explained in the [fixture contract](FIXTURE-CONTRACT.md). Tracked SQLite files
remain source inputs; disposable setup replaces its own database copies.

## Attribution and redistribution

The repository's original MIT license covers its adapter, scripts, and test
code. Symfony Demo is MIT under [app/LICENSE](../app/LICENSE).
Serena is GPL-3.0-or-later; Mago is MIT OR Apache-2.0. Their licenses and notices
must accompany redistributed images. PHP, Python, Rust, uv, Composer, operating
system packages, and Python/Composer dependencies retain their own licenses;
the repository's MIT grant does not replace them.

`docker/collect-licenses` and Docker build steps collect notices under
`/opt/licenses`; the image also includes package inventories. uv/Composer
notices are retained in [licenses/](../licenses/README.md). Review those inputs
when changing dependencies or distributing the image.

Symfony Docker revision `92d0d49293cd8678d82ca57c9c81b2dc45cf5561` was a design
reference; this repository's PHP CLI development Dockerfile/router were authored
here. The earlier Agentscient fixture at
`7d1abb3c4ac01451d83e1c1e12742b9fa2067561` informed copy/reset and timestamp
handling. It does not impose role systems or operating policies on this project.
The [original implementation plan](IMPLEMENTATION-PLAN.md) retains that history.

## Result provenance

Acceptance records source commit, full file inventory, and dirty-file contents
in `metadata.json`. `executed-identity.json` records installed adapter, verifier,
locks, and package/runtime identities; image records identify actual running
container images. A local image may have no registry digest, so its content
addressed image ID is retained. The expected result inventory and context are
recorded before checks; artifacts are bound to the relevant run and attempt.

Raw observations under [evidence/](evidence/) retain their own tested inputs.
Changing documentation or merging a patch does not rerun an old agent session.
Jev's optional TypeSafe request/response, model, latency, and available usage
are recorded separately from application acceptance. Mock and live records
remain distinguishable; see [Testing](TESTING.md) and [Jev](JEV.md).
