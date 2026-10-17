# Complete Ubuntu setup

Yoda is tailored to Slovak. This installer and its documentation are in English; the app interface, commands and Lili voice remain Slovak.

## Download and run

Download [Yoda-Ubuntu-Setup.run](https://raw.githubusercontent.com/Beso333/yoda-voice-manager/main/dist/Yoda-Ubuntu-Setup.run) to the other computer. Open a terminal in the download directory and run:

```bash
bash Yoda-Ubuntu-Setup.run
```

Run it as your regular desktop user, **not** with `sudo bash`. It prints the planned changes and asks for confirmation, then requests sudo privileges only for the required system changes. Downloading through the browser and running the saved file avoids piping a remote script directly into a shell.

Requirements: Ubuntu GNOME desktop 24.04 or newer, a 64-bit Intel/AMD CPU, system Python 3, an internet connection, sudo privileges and at least 3 GiB of free space in the home filesystem. Additional free space may be needed on the system filesystem for apt packages. ARM and older Ubuntu releases are rejected. Native app testing has been on Ubuntu 26.04.1; a real clean install on Ubuntu 24.04 has not been performed.

## What it installs

- Ubuntu GTK/Python, Cairo integration, audio and desktop dependencies through apt.
- The official Voxtype 1.1.1 amd64 package when no compatible version is present. A compatible existing installation is reused.
- A pinned multilingual Whisper `small` model, about 488 MB, with language set to `sk`.
- Piper 1.8.0 in a private virtual environment, plus the local Lili model, JSON configuration and model card. The voice model is about 63 MB. Piper dependencies come from PyPI.
- Yoda, the English help, application-menu entry and a localized-directory-aware desktop shortcut.

Downloads and package dependencies can require substantially more data than the two model sizes above. The installer file is small because it downloads third-party dependencies; it is **not an offline installer**. Once installed, recognition and spoken confirmations run locally.

Downloaded Voxtype/model assets are pinned to specific versions/revisions and SHA-256 hashes in [installer/downloads.json](../installer/downloads.json). No binary or voice model is redistributed inside the installer. Upstream model/license information is retained in the Lili model card.

## Keyboard access and services

The confirmation includes adding the current user to the `input` group when needed. This grants broad access to keyboard/input devices. If the group is not yet active in the current session, log out of Ubuntu and log back in after setup.

The installer disables only the current user's separate `voxtype.service`, if present. It does not kill arbitrary manually launched processes. Close any existing Yoda or manually launched Voxtype before setup. No boot/login autostart is enabled, and the installer does not automatically start recording or launch Yoda.

After setup, manually open **Yoda – Voice Control**, wait for readiness and hold Right Ctrl while saying `otvor terminál`. Release the key to transcribe. GNOME may ask you to choose **Allow Launching** for the desktop shortcut.

## Installed locations

- Launcher: `~/.local/bin/yoda-voice-manager`.
- App code: `$XDG_DATA_HOME/yoda/yoda-voice-manager.py`, normally `~/.local/share/yoda/yoda-voice-manager.py`.
- Private Piper environment: `$XDG_DATA_HOME/yoda/piper/venv`.
- Lili files: `$XDG_DATA_HOME/yoda/voices`.
- Whisper model: `$XDG_DATA_HOME/voxtype/models/ggml-small.bin`.
- Yoda-specific Voxtype configuration: `$XDG_CONFIG_HOME/yoda/voxtype.toml`.
- English help: `~/.local/share/doc/yoda/HELP.txt`.

The global `~/.config/voxtype/config.toml` is preserved. Existing changed Yoda files are backed up beside themselves with a timestamp. Re-running setup reuses hash-verified assets and existing compatible Voxtype; it may retry apt/pip dependency checks. The managed Yoda-specific configuration is regenerated with a backup when it differs. An existing voice on/off preference is preserved; a fresh complete installation enables voice output.

## Options

```bash
# Inspect the embedded payload, without installation or downloads:
bash Yoda-Ubuntu-Setup.run --verify

# Preview the setup plan, without installation or downloads:
bash Yoda-Ubuntu-Setup.run --dry-run

# Install recognition without Piper/Lili:
bash Yoda-Ubuntu-Setup.run --without-voice

# Skip the desktop shortcut:
bash Yoda-Ubuntu-Setup.run --no-desktop-shortcut

# Explicitly accept the displayed changes (sudo may still prompt):
bash Yoda-Ubuntu-Setup.run --yes

# Extract into a NEW directory without installing anything:
bash Yoda-Ubuntu-Setup.run --extract-only ./yoda-setup-source
```

The embedded payload is checked before extraction. You can also download [the installer checksum](../dist/Yoda-Ubuntu-Setup.run.sha256) into the same directory and run `sha256sum -c Yoda-Ubuntu-Setup.run.sha256`.

If setup fails, it reports the error and exits unsuccessfully. Earlier package/file changes may already be present; setup is not an atomic system transaction. Fix the reported issue and rerun. Do not remove unrelated applications or reset a working system to retry.

## Building and testing

```bash
python3 installer/build_installer.py
python3 installer/test_setup.py
python3 test_yoda.py
bash dist/Yoda-Ubuntu-Setup.run --verify
bash dist/Yoda-Ubuntu-Setup.run --dry-run
```

Installer tests simulate apt, sudo, user/group changes, service changes and model downloads inside temporary directories. They do not install system packages. They also exercise real checksum handling with small fixtures and preservation of existing files/symlink targets. Separate checks downloaded the actual upstream Lili JSON/model card and verified their hashes.

A full clean-machine installation has not been physically verified. The install-flow simulation, embedded-payload checks and previously verified native Yoda behavior are the current evidence, not a claim that every Ubuntu PC has been tested.

Upstream references: [Voxtype downloads](https://voxtype.io/download/), [Voxtype 1.1.1](https://github.com/peteonrails/voxtype/releases/tag/v1.1.1), [Piper CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md), [Lili model files](https://huggingface.co/rhasspy/piper-voices/tree/main/sk/sk_SK/lili/medium).
