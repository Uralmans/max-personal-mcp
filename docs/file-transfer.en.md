# File transfer

[Русский](file-transfer.ru.md) · [README](../README.en.md)

## 1. Stage a copy

Identify the file and destination from the human's explicit request. For your own Saved Messages, verify chat `0` with `get_chat`; use a confirmed chat ID for any other destination.

```sh
python3 scripts/transfer.py stage /path/to/report.zip
```

PowerShell:

```powershell
py -3 scripts/transfer.py stage 'C:\path\report.zip'
```

The helper creates a UUID job in `transfer/pending`, copies the file and computes SHA-256. Duplicate filenames get separate subdirectories. The result includes `job`, `bytes`, `sha256` and `container_path`. The original is unchanged.

The default root is `transfer` in this repository. To relocate it, set the same **absolute** `MAX_TRANSFER_DIR` for both the helper and Compose before starting the container. POSIX example: `export MAX_TRANSFER_DIR="$HOME/.local/share/max-mcp-transfer"`. PowerShell: `$env:MAX_TRANSFER_DIR = Join-Path $HOME 'max-mcp-transfer'`.

## 2. Send through MCP

Call `send_file` with:

```json
{
  "chat_id": "0",
  "file_path": "/transfer/<job>/000/report.zip",
  "caption": "Requested document"
}
```

Replace `<job>` with the actual staging ID. `reply_to` is an optional string message ID. Captions support up to 4,000 characters and PyMax formatting. Do not expand the mount to your entire disk.

The tool accepts regular files from 1 byte to 2,000,000,000 bytes. It creates a private immutable snapshot in the Docker volume, requiring enough free space and time. Symlinks, hard links, `..`, directories and special files are rejected.

`accepted_by_max` means MAX returned a message ID; it does not prove a recipient downloaded the file. The result also includes the size and SHA-256 of the submitted bytes.

## 3. Verify and clean up

Use `read_messages` to verify the message ID, attachment name and size. For byte-level verification, call `download_file` using the file ID, message, name and expected size from history, then compare SHA-256. Do not publish signed URLs or attachment tokens.

After verification:

```sh
python3 scripts/transfer.py finish --job <job> --chat-id 0 --message-id <message-id>
```

This writes a receipt to `transfer/receipts` and removes the staged job. The helper trusts your verification and does not contact MAX itself. Also remove any verification download from `/data/downloads` after comparing it.

## Failures and retention

On a timeout or unknown outcome, inspect history before retrying. The private `/data/uploads/max-send-*` snapshot is deleted on ordinary completion, exceptions and normal cancellation. A process crash can leave it on disk. The host copy remains until `finish`, `cancel` or expiry cleanup.

```sh
python3 scripts/transfer.py status
python3 scripts/transfer.py cancel --job <job>
python3 scripts/transfer.py sweep
```

`sweep` removes managed jobs older than 24 hours; `stage` performs the same cleanup before staging new files. There is no background timer. Do not delete the whole shared directory manually: other jobs may be using it. Receipts contain local paths and chat IDs, and are also excluded from Git.

The MCP wrapper does not retry an unknown network outcome. PyMax may separately repeat a request after the explicit server response `attachment.not.ready`; that is a different case.
