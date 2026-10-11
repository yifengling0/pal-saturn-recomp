"""Opt-in data-CD runtime source transform for a dedicated build copy only.

The stable five-patch runtime remains untouched. This module has no game data,
Linux dependencies or build/compiler side effects. Call apply_data_cd_speed()
on the copied runtime before configuring that build.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path

_SOURCE = Path('src/machine/cdblock.cpp')
_BASE_SHA256 = '457dfbc5933e7062a69dd22f7c616e2db0f2da732519d3106dfe926c85950a3c'
_PATCHED_SHA256 = 'cfb12d44872e17e020281dcf7af49caee1144c6970ba306e1e9141c017ef128a'
_FEATURE = 'SATURN_DATA_CD_SPEED'
_EDITS = (
    ('#include <cstring>\n', '#include <cstring>\n#include <cstdlib>\n'),
    ('static bool g_audio_play;\n', '''static bool g_audio_play;
// Multiplier of the existing 300-sector/s data path; CD-DA remains 75 sectors/s.
// Host configuration, fixed at initialization, rather than guest CD hardware state.
static unsigned g_data_cd_speed = 1;
static unsigned data_cd_speed_from_environment() {
    const char* value = std::getenv("SATURN_DATA_CD_SPEED");
    if (!value || !std::strcmp(value, "1")) return 1;
    if (!std::strcmp(value, "2")) return 2;
    if (!std::strcmp(value, "4")) return 4;
    sat_fatal("SATURN_DATA_CD_SPEED must be 1, 2, or 4 (got '%s')", value);
}
'''),
    ('uint64_t rate = g_audio_play ? 75 : 150 * 2;',
     'uint64_t rate = g_audio_play ? 75 : 300ull * g_data_cd_speed;'),
    ('void cd_init() {\n    reset_all();', '''void cd_init() {
    g_data_cd_speed = data_cd_speed_from_environment();
    if (g_data_cd_speed != 1)
        sat_note("CD data delivery: %ux baseline (%u sectors/s); CD-DA unchanged at 75 sectors/s",
                 g_data_cd_speed, 300 * g_data_cd_speed);
    reset_all();'''),
)


def _normalized(data: bytes) -> bytes:
    # Windows checkout line endings are accepted, but mixed/lone CR is refused.
    normalized = data.replace(b'\r\n', b'\n')
    if b'\r' in normalized:
        raise ValueError('Unexpected lone CR in cdblock.cpp; refusing to patch')
    if b'\r\n' in data and b'\n' in data.replace(b'\r\n', b''):
        raise ValueError('Mixed line endings in cdblock.cpp; refusing to patch')
    return normalized


def apply_data_cd_speed(runtime: str | Path) -> dict:
    """Apply once to a build runtime copy, or verify an identical prior result.

    Unknown baseline or modified post-patch files are rejected before writing.
    Original LF/CRLF is retained. The returned hashes are normalized to LF.
    """
    path = Path(runtime) / _SOURCE
    raw = path.read_bytes()
    data = _normalized(raw)
    before = hashlib.sha256(data).hexdigest()
    if before == _PATCHED_SHA256:
        return {'changed': False, 'feature': _FEATURE, 'sha256': before}
    if before != _BASE_SHA256:
        raise ValueError(f'Unexpected cdblock.cpp SHA256 {before}; refusing data-CD transform')
    text = data.decode('utf-8')
    for old, new in _EDITS:
        if text.count(old) != 1:
            raise ValueError('Data-CD source anchor is missing or ambiguous; refusing to patch')
        text = text.replace(old, new, 1)
    after = text.encode('utf-8')
    if hashlib.sha256(after).hexdigest() != _PATCHED_SHA256:
        raise ValueError('Data-CD transform result hash mismatch; refusing to write')
    if b'\r\n' in raw:
        after = after.replace(b'\n', b'\r\n')
    # Do not leave partially written source on a failed write/replace.
    temporary = path.with_name(path.name + '.data-cd.tmp')
    if temporary.exists():
        raise FileExistsError(f'Stale temporary source {temporary}; review it before retrying')
    created = False
    try:
        with temporary.open('xb') as stream:
            created = True
            stream.write(after)
        os.replace(temporary, path)
    finally:
        if created and temporary.exists():
            temporary.unlink()
    if path.read_bytes() != after:
        raise OSError('Data-CD transformed source did not verify after write')
    return {'changed': True, 'feature': _FEATURE, 'sha256': _PATCHED_SHA256}
