"""macOS-only CONNECT helper, restricted to MAX:443 and bound to en0.

TLS remains end to end: this process never decrypts MAX traffic.
"""
import asyncio
import base64
import contextlib
import ipaddress
import os
import secrets
import socket
from pathlib import Path


def allowed_host(host):
    host = host.lower().rstrip('.')
    return any(host == suffix or host.endswith('.' + suffix)
               for suffix in ('max.ru', 'oneme.ru'))


async def direct_connection(host):
    loop = asyncio.get_running_loop()
    addresses = await loop.getaddrinfo(host, 443, family=socket.AF_INET,
                                       type=socket.SOCK_STREAM)
    last_error = None
    for _, _, _, _, address in addresses:
        if not ipaddress.ip_address(address[0]).is_global:
            continue
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Darwin IP_BOUND_IF: bind the outgoing route to the physical interface.
            sock.setsockopt(socket.IPPROTO_IP, 25,
                            socket.if_nametoindex(os.getenv('MAX_DIRECT_INTERFACE', 'en0')))
            sock.setblocking(False)
            await asyncio.wait_for(loop.sock_connect(sock, address), timeout=8)
            return await asyncio.open_connection(sock=sock)
        except Exception as exc:
            last_error = exc
            sock.close()
    raise ConnectionError('No direct MAX connection') from last_error


class Proxy:
    def __init__(self, token):
        self.authorization = 'Basic ' + base64.b64encode(('max:' + token).encode()).decode()
        self.slots = asyncio.Semaphore(16)

    async def reply(self, writer, status):
        writer.write(('HTTP/1.1 ' + status + '\r\nContent-Length: 0\r\n\r\n').encode())
        await writer.drain()

    async def copy(self, reader, writer):
        while True:
            data = await reader.read(65536)
            if not data:
                return
            writer.write(data)
            await writer.drain()

    async def handle(self, reader, writer):
        upstream = None
        pumps = []
        try:
            async with self.slots:
                raw = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout=10)
                if len(raw) > 8192:
                    return await self.reply(writer, '431 Headers Too Large')
                lines = raw.decode('ascii').split('\r\n')
                method, target, version = lines[0].split(' ')
                headers = dict(line.split(':', 1) for line in lines[1:] if line)
                headers = {key.lower(): value.strip() for key, value in headers.items()}
                if not secrets.compare_digest(headers.get('proxy-authorization', ''), self.authorization):
                    return await self.reply(writer, '407 Proxy Authentication Required')
                host, port = target.rsplit(':', 1)
                if method != 'CONNECT' or port != '443' or not allowed_host(host):
                    return await self.reply(writer, '403 Forbidden')
                upstream_reader, upstream = await direct_connection(host)
                writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                await writer.drain()
                pumps = [asyncio.create_task(self.copy(reader, upstream)),
                         asyncio.create_task(self.copy(upstream_reader, writer))]
                await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
        except (ValueError, UnicodeError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            with contextlib.suppress(Exception):
                await self.reply(writer, '400 Bad Request')
        except Exception:
            with contextlib.suppress(Exception):
                await self.reply(writer, '502 Bad Gateway')
        finally:
            for pump in pumps:
                pump.cancel()
            if pumps:
                await asyncio.gather(*pumps, return_exceptions=True)
            if upstream:
                upstream.close()
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


async def main():
    os.umask(0o077)
    token = Path(os.environ['MAX_DIRECT_TOKEN_FILE']).read_text().strip()
    proxy = Proxy(token)
    server = await asyncio.start_server(proxy.handle, '127.0.0.1', 19031, limit=8192)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())
