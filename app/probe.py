"""Read-only end-to-end probe through the same stdio bridge used by Codex."""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    async with stdio_client(StdioServerParameters(command='python', args=['/app/bridge.py'])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            names = [t.name for t in tools]
            assert set(names) == {'account_status', 'get_me', 'list_chats', 'get_chat', 'read_messages', 'get_user', 'send_message', 'download_file', 'send_file'}, names
            result = await session.call_tool('account_status', {})
            assert not result.isError, result
            status = json.loads(result.content[0].text)
            print(json.dumps({'stdio_handshake': 'ok', 'tools': names, 'account': status}, ensure_ascii=False))
            if status['authorized']:
                me = await session.call_tool('get_me', {})
                chats = await session.call_tool('list_chats', {'limit': 1})
                assert not me.isError and not chats.isError
                print('Authenticated profile and chat listing: OK (private contents omitted)')
            else:
                result = await session.call_tool('list_chats', {'limit': 1})
                assert result.isError
                print('Unauthenticated account access correctly blocked')


if __name__ == '__main__':
    asyncio.run(main())
