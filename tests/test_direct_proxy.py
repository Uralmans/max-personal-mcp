import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, 'app')
import direct_proxy


class ProxyBoundaries(unittest.IsolatedAsyncioTestCase):
    def test_domain_scope(self):
        for host in ['max.ru', 'web.max.ru', 'api.oneme.ru', 'oneme.ru']:
            self.assertTrue(direct_proxy.allowed_host(host))
        for host in ['evilmax.ru', 'max.ru.evil.example', '127.0.0.1', 'example.com']:
            self.assertFalse(direct_proxy.allowed_host(host))

    async def test_auth_and_target_scope(self):
        proxy = direct_proxy.Proxy('test-secret')
        server = await asyncio.start_server(proxy.handle, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]
        async def request(target, auth):
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(('CONNECT ' + target + ' HTTP/1.1\r\nProxy-Authorization: ' + auth + '\r\n\r\n').encode())
            await writer.drain()
            result = await reader.read()
            writer.close()
            await writer.wait_closed()
            return result
        try:
            with patch.object(direct_proxy, 'direct_connection', new=AsyncMock()) as connect:
                self.assertIn(b'407', await request('api.oneme.ru:443', 'Basic wrong'))
                self.assertIn(b'403', await request('example.com:443', proxy.authorization))
                self.assertIn(b'403', await request('api.oneme.ru:80', proxy.authorization))
                self.assertIn(b'403', await request('127.0.0.1:443', proxy.authorization))
                connect.assert_not_awaited()
        finally:
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    unittest.main()
