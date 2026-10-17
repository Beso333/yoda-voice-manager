"""Focused regression tests; no microphone, desktop actions or cloud access."""
import runpy
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

MODULE = runpy.run_path(str(Path(__file__).with_name('yoda-voice-manager')), run_name='yoda_tests')
WINDOW = MODULE['YodaWindow']
GLOBALS = WINDOW.try_execute_transcript.__globals__


class Entry:
    def __init__(self, text=''):
        self.text = text
        self.sensitive = True
    def get_text(self): return self.text
    def set_text(self, text): self.text = text
    def set_position(self, _position): pass
    def set_sensitive(self, value): self.sensitive = value


class Harness:
    def __init__(self, text=''):
        self.closed = False
        self.command_in_progress = False
        self.speech_in_progress = False
        self.last_executed_text = ''
        self.previous_voxtype_state = 'idle'
        self.voice_available = True
        self.voxtype_process = Mock()
        self.voxtype_process.poll.return_value = None
        self.entry = Entry(text)
        self.orb = SimpleNamespace(state='ready', animation_source=0)
        self.output_switch = Mock()
        self.output_switch.get_active.return_value = False
        self.show_result = Mock()
        self.set_state = Mock(side_effect=lambda state, *args: setattr(self.orb, 'state', state))
        self.speech_lock = threading.Lock()
        self.speech_cancel = threading.Event()
        self.speech_process = None
        self.get_application = Mock(return_value=Mock())
        self.stop_voice_service = Mock()


for name in ('try_execute_transcript', 'finish_command', 'poll_voxtype', 'read_voxtype_state',
             'stop_speech', 'speak', 'finish_speech', 'handle_entry', 'on_close', 'toggle_output'):
    setattr(Harness, name, getattr(WINDOW, name))


