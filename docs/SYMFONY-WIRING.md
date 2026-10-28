# Symfony wiring in Mago slice 1

The existing `App\Form\Type\TagsInputType` receives `TagRepository $tags` at
`src/Form/Type/TagsInputType.php:34`. `PostType` selects that form type. `TagsInputType::buildForm` adds the
collection/string transformers, and `buildView` reads `$tags->findAll()`.
The repository takes Doctrine's `ManagerRegistry` interface at
`src/Repository/TagRepository.php:31` and supplies `Tag::class` to its parent.
Serena/Mago establishes those source relationships; Mate establishes the compiled
service bindings. [Semantic proof](SERVICE-SEMANTICS.md) records the actual REPL calls.

The dev container binds `TagsInputType` argument `tags` to service
`App\Repository\TagRepository`, whose class has the same name. That repository's
`registry` argument refers to service `doctrine`, implemented by
`Doctrine\Bundle\DoctrineBundle\Registry`. Mate's installed
`symfony-service-detail` tool reports both argument names/IDs; native
`debug:container --env=dev` corroborates the selected service and dependency.
This is compiled dev configuration, not a claim about a measured request.

## Coherent executable, SDK and package

The LSP and CLI retain experimental Mago
`46df50c96d93d0ac3655c116c375574277cf0b30` (`1.58.2`, MANA 2.1). The declared
Composer package repository installs the SDK from **that exact source revision**,
with no packaged binary launcher. Every tool invocation uses `/usr/local/bin/mago`.
It therefore cannot silently download stable 1.59.0, whose MANA 2.2 worker would
be incompatible. This is a deliberately identified experimental SDK package,
not a claim that stable `1.58.2` is identical.

