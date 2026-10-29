# Contributing

Changes should preserve a reproducible development environment, independently
checked application outcomes, and useful records of failures as well as success.
Start with [Getting started](GETTING-STARTED.md), [Architecture](ARCHITECTURE.md),
and [Testing](TESTING.md). Open a focused pull request against `master`.

## Find the implementation

| Area | Location |
| --- | --- |
| Public commands and workspace lifecycle | `bin/poc`, `bin/poclib.py`, other `bin/` launchers and libraries |
| Serena transport and position conversion | `adapter/src/serena_mago/server.py` |
| Runtime image and application setup | `Dockerfile`, `compose.yaml`, `docker/` |
| Pinned sources and patches | `toolchain.lock.json`, `uv.lock`, `patches/` |
| Symfony inspection dependencies/configuration | `fixtures/mate/overlay.json`, its Composer lock and config |
| Original application and approved adaptation | `app/`, `fixtures/upstream.sha256.json`, `fixtures/adaptations.json` |
| Properties and failure controls | `tests/fast/` |
| Protocol, task, and application acceptance | `tests/integration/` |
| CI reporting and advisory consumer | `.github/workflows/`, `tools/ci/` |

Keep application work in disposable copies. The [fixture contract](FIXTURE-CONTRACT.md)
describes the intentional timestamp adaptation, setup, exact original test
identities, and task-specific allowed changes. Updating the fixture requires a
deliberate provenance and verifier update, not relaxing expectations to make an
unexplained failure disappear.

## Validate a change

Run `uv sync --frozen --python 3.12.12` and `./bin/poc fast`. Node is required by
fast tests of the Actions helper. Inspect `git diff --check` before submission.
For changes to the adapter, patches, dependencies, fixtures, runtime scripts,
or acceptance code, rebuild the image and run the relevant container checks
from [Testing](TESTING.md). Installed-code inventories reject stale images.
GitHub [CI](CI.md) runs the full acceptance sequence.

Use tests that exercise the behavior and credible failure cases. Keep source,
executable, SDK, extension, and lock identities coherent. A Mago version string
alone cannot identify an unpatched versus patched executable. Record new
observations with their actual image and source rather than attributing an
older session to a newer candidate.

## Maintain documentation

When changing a command or configuration, update [Commands](COMMANDS.md), the
relevant workflow, and any affected quick start or troubleshooting entry.
When changing capabilities, update [Capabilities](CAPABILITIES.md) and
[Symfony coverage](RUNTIME-COVERAGE.md) against the actual execution path and
results. Keep default behavior, optional configuration, and earlier observations
unambiguous.

Documentation changes should check local links/anchors, command syntax, example
paths, and consistency across each scenario. Exercise changed setup/runtime
instructions when possible; report scenarios that were only source-reviewed.
Keep the README focused on first use and the [index](index.md) as the route to
detailed reference and historical evidence. Real command names remain exact;
headings and explanations should describe what users accomplish.

Preserve retained evidence bytes and manifest/checksum relationships. If an
explanatory report needs correction, make its revision scope clear and keep its
original observations attributable. Existing historical paths may remain in
place with clear labels. Draft upstream reports in [contribution records](UPSTREAM-CONTRIBUTIONS.md)
are research material; their presence is not evidence that a submission occurred.

## Describe a pull request

Explain the problem, resulting behavior or reader experience, relevant
validation, and material limits. State which checks were actually run and
which recorded results are historical. A model account or paid advisory call
is not needed to validate ordinary documentation changes or deterministic tests.
Include migration notes if changing public interfaces.

Retain licenses and attribution for reused material; see [Provenance](PROVENANCE.md).
