"""Local stdio MCP proxy: credentials never leave the container volume."""
import asyncio
from pathlib import Path
import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server import Server
from mcp.server.stdio import stdio_server


async def main():
    token = Path('/data/mcp-token').read_text().strip()
    async with httpx.AsyncClient(headers={'Authorization': f'Bearer {token}'},
                                 timeout=httpx.Timeout(60, read=300)) as http_client, streamable_http_client(
        'http://127.0.0.1:8765/mcp', http_client=http_client,
    ) as (read, write, _):
        async with ClientSession(read, write) as upstream:
            await upstream.initialize()
            server = Server('max-personal')

            @server.list_tools()
            async def list_tools():
                return (await upstream.list_tools()).tools

            @server.call_tool()
            async def call_tool(name, arguments):
                return await upstream.call_tool(name, arguments)

            async with stdio_server() as (stdin, stdout):
                await server.run(stdin, stdout, server.create_initialization_options())


if __name__ == '__main__':
    asyncio.run(main())
