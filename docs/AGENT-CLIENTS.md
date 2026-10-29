# Connect an agent client

The environment exposes Serena over the Model Context Protocol (MCP). Any suitable client can launch the same stdio command; its configuration syntax and the repository's ability to verify its native transcript are separate concerns.

## Shared connection requirements

Complete [Getting started](GETTING-STARTED.md) and start the workspace first. The MCP launcher requires the selected PHP service to be running; it does not build or start that service. For example, the default workspace uses:

```text
Command: /absolute/path/to/mago-serena_v2-poc/bin/serena-mcp
Arguments: --run dev
Transport: stdio
```

Replace the checkout path with the real **host absolute path**. Use a path visible to the process running your agent client, and keep it as one command field even when it contains spaces. Replace `dev` consistently when connecting another workspace. The launcher determines the checkout and Compose paths independently of the client's working directory. MCP messages use stdout; diagnostics use stderr. The server is not available at the Demo application's HTTP address.

The agent's working application is `workspaces/dev/app/` on the host and `/app` inside the PHP service. Point native agent file tools at that disposable application. The checked-in `app/` is fixture input.

Model selection, reasoning level, execution mode, permissions and authentication belong to the native client. This repository does not supply a universal model profile or choose those settings. The container service has no host credential mount; your authenticated client runs on the host.

## Codex CLI

Codex uses TOML, not the generated `mcpServers` JSON. Add the following server table to your Codex configuration, normally `~/.codex/config.toml`, or use a project-scoped `.codex/config.toml` in a trusted project:

```toml
[mcp_servers.serena]
command = "/absolute/path/to/mago-serena_v2-poc/bin/serena-mcp"
args = ["--run", "dev"]
```

Merge the table into the existing file rather than replacing unrelated settings. Ensure the launcher runs in the same host environment that has Docker access; for example, a WSL path needs a client process that can execute in that environment. `codex mcp list` shows configured servers; `/mcp` in Codex's terminal interface shows active connections.

The schema and locations above follow the [official Codex MCP documentation](https://developers.openai.com/codex/mcp/). They describe native client setup; they do not establish a fresh authenticated run against this checkout.

## Generated JSON and other clients

`./bin/poc agent-task` emits an exact launcher path and selected run arguments in `artifacts/ID/mcp-config.json`. Its schema is a top-level `mcpServers` map:

```json
{
  "mcpServers": {
    "serena": {
      "command": "/absolute/path/to/mago-serena_v2-poc/bin/serena-mcp",
      "args": ["--run", "dev"]
    }
  }
}
```

This is the repository's generated connection template. Use it directly only if your client documents that schema, and place it where that client expects it. Otherwise translate the command and argument array into its native configuration; the file is not itself a universal client-installation mechanism. A prepared agent task uses a unique `agent-*` run rather than the illustrative `dev` value above.

Other stdio MCP clients can use the shared launcher contract. Their connectivity must be checked in the actual client. There is no general native-transcript adapter registry in this repository, and the supplied `verify-agent` parser specifically understands Codex events.

## Use the Serena session

After MCP discovery, call `initial_instructions`. Use its session token for `serena_repl`, then request `s.info("lsp")` before invoking the facade. Only the cell's final expression returns tool content; Python variables persist in that REPL session. [Development workflows](WORKFLOWS.md#navigate-and-edit-semantically) gives source-query examples.

A connected server establishes tool access. It does not establish that a model used the tools, that a source change is correct, or that a retained transcript is supported by the verifier.

## Verify an agent-driven rename

Build the image and install host dependencies before preparing this task:

```sh
./bin/poc agent-task
```

The command creates a unique running workspace with a passing baseline suite, task instructions, application snapshot, expected test inventory and generated connection JSON. Read its printed workspace/run ID and `artifacts/ID/agent-task.txt`. Configure your client for that exact run; for Codex, translate the generated command/args into its native TOML table. Run your authenticated session against the disposable application and retain its native JSONL output at `artifacts/ID/agent-transcript.jsonl`.

For a new Codex execution, the native [`codex exec --json` mode](https://developers.openai.com/codex/noninteractive/) writes a JSONL event stream on stdout. Capture that stream without pretty-printing or filtering and retain stderr separately; a final-message-only export is not a tool-call transcript. Choose the task brief and execution permissions in the native client.

The supplied reader expects completed Codex `item.completed` events containing successful `mcp_tool_call` items for Serena REPL symbol lookup, reference lookup and the declared semantic rename. Native transcript formats can evolve; preserve the original records rather than manufacturing events to satisfy the parser. This reader does not parse arbitrary Claude, Grok or other clients' transcripts.

After the session, substitute the printed run ID:

```sh
./bin/poc verify-agent ID
```

Verification independently checks the declared rename's exact application diff, original PHPUnit identities, actual semantic tool-call records and a fresh semantic requery. Its result is task-specific. It does not certify arbitrary coding tasks, and passing application tests without the expected transcript is insufficient for this command.

Results include `agent-result.json`, `agent-phpunit.xml`, `agent-phpunit.log`, `agent-verification.log` and fresh semantic-query records under `artifacts/ID/`. Once any desired application edits have been saved elsewhere, `./bin/poc down --run ID --purge` removes the disposable workspace while retaining those artifacts. See [Testing and results](TESTING.md) and [Troubleshooting](TROUBLESHOOTING.md) for interpretation.
