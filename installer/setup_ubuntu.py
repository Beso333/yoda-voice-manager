#!/usr/bin/python3
"""Complete, interactive per-user Yoda setup for Ubuntu 24.04+ on amd64."""
import argparse
from datetime import datetime
import grp
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
ASSETS = json.loads((ROOT/'installer/downloads.json').read_text())
PACKAGES = ['ca-certificates', 'python3', 'python3-venv', 'python3-gi',
            'python3-cairo', 'python3-gi-cairo', 'gir1.2-gtk-4.0', 'mpv', 'gnome-terminal',
            'nautilus', 'wireplumber', 'pipewire-alsa', 'xdg-user-dirs']


def run(argv, **kwargs):
    print('+', shlex.join(map(str, argv)), flush=True)
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backup(path):
    if path.exists() or path.is_symlink():
        target = path.with_name(path.name+'.backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        shutil.copy2(path, target, follow_symlinks=False)
        print('Backup:', target)


def write(path, content, executable=False):
    data = content.encode() if isinstance(content, str) else content
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and path.read_bytes() != data):
        backup(path)
    partial = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.yoda-write-', delete=False) as output:
            partial = Path(output.name)
            output.write(data)
        partial.chmod(0o755 if executable else 0o600)
        partial.replace(path)
    finally:
        if partial and partial.exists():
            partial.unlink()


