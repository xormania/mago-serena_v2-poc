# Runtime tool notices

These unmodified notices accompany the pinned runtime tools copied into the
development image. The image stores them under `/opt/licenses/tools`.

| Tool | Exact release source |
| --- | --- |
| uv 0.12.8 | https://github.com/astral-sh/uv/tree/0.12.8 — LICENSE-MIT and LICENSE-APACHE |
| Composer 2.9.1 | https://github.com/composer/composer/tree/2.9.1 — LICENSE |

PHP 8.5.12's LICENSE is extracted from the official image's matching source
archive. Python 3.12.12's installed LICENSE.txt is preserved. Mago's upstream
licenses, prelude notice, Cargo.lock and downloaded crate notices are collected
from the pinned build. Installed Python distribution notices are copied by
`docker/collect-licenses`. The PoC MIT notice is also included. Base OS package
copyright files remain in `/usr/share/doc`; installed versions are recorded in
`/opt/os-packages.txt`. The Demo keeps its own license in each application copy.