class YodaTests(unittest.TestCase):
    def execute(self, window, argv=None):
        callbacks = []
        done = threading.Event()
        def enqueue(delay, callback, *args):
            callbacks.append((callback, args)); done.set(); return 1
        command = MODULE['Command']('Test', 'Test dokončený.', argv or ('/usr/bin/true',))
        with patch.dict(GLOBALS['COMMANDS'], {'otvor terminal': command}), patch.object(MODULE['GLib'], 'timeout_add', enqueue):
            window.try_execute_transcript()
            self.assertTrue(done.wait(3), 'Command worker did not complete')
        callback, args = callbacks[0]
        callback(*args)

    def test_exact_polite_command_executes(self):
        window = Harness('OtvOr terminál prosím!')
        self.execute(window)
        self.assertEqual(window.orb.state, 'ready')
        window.show_result.assert_called_with('Test dokončený.', 'success')
        self.assertEqual(window.entry.text, 'OtvOr terminál prosím!')

    def test_extra_commands_and_shell_text_are_rejected(self):
        for text in ('otvor terminal a zamkni pocitac', 'otvor terminal; rm -rf /',
                     'otvor terminal $(id)', 'otvor terminal prosim prosim', 'nahodny text'):
            with self.subTest(text=text), patch('subprocess.run') as run:
                window = Harness(text); window.try_execute_transcript()
                run.assert_not_called(); self.assertEqual(window.orb.state, 'error')

    def test_nonzero_exit_is_failure(self):
        window = Harness('otvor terminal')
        self.execute(window, ('/usr/bin/false',))
        self.assertEqual(window.orb.state, 'error')
        self.assertTrue(window.entry.sensitive)
        self.assertEqual(window.show_result.call_args.args[1], 'error')

    def test_missing_executable_is_failure(self):
        window = Harness('otvor terminal')
        self.execute(window, ('/nonexistent/yoda-command',))
        self.assertEqual(window.orb.state, 'error')

    def test_timeout_is_failure(self):
        window = Harness('otvor terminal')
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('test', 15)):
            self.execute(window)
        self.assertEqual(window.orb.state, 'error')

    def test_completion_during_recording_never_speaks(self):
        window = Harness(); window.orb.state = 'listening'
        window.output_switch.get_active.return_value = True
        window.speak = Mock()
        window.finish_command(True, 'Hotovo.')
        self.assertEqual(window.orb.state, 'listening'); window.speak.assert_not_called()

    def test_busy_transcript_is_retained_with_instruction(self):
        window = Harness('otvor terminal'); window.command_in_progress = True
        with patch('subprocess.run') as run:
            window.try_execute_transcript(); run.assert_not_called()
        self.assertEqual(window.entry.text, 'otvor terminal')
        self.assertIn('Enter', window.show_result.call_args.args[0])

    def test_busy_voice_result_does_not_leave_transcribing_stuck(self):
        window = Harness('otvor subory'); window.last_executed_text = 'otvor terminal'
        window.command_in_progress = True; window.orb.state = 'transcribing'
        window.try_execute_transcript(); window.finish_command(True, 'Hotovo.')
        self.assertEqual(window.orb.state, 'ready')
        self.assertIn('Enter', window.show_result.call_args.args[0])
        self.assertEqual(window.entry.text, 'otvor subory')

    def test_corrupt_transcript_is_visible_error(self):
        with tempfile.TemporaryDirectory() as temp:
            state, transcript = Path(temp)/'state', Path(temp)/'transcript'
            state.write_text('idle'); transcript.write_bytes(bytes([255, 254]))
            window = Harness()
            with patch.dict(GLOBALS, STATE_FILE=state, TRANSCRIPT_FILE=transcript): window.poll_voxtype()
            self.assertEqual(window.orb.state, 'error')

    def test_closed_window_never_executes(self):
        window = Harness('otvor terminal'); window.closed = True
        with patch('subprocess.run') as run:
            window.try_execute_transcript(); run.assert_not_called()

    def test_new_recording_cancels_speech(self):
        with tempfile.TemporaryDirectory() as temp:
            state, transcript = Path(temp)/'state', Path(temp)/'transcript'
            state.write_text('recording'); transcript.write_text('old text')
            window = Harness(); window.speech_in_progress = True
            process = Mock(); process.poll.return_value = None; window.speech_process = process
            with patch.dict(GLOBALS, STATE_FILE=state, TRANSCRIPT_FILE=transcript): window.poll_voxtype()
            process.terminate.assert_called_once()
            self.assertFalse(window.speech_in_progress)
            self.assertFalse(transcript.exists())
            self.assertEqual(window.orb.state, 'listening')

    def test_missing_state_is_visible_error(self):
        with tempfile.TemporaryDirectory() as temp:
            window = Harness()
            with patch.dict(GLOBALS, STATE_FILE=Path(temp)/'missing'): window.poll_voxtype()
            self.assertEqual(window.orb.state, 'error')

    def test_dead_daemon_is_visible_error(self):
        window = Harness(); window.voxtype_process.poll.return_value = 1
        window.poll_voxtype()
        self.assertFalse(window.voice_available); self.assertEqual(window.orb.state, 'error')

    def test_transcript_is_consumed_only_once(self):
        with tempfile.TemporaryDirectory() as temp:
            state, transcript = Path(temp)/'state', Path(temp)/'transcript'
            state.write_text('idle'); transcript.write_text('otvor terminal')
            window = Harness(); window.try_execute_transcript = Mock()
            with patch.dict(GLOBALS, STATE_FILE=state, TRANSCRIPT_FILE=transcript):
                window.poll_voxtype(); window.poll_voxtype()
            window.try_execute_transcript.assert_called_once()
            self.assertEqual(window.entry.text, 'otvor terminal')

    def test_cancelled_voice_callback_cannot_override_new_state(self):
        window = Harness(); old = window.speech_cancel; old.set()
        window.speech_cancel = threading.Event(); window.speech_in_progress = True
        window.orb.state = 'listening'
        window.finish_speech(old, True)
        self.assertEqual(window.orb.state, 'listening'); window.set_state.assert_not_called()

    def test_speech_process_terminates_on_close(self):
        # Exercise actual child cancellation, not only a mocked terminate method.
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp)/'voice'
            fake.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(10)\n'); fake.chmod(0o700)
            window = Harness(); done = threading.Event()
            def enqueue(*_args): done.set(); return 1
            with patch.dict(GLOBALS, PIPER=fake, LILI=Path('/usr/bin/true'), MPV=str(fake)), patch.object(MODULE['GLib'], 'idle_add', enqueue):
                window.speak('test')
                deadline = time.monotonic()+2
                while window.speech_process is None and time.monotonic()<deadline: time.sleep(.01)
                process = window.speech_process; self.assertIsNotNone(process)
                window.on_close()
                self.assertTrue(done.wait(2), 'Voice worker did not stop')
                self.assertIsNotNone(process.poll()); self.assertTrue(window.closed)

    def test_switch_off_stops_current_voice(self):
        with tempfile.TemporaryDirectory() as temp:
            window = Harness(); window.orb.state = 'speaking'; window.stop_speech = Mock()
            path = Path(temp)/'voice-state'
            with patch.dict(GLOBALS, VOICE_STATE=path): window.toggle_output(None, False)
            self.assertEqual(path.read_text(), 'off\n'); window.stop_speech.assert_called_once()
            self.assertEqual(window.orb.state, 'ready')


if __name__ == '__main__': unittest.main(verbosity=2)
