"""Build-identity regression tests: no ROM, compiler, SDK, or game execution.

Synthetic support files replace expected helper maps only inside isolated mocks.
The restored tap header is read from the actual 0015 patch and keeps its real pin.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

keyboard = load('pal_keyboard_profile')
setup = load('prepare_linux_runtime')


def restored_header():
    text = (ROOT / 'patches/0015-windows-harmony-presses-held-for-the-game.patch').read_text()
    marker = '--- /dev/null\n+++ b/runtime/src/host/pal_tap_hold.h\n@@ -0,0 +1,81 @@\n'
    if text.count(marker) != 1:
        raise AssertionError('0015 must contain the exact 81-line new-file hunk')
    lines = text.split(marker)[1].splitlines()
    if len(lines) != 81 or any(not line.startswith('+') for line in lines):
        raise AssertionError('Unexpected tap header hunk')
    return ''.join(line[1:] + '\n' for line in lines).encode()


class TapSupportIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='tap identity ')
        self.addCleanup(self.tmp.cleanup)
        self.runtime = Path(self.tmp.name)
        host = self.runtime / 'src/host'
        host.mkdir(parents=True)
        (host / 'host.cpp').write_text('#include "pal_tap_hold.h"\n')
        (host / 'settings.cpp').write_text('// synthetic non-UI settings\n')
        self.header = host / 'pal_tap_hold.h'
        self.header.write_bytes(restored_header())
        self.touch = host / 'touch_pad.h'
        self.touch.write_bytes(b'// synthetic touch helper\n')
        expected = dict(keyboard.TAP_HOLD_RUNTIME_FILES)
        expected['src/host/touch_pad.h'] = keyboard.sha(self.touch.read_bytes())
        for mocker in (patch.object(keyboard, 'HARMONY_RUNTIME_HELPERS', {}),
                       patch.object(keyboard, 'HARMONY_UI_RUNTIME_FILES', {}),
                       patch.object(keyboard, 'HARMONY_DISCOVERY_RUNTIME_FILES', {}),
                       patch.object(keyboard, 'HARMONY_EDGE_RUNTIME_FILES', {}),
                       patch.object(keyboard, 'TAP_HOLD_RUNTIME_FILES', expected)):
            mocker.start()
            self.addCleanup(mocker.stop)

    def test_restored_header_is_exact_reviewed_history(self):
        self.assertEqual(keyboard.sha(restored_header()),
                         '072788032e2f8abce11764caa48068ff43c9d0fafc24236240f63debd2288a47')
        self.assertEqual(keyboard.TAP_HOLD_RUNTIME_FILES['src/host/pal_tap_hold.h'],
                         keyboard.sha(restored_header()))

    def test_complete_helper_inventory_includes_tap(self):
        inputs = keyboard.runtime_support_inputs(self.runtime)
        self.assertEqual(inputs[self.header], restored_header())
        self.assertIn(self.touch, inputs)

    def test_missing_helper_is_rejected(self):
        self.header.unlink()
        with self.assertRaisesRegex(ValueError, 'helper changed or missing'):
            keyboard.runtime_support_inputs(self.runtime)

    def test_changed_helper_is_rejected(self):
        self.header.write_bytes(self.header.read_bytes() + b'// drift\n')
        with self.assertRaisesRegex(ValueError, 'helper changed or missing'):
            keyboard.runtime_support_inputs(self.runtime)

    def test_unused_tap_helper_is_mixed_variant(self):
        (self.runtime / 'src/host/host.cpp').write_text('// host without tap\n')
        with self.assertRaisesRegex(ValueError, 'Mixed tap-hold'):
            keyboard.runtime_support_inputs(self.runtime)

    def test_changed_touch_helper_is_not_an_allowed_alternative(self):
        self.touch.write_bytes(b'// old or arbitrary touch helper\n')
        with self.assertRaisesRegex(ValueError, 'helper changed or missing'):
            keyboard.runtime_support_inputs(self.runtime)

    def test_complete_support_manifest_passes(self):
        inputs = keyboard.runtime_support_inputs(self.runtime)
        manifest = {'inputs_sha256': {'runtime': {
            p.relative_to(self.runtime).as_posix(): keyboard.sha(raw)
            for p, raw in inputs.items()}}}
        keyboard.verify_runtime_support_manifest(manifest, self.runtime, inputs)

    def test_manifest_must_own_tap_dependency(self):
        inputs = keyboard.runtime_support_inputs(self.runtime)
        with self.assertRaisesRegex(ValueError, 'Incomplete runtime support manifest'):
            keyboard.verify_runtime_support_manifest({'inputs_sha256': {'runtime': {}}},
                                                      self.runtime, inputs)

    def test_manifest_must_pin_exact_helper_bytes(self):
        inputs = {self.header: self.header.read_bytes()}
        manifest = {'inputs_sha256': {'runtime': {'src/host/pal_tap_hold.h': '0' * 64}}}
        with self.assertRaisesRegex(ValueError, 'Incomplete runtime support manifest'):
            keyboard.verify_runtime_support_manifest(manifest, self.runtime, inputs)


class AudioCadenceSupportIdentityTests(TapSupportIdentityTests):
    def setUp(self):
        super().setUp()
        self.audio = self.runtime/'src/host/pal_audio_jitter_policy.h'
        self.old = b'// old bounded prime\n'
        self.new = b'// quantum bounded prime\n'
        self.audio.write_bytes(self.old)
        for mocker in (patch.object(keyboard, 'HARMONY_RUNTIME_HELPERS',
                                   {'pal_audio_jitter_policy.h': keyboard.sha(self.old)}),
                       patch.object(keyboard, 'AUDIO_CADENCE_HELPER_SHA', keyboard.sha(self.new))):
            mocker.start()
            self.addCleanup(mocker.stop)

    def test_new_host_rejects_old_prime_header(self):
        with (self.runtime/'src/host/host.cpp').open('a') as out: out.write('struct AudioLiveWindow {\n')
        with self.assertRaisesRegex(ValueError, 'helper changed or missing'):
            keyboard.runtime_support_inputs(self.runtime)

    def test_new_host_accepts_exact_new_header(self):
        with (self.runtime/'src/host/host.cpp').open('a') as out: out.write('struct AudioLiveWindow {\n')
        self.audio.write_bytes(self.new)
        self.assertEqual(keyboard.runtime_support_inputs(self.runtime)[self.audio], self.new)

    def test_old_host_rejects_new_prime_header(self):
        self.audio.write_bytes(self.new)
        with self.assertRaisesRegex(ValueError, 'helper changed or missing'):
            keyboard.runtime_support_inputs(self.runtime)


class PatchNumberIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='patch identity ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'patches').mkdir()
        mocker = patch.object(setup, 'ROOT', self.root)
        mocker.start()
        self.addCleanup(mocker.stop)

    def test_user_patch_numbers_include_input_audio_and_render_once(self):
        # 0014/0015 are the input patches, 0016 the guest-consumed field input, and 0017 the stub
        # VBlank clock 0016 needs to link selftest; 0018 adds scene-held continuity;
        # 0019 enables the existing audio policy for SDL's real OHAudio driver name.
        # 0023 adds PCM output; 0024-0026 reduce video decode and handoff cost;
        # 0027 stops background production while servicing SDL lifecycle events.
        self.assertEqual(setup.NUMBERS[-15:], (14, 15, 16, 17, 18, 19, 22, 23, 24, 25, 26, 27, 28, 29, 30))
        self.assertEqual(len(setup.NUMBERS), len(set(setup.NUMBERS)))

    def test_resolves_unique_numbered_files(self):
        for number in (14, 15):
            (self.root / 'patches' / f'{number:04d}-one.patch').touch()
        self.assertEqual([p.name for p in setup.patch_set((14, 15))],
                         ['0014-one.patch', '0015-one.patch'])

    def test_missing_patch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '0015-.* is missing'):
            setup.patch_set((15,))

    def test_collision_is_rejected_instead_of_next_glob(self):
        for name in ('0014-one.patch', '0014-two.patch'):
            (self.root / 'patches' / name).touch()
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            setup.patch_set((14,))


class SetupAddedFileIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='new helper identity ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.clean = self.root / 'clean'
        self.clean.mkdir()
        setup.git(self.clean, 'init', '-b', 'master')
        (self.clean / 'README').write_text('fixture\n')
        setup.git(self.clean, 'add', '.')
        setup.git(self.clean, '-c', 'user.name=Test', '-c', 'user.email=test@localhost',
                  'commit', '-m', 'fixture')
        self.pin = setup.git(self.clean, 'rev-parse', 'HEAD').decode().strip()
        self.diff = self.root / 'add-helper.patch'
        self.diff.write_text('--- /dev/null\n+++ b/new-helper.h\n@@ -0,0 +1 @@\n+exact helper\n')
        self.dest = self.root / 'patched'
        self.assertTrue(self.prepare())

    def prepare(self):
        return setup.prepare(self.clean, self.dest, self.pin, [self.diff])

    def test_new_file_is_tracked_and_repeat_works(self):
        self.assertEqual(setup.git(self.dest, 'ls-files', '--error-unmatch', 'new-helper.h').strip(),
                         b'new-helper.h')
        self.assertFalse(self.prepare())

    def test_modified_added_helper_is_rejected(self):
        (self.dest / 'new-helper.h').write_text('unreviewed helper\n')
        with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
            self.prepare()

    def test_deleted_added_helper_is_rejected(self):
        (self.dest / 'new-helper.h').unlink()
        with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
