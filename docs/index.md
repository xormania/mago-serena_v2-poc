# Documentation

Start with [Getting started](GETTING-STARTED.md) to build the environment and
open the application. Use [Workflows](WORKFLOWS.md) for everyday development.
Guides describe the pinned implementation; experiment reports describe particular
runs and configurations.

## Guides and reference

| Need | Read |
| --- | --- |
| Install, start, edit, and stop | [Getting started](GETTING-STARTED.md) |
| Analyze, navigate, generate, or diagnose | [Workflows](WORKFLOWS.md) |
| Connect an agent and retain its transcript | [Agent clients](AGENT-CLIENTS.md) |
| Look up flags, defaults, paths, and exits | [Commands and configuration](COMMANDS.md) |
| Run checks and interpret results | [Testing](TESTING.md) |
| Resolve a setup or runtime problem | [Troubleshooting](TROUBLESHOOTING.md) |
| Understand components and isolation | [Architecture](ARCHITECTURE.md) |
| Check support and verification scope | [Capabilities](CAPABILITIES.md), [Symfony coverage](RUNTIME-COVERAGE.md) |
| Inspect PHP tooling details | [Mago PHP reference](MAGO-PHP.md) |
| Inspect compiled Symfony dependencies | [Symfony wiring](SYMFONY-WIRING.md) |
| Enable external workers in the patched LSP | [Mago LSP extensions](MAGO-LSP-EXTENSIONS.md) |
| Reuse the application fixture | [Fixture contract](FIXTURE-CONTRACT.md) |
| Change this repository | [Contributing](CONTRIBUTING.md), [CI](CI.md), [Roadmap](ROADMAP.md) |
| Understand advisory diagnosis | [Jev](JEV.md) |
| Find source pins and licensing | [Provenance](PROVENANCE.md), [license notices](../licenses/README.md) |

## Historical results and reproductions

These reports retain configurations, observations, failures, and reproductions.
Their numbered task names and counts identify experiments; they are not a
sequence users must complete. Original paths remain available for existing links.
Consult the guides above for present operation.

| Record | Scope |
| --- | --- |
| [Service investigation](SLICE-1.md), [selected service semantics](SERVICE-SEMANTICS.md) | PHP/source and compiled-wiring investigation with original LSP boundary |
| [Console command generation](SLICE-2.md) | Maker feature, agent session, independent replay |
| [Request diagnosis and repair](SLICE-3.md) | HTTP/profiler/log correlation, repair, independent replay |
| [Findings](FINDINGS.md) | Original acceptance, strengthened verification, earlier CI observations |
| [Upstream contribution records](UPSTREAM-CONTRIBUTIONS.md) | Inspected revisions, reproductions, candidate patches, and draft reports |
| [Original implementation plan](IMPLEMENTATION-PLAN.md) | Initial scope/instructions, superseded for everyday usage |
| [Retained evidence](evidence/) | Raw records and indexes, attributed to each run |
| [Upstream reproductions](upstream/) | Focused compatibility and protocol investigations |

Read counts and timings with their associated run. The request-repair replay
and adaptive session, for example, have different assertion counts because
fixture associations are randomized. Neither count defines every future run.
