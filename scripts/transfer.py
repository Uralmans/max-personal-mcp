#!/usr/bin/env python3
"""Local staging only. Does not send MAX messages or delete source files."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(os.environ.get('MAX_TRANSFER_DIR', str(Path(__file__).resolve().parents[1] / 'transfer'))).expanduser().resolve()
PENDING = ROOT / 'pending'
RECEIPTS = ROOT / 'receipts'
MARKER = 'max-file-transfer-v1'
TTL = 86400


def init():
    for p in (ROOT, PENDING, RECEIPTS):
        p.mkdir(parents=True, exist_ok=True)
    ROOT.chmod(0o700)
    PENDING.chmod(0o755)
    RECEIPTS.chmod(0o700)


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(p, value):
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.chmod(0o600)
    temp.replace(p)


def job_path(job):
    if str(uuid.UUID(job)) != job:
        raise ValueError('Invalid job ID')
    p = PENDING / job
    if p.is_symlink():
        raise ValueError('Job directory must not be a symlink')
    return p


def load(job):
    p = job_path(job)
    m = p / 'manifest.json'
    if m.is_symlink():
        raise ValueError('Manifest must not be a symlink')
    data = json.loads(m.read_text())
    if data.get('kind') != MARKER or data.get('job') != job:
        raise ValueError('Not a managed transfer job')
    return p, data


def sweep():
    removed = []
    for p in PENDING.iterdir():
        try:
            path, data = load(p.name)
            if time.time() - data['created_at'] >= TTL:
                shutil.rmtree(path)
                removed.append(p.name)
        except (ValueError, KeyError, OSError):
            continue
    return removed


def stage(paths):
    sources = [Path(p).expanduser().resolve(strict=True) for p in paths]
    for p in sources:
        if not p.is_file() or p.is_relative_to(ROOT):
            raise ValueError('Source must be a regular file outside the transfer folder')
    job = str(uuid.uuid4())
    target = job_path(job)
    target.mkdir(mode=0o755)
    files = []
    try:
        for i, src in enumerate(sources):
            # Separate folders preserve original names, including duplicate basenames.
            folder = target / f'{i:03d}'
            folder.mkdir(mode=0o755)
            dest = folder / src.name
            before = src.stat()
            shutil.copyfile(src, dest)
            dest.chmod(0o644)
            copied_hash = digest(dest)
            original_hash = digest(src)
            after = src.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or copied_hash != original_hash:
                raise ValueError('Source changed during copying; retry when it stops changing')
            files.append({'source': str(src), 'name': src.name, 'bytes': dest.stat().st_size,
                          'sha256': copied_hash, 'container_path': '/transfer/' + str(dest.relative_to(PENDING))})
        data = {'kind': MARKER, 'job': job, 'created_at': time.time(), 'files': files}
        write_json(target / 'manifest.json', data)
        return data
    except BaseException:
        shutil.rmtree(target)
        raise


def finish(job, chat, messages):
    p, data = load(job)
    if not messages or any(m <= 0 for m in messages):
        raise ValueError('Verified positive message IDs required')
    data.update(chat_id=chat, message_ids=messages,
                verified_at=dt.datetime.now(dt.timezone.utc).isoformat())
    write_json(RECEIPTS / (job + '.json'), data)
    shutil.rmtree(p)
    return {'job': job, 'copies_deleted': not p.exists(), 'receipt': str(RECEIPTS / (job + '.json'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('stage'); s.add_argument('paths', nargs='+')
    f = sub.add_parser('finish'); f.add_argument('--job', required=True); f.add_argument('--chat-id', required=True); f.add_argument('--message-id', type=int, action='append', required=True)
    c = sub.add_parser('cancel'); c.add_argument('--job', required=True)
    sub.add_parser('sweep')
    sub.add_parser('status')
    args = parser.parse_args()
    init()
    if args.command == 'stage':
        expired = sweep()
        result = stage(args.paths)
        result['expired_jobs_removed'] = expired
    elif args.command == 'finish':
        result = finish(args.job, args.chat_id, args.message_id)
    elif args.command == 'cancel':
        p, _ = load(args.job); shutil.rmtree(p)
        result = {'job': args.job, 'copies_deleted': not p.exists()}
    elif args.command == 'sweep':
        result = {'expired_jobs_removed': sweep()}
    else:
        result = {'pending_jobs': [p.name for p in PENDING.iterdir()], 'ttl_hours': TTL // 3600}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
