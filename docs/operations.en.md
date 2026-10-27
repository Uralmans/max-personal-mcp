# Operations

[Русский](operations.ru.md) · [README](../README.en.md)

## Start and sign in

1. Clone the repository and run `python3 scripts/transfer.py status` to create the transfer directory.
2. Optionally copy `.env.example` to `.env` and configure a proxy. Keep `.env` local.
3. Run `docker compose up -d --build`.
4. Open `http://127.0.0.1:9030/`, request a QR code and approve it through the devices section in MAX on your phone. Exact labels depend on the MAX version.
5. Enter an account password on the local page if requested, and wait for the connected state. The current sign-in UI is in Russian.

On Windows, Python may be invoked as `py -3` or `python`. Use Docker Desktop in Linux-container mode. Commands using `$PWD` assume a POSIX shell; use `"${PWD}/tests:/tests:ro"` for the test bind mount in PowerShell.

The container has the fixed name `max-mcp`. If it is already in use, identify the existing project before making changes. Do not delete a running service or its volume just to launch a second copy.

## Session persistence

The session, authorization marker and MCP secret live in the named `max-session` volume. Compose prefixes its name with the project name. Stopping the container preserves the session. `docker compose down -v` deletes it; avoid that command when keeping your sign-in.

The service attempts to restore the session after a restart. A revoked session requires another QR sign-in. Revoke access through MAX's device list. The application sends a requested 2FA password to MAX but does not store it. The saved session itself grants account access without re-entering the password, so protect the volume.

## Health checks

```sh
docker compose ps
docker exec max-mcp python /app/probe.py
```

`/health` confirms service availability, not account sign-in. Only `account_status.authorized=true` confirms an active account connection. `probe.py` exercises the actual stdio bridge, tool list and account access without printing private profile or chat content. It sends no messages.

`list_chats` reads the login/sync cache, which may be incomplete. An empty search result does not prove that a chat is absent. Saved Messages may have no title; inspect chat ID `0` using `get_chat`.

## Proxy and networking

`MAX_PROXY` is passed to PyMax, and attachment downloads use the same proxy. Scheme/authentication compatibility depends on the underlying libraries; validate your chosen proxy. Do not publish a proxy URL containing credentials.

If connection or QR generation fails, check DNS and MAX connectivity from both the host and the container. Run `docker compose up -d` after editing `.env`. The service does not automatically change your system VPN or routes.

`app/direct_proxy.py` is an **optional, experimental macOS utility**, not started by Compose. It exposes a CONNECT proxy on `127.0.0.1:19031`, bound to `MAX_DIRECT_INTERFACE` (default `en0`). Set `MAX_DIRECT_TOKEN_FILE` to a secret file you create. Only `max.ru`/`oneme.ru` and their subdomains, port 443 and global IPv4 destinations are allowed. TLS remains end-to-end. The utility does not support Windows/Linux; use it only if you understand the route and how the container reaches the host.

## Updates and rollback

Preserve the current application tag/image before updating. Check out the desired Git tag or commit and run `docker compose up -d --build`. Keep the Compose project name unchanged to retain the same volume.

To roll back, restore the earlier commit and rebuild with the same volume. This project does not migrate the session; validate session-format compatibility separately when changing PyMax versions.

Recreating the container can close existing stdio connections. Reconnect MAX MCP in the client or start a new chat.

## Limits

No calls, message deletion/editing, multi-user roles or promise of full official-app parity. Pass MCP argument IDs as strings because large numbers can lose precision in JavaScript. PyMax responses may contain numeric IDs; account for this when processing JSON yourself.
