"""Bounded, no-symlink reads from the transfer mount; immutable private upload copy."""
import asyncio
import hashlib
import os
import stat
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 2_000_000_000


@dataclass(frozen=True)
class Snapshot:
    path: Path
    name: str
    size: int
    sha256: str


def open_transfer_file(file_path: str, root: Path):
    """Traverse using directory descriptors: no symlink or '..' escape/race."""
    candidate = Path(file_path)
    if not candidate.is_absolute() or '..' in candidate.parts:
        raise ValueError('Нужен абсолютный путь внутри /transfer без ..')
    try:
        parts = candidate.relative_to(root).parts
    except ValueError:
        raise ValueError('Файл должен находиться внутри /transfer') from None
    if not parts or any(ord(c) < 32 for c in parts[-1]):
        raise ValueError('Некорректное имя файла')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    source = os.fdopen(fd, 'rb')
    info = os.fstat(source.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        source.close()
        raise ValueError('Нужен обычный файл, не ссылка или специальное устройство')
    return source, parts[-1]


@asynccontextmanager
async def upload_snapshot(file_path: str, root: Path, data_dir: Path,
                          max_size: int = MAX_FILE_BYTES):
    """Freeze exactly the bytes whose size/hash are returned; delete on all outcomes."""
    temporary = None
    try:
        source, name = open_transfer_file(file_path, root)
        with source:
            before = os.fstat(source.fileno())
            if not 0 < before.st_size <= max_size:
                raise ValueError('Размер файла должен быть от 1 байта до 2 ГБ')
            folder = data_dir / 'uploads'
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=folder, prefix='max-send-', delete=False) as out:
                temporary = Path(out.name)
                sha = hashlib.sha256()
                total = 0
                while chunk := await asyncio.to_thread(source.read, 1024 * 1024):
                    total += len(chunk)
                    if total > max_size:
                        raise ValueError('Файл вырос сверх допустимого размера')
                    sha.update(chunk)
                    out.write(chunk)
                after = os.fstat(source.fileno())
                if total != before.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('Файл изменился при подготовке; создайте новую копию передачи')
        yield Snapshot(temporary, name, total, sha.hexdigest())
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
