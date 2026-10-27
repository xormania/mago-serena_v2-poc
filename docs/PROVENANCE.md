# Sources and licenses

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
