# Security and privacy

[Русский](SECURITY.md)

## Trust model

Designed for one trusted host and one account owner. An MCP client with `docker exec` access can read conversations and send messages. “Send only when explicitly requested” is conveyed through tool descriptions and MCP instructions; the server has no separate approval gate for each send. Do not connect untrusted agents or remote users.

The published port binds to loopback only. Do not change it to `0.0.0.0`, expose the Docker socket or use this configuration as a shared internet service. The Linux container runs without root, but host-side Docker access is itself privileged.

## Secret locations

| Data | Location |
| --- | --- |
| MAX session, authorization marker, MCP secret | Docker volume `/data` |
| Sign-in password | Process memory while requested; the application does not write it to disk |
| Proxy credentials | Your local `.env` or environment |
| Staged files and receipts | `transfer/`, inside the checkout by default |
| Downloaded attachments | `/data/downloads` |
| Private outgoing snapshot | `/data/uploads`, removed on normal completion |

Never attach a volume export, QR code, HAR, full profile/history output or a personal attachment to an issue. MAX history may include signed URLs and attachment tokens. Some application errors redact remote content, but this is not a guarantee that every third-party log or traceback is anonymized.

The MAX session and local Bearer key are separate secrets: Bearer protects MCP while the session authorizes access to MAX. Revoke the device in MAX if its session leaks; changing only the MCP key does not revoke that session. Recreating a container does not erase persisted volume secrets.

## Application protections

- Host/Origin checks for local sign-in and Bearer authentication for MCP.
- `no-store`, frame blocking and local POST password submission.
- TLS verification in the MAX client; the optional CONNECT helper does not decrypt TLS.
- A dedicated transfer mount, no-link file traversal and immutable outgoing snapshots.
- Git exclusions, a Docker context allowlist and CI checks of published files.

The sign-in HTTP page is local. This does not defend against host malware or anyone with access to Docker or your OS account. There is no multi-user isolation, disk quota or concurrent-send limit. Monitor free space and avoid bulk uploads.

## Before committing

```sh
python3 scripts/check_public_files.py
# Optional independent scan with Gitleaks:
gitleaks dir . --redact
```

`.gitignore` cannot remove files already committed. Inspect `git diff --cached` and history. If a secret reaches GitHub, revoke/rotate it first, then clean the history. Reproduce issues using synthetic data rather than real sessions.

## Reporting vulnerabilities

Do not open a public issue containing secrets or private conversations. Use Security → Report a vulnerability if private reporting is enabled for the repository. Otherwise use an available owner contact to share a brief, non-sensitive description. There is no dedicated security team or guaranteed response time.
