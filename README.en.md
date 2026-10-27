# MAX Personal MCP

[![CI](https://github.com/Uralmans/max-personal-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Uralmans/max-personal-mcp/actions/workflows/ci.yml)

**Bring your personal MAX account to an AI assistant: chats, history, messages and files over MCP.**

[Русский](README.md) · [Operations](docs/operations.en.md) · [File transfer](docs/file-transfer.en.md) · [Security](SECURITY.en.md)

A local [Model Context Protocol](https://modelcontextprotocol.io/) server for a **personal MAX account**. Runs in Docker, signs in using a QR code and keeps the session in a dedicated volume. A stdio bridge lets Codex and other MCP clients connect without copying the access secret out of the container.

> An independent project, not affiliated with MAX or its owners. Uses the unofficial [PyMax](https://github.com/MaxApiTeam/PyMax) client, not the Bot API. Service changes may break compatibility. Review MAX's rules and use your own account.

## Tools

| Tool | Purpose |
| --- | --- |
| `account_status` | Connection state and local sign-in URL |
| `get_me` | Current account profile |
| `list_chats` | List and search chats in the synchronization cache |
| `get_chat` | Chat details by ID |
| `read_messages` | History without a separate mark-as-read operation |
| `get_user` | User profile by ID |
| `send_message` | Text messages, including replies |
| `send_file` | Local document, caption and optional reply |
| `download_file` | Download an attachment and verify its size |

Send only when the human explicitly requests it. After an unknown outcome, check history before trying again: network failures are not retried automatically. Chat `0` is used for Saved Messages; verify it with `get_chat` before the first send.

## Quick start

Requires Docker Engine with Compose v2 (or Docker Desktop), Python 3.10+ for the transfer helper, and MAX on your phone. The Linux container is host-independent; live MAX verification was performed on Docker Desktop for macOS. Validate Windows and Linux in your own environment.

```sh
git clone https://github.com/Uralmans/max-personal-mcp.git
cd max-personal-mcp
python3 scripts/transfer.py status
docker compose up -d --build
```

Open the [local sign-in page](http://127.0.0.1:9030/), request a QR code and approve it in MAX on your phone. If MAX requests an account password, enter it only on the local page. Wait for the connected status.

The `status` command creates the transfer directory before Compose starts; the directory is mounted read-only. A proxy is optional: copy `.env.example` to `.env` and set `MAX_PROXY` if needed. Never publish that file.

## Connect an MCP client

For clients supporting stdio:

```json
{
  "mcpServers": {
    "max": {
      "command": "docker",
      "args": ["exec", "-i", "max-mcp", "python", "/app/bridge.py"]
    }
  }
}
```

Make Docker CLI available to the MCP client. Reconnect the server or start a new chat after configuring it. The container must already be running and signed in.

```text
MCP client → docker exec / stdio → bridge → local MCP server → MAX
                                                │
                                    session in Docker volume
```

## Send a file

```sh
python3 scripts/transfer.py stage /path/to/report.zip
```

The helper returns `/transfer/<job>/000/report.zip`, its size and SHA-256. Pass the container path to `send_file`, then verify the attachment name and size in chat history. Run `finish` only after verification. See [file transfer](docs/file-transfer.en.md), including Windows commands.

This workflow does not grant access to your entire disk. Original files are preserved. The admission limit is 2 GB; actual success depends on MAX, network conditions, timeouts and free disk space.

## Security properties

- The published port binds to `127.0.0.1` only; MCP requires a Bearer secret read by the bridge.
- Browser sign-in checks Host and Origin; QR and status responses are not cached.
- The container runs as a non-root user with a read-only root filesystem and no Linux capabilities.
- Uploads use a dedicated directory; traversal, links and special files are rejected.
- Credentials, `.env`, sessions, QR codes, reports and transfer copies are excluded from Git. The Docker build uses a file allowlist.

A trusted MCP client can still read personal messages and perform authorized sends. This is a local, single-owner service, without separate user roles or per-user authorization. Read the [security model](SECURITY.en.md).

## Validation

```sh
docker compose build
docker run --rm --read-only --tmpfs /tmp -v "$PWD/tests:/tests:ro" \
  local/max-personal-mcp:0.2.0 python -m unittest discover -s /tests -v
docker exec max-mcp python /app/probe.py
python3 scripts/check_public_files.py
```

22 automated tests cover boundaries, file handling and failure paths without contacting MAX. A live ZIP transfer to Saved Messages was also verified in the deployed environment: history contained the attachment, and downloading it reproduced the original SHA-256. This does not validate every file format or sizes up to 2 GB. CI uses no personal account or secrets.

## Documentation and contributions

- [Operations and troubleshooting](docs/operations.en.md)
- [File transfer](docs/file-transfer.en.md)
- [Security model](SECURITY.en.md)
- [Contributing](CONTRIBUTING.en.md)
- [Changelog](CHANGELOG.md)

Licensed under [MIT](LICENSE). PyMax and other dependencies retain their own licenses; their source trees and sessions are not bundled in this repository.
