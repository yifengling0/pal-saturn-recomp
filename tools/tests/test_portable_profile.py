import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('portable_profile', Path(__file__).parents[1] / 'run_pal_profile.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def make_exe(tmp_path):
    exe = tmp_path / 'path with spaces' / 'saturn.exe'
    exe.parent.mkdir()
    exe.write_bytes(b'fixture, never executed')
    return exe


def test_manifest_and_profile_boundaries(tmp_path):
    exe = make_exe(tmp_path)
    manifest = exe.parent / m.MANIFEST
    manifest.write_text(json.dumps({'schema': 1, 'exe_sha256': m.sha256(exe), 'features': ['input_v4', 'effect_wait_v3']}))
    for profile, values in m.PROFILES.items():
        with patch.dict(os.environ, {'PAL_RESPONSIVE_WAKE': '1', 'PAL_SHORT_EFFECT_PREP': '1', 'SATURN_DATA_CD_SPEED': '4'}), patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=17)) as run:
            assert m.main([profile, '--exe', str(exe), '--', '--cue', 'disc path/game.cue']) == 17
            args, kwargs = run.call_args
            assert args[0] == [str(exe), '--cue', 'disc path/game.cue']
            env = kwargs['env']
            assert tuple(env[k] for k in ('PAL_RESPONSIVE_INPUT', 'PAL_RESPONSIVE_ALIGN', 'PAL_RESPONSIVE_WAKE')) == values
            assert env['PAL_SHORT_EFFECT_PREP'] == '0'
            assert env['SATURN_DATA_CD_SPEED'] == '1'
    with patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
        assert m.main(['precise', '--quick-spell', '--exe', str(exe)]) == 0
        assert run.call_args.kwargs['env']['PAL_SHORT_EFFECT_PREP'] == '1'


def test_unidentified_or_changed_binary_fails_closed(tmp_path):
    exe = make_exe(tmp_path)
    with patch.object(m.subprocess, 'run') as run:
        assert m.main(['precise', '--exe', str(exe)]) == 3
        run.assert_not_called()
        (exe.parent / m.MANIFEST).write_text(json.dumps({'schema': 1, 'exe_sha256': 'wrong', 'features': ['input_v4']}))
        assert m.main(['precise', '--exe', str(exe)]) == 3
        run.assert_not_called()


def test_original_accepts_baseline_and_missing_exe_fails(tmp_path):
    exe = make_exe(tmp_path)
    with patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
        assert m.main(['original', '--exe', str(exe)]) == 0
    assert m.main(['original', '--exe', str(exe.parent / 'missing.exe')]) == 3
