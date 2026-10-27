"""Real MCP client; one entrypoint for deterministic checks and manual probes."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import re

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from trace import BoundedJsonl


def text_of(result):
    return '\n'.join(block.text for block in result.content if hasattr(block, 'text'))


class Repl:
    def __init__(self, client, log):
        self.client = client
        self.log = log
        self.session = None

    async def call(self, name, arguments):
        result = await asyncio.wait_for(self.client.call_tool(name, arguments), timeout=120)
        self.log.write(json.dumps({'tool': name, 'arguments': arguments, 'result': result.model_dump(mode='json')}) + '\n')
        self.log.flush()
        return text_of(result)

    async def start(self):
        identity = await self.client.initialize()
        listing = await self.client.list_tools()
        self.log.write(json.dumps({'initialize': identity.model_dump(mode='json'), 'tools': listing.model_dump(mode='json')}) + '\n')
        names = {tool.name for tool in listing.tools}
        assert {'initial_instructions', 'serena_repl'} <= names, names
        instructions = await self.call('initial_instructions', {})
        match = re.search(r'session(?:\s+id)?[^\n]{0,40}?[`\'"]([a-zA-Z0-9_-]+)[`\'"]', instructions, re.I)
        if not match:
            raise AssertionError('No session token found in initial_instructions: ' + instructions[-2500:])
        self.session = match.group(1)
        return self

    async def code(self, code):
        return await self.call('serena_repl', {'session': self.session, 'code': code})


@asynccontextmanager
async def connect(root, evidence, command=None, extra_env=None):
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    command = command or ['serena', 'start-mcp-server', '--project', str(root), '--agent-interface', 'REPL',
                          '--enable-web-dashboard', 'false', '--enable-gui-log-window', 'false', '--open-web-dashboard', 'false']
    with (evidence / 'mcp.stderr').open('w') as stderr, BoundedJsonl(evidence / 'mcp.jsonl') as log:
        params = StdioServerParameters(command=command[0], args=command[1:], cwd=str(root), env={**os.environ, **(extra_env or {})})
        async with stdio_client(params, errlog=stderr) as streams:
            async with ClientSession(*streams, read_timeout_seconds=120) as client:
                repl = Repl(client, log)
                await repl.start()
                yield repl