def download(key, target):
    item = ASSETS[key]
    if target.is_file() and checksum(target) == item['sha256']:
        print('Verified existing file:', target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    # Unique partial file; an interrupted download never replaces a working file.
    last_error = None
    for attempt in range(3):
        partial = None
        try:
            print('Downloading:', item['url'], flush=True)
            request = urllib.request.Request(item['url'], headers={'User-Agent': 'Yoda-Ubuntu-Setup/1'})
            with urllib.request.urlopen(request, timeout=90) as response, tempfile.NamedTemporaryFile(dir=target.parent, prefix='.yoda-download-', delete=False) as output:
                partial = Path(output.name)
                digest = hashlib.sha256()
                total, reported = 0, 0
                while True:
                    chunk = response.read(1024*1024)
                    if not chunk:
                        break
                    digest.update(chunk); output.write(chunk); total += len(chunk)
                    if total-reported >= 32*1024*1024:
                        print(f'  {total//(1024*1024)} MiB downloaded', flush=True); reported = total
            if digest.hexdigest() != item['sha256']:
                raise ValueError('SHA-256 mismatch for '+key)
            backup(target)
            partial.replace(target)
            print('Verified SHA-256:', target)
            return
        except (OSError, ValueError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(attempt+1)
        finally:
            if partial and partial.exists():
                partial.unlink()
    raise RuntimeError(f'Download failed for {key}: {last_error}')


def check_platform():
    if os.geteuid() == 0:
        raise RuntimeError('Run as your regular desktop user, NOT with sudo. Setup requests sudo only when needed.')
    release = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1); release[key] = value.strip('"')
    version = tuple(int(p) for p in release.get('VERSION_ID', '0.0').split('.')[:2])
    if release.get('ID') != 'ubuntu' or version < (24, 4):
        raise RuntimeError('This installer requires Ubuntu 24.04 or newer (Ubuntu GNOME desktop).')
    if platform.machine() not in ('x86_64', 'amd64'):
        raise RuntimeError('This installer supports 64-bit Intel/AMD PCs only, not ARM.')
    if not shutil.which('sudo'):
        raise RuntimeError('sudo is required for installing system dependencies.')
    return release.get('PRETTY_NAME', 'Ubuntu')


def compatible_voxtype():
    candidate = shutil.which('voxtype')
    if not candidate:
        return None
    try:
        result = subprocess.run([candidate, '--version'], capture_output=True, text=True, check=True)
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', result.stdout)
        help_text = subprocess.run([candidate, '--help'], capture_output=True, text=True, check=True).stdout
        if match and tuple(map(int, match.groups())) >= (1, 1, 1) and all(flag in help_text for flag in ('--file-path', '--whisper-mode', '--file-mode')):
            return candidate
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def desktop_directory(home):
    try:
        path = subprocess.check_output(['xdg-user-dir', 'DESKTOP'], text=True).strip()
        if path and Path(path).is_absolute() and Path(path).resolve() != home.resolve():
            return Path(path)
    except (OSError, subprocess.SubprocessError):
        pass
    return home/'Desktop'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Show the plan without downloads or installation')
    parser.add_argument('--yes', action='store_true', help='Accept the displayed system, service and input-group changes')
    parser.add_argument('--without-voice', action='store_true', help='Skip installing Piper and the Lili voice')
    parser.add_argument('--no-desktop-shortcut', action='store_true')
    args = parser.parse_args(argv)
    distro = check_platform()
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME', str(home/'.local/share')))/'yoda'
    config_home = Path(os.environ.get('XDG_CONFIG_HOME', str(home/'.config')))
    config = config_home/'yoda'
    cache = Path(os.environ.get('XDG_CACHE_HOME', str(home/'.cache')))/'yoda-installer'
    prefix = home/'.local'
    user = pwd.getpwuid(os.getuid()).pw_name
    try:
        input_group = grp.getgrnam('input')
    except KeyError:
        raise RuntimeError('The standard input group is missing. Configure keyboard access for this Ubuntu installation first.')
    add_group = user not in input_group.gr_mem and os.getgid() != input_group.gr_gid
    need_login = input_group.gr_gid not in os.getgroups()
    voxtype = compatible_voxtype()
    voice = not args.without_voice
    print('\nYODA COMPLETE UBUNTU SETUP — tailored to Slovak\n')
    print('System:', distro)
    print('1. Install Ubuntu dependencies using sudo apt-get:', ', '.join(PACKAGES))
    print('2.', 'Reuse compatible Voxtype: '+voxtype if voxtype else 'Download and install verified Voxtype 1.1.1 amd64 package')
    print('3. Download/verify local Whisper small (~488 MB).')
    print('4.', 'Install private Piper 1.8.0 environment and Lili voice (~63 MB model).' if voice else 'Skip voice-output installation.')
    print('5. Install Yoda, English help, private Slovak configuration and application launcher.')
    print('6. Disable only the separate voxtype.service for this user, if present. Do not enable autostart.')
    print('7.', 'Add '+user+' to input group (broad keyboard/device access; logout/login required).' if add_group else 'Keep existing input-group membership.')
    print('8.', 'Create a desktop shortcut.' if not args.no_desktop_shortcut else 'Skip desktop shortcut.')
    print('Internet, sudo privileges and several GB of free disk space are required.\n')
    if args.dry_run:
        print('DRY RUN: no files, packages, services, groups or downloads changed.')
        return 0
    if not args.yes and input('Apply this setup? [y/N] ').strip().lower() not in ('y', 'yes'):
        print('Cancelled. No changes made.'); return 0
    if shutil.disk_usage(home).free < 3*1024**3:
        raise RuntimeError('At least 3 GiB of free disk space in your home filesystem is required.')
    run(['sudo', '-v'])
    if not voxtype:
        package = cache/'voxtype_1.1.1-1_amd64.deb'
        download('voxtype_deb', package)
    run(['sudo', 'apt-get', 'update'])
    install = ['sudo', 'apt-get', 'install', '-y', *PACKAGES]
    if not voxtype:
        install.append(str(package))
    run(install)
    voxtype = voxtype or '/usr/bin/voxtype'
    models = Path(os.environ.get('XDG_DATA_HOME', str(home/'.local/share')))/'voxtype/models'
    download('whisper_small', models/'ggml-small.bin')
    piper = data/'piper/venv/bin/piper'
    model = data/'voices/sk_SK-lili-medium.onnx'
    if voice:
        if not (data/'piper/venv/bin/python').is_file():
            run(['/usr/bin/python3', '-m', 'venv', data/'piper/venv'])
        run([data/'piper/venv/bin/python', '-m', 'pip', '--isolated', 'install', '--index-url', 'https://pypi.org/simple', '--disable-pip-version-check', '--only-binary=:all:', 'piper-tts=='+ASSETS['piper_version']])
        download('lili_model', model)
        download('lili_config', model.with_name(model.name+'.json'))
        download('lili_model_card', data/'voices/Lili-MODEL_CARD')
        with tempfile.TemporaryDirectory(prefix='yoda-voice-check-') as temp:
            audio = Path(temp)/'check.wav'
            run([piper, '--model', model, '--output_file', audio], input='Yoda je pripravená.\n', text=True, timeout=40)
            if not audio.is_file() or audio.stat().st_size < 44:
                raise RuntimeError('Piper did not generate a valid audio file.')
    settings = (ROOT/'voxtype.example.toml').read_text()
    settings = settings.replace('model = "small"', 'model = '+json.dumps(str(models/'ggml-small.bin')))
    write(config/'voxtype.toml', settings)
    write(data/'yoda-voice-manager.py', (ROOT/'yoda-voice-manager').read_bytes())
    write(prefix/'share/doc/yoda/HELP.txt', (ROOT/'HELP.txt').read_bytes())
    wrapper = '#!/bin/sh\n'
    environment = {'YODA_VOXTYPE': str(voxtype), 'YODA_VOXTYPE_CONFIG': str(config/'voxtype.toml')}
    if voice:
        environment.update(YODA_PIPER=str(piper), YODA_LILI_MODEL=str(model))
    for key, value in environment.items():
        wrapper += 'export '+key+'='+shlex.quote(value)+'\n'
    wrapper += 'exec /usr/bin/python3 '+shlex.quote(str(data/'yoda-voice-manager.py'))+' "$@"\n'
    launcher = prefix/'bin/yoda-voice-manager'
    write(launcher, wrapper, True)
    quoted = str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    entry = ('[Desktop Entry]\nType=Application\nName=Yoda – Voice Control\n'
             'Comment=Local voice commands tailored to Slovak\n'
             f'Exec="{quoted}"\nIcon=audio-input-microphone-symbolic\nTerminal=false\n'
             'Categories=Utility;Accessibility;\nStartupNotify=true\n')
    write(prefix/'share/applications/io.github.Beso333.Yoda.desktop', entry)
    if not (config/'output-state').exists():
        write(config/'output-state', 'on\n' if voice else 'off\n')
    if not args.no_desktop_shortcut:
        shortcut = desktop_directory(home)/'Yoda-Voice-Control.desktop'
        write(shortcut, entry, True)
        subprocess.run(['gio', 'set', str(shortcut), 'metadata::trusted', 'true'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    service = subprocess.run(['systemctl', '--user', 'show', 'voxtype.service', '--property=LoadState', '--value'], capture_output=True, text=True)
    if service.returncode == 0 and service.stdout.strip() not in ('', 'not-found'):
        run(['systemctl', '--user', 'disable', '--now', 'voxtype.service'])
    elif service.returncode != 0:
        print('Note: could not inspect user services. Stop any independent Voxtype daemon before using Yoda.')
    if add_group:
        run(['sudo', 'usermod', '-aG', 'input', user])
    run([launcher, '--self-test'])
    run(['/usr/bin/python3', ROOT/'test_yoda.py'])
    run([voxtype, '--config', config/'voxtype.toml', 'config'], stdout=subprocess.DEVNULL)
    print('\nSETUP COMPLETE. Yoda has NOT been started automatically.')
    if need_login:
        print('LOG OUT of Ubuntu and log back in before using Right Ctrl.')
    print('Open Yoda – Voice Control from the application menu or desktop shortcut.')
    print('If GNOME asks, choose Allow Launching. Hold Right Ctrl and say: otvor terminál.')
    print('Models and speech run locally after installation; no cloud API is needed.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print('\nSETUP FAILED:', error, file=sys.stderr)
        print('Setup may be partially complete. Fix the reported issue and rerun; changed user files have timestamped backups.', file=sys.stderr)
        raise SystemExit(1)
