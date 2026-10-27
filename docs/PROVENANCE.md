# Sources and licenses

Slice 1 preserves the original toolchain lock and `app/` manifest. The separate
[`fixtures/mate` overlay](../fixtures/mate/overlay.json) declares its own exact
Composer lock, Mate/Symfony packages, experimental Mago SDK source and wiring
package. It also records the single required existing-package update and why.
The executable remains the original source-built experimental Mago; no packaged
Mago binary replaces it. The new PHP observer uses Mago's public SDK and is
authored here; its scoped formatting and second-pass stability were checked
with Mago. Installed overlay package licenses remain in their vendor directories.

All source starting pins in the implementation plan were retained. Exact
versions, source SHAs, image manifest digests and dependency lock hashes are in
`toolchain.lock.json`. `uv.lock` resolves the pinned Serena commit together with
the local adapter; the adapter is installed into the same Python environment.
Rust 1.99.0 was available and used without lowering Mago's declared requirement.

`app/` is a `git archive` of the official Demo commit. Its LICENSE, copyright
headers, tests, Composer manifest/lock and environment seeds are preserved.
The manifest records every original file before adaptation. The only changed
source file is the documented past-comment timestamp line. Setup behavior is
implemented outside the application; Composer auto-scripts are explicitly
reproduced with a copy of the environment seed. Upstream tracked SQLite databases
remain as historical source input; disposable environments always replace them.

The earlier Agentscient fixture at
`7d1abb3c4ac01451d83e1c1e12742b9fa2067561` supplied the documented copy/reset and
timestamp lessons. No roles, private dependencies, orchestration, instructions
or credentials were imported. Symfony Docker at
`92d0d49293cd8678d82ca57c9c81b2dc45cf5561` was a design reference; this repository's
small PHP CLI development Dockerfile and router are newly authored, not copied
Docker definitions.

The repository's original MIT LICENSE remains. Symfony Demo is MIT with its
own license in `app/LICENSE`. The adapter/harness code is covered by this
repository's MIT license. Serena is GPL-3.0-or-later; Mago is MIT OR Apache-2.0.
They are installed/built from their pinned upstream sources in the image. Their
licenses and notices must accompany any redistributed image; see
`docker/collect-licenses` for the image's `/opt/licenses` collection. PHP,
Python, Rust, uv, Composer and Composer/Python dependencies retain their own
licenses. Runtime copies are distinct from the PoC repository's MIT grant.
Pinned uv and Composer notices are also preserved in `licenses/`; the image
collects these alongside the PHP and Python runtime licenses.

The hardening work starts from reviewed PoC commit
`41729d30d23459de1ba53023051eb55894fb33b9`, on `poc/serena-mago-hardening`.
The fetched source branch had no later changes. All application/tool pins and
dependency locks remain unchanged. New tiny PHP probes and Python clients are
authored here under this repository's MIT license; they are independent of the
Demo except where explicitly labeled. Upstream source inspected for comparison
retains its own license and is not vendored by these probes. The
[contribution ledger](UPSTREAM-CONTRIBUTIONS.md) records exact inspected revisions,
guidance, prior work, protocol evidence and draft material.

Each hardened run records `metadata.json` with the source commit, complete source
manifest and base64 dirty-file contents/deletions, fixture checksum/adaptation
manifests and pinned toolchain. `executed-identity.json` hashes the installed
adapter, SolidLSP, verifier/harness and locks, lists installed package/runtime
versions, and is checked against host source. `image-identity.json` records the
actual container image ID and available registry digests for each fresh service.
Local images may have no repository digest; their content-addressed image IDs
are still recorded. `run-plan.json` defines the expected inventory before checks;
each result is bound to its source context, run and attempt. Full dirty content
describes the tested tree without pretending that HEAD alone contains it.

Jev is a separate optional TypeSafe CI API call, not an application dependency.
Its model, endpoint, configuration, sanitized request/response, latency and
available usage/cost are retained separately. Local provider tests are mocked and
labeled accordingly. Historical model-driven acceptance is not evidence that a
model or live Jev reran after hardening. See [the Jev notes](JEV.md).