The [overlay](../fixtures/mate/overlay.json) adds Mate and its Symfony extension
at `0.15.0`, SDK, Revolt, and
[`Byte-Kitsune/mago-symfony-wiring` at `28c3f54`](https://github.com/Byte-Kitsune/mago-symfony-wiring/tree/28c3f54065b71fe046a7474ced401aeadc941b0f).
That development snapshot identifies its extension as `1.3.0-RC1`. Its supported
PHP reference backend is explicitly selected with `MAGO_EXTENSION_BACKEND=php`;
no native engine asset download is required. Its `nikic/php-parser ^5.9`
requirement accounts for the overlay's single existing-package update,
`5.7.0 → 5.9.0`. All other existing package versions remain locked.

## Demonstrated contribution

The same healthy PHP source, vendor dependencies, config and compiled reference
were analyzed with the wiring package off and on. The small
[after-analysis observer](../fixtures/mago/extensions.php) queries Mago's own
`SymbolReferences` and `Codebase` APIs; it contributes no graph edges and performs
no parsing. Both runs retain the complete source set, including the selected
service, dependency and caller.

| Control | Actual result |
| --- | --- |
| Extension off | `TagRepository::__construct → ManagerRegistry` native Signature edge; no concrete Registry edge |
| Extension on | Adds `TagRepository::__construct → Doctrine\Bundle\DoctrineBundle\Registry` Body edge |
| Invalid compiled binding | Replacing the repository argument's service ID with an unresolved ID removes that concrete edge; no invented class |
| Restored binding | Concrete Registry edge returns on the unchanged PHP source |
| Direct selected-service edge | `TagsInputType → TagRepository` is unchanged: Mago's graph intentionally suppresses matching Body edges when a Signature edge exists |
| Active execution | Package `analysis-attestation` note reports complete service map and 34 source files; the observer independently records the final graph |

The invalid map is an explicitly labelled disposable package control, not a
fresh Symfony export. The ordinary host freshness guard rejects its changed
bytes before a framework read. All source/reference/instruction bytes are
restored after controls. The original application still reports 30 native
analyzer diagnostics in this source-only snapshot with either package state;
these findings are retained, not suppressed or called clean.

A graph Body edge establishes a framework-known dependency reference. It does
not prove a runtime call occurred or that every service is reachable. The
pinned LSP does not initialize external analyzers: the CLI contribution does
not reach Serena through this server revision. [The live propagation control](SERVICE-SEMANTICS.md)
separates that server integration gap from SDK/package execution and adapter
exposure.

## Commands and freshness

```sh
./bin/poc up --run slice1-dev --no-build
./bin/poc mate-prepare --run slice1-dev
./bin/poc mago-enriched --run slice1-dev \
  --symbol='App\Repository\TagRepository' -- analyze --reporting-format json
# Equivalent public Mago profile; default profile remains native:
./bin/mago --run slice1-dev --profile symfony \
  --symbol='App\Repository\TagRepository' -- analyze --reporting-format json
# Same application/preparation, explicitly disable the wiring contribution:
./bin/poc mago-enriched --run slice1-dev --extension-off -- analyze --reporting-format json
./bin/mate --run slice1-dev -- tools:list --format=json
./bin/mate --run slice1-dev -- tools:inspect symfony-service-detail --format=json
./bin/mate --run slice1-dev -- tools:call symfony-service-detail \
  --id='App\Form\Type\TagsInputType' --context=inspection-dev --format=json
./bin/poc slice1
# Also proves a source change is rejected, then analyzed after explicit refresh:
.venv/bin/python tests/integration/enriched_analysis.py --run slice1-dev
```

`mago-enriched` is the ordinary run-bound CLI analysis path, independent of the
acceptance harness and caller's current directory. It analyzes all `src/` and
`tests/`, with `vendor/` declarations, using the matched executable/SDK and the
installed wiring worker. Repeat `--symbol=Fully\Qualified\Class` to observe up
to eight selected constructor reference sets through Mago's own Codebase and
SymbolReferences APIs. Missing declarations are represented as `null`; the
observer does not parse PHP or add edges. The original slice-1 observer fields
remain available so its separate controls still run unchanged.

Preparation installs both native and enriched configurations before sealing the
complete application/dependency state. Source edits, dependency changes, missing
or changed compiled XML/reference, another workspace/container, a mismatched SDK
source, or changed extension configuration prevent an enriched read. Run
`./bin/poc mate-prepare --run RUN` explicitly after an intentional source change.
An absent/stale preparation returns **3** with that refresh instruction and no
native diagnostics; a completed native analysis retains its real exit and
diagnostic bytes. Existing application findings still return **1**. If the
native process exits 0/1 but its required graph/attestation is absent, malformed
or incomplete, the wrapper returns **3**, reports the reason on stderr and keeps
the unmodified `native_exit` in evidence. Other native failure exits remain
unchanged. Native
analysis remains `./bin/poc mago --run RUN -- analyze --reporting-format json`.

Each enriched invocation retains `stdout`, `stderr`, `graph.json` and
`invocation.json` under `artifacts/RUN/mago/enriched/UUID/`. The JSON identifies
`run_id`, `host_workspace`, `preparation_id`, preparation/source/config/dependency
hashes, `native_exit`, public `exit`, `status` (`clean`, `findings`,
`stale_preparation`, or `tool_failure`), exact argv, selected symbols and evidence
paths. `graph.json` contains the final native source/test inventory and
`symbols[FQCN]` declaration/constructor references. The on/off controls now invoke
this public command from `/tmp`; changed/absent facts are also rejected through
it. The invalid-binding graph remains a labelled direct package probe because
the public freshness guard correctly refuses fabricated compiled facts.

This interface enriches CLI analysis only. It does not change the known pinned
LSP external-worker startup boundary or claim framework-enriched Serena results.

`mate-prepare` installs the declared lock without plugins/scripts, preserves
existing owner `AGENTS.md`/`CLAUDE.md` text outside Mate's managed blocks,
initializes/discovers installed schemas, explicitly compiles `dev`, sanitizes
the two Console service views using the package's exporter, and seals source,
dependency, metadata, reference and container identities in trusted run state.
The generated `mate/AGENT_INSTRUCTIONS.md` is Mate's discovery aggregate;
owner instructions belong outside that generated artifact.

Raw service views can contain scalar configuration, so they remain private in
disposable state. Retained evidence includes their hashes, exact exporter argv
and the sanitized reference. Reads reject missing service, wrong project/run or
workspace, changed source/dependencies, absent/stale XML, changed/absent reference,
and replaced container. Explicit `mate-prepare` is the recovery after changes;
readable stale dumps never establish current framework-aware analysis.

The local review found and fixed an early host-guard defect: Symfony Console
accepts `tools:ca` as an abbreviation for `tools:call`, while the initial guard
recognized only exact data-command names. The fixed wrapper exempts only exact
metadata-independent discovery/help commands; all other command names require
fresh preparation. A real stale-source control now checks both spellings and
requires rejection before either returns data. This was a local PoC wrapper
defect, with no upstream attribution.

[Framework evidence](evidence/slice1/framework/result.json) records the first
complete real framework run and its controls. Its per-command/graph snapshots
sit alongside it; full successful and failed attempts remain in ignored
`artifacts/`. Later integrated slice evidence records any subsequent run.
