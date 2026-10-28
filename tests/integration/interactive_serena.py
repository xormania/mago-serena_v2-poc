#!/usr/bin/env python3
"""Keep a real host MCP/Serena REPL open for an adaptive agent investigation.

Read one JSON object {"code": "..."} per line. This runner makes no semantic
decisions and replays no task: the calling agent supplies each next cell after
reading the previous result. Requests and results are retained by mcp_client.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from mcp_client import connect

ROOT = Path(__file__).resolve().parents[2]


async def run(run_id, evidence):
    command = [str(ROOT/'bin/serena-mcp'), '--run', run_id]
    async with connect('/tmp', evidence, command=command) as repl:
        print(json.dumps({'ready': True, 'session': repl.session}), flush=True)
        while line := await asyncio.to_thread(sys.stdin.readline):
            request = json.loads(line)
            if request.get('close'):
                break
            result = await repl.code(request['code'])
            print(json.dumps({'result': result}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--evidence', required=True)
    args = parser.parse_args()
    asyncio.run(run(args.run, args.evidence))
