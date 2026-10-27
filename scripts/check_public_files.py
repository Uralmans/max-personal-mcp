#!/usr/bin/env python3
"""Reject private artifacts and common credentials in tracked/indexed files.

This is a focused guard, not a replacement for a dedicated secret scanner.
No matching content is printed.
"""
import re
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = {'app', 'tests', 'scripts', 'docs', '.github'}
ALLOWED_FILES = {'README.md', 'README.en.md', 'LICENSE', 'SECURITY.md', 'SECURITY.en.md',
                 'CONTRIBUTING.md', 'CONTRIBUTING.en.md', 'CHANGELOG.md', 'Dockerfile',
                 'compose.yaml', 'requirements.txt', 'requirements.lock.txt',
                 '.gitignore', '.dockerignore', '.env.example'}
PRIVATE_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.session', '.pem', '.key', '.pfx', '.p12',
                    '.png', '.jpg', '.jpeg', '.gif', '.zip', '.tar', '.gz', '.log', '.token'}
PATTERNS = {
    'personal home path': re.compile(r'(?:/(?:Users|home)/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[^\\\s]+\\)'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
    'GitHub access token': re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})'),
    'Russian phone number': re.compile(r'(?<!\d)(?:\+7|8)\d{10}(?!\d)'),
    'credential in URL': re.compile(r'https?://[^\s/@:]+:[^\s/@]+@'),
    'literal long secret': re.compile(r'''(?i)(?:password|token|secret)\s*[:=]\s*["'][A-Za-z0-9+/=_-]{24,}["']'''),
}


def main():
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True, capture_output=True)
    paths = [p for p in result.stdout.decode().split('\0') if p]
    if not paths:
        print('No tracked files: stage the intended public files before checking.', file=sys.stderr)
        return 1
    findings=[]
    for name in paths:
        path=Path(name)
        if (len(path.parts)==1 and name not in ALLOWED_FILES) or (len(path.parts)>1 and path.parts[0] not in ALLOWED_ROOTS):
            findings.append((name,'unexpected tracked path'))
        if path.suffix.lower() in PRIVATE_SUFFIXES or (path.name.startswith('.env') and path.name!='.env.example'):
            findings.append((name,'private artifact type'))
        # Scan staged bytes: a clean working tree must not hide secrets in the index.
        raw=subprocess.run(['git','show',':'+name],cwd=ROOT,check=True,capture_output=True).stdout
        try: content=raw.decode('utf-8')
        except UnicodeDecodeError:
            findings.append((name,'binary file requires manual review'));continue
        for kind,pattern in PATTERNS.items():
            if pattern.search(content): findings.append((name,kind))
    for name,kind in findings: print(f'{name}: {kind}',file=sys.stderr)
    if findings: return 1
    print(f'Privacy guard: {len(paths)} tracked files checked; no configured findings.')
    return 0


if __name__=='__main__': sys.exit(main())
