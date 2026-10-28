# Slice 2: generate and verify a Symfony command

The disposable task implements `app:tags:count` using the existing
`App\Repository\TagRepository`. Its contract is deliberately small: count all
persisted `Tag` rows, write exactly `Tag count: N` followed by one newline, and
return success (`0`). It adds no application arguments or options. The original
Demo fixture, provenance locks, original tests and global integrity verifier are
unchanged. The command and two focused tests live in the declared
[task outputs](../fixtures/slice2/task.json), and are installed only in an owned
task workspace.

The [fresh adaptive exercise](evidence/slice2/fresh-agent/result.json) passes.
The separate [exact-image integrated validation](evidence/slice2/integration/validation.json)
also passes at `9e74151804e5e30f7b55d4e66cf09dd9ff0f7389`: 148 fast tests,
31 original acceptance checks, nine slice-1 stages and all 12 slice-2 stages.
Its [retained artifact manifest](evidence/slice2/integration/manifest.json)
binds the raw reports, image/source identities, public graph, PHPUnit results
and reviewed final task diff. Hosted CI duration and artifacts are reported in
the integrated PR's verification record.
The actual coding agent inspected installed Maker help, generated the command,
queried the generated class, `TagRepository`, Doctrine's inherited `count`, and
the installed command-test facilities through the real **host MCP → Serena REPL
→ Mago** route. After reading those results it changed the class with
`s.edit.replace_symbol_body` and inserted its repository import with
`s.edit.insert_before_symbol`. The
[raw MCP requests/results](evidence/slice2/fresh-agent/mcp/mcp.jsonl) and
[adaptive decisions](evidence/slice2/fresh-agent/chronology.json) retain both
successful operations and failed exploratory requests.

Ordinary edits were needed for import cleanup, the file-header `strict_types`
declaration suggested by Mago, and creating a test file which had no existing
symbol. An initial cleanup regex had incorrect backslash escaping; the agent
used exact literal replacements after observing the error. An initial
`lint --fix --reporting-format json` call returned native exit `2`: this pinned
CLI forbids combining those flags. The corrected scoped `lint --fix` call
returned `0`; its inspected diff is empty because no safe fix applies to the
final files. Native formatting reordered imports and normalized the generated
constructor layout, and subsequent check/write passes were stable. Those
adjustments are limited to the two task PHP files.

## Observed behavior and framework contribution

| Check | Fresh exercise result |
| --- | --- |
| Actual Maker | `php bin/console make:command app:tags:count --no-interaction`; generates `src/Command/TagsCountCommand.php` |
| Focused PHPUnit | 2 tests / 4 assertions: empty database and three persisted tags |
| Real Console processes | `Tag count: 0\n` and `Tag count: 3\n`, both exit `0`; the owned test database is restored afterwards |
| Full application suite | 55 tests / 124 assertions |
| Original identities within that suite | All original 53 tests / 120 assertions pass with exact class/method/dataset/file/line identities and unchanged original test/configuration hashes |
| Defective/restored feature control | Count-plus-one variant fails both output assertions with exit `1`; restoring exact source passes 2 tests / 4 assertions |
| Full native Mago reports | Existing 35 analyzer / 125 lint findings retained; complete diagnostic multisets match before/after, with no introduced/removed finding and no finding on the new command/test |
| Public Symfony-enriched Mago | Native exit `1` retained as `findings`; all 48 source/test hosts covered, with installed vendor context |

The full suite's total is discovered from PHPUnit, not fixed to the old `53`.
The unchanged original verifier checks the complete new suite, then an explicit
retained projection of the same JUnit result checks the exact original identity
set separately. The original baseline also runs before generation. The two new
test identities and assertions are reported separately. The `slice2` PHPUnit
group supports focused execution without editing original suite configuration.

Mate and native `debug:container --env=dev --format=json` agree that the generated
command is registered with the `console.command` tag and that constructor
parameter `tags` binds to `App\Repository\TagRepository`. Symfony may describe
this private command service as removed/inlined in its compiled view; its command
registration, explicit dependency binding and actual execution are independently
verified.

