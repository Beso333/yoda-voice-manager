# Testing and known limits

Run with the system Python that provides PyGObject:

```sh
/usr/bin/python3 yoda-voice-manager --self-test
/usr/bin/python3 test_yoda.py
```

The 17 regression cases cover exact/polite allow-list matching, rejected compound/shell-like text, nonzero exit, missing executable, timeout, closed-window dispatch, busy input, transcript consumption, missing/corrupt state, daemon exit, speech interruption, stale callbacks and switch persistence. Desktop actions are mocked/replaced with harmless processes. One disposable local child verifies real cancellation.

## Native verification

The original locally deployed version was verified on Ubuntu 26.04.1, GNOME 50.1/Wayland, GTK 4.22 and Voxtype 1.1.1:

- Actual Right Ctrl recording and local Slovak transcription: a 2.05-second human clip transcribed in 1.23 seconds and opened GNOME Terminal. This is one measurement, not a performance guarantee.
- Compact 180×368 window, unchanged instance on a second desktop launch.
- Completed transcript file consumed once; an unknown compound phrase rejected; a known terminal command dispatched.
- Real Piper/mpv playback observed.
- Intentional termination of only the owned Voxtype produced a visible error; closing reaped the daemon; reopening recovered.
- Short idle CPU sample: Yoda 0.5%, Voxtype 1.5% of one CPU core on the tested laptop.

The publication copy additionally replaces user-specific paths with configurable defaults and includes a file-only installer. Regression tests and an installation into a disposable temporary directory are used to check this packaging. These checks do not establish compatibility with every desktop or distribution.

## Limits

- This audit did not verify a physical click on the voice switch; accessibility automation could not activate the switch reliably. The switch callback and process cancellation are regression-tested.
- Lock, volume and mute actions are not triggered in automated tests. Their fixed argument mappings and installed executable availability were inspected on the original laptop.
- Codex/OpenCode desktop identifiers depend on installation method. The provided IDs matched the tested laptop.
- Recognition can be wrong. Unknown phrases remain editable and are never guessed into another command.
- A zero command/launcher exit status is not proof that another application completed its own internal work.
- Unexpected Voxtype exit currently requires closing/reopening Yoda.
