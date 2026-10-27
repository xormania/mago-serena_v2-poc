"""Canonicalize Serena's generated project config before sealing its baseline."""
import asyncio
import os
from pathlib import Path

from mcp_client import connect


async def main():
    evidence = Path(os.environ.get('POC_EVIDENCE','/evidence'))/'baseline-mcp'
    async with connect('/app', evidence) as repl:
        count = await repl.code('len(s.lsp.find_symbol("PostRepository/findLatest", relative_path="src/Repository/PostRepository.php").symbols)')
        assert count == '1', f'Fresh baseline semantic lookup failed: {count}'


if __name__ == '__main__':
    asyncio.run(main())