The real public enriched command consumes freshly exported metadata. Mago's own
graph contains the command's native **Signature** reference to `TagRepository`;
the wiring extension adds the repository constructor's **Body** reference to
`Doctrine\Bundle\DoctrineBundle\Registry`, the concrete implementation of its
`ManagerRegistry` dependency. The package's completion attestation and the
[selected final graph](evidence/slice2/fresh-agent/public-graph.json) are retained
alongside the [native invocation](evidence/slice2/fresh-agent/public-invocation.json).
The existing native signature makes an extra direct command-to-repository Body
edge redundant. These are compiled dependency facts, not measured runtime calls.

## Reproduction

```sh
uv sync --frozen --python 3.12.12
# Build the current checkout once before acceptance, or reuse its verified image.
docker buildx build --load -t mago-serena-poc:local .

# Independent fresh task replay and acceptance; keep its app available to inspect.
./bin/poc slice2 --run slice2-acceptance --keep-running

# Explicit metadata refresh after an intentional source/dependency change.
./bin/poc mate-prepare --run slice2-acceptance
./bin/poc mago-enriched --run slice2-acceptance \
  --symbol 'App\Command\TagsCountCommand' \
  --symbol 'App\Repository\TagRepository' -- analyze --reporting-format json
# Native findings on this application deliberately return status 1.
./bin/mago --run slice2-acceptance -- analyze --reporting-format json
./bin/poc exec --run slice2-acceptance -- php vendor/bin/phpunit \
  --configuration phpunit.dist.xml --group slice2
./bin/poc exec --run slice2-acceptance -- env APP_ENV=test APP_DEBUG=1 \
  php bin/console app:tags:count --no-interaction --no-ansi
./bin/poc down --run slice2-acceptance
```

The replay starts with a fresh owned workspace, prepares the supported overlay,
records original source/dependency/tool/test identities and full native reports,
discovers Maker options from installed help, and retains the actual generated
skeleton before applying the two declared task outputs. It verifies safe fixes,
scoped formatting and stability, native diagnostic deltas, real semantic replay,
stale rejection by the public enriched interface, explicit refresh, compiled
bindings, actual command execution, focused/full tests, the defective/restored
control, and exact final task integrity. Commands select the workspace through
the checkout-derived root even when launched from another working directory.
An existing workspace containing the task output is rejected; use a new run ID
to reproduce from a clean starting point.

Each attempt is retained under
`artifacts/<run>/slice2/attempt-<uuid>/results.json`; its `source.json`, run ID,
workspace, attempt ID and `source_context_sha256` bind every stage. Raw native
reports, tool exits, generated/final source, diffs, preparation identities,
MCP transcripts, JUnit inventories and failures remain beside it or in the
run's retained Mago/Mate invocation directories. `slice2-result.json` is the
latest summary. Stage failures retain `<stage>-error.txt` for the repaired Jev
collector. No provider request is needed for this acceptance.

## Fresh agent versus replay

The recorded fresh session is `b-slice2-20261028`, beginning from source revision
`8f154f798d7cf9ae7cf3cb33b0b99352de99dec4`. It reused the compatible immutable
base image and installed the declared Composer overlay in its own app. While
Agent A finished the public interface, the agent explicitly reconciled only the
disposable `.mago` observer/config to A's implementation, refreshed metadata and
then consumed A's real public command. The prior config bytes, initial complete
application manifest, later manifest delta, image identity and preparation are
retained. This is separate from the final integrated exact-image acceptance.

`./bin/poc slice2` is **scripted replay**, not another fresh agent success. It
first validates the bounded
[fresh-agent artifact index](evidence/slice2/fresh-agent/index.json), all retained
artifact hashes, semantic retrieval followed by an actual successful semantic
edit, pinned executable/SDK identity, the real public analysis and exact final
command/test hashes. Missing or changed fresh evidence cannot make the replay
pass. Independent checks compare the full diagnostic bodies rather than using
unchanged counts as a proxy for regression freedom.

For a new adaptive session, follow the
[task instructions](slice2-agent-task.txt) in a new disposable workspace and
retain its own requests/results and final output; do not count replaying the
committed final files as a fresh exercise.

The experimental Mago executable and SDK remain at source
`46df50c96d93d0ac3655c116c375574277cf0b30` (`1.58.2`). Native Serena/Mago navigation
and edits are demonstrated; the pinned LSP still does not start external analyzer
workers. CLI enrichment is therefore separately attributed, and no enriched LSP
result is claimed. Existing slice-1 calibrations, rename/full-sync/stale-span
evidence and original acceptance remain independently runnable. Slice 3 remains
later work.
