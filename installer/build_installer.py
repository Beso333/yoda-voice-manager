#!/usr/bin/python3
"""Build one reproducible self-extracting Ubuntu installer; no dependencies."""
import argparse
import base64
import hashlib
import io
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
FILES = ['yoda-voice-manager', 'HELP.txt', 'voxtype.example.toml', 'test_yoda.py',
         'installer/setup_ubuntu.py', 'installer/downloads.json']
BOOTSTRAP = r'''#!/usr/bin/env bash
set -euo pipefail
if [[ ! -x /usr/bin/python3 ]]; then
    echo "System Python 3 is required. Install python3 using Ubuntu Software/apt first." >&2
    exit 1
fi
exec /usr/bin/python3 - "$0" "$@" <<'PYBOOT'
import ast, base64, hashlib, io, pathlib, stat, subprocess, sys, tempfile, zipfile
archive_path = pathlib.Path(sys.argv[1])
args = sys.argv[2:]
marker = b"\n__YODA_PAYLOAD_BASE64__\n"
payload = base64.b64decode(archive_path.read_bytes().split(marker, 1)[1], validate=False)
expected = "PAYLOAD_SHA256"
if hashlib.sha256(payload).hexdigest() != expected:
    raise SystemExit('Installer payload checksum mismatch. Download a fresh copy.')
with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    for entry in archive.infolist():
        name = pathlib.PurePosixPath(entry.filename)
        if name.is_absolute() or '..' in name.parts or stat.S_ISLNK(entry.external_attr >> 16):
            raise SystemExit('Unsafe installer archive entry')
        if entry.filename.endswith('.py') or entry.filename == 'yoda-voice-manager':
            ast.parse(archive.read(entry).decode('utf-8'), filename=entry.filename)
    if '--verify' in args:
        print('Verified embedded payload SHA-256, paths and Python syntax:', expected)
        print('Payload files:', len(archive.infolist()))
        raise SystemExit(0)
    if '--extract-only' in args:
        index = args.index('--extract-only')
        if len(args) != 2 or index != 0:
            raise SystemExit('Usage: bash Yoda-Ubuntu-Setup.run --extract-only NEW_DIRECTORY')
        destination = pathlib.Path(args[1]).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=False)
        archive.extractall(destination)
        print('Extracted without installation:', destination)
        raise SystemExit(0)
    with tempfile.TemporaryDirectory(prefix='yoda-setup-') as temp:
        archive.extractall(temp)
        tty = None
        if not any(flag in args for flag in ('--yes', '--dry-run', '--help', '-h')):
            try:
                tty = open('/dev/tty', 'r')
            except OSError:
                raise SystemExit('Run from an interactive terminal, or explicitly use --yes.')
        try:
            result = subprocess.run(['/usr/bin/python3', str(pathlib.Path(temp)/'installer/setup_ubuntu.py'), *args],
                                    stdin=tty if tty else subprocess.DEVNULL)
            raise SystemExit(result.returncode)
        finally:
            if tty:
                tty.close()
PYBOOT
__YODA_PAYLOAD_BASE64__
'''


def build(destination):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in FILES:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (ROOT/name).read_bytes())
    payload = data.getvalue()
    header = BOOTSTRAP.replace('PAYLOAD_SHA256', hashlib.sha256(payload).hexdigest())
    encoded = base64.b64encode(payload).decode('ascii')
    result = header + '\n'.join(encoded[i:i+76] for i in range(0, len(encoded), 76))+'\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result)
    destination.chmod(0o755)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix+'.sha256').write_text(digest+'  '+destination.name+'\n')
    print(destination, len(result.encode()), 'bytes', digest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist/Yoda-Ubuntu-Setup.run')
    build(parser.parse_args().output)
