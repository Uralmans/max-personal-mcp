# Contributing

[Русский](CONTRIBUTING.md)

1. Branch from `main` and make a small, complete change.
2. Add meaningful tests when changing access boundaries or network behavior.
3. Update both Russian and English documentation for user-facing changes.
4. Check published files: `python3 scripts/check_public_files.py`.
5. Build the image and run tests as described in the README. Tests need no MAX account.
6. Explain the problem, resulting behavior and validation in your pull request.

Do not add real user IDs, phone numbers, QR codes, sessions, signed URLs, tokens, local dumps or conversations. Automated tests must not send real messages. Any manual send test requires the account owner's explicit instruction and a specific recipient.

The MCP wrapper is in `app/server.py`, file boundaries in `app/attachments.py`, stdio proxy in `app/bridge.py`, and host-side staging in `scripts/transfer.py`.
