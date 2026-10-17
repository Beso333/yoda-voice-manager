"""Installer tests: simulate privileged operations; never run apt/sudo/usermod."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('yoda_setup', Path(__file__).with_name('setup_ubuntu.py'))
SETUP = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(SETUP)


class InstallerTests(unittest.TestCase):
    def simulate(self, flags, existing=False, answer='yes'):
        with tempfile.TemporaryDirectory(prefix='yoda-setup-test-') as temp:
            home = Path(temp)
            global_config = home/'config/voxtype/config.toml'
            global_config.parent.mkdir(parents=True); global_config.write_text('keep existing config')
            events = []
            def run(argv, **kwargs):
                argv = list(map(str, argv)); events.append(('run', argv))
                if '--output_file' in argv:
                    Path(argv[argv.index('--output_file')+1]).write_bytes(b'RIFF'+bytes(100))
                return subprocess.CompletedProcess(argv, 0)
            def download(key, target):
                events.append(('download', key)); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b'test fixture')
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(SETUP, 'check_platform', return_value='Ubuntu 24.04 test'))
                stack.enter_context(patch.object(SETUP.Path, 'home', return_value=home))
                stack.enter_context(patch.dict(SETUP.os.environ, XDG_DATA_HOME=str(home/'data'), XDG_CONFIG_HOME=str(home/'config'), XDG_CACHE_HOME=str(home/'cache')))
                stack.enter_context(patch.object(SETUP.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='tester')))
                stack.enter_context(patch.object(SETUP.grp, 'getgrnam', return_value=SimpleNamespace(gr_mem=[], gr_gid=999)))
                stack.enter_context(patch.object(SETUP.os, 'getgid', return_value=1000))
                stack.enter_context(patch.object(SETUP.os, 'getgroups', return_value=[1000]))
                stack.enter_context(patch.object(SETUP.shutil, 'disk_usage', return_value=SimpleNamespace(free=10*1024**3)))
                stack.enter_context(patch.object(SETUP, 'compatible_voxtype', return_value='/usr/bin/voxtype' if existing else None))
                stack.enter_context(patch.object(SETUP, 'run', side_effect=run))
                stack.enter_context(patch.object(SETUP, 'download', side_effect=download))
                stack.enter_context(patch.object(SETUP.subprocess, 'check_output', return_value=str(home/'Desktop')))
                stack.enter_context(patch.object(SETUP.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='loaded\n')))
                stack.enter_context(patch('builtins.input', return_value=answer))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                result = SETUP.main(flags)
            self.assertEqual(result, 0)
            self.assertEqual(global_config.read_text(), 'keep existing config')
            files = {str(p.relative_to(home)): p.read_bytes() for p in home.rglob('*') if p.is_file()}
            return events, files

    def test_complete_fresh_install_flow(self):
        events, files = self.simulate(['--yes'])
        downloaded = [e[1] for e in events if e[0]=='download']
        self.assertEqual(downloaded, ['voxtype_deb','whisper_small','lili_model','lili_config','lili_model_card'])
        commands = [e[1] for e in events if e[0]=='run']
        self.assertTrue(any(c[:4]==['sudo','apt-get','install','-y'] for c in commands))
        self.assertIn(['sudo','usermod','-aG','input','tester'], commands)
        self.assertIn(['systemctl','--user','disable','--now','voxtype.service'], commands)
        self.assertTrue(any(c[-1]=='piper-tts==1.8.0' for c in commands))
        self.assertIn(b'YODA_VOXTYPE_CONFIG=', files['.local/bin/yoda-voice-manager'])
        self.assertIn(b'YODA_PIPER=', files['.local/bin/yoda-voice-manager'])
        self.assertIn('Desktop/Yoda-Voice-Control.desktop', files)
        self.assertEqual(files['config/yoda/output-state'], b'on\n')
        self.assertIn('config/yoda/voxtype.toml', files)
        self.assertFalse(any('enable' in c for c in commands))

    def test_existing_voxtype_and_no_voice(self):
        events, files = self.simulate(['--yes','--without-voice','--no-desktop-shortcut'], existing=True)
        downloaded = [e[1] for e in events if e[0]=='download']
        self.assertEqual(downloaded, ['whisper_small'])
        self.assertNotIn(b'YODA_PIPER=', files['.local/bin/yoda-voice-manager'])
        self.assertEqual(files['config/yoda/output-state'], b'off\n')
        self.assertNotIn('Desktop/Yoda-Voice-Control.desktop', files)

    def test_dry_run_performs_no_operations(self):
        events, files = self.simulate(['--dry-run'])
        self.assertEqual(events, [])
        self.assertNotIn('.local/bin/yoda-voice-manager', files)

    def test_declining_performs_no_operations(self):
        events, files = self.simulate([], answer='no')
        self.assertEqual(events, [])
        self.assertNotIn('.local/bin/yoda-voice-manager', files)

    def test_verified_download_and_cached_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'asset'; data = b'verified model fixture'
            item = {'url':'https://example.invalid/model','sha256':hashlib.sha256(data).hexdigest()}
            with patch.dict(SETUP.ASSETS, fixture=item), patch.object(SETUP.urllib.request,'urlopen',return_value=io.BytesIO(data)) as fetch:
                SETUP.download('fixture',target);SETUP.download('fixture',target)
                self.assertEqual(target.read_bytes(),data);self.assertEqual(fetch.call_count,1)

    def test_corrupt_download_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'asset';target.write_bytes(b'previous working file')
            item = {'url':'https://example.invalid/model','sha256':hashlib.sha256(b'expected').hexdigest()}
            with patch.dict(SETUP.ASSETS, fixture=item), patch.object(SETUP.time,'sleep'), patch.object(SETUP.urllib.request,'urlopen',side_effect=lambda *a,**k:io.BytesIO(b'corrupt')):
                with self.assertRaises(RuntimeError):SETUP.download('fixture',target)
            self.assertEqual(target.read_bytes(),b'previous working file')
            self.assertEqual(list(Path(temp).glob('.yoda-download-*')),[])

    def test_changed_file_is_backed_up(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'config';target.write_text('original')
            SETUP.write(target,'new')
            self.assertEqual(next(Path(temp).glob('config.backup-*')).read_text(),'original')
            SETUP.write(target,'new')
            self.assertEqual(len(list(Path(temp).glob('config.backup-*'))),1)

    def test_symlink_target_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            original=Path(temp)/'original'; original.write_text('unrelated file')
            link=Path(temp)/'launcher'; link.symlink_to(original)
            SETUP.write(link,'new launcher',True)
            self.assertEqual(original.read_text(),'unrelated file')
            self.assertFalse(link.is_symlink())
            self.assertTrue(next(Path(temp).glob('launcher.backup-*')).is_symlink())

    def test_root_run_is_refused(self):
        with patch.object(SETUP.os,'geteuid',return_value=0):
            with self.assertRaisesRegex(RuntimeError,'NOT with sudo'):SETUP.check_platform()

    def test_arm_is_refused(self):
        with patch.object(SETUP.os,'geteuid',return_value=1000), patch.object(SETUP.Path,'read_text',return_value='ID=ubuntu\nVERSION_ID="24.04"\n'),patch.object(SETUP.platform,'machine',return_value='aarch64'):
            with self.assertRaisesRegex(RuntimeError,'not ARM'):SETUP.check_platform()

    def test_old_ubuntu_is_refused(self):
        with patch.object(SETUP.os,'geteuid',return_value=1000), patch.object(SETUP.Path,'read_text',return_value='ID=ubuntu\nVERSION_ID="22.04"\n'):
            with self.assertRaisesRegex(RuntimeError,'24.04'):SETUP.check_platform()


if __name__ == '__main__':unittest.main(verbosity=2)
