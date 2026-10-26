# Battle casting voice audit (2026-10-26)

Status: **reported female voice for Li Xiaoyao not reproduced**. This is an
investigation record, not a claim that the reported audio bug was fixed.
No gender-based replacement, pitch adjustment or voice-routing patch was made.

## Reproduction and observations

Cold boot from private original-disc saves, fixed RTC `1998-11-01T12:00:00`,
scripted pad input, Linux headless runtime, full PAL-options preparation.
No resume shortcut or guest-memory writes were used. Responsive input was off
for the historical replay timing. Input and saves are not distributed.

| Replay | Preparation / animation | Cast VBlank | Role / sound ID | PCM bytes | PCM FNV-1a | SCSP format |
|---|---|---:|---|---:|---|---|
| Li Xiaoyao, first Sword spell | original / 1x | 4039 | 0 / 9 | 5424 | E247AE93 | 8-bit |
| Same first Sword spell | quick / 1.5x | 4039 | 0 / 9 | 5424 | E247AE93 | 8-bit |
| Zhao Ling'er, Thunder, three-person party | original / 1x | 5893 | 1 / 10 | 4958 | 903CA2E2 | 8-bit |
| Lin Yueru, Qi Jian Zhi, first party slot | quick / 1x | 4681 | 2 / 11 | 5496 | 5AC8BA9D | 16-bit |

All four runs use the original SCSP pitch: OCT -1, FNS 0x300
(effective sample rate 38587.5 Hz). The accelerated Sword animation advances
the subsequent effect from VBlank 4201 to 4094, but does not alter the casting
voice sample, submission time, format or pitch.

The observer read raw RAM and host state only. Adding it to the original-speed
baseline left the complete WAV byte-identical (SHA256
`265a445ed80812d00b7c2c934cba1ec92e050af928180dc45736721497865d58`).
The observer was confined to private generated diagnostic builds; release
builds are regenerated without it.

## Resource chain

Casting entry `060464B8` calls `0603BBDC`, then `06032658` (return address
`0603BD8E`), then the sample submission entry `0605E184`. Current party slot
and role ID determine the original role-data record and sample block.
Character samples come from `PPAIF.JOE`, not the generic skill-effect AIF cache.
All 41 original party-combination blocks, valid character slots and four
sample offsets were checked: each sample stays within its 0x9800-byte slot,
and each role/action has the same hash across combinations.

Casting PCM SHA256 identities, verified against runtime FNV/length/pointer:

- Li: `64b2b7e6c1e5c42a0dc6b0b66736ff4050020164154b253ef8498366c7c8968a`
- Ling'er: `d4e267728a89a95093e4820676ba71011082cad15c7750710ad68d6d2c9b1385`
- Yueru: `ca23c71477147fedff2618ac5a626328feaf98b3c0862a9fd6174d4bbac8a29a`

These raw samples have no rate header. Arbitrarily decoding them at 11025 or
22050 Hz and judging apparent gender would not reproduce the game's playback.

## Limits and next reproduction needed

This verifies a data-flow subset, not audible device acceptance. No physical
Windows/OHOS audio output was tested; no subjective voice-gender claim is made.
Li Xiaoyao casting in a multi-character party and every other spell/scene have
not been exhaustively tested. A specific skill, video and/or pre-battle save
is needed to investigate the reported case further. The current evidence does
not rule out another scene, action overlap, or a device-specific issue.

No commercial disc, extracted PCM, generated game code or save is included.
