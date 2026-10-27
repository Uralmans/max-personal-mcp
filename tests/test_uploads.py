"""File boundary, immutable upload and no-retry tests. No external requests."""
import asyncio
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

os.environ['MAX_DATA_DIR'] = tempfile.mkdtemp(prefix='max-mcp-test-')
sys.path.insert(0, '/app')
import attachments
import server


class Uploads(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'transfer'
        self.root.mkdir()
        self.data = self.base / 'private'
        self.data.mkdir()
        self.source = self.root / 'Отчёт с пробелами.zip'
        self.raw = b'PK\x03\x04\x00\xff-test-data'
        self.source.write_bytes(self.raw)

    def tearDown(self):
        self.temp.cleanup()

    def snapshot(self, file_path, root, data):
        return attachments.upload_snapshot(file_path, self.root, self.data)

    async def test_snapshot_hash_name_permissions_and_cleanup(self):
        async with self.snapshot(str(self.source), None, None) as snap:
            self.assertEqual(snap.path.read_bytes(), self.raw)
            self.assertEqual(snap.sha256, hashlib.sha256(self.raw).hexdigest())
            self.assertEqual(snap.name, self.source.name)
            self.assertEqual(snap.size, len(self.raw))
            self.assertEqual(snap.path.stat().st_mode & 0o777, 0o600)
            self.source.write_bytes(b'changed after snapshot')
            self.assertEqual(snap.path.read_bytes(), self.raw)
        self.assertFalse(snap.path.exists())
        self.assertTrue(self.source.exists())

    async def test_rejects_outside_relative_traversal_symlink_directory_and_fifo(self):
        outside=self.base / 'secret'
        outside.write_bytes(b'not shared')
        (self.root/'link').symlink_to(outside)
        (self.root/'directory-link').symlink_to(self.base, target_is_directory=True)
        (self.root/'inside-link').symlink_to(self.source)
        os.mkfifo(self.root/'fifo')
        for candidate in [str(outside), 'relative.zip', str(self.root/'..'/'secret'),
                          str(self.root/'link'), str(self.root/'directory-link'/'secret'),
                          str(self.root/'inside-link'), str(self.root), str(self.root/'fifo')]:
            with self.subTest(candidate=candidate):
                with self.assertRaises((ValueError, OSError)):
                    async with self.snapshot(candidate, None, None):
                        self.fail('Invalid file accepted')

    async def test_size_limit_empty_file_and_cleanup_on_failure(self):
        with self.assertRaises(ValueError):
            async with attachments.upload_snapshot(str(self.source),self.root,self.data,max_size=1): pass
        self.source.write_bytes(b'')
        with self.assertRaises(ValueError):
            async with self.snapshot(str(self.source),None,None): pass
        self.source.write_bytes(self.raw)
        with self.assertRaises(TimeoutError):
            async with self.snapshot(str(self.source),None,None) as snap: raise TimeoutError('failed')
        self.assertFalse(snap.path.exists())

    async def test_cancel_during_send_removes_private_snapshot(self):
        with self.assertRaises(asyncio.CancelledError):
            async with self.snapshot(str(self.source),None,None) as snap: raise asyncio.CancelledError()
        self.assertFalse(snap.path.exists())

    async def test_send_file_uses_exact_snapshot_and_preserves_reply_and_caption(self):
        async def sent(destination, text, attachments, reply_to):
            self.assertEqual(destination,0)
            self.assertEqual(text,'approved caption')
            self.assertEqual(reply_to,9007199254740993)
            self.assertEqual(len(attachments),1)
            self.assertEqual(attachments[0].name,self.source.name)
            self.assertEqual(await attachments[0].read(),self.raw)
            self.sent_path=Path(attachments[0].path)
            return SimpleNamespace(id=9007199254740995)
        fake=SimpleNamespace(send_message=AsyncMock(side_effect=sent))
        with patch.object(server.account,'require',return_value=fake), patch.object(server,'upload_snapshot',self.snapshot):
            result=await server.send_file('0',str(self.source),'approved caption','9007199254740993')
        self.assertEqual(result['message_id'],'9007199254740995')
        self.assertEqual(result['sha256'],hashlib.sha256(self.raw).hexdigest())
        self.assertFalse(self.sent_path.exists())
        fake.send_message.assert_awaited_once()

    async def test_unknown_send_result_not_retried_and_remote_secrets_not_exposed(self):
        fake=SimpleNamespace(send_message=AsyncMock(side_effect=TimeoutError('signed-url-secret')))
        with patch.object(server.account,'require',return_value=fake), patch.object(server,'upload_snapshot',self.snapshot):
            with self.assertRaises(RuntimeError) as caught:
                await server.send_file('0',str(self.source))
        self.assertNotIn('signed-url-secret',str(caught.exception))
        fake.send_message.assert_awaited_once()
        self.assertEqual(list((self.data/'uploads').iterdir()),[])

    async def test_invalid_input_never_sent(self):
        fake=SimpleNamespace(send_message=AsyncMock())
        with patch.object(server.account,'require',return_value=fake), patch.object(server,'upload_snapshot',self.snapshot):
            for args in [('bad-id',str(self.source),''),('0',str(self.source),'x'*4001),('0','/data/max.db','')]:
                with self.assertRaises(ValueError): await server.send_file(*args)
        fake.send_message.assert_not_awaited()

    async def test_protected_send_requires_login(self):
        with self.assertRaisesRegex(ValueError,'Сначала войдите'):
            await server.send_file('0',str(self.source))


if __name__=='__main__': unittest.main()
