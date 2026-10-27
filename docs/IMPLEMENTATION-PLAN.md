# Serena v2 REPL + Mago LSP: Symfony Demo PoC
Implementation handoff for Sol Ultra · prepared 2026-10-27

## 1. Goal and scope

Implement the PoC in https://github.com/xormania/mago-serena_v2-poc.

Prove that an agent can use Serena's v2 REPL over MCP to navigate and modify the official Symfony Demo application, with the experimental Mago LSP providing PHP semantics inside Docker. Demonstrate correct results, observable failures, and a reproducible way to report integration defects to either project.

This document is a plan. Repository and upstream source were inspected; the proposed stack has not been built or executed during planning. No runtime result below is claimed as a pass.

Start with a small working vertical slice. Keep the adapter outside Serena using its existing extension mechanism. Add a narrowly scoped upstream patch only if an observed incompatibility makes it necessary. There is no need to build a general command router, agent orchestrator, editor extension, or new MCP server: Serena already supplies the MCP interface, and Docker supplies the process boundary.

The primary deliverables are a runnable development container, an external Mago adapter, an automated acceptance harness, one real agent exercise, and a short evidence-backed findings report. Symfony Mate can be explored later; it is not required to establish this integration.

## 2. Starting point and pinned inputs

The target repository currently contains its MIT LICENSE only, on `master`, at `16a92a2596acb4dc3532c9b285de3ea0dbad0989`.

Use these inspected commits as the starting lock. Recheck them before implementation; if changing a pin, record why and rerun the affected checks. Do not build from a moving branch name.

| Component | Starting revision | Purpose |
| --- | --- | --- |
| Symfony Demo | `8d2e2ef75c3e18df173d8bf2379a14abb58c4c31` | Actual application and original tests |
| Serena, current `main` | `9e1cced0c34ed48d668e179f7c56c77b4d14a3e3` | v2 REPL, MCP server, SolidLSP |
| Mago, `next-server` | `46df50c96d93d0ac3655c116c375574277cf0b30` | Experimental LSP and matching CLI |
| Symfony Docker | `92d0d49293cd8678d82ca57c9c81b2dc45cf5561` | Reference for development Docker setup; adapt only what is needed |
| Earlier fixture, `uscient/agentscient-test-repo` | `7d1abb3c4ac01451d83e1c1e12742b9fa2067561` | Provenance and fixture lessons, not the application source or workflow |

Runtime decisions:

- Start with PHP 8.5 and SQLite. Demo's Composer manifest requires PHP >=8.4 and targets Symfony 8.1; its current test workflow exercises PHP 8.4 and 8.5. Follow Composer and the lockfile rather than the older PHP requirement in its README. Do not upgrade the application's framework as part of this PoC.
- Install Serena and the adapter in one isolated Python environment. Select a Python version supported by Serena's pinned manifest and pin it, uv, and resolved dependencies.
- Build Mago from the exact source commit with its lockfile. This commit declares Rust 1.99.0. Check toolchain availability early; do not quietly lower its manifest requirement or substitute stable Mago. Pin the actual compatible toolchain.
- Mago starts as `MAGO_EXPERIMENTAL_SERVER=1 mago language-server`, speaking LSP over stdio. Keep its analyzer enabled.
- Record image digests, PHP/Composer/Python/Rust versions, dependency lock hashes, adapter revision, and Mago source SHA. Mago's version string alone does not identify this experimental server.
- Preserve the Demo's license and headers, and third-party license notices for incorporated Docker definitions and tools. The PoC repository's MIT license does not replace upstream licenses.

## 3. Reuse the user's previous Symfony Demo work selectively

