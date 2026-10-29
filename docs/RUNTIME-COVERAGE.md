# Symfony workflow coverage

Use [the workflow guide](WORKFLOWS.md) for ordinary development and
[capabilities](CAPABILITIES.md) for component-level support. This inventory
separates installed tools and accessible interfaces from the particular workflows
exercised by retained investigations. An unexercised task is an evidence gap,
not a prohibition on using the installed tools.

The [service investigation](SLICE-1.md), [command-generation task](SLICE-2.md),
[request-repair task](SLICE-3.md), and [LSP extension investigation](MAGO-LSP-EXTENSIONS.md)
retain actual requests, responses, source changes, and independent checks.
Scripted acceptance replays and agent-selected actions have separate records.

## Recorded workflow coverage

| Workflow | Installed | Agent-accessible path | Exercised evidence | Limits of the recorded coverage |
| --- | --- | --- | --- | --- |
| PHP/source work | Pinned Mago executable/SDK and Serena adapter | Mago CLI; host MCP → Serena REPL → Mago for bodies, definitions, references, hover and semantic edits | Service and command tasks inspect application/vendor declarations, rename/edit source, analyze/lint/fix and check formatting stability; request repair restores a controller method | Existing native findings remain visible. Completion, signature help and broad framework analysis parity are unproven. |
| Maker generation | Maker Bundle | `poc exec -- php bin/console make:*` | The command task discovers actual help and generates `app:tags:count` | Entity, form, migration and security generation have no new agent task proof. |
| Container/services | Mate Symfony extension and wiring worker | Mate `symfony-services`, `symfony-service-detail`; native `debug:container`; public Symfony-enriched Mago CLI | Compiled selected-service bindings and the wiring package's concrete Registry edge, with stale/absent/invalid/restored controls; the patched LSP separately demonstrates native graph contribution and Serena forwarding | Compiled dependency facts do not establish measured calls. The unpatched baseline omits external analyzers; patched LSP enrichment still needs workspace opt-in and export-plus-reload freshness. |
| Routing | Symfony Routing/Console | Symfony Console and real HTTP requests through the selected container | Existing Demo routes and recorded tag-filter request execute | No dedicated Mate route inspector is installed at this pin. Creating/debugging new routes is follow-on work. |
| Profiler/exceptions | Symfony profiler and Mate Symfony extension | Mate `symfony-profiler-list`, `symfony-profiler-get`; profile and collector resources | The request-repair task records failed and recovered responses with exact profile tokens, exception source and request metadata | A failure before profiling starts may have no profile. Reading a historical record never establishes current application health. |
| SQL/Doctrine | Doctrine ORM/Bundle and profiler collector | ORM repositories, Console commands and profile resources | The request-repair task reads the `db` collector: zero queries for the invalid field failure before execution, four queries for the recovered request | No new migration, schema change, query tuning or broad SQL-collector interpretation task is proved. |
| Logs | Official Monolog Mate extension | `monolog-search`, `monolog-context-search`, tail/file/channel tools | The request-repair task searches the selected dev logs and correlates exception/request evidence | Discovery of other log tools is availability evidence only unless the transcript records their use. Rotation, production aggregation and arbitrary log formats remain unproven. |
| Environment configuration | Mate core and Symfony Dotenv | Mate `server-info`, `symfony-dotenv-check`; selected-run dev environment and explicit context/directory maps | Runtime setup distinguishes the Mate CLI process from the application's HTTP evidence | `server-info` describes its own PHP process. No new secret/configuration repair or deployment-environment task is proved. |
| Framework resources | Symfony validators and Doctrine | Symfony `lint:yaml`, `lint:twig`, `lint:xliff`, `lint:translations`, `lint:container`; Doctrine schema validation | Original acceptance runs these native framework checks | No task mutates resource files or demonstrates agent repair of a resource-validation failure. |
| Tests | PHPUnit and independent verifier | Public selected-run execution; original identity inventory and complete manifest checks | Original suite identities are preserved; command and request-repair tasks separately report declared new tests and discovered combined totals, including defective/restored controls | Passing task tests does not establish every possible request or framework feature. |
| Database changes | SQLite and Doctrine | Owned development/test databases, fixtures, Doctrine Console | Workspace isolation and existing data; the command task counts empty/populated data with restored owned test database | No schema/migration authoring, data migration or alternate database backend task is proved. |
| Forms/security | Demo forms, authenticators/voters | Source tools, Symfony Console and tests | Original tests cover existing form/admin/user behavior; the service investigation inspects `TagsInputType` semantics/wiring | No new form, validation rule, authentication flow, authorization policy or security repair task is proved. |
| Browser/UI behavior | HTTP server and DomCrawler | Public selected-run HTTP execution and HTML assertions | Original controller tests and recorded tag-filter response/HTML behavior | No real browser automation, JavaScript interaction, layout, accessibility or visual regression exercise. |

## Runtime tool contracts

Mate and both Symfony/Monolog extensions are pinned to `0.15.0` in the declared
development overlay. Public commands select an owned run before entering its
container. `inspection-dev` maps to that application's dev profiler and log
directories; profiler tokens, URLs, times and log record metadata preserve the
observations' provenance. The exact installed discovery/schema capture belongs
to the [recorded request-repair evidence](SLICE-3.md), rather than newer online documentation.

`symfony-profiler-list` accepts bounded filtering by method, URL, status, time and
context. `symfony-profiler-get` selects a token. `resources:read` retrieves
`symfony-profiler://profile/{token}` or
`symfony-profiler://profile/{token}/{collector}`. Request headers supply the
token; selecting the newest unrelated profile is insufficient correlation.

`monolog-search` supports term/regex, level, channel, environment, time, limit
and `kernelContext`; `monolog-context-search` supports structured key/value,
level, environment, limit and `kernelContext`. The installed `monolog-tail`,
`monolog-list-files` and `monolog-list-channels` broaden access, but installation
alone earns no exercised status.

Historical runtime reads survive stale source and a failed application boot.
Compiled service/enriched analysis reads still require fresh preparation. Only
an explicit `poc mate-prepare` refreshes metadata; preserve the failed request's
runtime evidence first. See [runtime inspection](WORKFLOWS.md) for usage and the
[request-repair report](SLICE-3.md) for its recorded controls.

## Recorded request and test counts

The adaptive request-repair run preserved 53 original tests / 120 assertions
and recorded 54 tests / 134 assertions with its new regression test. Its
HTTP 200 → 500 → 200 sequence has distinct request markers and profiler tokens.
The separate scripted replay recorded 54 tests / 135 assertions. The report
explains that randomized tag/post associations affect assertion counts; these
are different observations, not competing canonical totals.

An invalid-service control returned HTTP 500 before profiling started, with no
new token, while the earlier failed request's profile and logs remained readable.
See [the original observations](SLICE-3.md#fresh-adaptive-evidence). The recorded
CLI enrichment and source queries are independent of the later patched LSP
extension experiment; neither report substitutes for the other's evidence.
