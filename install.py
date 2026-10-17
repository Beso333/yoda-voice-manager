#!/usr/bin/python3
"""Install only project files for the current user; no downloads or sudo."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
APP_ID = 'io.github.Beso333.Yoda'


def save_file(destination, content, executable=False):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.read_bytes() != content:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup = destination.with_name(destination.name + '.backup-' + stamp)
        shutil.copy2(destination, backup)
        print('Backup:', backup)
    destination.write_bytes(content)
    destination.chmod(0o755 if executable else 0o644)
    print('Installed:', destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=Path.home()/'.local')
    parser.add_argument('--config-home', type=Path,
                        default=Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))))
    parser.add_argument('--desktop-dir', type=Path, help='Optional actual desktop directory')
    args = parser.parse_args()
    prefix = args.prefix.expanduser().resolve()
    binary = prefix/'bin/yoda-voice-manager'
    executable = str(binary).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    desktop = ('[Desktop Entry]\nType=Application\nName=Yoda – Voice Control\n'
               'Comment=Local voice commands tailored to Slovak\n'
               f'Exec="{executable}"\nIcon=audio-input-microphone-symbolic\n'
               'Terminal=false\nCategories=Utility;Accessibility;\nStartupNotify=true\n')
    save_file(binary, (ROOT/'yoda-voice-manager').read_bytes(), True)
    save_file(prefix/f'share/applications/{APP_ID}.desktop', desktop.encode())
    save_file(prefix/'share/doc/yoda/HELP.txt', (ROOT/'HELP.txt').read_bytes())
    config = args.config_home.expanduser().resolve()/'voxtype/config.toml'
    if not config.exists():
        save_file(config, (ROOT/'voxtype.example.toml').read_bytes())
    else:
        print('Preserved existing configuration:', config)
    if args.desktop_dir:
        save_file(args.desktop_dir.expanduser().resolve()/'Yoda-Voice-Control.desktop', desktop.encode(), True)
    print('Done. Install/check dependencies separately before launching Yoda.')


if __name__ == '__main__':
    main()