The earlier Agentscient acceptance fixture used the same official Demo commit proposed here. Its [provenance](https://github.com/uscient/agentscient-test-repo/blob/7d1abb3c4ac01451d83e1c1e12742b9fa2067561/docs/PROVENANCE.md) records two directly useful adaptations:

1. Copy, rather than rename, `.env.local.demo` during repeatable environment setup.
2. Give seeded comments past timestamps. The official fixture currently uses `now + ... seconds`; the prior fixture uses `now - ... seconds` because loading fresh fixtures immediately before the original new-comment test can otherwise fail.

Reproduce the comment issue on the chosen baseline, then carry the small documented adaptation if needed. Retain the original test assertions. Keep these changes in an explicit patch/provenance manifest so the application baseline remains understandable.

Also reuse the earlier approach of fresh databases, independent expectations, disposable workspaces, and source-integrity checks. Earlier reported test totals are historical context, not acceptance thresholds for this repository; discover and report the actual suite here.

Do not import the earlier fixture's CO/XO roles, private runtime dependencies, credentials, Jev configuration, greeting exercise, or repository-specific agent instructions. UXor's custom demo is a separate application; use official Symfony Demo for this PoC.

## 4. Repository strategy and future MinSpec reuse

**Recommendation: do not create another general-purpose test repository for this PoC yet.** Keep the initial integration in `xormania/mago-serena_v2-poc`, but make its application fixture easy for another consumer to use.

The existing [MinSpec Workbench](https://github.com/minspec/workbench) describes itself as the Symfony integration host for packages and recipes. [Workbench Fixtures](https://github.com/minspec/workbench-fixtures) describes a centralized dev-only fixture profile registry. These are relevant precedents. MinSpec Rebirth leaves exact package boundaries open, so neither repository's old structure or governance should become a prerequisite for this PoC.

Maintain a clear split within this repository:

| Reusable fixture material | Serena/Mago integration material |
| --- | --- |
| Official Demo source pin, provenance, minimal setup patches | Toolchain pins and Docker development tooling |
| Application dependency lock and database/reset procedure | External SolidLSP adapter and Serena/Mago configuration |
| Named coding scenarios and independently specified expected outcomes | MCP/LSP protocol probes and integration-specific assertions |
| Application integrity and behavioral checks | Backend identity, session/restart checks and tool transcripts |

The fixture should be usable without Serena, Mago or an agent orchestrator. Describe its setup/reset/check contract and versions explicitly. Keep generated run evidence outside its source.

When a second active consumer needs the same fixture and scenarios, extract that contract into the refreshed MinSpec fixture system and have consumers pin a revision. Each consumer still creates its own disposable workspace. Avoid maintaining parallel edited copies of the Demo or sharing a live mutable checkout.

If MinSpec ultimately needs a separate repository for full application testbeds, establish that as a deliberate boundary alongside its fixture-package registry. Do not assume that a full Demo application and installable fixture profiles are the same kind of artifact.

For Sol's present assignment: no new repository is required, and no changes to existing MinSpec repositories are requested. Implement the separation above here; do not expand the PoC into a MinSpec migration.

## 5. Runtime design

Use one long-running development service, named `php`, containing PHP, Serena, the adapter, and Mago. Serena launches Mago as a child process. Both see the Demo at `/app`.

| Surface | Location and contract |
| --- | --- |
| Host agent/editor | Opens this repository; launches the MCP process through the repository wrapper |
| Host MCP wrapper | Uses Compose exec with `-T`, explicit project/config paths and working directory `/app`; stdout is MCP only |
| Container Serena process | Explicit REPL mode; project root `/app`; adapter installed in the same Python environment |
| Container Mago process | Same filesystem, workspace root and dependency tree; stdio stays between SolidLSP and Mago |
| PHP commands and tests | Run in the same development service and application directory |
| Source/dependencies | Bind-mounted Demo workspace; one visible `/app/vendor` tree |
| State and output | Deliberately scoped `var`, Serena state/cache, and evidence paths; isolated per acceptance run |

Implement the host wrapper as a normal executable with argument-safe forwarding, not a shell string assembled from agent input. Resolve paths relative to the wrapper so it works from another host directory and from a checkout path containing spaces. Diagnostics go to stderr. A stopped container should produce an actionable error; a separate `up` command handles lifecycle.

Keep MCP on stdio for the initial PoC. No host/container URI translation should be required for LSP traffic. Document the host `app/` to container `/app` mapping for native agent file operations.

Do not mount the Docker socket. Do not expose unauthenticated network MCP. Serena's REPL runs Python with the process's privileges: API inclusion/exclusion and read-only settings are steering, not an isolation boundary. Run with a practical non-root identity, correct workspace ownership, and only required mounts. Do not mount host credentials by default.

Avoid accidentally inheriting anonymous volumes that make two containers see different `var` or `vendor` contents. Use the same running service for application commands; give automated runs unique Compose project names and disposable application copies. Cleanup must target only the run it created.

## 6. Proposed repository layout

These paths and commands are implementation targets, not existing files.

| Path | Contents |
| --- | --- |
| `app/` | Pinned official Demo snapshot, original license and tests, documented minimal fixture adaptations |
| `docker/`, `Dockerfile`, `compose.yaml` | Development image, entrypoint, process and volume configuration |
| `adapter/` | Small installable Python package registering the Mago SolidLSP backend |
| `config/` | Serena defaults, project-config template and Mago configuration |
| `fixtures/semantic/` | Tiny PHP cases with known answers for inheritance, rename, diagnostics and position encoding |
| `tests/integration/` | Direct LSP probes, real MCP client, expectations and reset/lifecycle helpers |
| `bin/poc` | Entry point for setup, checks, evidence and cleanup |
| `bin/serena-mcp` | Host-facing stdio wrapper suitable for an MCP client's command configuration |
| `docs/` | Provenance, architecture, capability matrix, agent exercise and findings |
| `toolchain.lock.json` | Exact upstream/toolchain/dependency identity |
| `.github/workflows/poc.yml` | Docker integration checks and evidence artifacts |
| `artifacts/`, `workspaces/` | Ignored outputs and disposable runs |

Keep imported Demo content separate from the PoC harness. Capture a checksum manifest of original application files plus an explicit list of intended adaptations/additions. Acceptance runs must not rewrite the checked-in baseline.

Provide these command contracts, with help and meaningful exit codes:

- `./bin/poc up`: build/start the default development environment and report readiness.
- `./bin/poc doctor`: show selected versions, paths, backend, and relevant dependency/readiness checks.
- `./bin/poc test`: create an isolated run, execute automated acceptance, and write human- and machine-readable results.
- `./bin/serena-mcp`: launch Serena over stdio in that environment.
- `./bin/poc agent-task`: prepare the disposable real-agent exercise and print its instructions and exact MCP launch configuration.
- `./bin/poc report <run-id>`: summarize recorded evidence without inventing missing results.
- `./bin/poc down`: stop the selected environment; removal of its disposable data is an explicit option.

Sol may simplify filenames or combine scripts when this makes implementation clearer, while preserving the contracts.

## 7. Implementation sequence

### Milestone A — Reproducible Demo baseline

Import the official Demo snapshot and preserve provenance. Add the minimal Docker setup and pinned dependencies. Ensure Composer setup is repeatable without deleting tracked seed files. Build fresh SQLite databases using the application's actual test configuration and fixture setup.

Run the original Demo PHPUnit suite, inspect its existing lint/static-analysis workflow, and establish which checks belong in this integration's CI. Include a basic HTTP check of the running Demo. Record any baseline failure before changing it; reproduce the timestamp issue before applying the documented correction.

**Exit evidence:** two independent fresh-workspace/database runs pass the original PHPUnit suite; the Demo responds; runtime identity and all baseline adaptations are recorded. Do not hard-code a historical test count.

### Milestone B — First end-to-end semantic query

Build and launch the pinned Mago server. First use a small direct LSP client to establish initialize/initialized, workspace loading, document opening and a meaningful symbol response. Capture advertised capabilities and server stderr.

Then add the external adapter. Serena documents the `solidlsp.language_server_registration` entry-point group and `ExternalLanguageServerId`. Register a distinct key such as `mago`, install it alongside Serena, and select it explicitly in project configuration. No implicit fallback to another PHP server.

Start Serena in REPL mode using the pinned release's actual CLI/configuration. The MCP harness must initialize a real connection, discover tools, obtain the session through `initial_instructions`, and call `serena_repl` with that session. Use `s.info("lsp")` to obtain the live API contract.

Perform a symbol overview and find `PostRepository/findLatest` in `src/Repository/PostRepository.php`. Demonstrate a persisted Python variable across two REPL calls in the same session and report the resulting value through the final expression, as Serena requires.

**Exit evidence:** a real MCP transcript, corresponding LSP activity, selected backend/process identity, and an assertion locating the expected Demo symbol. A direct Python import or direct LSP call alone does not satisfy this milestone.

### Milestone C — Correct adapter behavior

Use SolidLSP's existing facilities where possible. Inspect and bridge only actual incompatibilities:

- Initialization root URI/workspace folders, process environment, startup readiness and clean shutdown.
- Document synchronization according to the negotiated capabilities; the selected Mago implementation uses full-document synchronization.
- Hierarchical document symbols, declaration/name selection ranges and full symbol/body ranges.
- Definitions/declarations, references, implementations and dependency navigation exposed by Serena.
- Rename WorkspaceEdits, including supported `changes` / `documentChanges` forms and version checks.
- Published diagnostics, completion/readiness of queries, cancellation, errors and bounded timeouts.
- Position encoding: honor the negotiated LSP encoding. Test non-ASCII and non-BMP text and CRLF; do not pass Mago core byte offsets directly into Serena edit ranges.
- File updates originating through Serena and outside it, stale symbol objects, server restart and unexpected server death.

Explicitly configure Mago's PHP target and source/dependency paths. Include Composer dependencies for analysis/navigation while excluding generated caches appropriately. Verify the pinned configuration schema rather than assuming config keys from another Mago version. Distinguish an LSP dependency-resolution defect from a Serena vendor-ignore policy.

Configure `included_apis` / `excluded_apis` for REPL access where needed; classic tool inclusion/exclusion does not configure REPL facades. Keep shell access available only as needed for ordinary in-container project checks; it is not a substitute for semantic proof.

**Exit evidence:** the core acceptance matrix below runs through real MCP/REPL calls. Any necessary Serena or Mago patch is small, pinned, separately documented, and accompanied by its minimal reproduction.

### Milestone D — Automation and failure evidence

Add a portable automated runner and GitHub Actions job using Docker. Run original application tests and integration checks from clean state. Use readiness conditions with bounded deadlines, not fixed sleeps. Cache builds using exact source/dependency identities.

Store a concise JSON result record and readable report for each scenario, including status, assertion, elapsed time, relevant versions, and paths to logs/diffs. Preserve diagnostics and selected protocol traces on failure. Redact credentials; avoid logging full environments.

Use explicit statuses: `pass`, `fail`, `blocked`, `not_exercised`. A skipped or unsupported requirement is not a pass. Distinguish a negative test that successfully observes the expected error from an unexpected failed check. Required core failures or blocks must prevent a green core result.

Include negative controls: a missing/wrong Mago executable must fail the backend check, and an intentionally wrong symbol expectation must fail the verifier. Tests should establish observable behavior, not merely mirror adapter implementation.

**Exit evidence:** a clean CI run proves the Docker/MCP integration without paid model credentials. If the implementation environment lacks Docker, use available CI execution and provide the local command; report anything still unrun accurately.

### Milestone E — One real agent session and upstream findings

Run the task in section 9 with a supported authenticated agent harness if available. Record the harness/model and transcript. Deterministic MCP automation and a real model-driven session are separate evidence.

If no authenticated harness is available, finish and validate the deterministic path, provide a ready-to-run task for xor, and mark the real-agent result pending. Do not fabricate a transcript or declare full real-agent acceptance.

Write a capability matrix and a short findings report. For defects, include a minimal PHP reproduction, exact revisions, expected/actual behavior, and the narrowest relevant protocol trace. Identify whether evidence points to Mago, the adapter, Serena, or environment setup; leave uncertain attribution explicit.

Prepare material useful to both upstream projects. Do not automatically open upstream issues, send messages, or publish upstream PRs.

## 8. Acceptance matrix

Core rows are required for a claim that the complete PoC works. An experimental limitation may be a useful result, but it must remain visible as a limitation.

| Scenario | Independent expected result | Route |
| --- | --- | --- |
| Demo symbols | `PostRepository/findLatest` and `BlogController/index` resolve to their actual declarations and source ranges | MCP → REPL → Mago |
| Cross-file references | The call from `BlogController::index` to `PostRepository::findLatest` is found; expected locations are derived from pinned source | MCP → REPL → Mago |
| Composer navigation | Resolve a selected imported Symfony/Doctrine declaration into the installed `vendor` tree, with documented Serena lookup policy | Direct LSP plus the available REPL navigation path |
| Demo rename | Rename `findLatest` to `findLatestPublished` on a disposable copy; update exactly the declaration and genuine PHP callers; original application tests still pass | REPL rename, independent diff/test verifier |
| Interface/inheritance | Tiny controlled fixture demonstrates declaration, implementation and reference relationships; valid member rename updates the expected family | MCP → REPL → Mago |
| Invalid rename | A deliberately colliding/invalid rename is refused with useful feedback and leaves files unchanged | MCP → REPL → Mago |
| Semantic body edit | Replace a small fixture method body through Serena's edit API; assert exact changed range and runtime behavior | REPL edit, fresh semantic query, PHP assertion |
| Position accuracy | Emoji/non-BMP text and CRLF before a target do not shift navigation or edit ranges | Protocol and file-content assertions |
| Diagnostics | A deliberately introduced known syntax/type error appears for the correct file/range; removing it clears that error | REPL diagnostic API with real LSP publication |
| External edit | Change a file outside Serena, then a fresh semantic query observes the current content | Container filesystem edit → fresh REPL query |
| REPL persistence | Variables survive same-session calls; a new process/session does not silently reuse prior namespace state | Actual MCP sessions |
| Partial execution | A cell that mutates a disposable fixture then raises leaves an observable mutation; the recovery procedure inspects state before retry | REPL plus independent hash/diff |
| Restart and death | Explicit restart establishes a working server; killed server yields a bounded, intelligible failure and recoverable fresh state | Process identity and fresh MCP query |
| Workspace isolation | Two runs have separate files/state/databases; cleanup of one does not affect the other | Runner and application tests |

Use small controlled PHP fixtures for exact set/range assertions. The Demo supplies realistic application behavior; its randomized fixture data should not be treated as a deterministic oracle. Keep pre-existing Mago diagnostics distinct from deliberately introduced ones; do not require an unverified zero-warning baseline or hide new errors under a blanket suppression.

For every feature, distinguish:

1. Advertised by Mago.
2. Verified by a direct LSP request.
3. Integrated through the adapter.
4. Exposed by Serena's current REPL.
5. Verified end to end.

Serena's current LSP facade includes symbol lookup, references, implementations, declaration lookup, diagnostics, rename and restart. Do not claim every Mago capability is available through it. Probe call hierarchy, type hierarchy, completion, hover, formatting and code actions as a secondary report where useful. Missing REPL exposure of those features need not expand this PoC into a large Serena fork.

A separate Phpactor control run can help locate a failure if necessary. Label it separately; it must never silently replace Mago or turn a Mago failure green.

## 9. Real-agent exercise

Use a fresh disposable Demo copy with the baseline tests passing. Give the agent this bounded task:

> Use the configured Serena REPL and its Mago backend to locate PostRepository::findLatest, identify its PHP callers, and rename it to findLatestPublished. Preserve all existing behavior. Show the references and symbol information that informed the edit, perform the semantic rename through Serena, re-query after the change, inspect the diff, and run the original Demo tests in the container. Report the exact files changed and any integration problem.

The verifier, outside the agent session, checks the expected diff, new/old references, source integrity and test results. The task prompt must not expose the verifier's exact expected line numbers or reference list.

Record that the agent used the REPL for meaningful semantic operations; a task completed entirely through text replacement does not prove the integration. Normal shell access for PHPUnit and inspection is fine. Do not impose a global MCP-only workflow.

After the exercise, retain the diff and transcript as evidence and discard the disposable application copy. The Demo snapshot in the PoC remains unchanged. Additional feature work can follow once this task establishes the core path.

## 10. Completion and handoff

The implementation is ready to review when:

- A clean clone has a short, accurate quickstart and explicit prerequisites.
- The pinned stack builds and the original Demo tests pass from fresh state.
- Automated core checks exercise real MCP, real Serena REPL and real Mago, with backend identity proved.
- Results identify passed, failed, blocked and unexercised capabilities.
- The real-agent task is either evidenced or explicitly pending with exact run instructions.
- Changes to upstream software, if any, are isolated and reproducible.
- Documentation includes fixture provenance, licenses, architecture, capability coverage, known limitations and useful upstream reproductions.

Prefer a few reviewable commits: baseline/runtime; adapter/vertical slice; correctness tests; CI/evidence/docs. Keep the target repository's existing license. Do not merge or publish releases as part of this handoff.

## 11. Ready-to-use instruction for Sol Ultra

Implement this plan in `xormania/mago-serena_v2-poc`, starting from its current `master`. Treat the document as the agreed scope and adapt routine implementation details as evidence requires.

Begin with a clean official Symfony Demo baseline and the first real MCP → Serena REPL → Mago semantic query. Use the external SolidLSP adapter mechanism before considering a Serena fork. Pin the inspected sources, verify toolchain availability early, and record any intentional pin change. Build and test the containerized integration, then complete the acceptance harness, CI and documentation. Preserve the original Demo tests and document fixture adaptations.

Use the earlier Agentscient fixture only for the provenance/reset lessons identified here. Do not import its orchestration or credentials. Keep the Demo fixture separable from the integration harness so MinSpec can consume it later; do not create or migrate MinSpec repositories for this assignment. Keep ordinary shell access for implementation and project tests. Do not broaden the work into Mate integration, a new routing platform, or a framework upgrade.

Continue through all work possible in the available environment. If Docker, authenticated model execution, or an upstream defect blocks a requirement, provide the exact reproduction and runnable remaining command, and distinguish the limitation from passed checks. Finish with a concise change summary, evidence links, actual test results and unresolved issues. Do not claim success from mocks or substitute a different language server silently. Leave upstream submissions and merging to xor.

## Source references

Inspected on 2026-10-27. Links below identify source, not evidence of a successful PoC run.

- [Target repository](https://github.com/xormania/mago-serena_v2-poc)
- [Official Symfony Demo snapshot](https://github.com/symfony/demo/tree/8d2e2ef75c3e18df173d8bf2379a14abb58c4c31)
- [Demo Composer manifest](https://github.com/symfony/demo/blob/8d2e2ef75c3e18df173d8bf2379a14abb58c4c31/composer.json)
- [Demo test workflow](https://github.com/symfony/demo/blob/8d2e2ef75c3e18df173d8bf2379a14abb58c4c31/.github/workflows/tests.yaml)
- [Demo fixtures](https://github.com/symfony/demo/blob/8d2e2ef75c3e18df173d8bf2379a14abb58c4c31/src/DataFixtures/AppFixtures.php)
- [Demo PostRepository](https://github.com/symfony/demo/blob/8d2e2ef75c3e18df173d8bf2379a14abb58c4c31/src/Repository/PostRepository.php) and [BlogController](https://github.com/symfony/demo/blob/8d2e2ef75c3e18df173d8bf2379a14abb58c4c31/src/Controller/BlogController.php)
- [Earlier fixture provenance](https://github.com/uscient/agentscient-test-repo/blob/7d1abb3c4ac01451d83e1c1e12742b9fa2067561/docs/PROVENANCE.md) and [adapted fixtures](https://github.com/uscient/agentscient-test-repo/blob/7d1abb3c4ac01451d83e1c1e12742b9fa2067561/src/DataFixtures/AppFixtures.php)
- [Serena external language-server registration](https://github.com/oraios/serena/blob/9e1cced0c34ed48d668e179f7c56c77b4d14a3e3/docs/03-special-guides/external_language_server_registration.md)
- [Serena REPL configuration](https://github.com/oraios/serena/blob/9e1cced0c34ed48d668e179f7c56c77b4d14a3e3/docs/02-usage/050_configuration.md)
- [Serena REPL tool/session contract](https://github.com/oraios/serena/blob/9e1cced0c34ed48d668e179f7c56c77b4d14a3e3/src/serena/tools/repl_tools.py)
- [Serena LSP facade](https://github.com/oraios/serena/blob/9e1cced0c34ed48d668e179f7c56c77b4d14a3e3/src/serena/repl/api/lsp_api.py)
- [Mago experimental server command](https://github.com/carthage-software/mago/blob/46df50c96d93d0ac3655c116c375574277cf0b30/src/commands/language_server.rs)
- [Mago toolchain requirement](https://github.com/carthage-software/mago/blob/46df50c96d93d0ac3655c116c375574277cf0b30/Cargo.toml)
- [Symfony Docker reference](https://github.com/dunglas/symfony-docker/tree/92d0d49293cd8678d82ca57c9c81b2dc45cf5561)

