# Process and filesystem contract

The host launcher runs `docker compose exec -T -w /app php serena
start-mcp-server --project /app --transport stdio --agent-interface REPL` with
explicit checkout, Compose file and project paths. Arguments remain an argv
array; stdout carries MCP only. The launcher works from another directory and
with spaces in the checkout path. A stopped service exits 3 with a startup hint.

Serena and the external adapter share `/opt/venv`. The adapter entry point
registers `ExternalLanguageServerId("mago")`; the project selects only that key.
Serena launches `/usr/local/bin/mago language-server` with
`MAGO_EXPERIMENTAL_SERVER=1`. The analyzer stays enabled. A build-time binary hash
and the live `mago-server` initialize response establish backend identity. There
is no fallback. Runtime identity includes the Mago source commit, Cargo lock
hash, image pins, Python lock hash and executable hash.

The adapter uses SolidLSP's transport extension point to convert UTF-16 wire
positions to Python string indices and back. Mago's own codec converts its core
byte offsets to UTF-16; the adapter never interprets those core offsets.
Ranged edits emitted by SolidLSP are sent as full document changes using the
updated buffer. Incoming WorkspaceEdit ranges are converted before applying
them. Versioned edits are checked before application; resource operations are
refused. Diagnostics use actual push publications, including empty publications
that clear a previous error. Bounded requests and the base process manager handle
shutdown and death. Server readiness follows the pinned implementation's
synchronous initialize/bootstrap, followed by asserted semantic responses.

The checked-in `app/` is immutable fixture input. Each development or acceptance
environment copies it to `workspaces/<id>/app`, bind-mounted as `/app`. That copy
contains its own vendor tree, SQLite databases, var directory and `.serena`
state. Global Serena state is `workspaces/<id>/state`, mounted at `/state`.
Evidence is `artifacts/<id>`, mounted at `/evidence`. No anonymous volumes hide
vendor or var. Run ids have unique Compose project names and dynamic HTTP ports;
the dev environment uses localhost:8000. Cleanup validates a checkout-owned marker
and targets only that Compose project. Evidence survives `down --purge`.

PHP's development server runs in the same `php` service used for Composer,
PHPUnit and MCP. The service runs with the invoking user's UID/GID; the image's
default identity is an unprivileged `poc` user. There is no Docker socket or host
credential mount, and MCP is not served over the network. The REPL has process
privileges: its API configuration and read-only flag are agent steering, not a
security boundary. The host authenticated agent can use shell commands normally.
