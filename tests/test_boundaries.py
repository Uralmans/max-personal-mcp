"""Security and account boundary tests; no MAX credentials or network calls."""
import asyncio
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ['MAX_DATA_DIR'] = tempfile.mkdtemp(prefix='max-mcp-test-')
sys.path.insert(0, '/app')
import server
from starlette.testclient import TestClient


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.http = TestClient(server.app, base_url='http://127.0.0.1:9030')

    def test_health_does_not_claim_account_login(self):
        response = self.http.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['account'], 'not_connected')
        self.assertEqual(self.http.get('/status').json()['authorized'], False)

    def test_mcp_requires_bearer(self):
        self.assertEqual(self.http.post('/mcp', json={}).status_code, 401)
        self.assertEqual(self.http.post('/mcp', json={}, headers={'Authorization': 'Bearer wrong'}).status_code, 401)

    def test_dns_rebinding_blocked(self):
        self.assertEqual(self.http.get('/status', headers={'host': 'evil.example:9030'}).status_code, 403)

    def test_browser_csrf_blocked_before_start(self):
        with patch.object(server.account, 'start', new=AsyncMock()) as start:
            for headers in [{}, {'Origin': 'http://evil.example'}, {'Origin': 'null'}]:
                self.assertEqual(self.http.post('/auth/start', headers=headers).status_code, 403)
            start.assert_not_called()

    def test_local_browser_can_start(self):
        with patch.object(server.account, 'start', new=AsyncMock()) as start:
            response = self.http.post('/auth/start', headers={'Origin': 'http://127.0.0.1:9030'})
            self.assertEqual(response.status_code, 200)
            start.assert_called_once()

    def test_qr_and_status_not_cached(self):
        self.assertEqual(self.http.get('/qr.png').status_code, 404)
        self.assertEqual(self.http.get('/status').headers['cache-control'], 'no-store')
        self.assertEqual(self.http.get('/status').headers['x-frame-options'], 'DENY')

    def test_protected_actions_require_login(self):
        for operation in [server.get_me(), server.list_chats(), server.read_messages('1'), server.send_message('1', 'test')]:
            with self.assertRaisesRegex(ValueError, 'Сначала войдите'):
                asyncio.run(operation)

    def test_pagination_bounds(self):
        for kwargs in [{'offset': -1}, {'limit': 101}, {'limit': 0}]:
            with self.assertRaises(ValueError):
                asyncio.run(server.list_chats(**kwargs))

    def test_read_history_does_not_mark_read(self):
        fake = SimpleNamespace(fetch_history=AsyncMock(return_value=[]))
        with patch.object(server.account, 'require', return_value=fake):
            result = asyncio.run(server.read_messages('9007199254740993', 5, 12345))
        fake.fetch_history.assert_awaited_once_with(9007199254740993, backward=5, from_time=12345, interactive=False)
        self.assertEqual(result['count'], 0)

    def test_send_not_retried_on_unknown_outcome(self):
        fake = SimpleNamespace(send_message=AsyncMock(side_effect=TimeoutError))
        with patch.object(server.account, 'require', return_value=fake):
            with self.assertRaises(TimeoutError):
                asyncio.run(server.send_message('42', 'approved text'))
        self.assertEqual(fake.send_message.await_count, 1)

    def test_download_rejects_invalid_destination_and_size(self):
        fake = SimpleNamespace(get_file_by_id=AsyncMock())
        with patch.object(server.account, 'require', return_value=fake):
            for name, size in [('../file', 1), ('file', 0), ('file', 2_000_000_001)]:
                with self.assertRaises(ValueError):
                    asyncio.run(server.download_file('0', '1', '2', name, size))
        fake.get_file_by_id.assert_not_awaited()

    def test_error_does_not_leak_credentials(self):
        async def exercise():
            account = server.Account()
            account.client = SimpleNamespace(start=AsyncMock(side_effect=ValueError('secret-password')),
                                             close=AsyncMock())
            await account.run()
            self.assertEqual(account.status()['error'], 'ValueError')
            self.assertNotIn('secret-password', str(account.status()))
        asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
