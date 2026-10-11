# Jade Buddha Temple: original-tempo chapter validation

2026-10-11 05:26 UTC. Taiwan T-37401H/V1.000/JT disc, stable release source
7c5d1d27a197adf9db3b725c5ad502f5c39d6028 (local byte-identical bcecd6d).
Linux SDL executable SHA256 c2d69106890756f2616ba18108aaf6308bc95a9ab9269f5b120183d86c73fddc.
This continuation ran input-only, headless, with all experience switches off,
animation1 and data-CD1. Fast host execution of scripted VBlanks is not a
wall-clock movement or sound benchmark. No guest state or save was edited.

## Actual completion

- Loaded the existing temple-exterior checkpoint normally. Completed Zhi Zhang's
  courtyard dialogue and the automatic introduction in the main hall, scene59.
- Won the three-monk group28 battle. Enemy IDs451/482/453 occupied three real
  slots; observed signed HP values crossed below zero and defeated actors left
  the scene. Li and Ling learned/advanced skills during the normal reward flow.
  Ling's displayed cultivation6→7 restored HP/MP to the new maxima.
- Continued the original story directly into the abbot group35 battle, without
  a field save or manually resetting combat state between them. The sole
  initial enemy object524 had1050 HP in slot1. It actually summoned two sword
  monks (object442,330 HP each) into slots0/2. All were defeated.
- The second reward flow displayed479 coins and **obtained Luo Han Robe**.
  A screenshot preserves this exact reward, not merely a static script prediction.
- Continued the small monk's dialogue, obtained Jade Buddha Beads, and naturally
  returned to the vanished-temple clearing, scene58/world(1184,560).
- Normal inventory/equipment menus confirmed the beads and robe. Equipped the
  beads on Ling: displayed spirit161/defense66 and equipment accessory object274.
  Equipped the robe on Li: displayed spirit68/defense82, body object214. The old
  bracelet and rattan armor returned to inventory. No item table was patched.

Additional exercised paths include selecting a friendly healing target,
healing up to the cap, insufficient-MP spells shown disabled, cancelling a
previous party member's queued command, enemy summons and retaining summoned
enemies after the summoner dies. Single remaining enemy automatically removes
an enemy-target confirmation step; a fixed two-confirm autoplay assumption was
corrected. This was a test-controller navigation mistake, not a runtime fix.

Newly learned Tian Gang Zhan Qi was selected and consumed13 MP, and Xuan Feng
Zhou consumed11 MP. This establishes those cast paths, not a complete timing,
status-duration, elemental-resistance or accelerated-effect acceptance matrix.
Only existing whitelisted effects retain prior accelerated-mode acceptance.

## Saves and fresh-process recovery

1. Normal post-victory save completed at VB53501:
   `jade-buddha-two-battles-victory.bup`
   SHA256 `7a05c3540e3f3f5cca348d297b9e7afbe6284cbf682635291724a151b71110e7`.
2. Normal save after equipment changes completed at VB54863:
   `jade-buddha-equipped-pearl.bup`
   SHA256 `24ae135aa7562a7e177bc66c9312eee7c03df665d57b60b9c76ea04465a383a4`.

Both were copied into separate fresh processes and loaded using the ordinary
boot/load input. Both exited0, left source and copied BUP unchanged and recovered
scene58/world(1184,560). The equipped save also recovered the exact equipment:

- Li, six BE16 words at0606640E: `00C4 00E1 00D6 00A8 00EB 00F9`
- Ling, six BE16 words at060664A4: `00C5 0000 00D2 00AA 00EE 0112`

The final save-time and fresh-load pictures have different PNG container hashes
but **identical decoded320×224 RGB bytes**. Mainline and both fresh-load logs
contain no FATAL. This does not verify Windows sound, Windows selftest, every
later game scene, or arbitrary save-slot behavior.

The legal full replay has1018 successful agent pad events plus the boot prefix,
SHA256 `40b77db332e4bd549fcfc63d9dce8a7d2397dc787a273976ee2b455108479ed5`.
Its source is the earlier temple-greeting checkpoint
`ec6bad5f127f42987726f578f982a69b492425f994acc971c158bda927f9cdbe`, not either
new endpoint save. Replay through VB54863 to include save completion. These
saves and inputs remain private test artifacts; no disc or extracted game data
is committed. Local evidence: `build/autoplay-live-007/`.

Next: Black Water Town and the general's tomb. A static script requires the
beads actually equipped for the tomb gate; passing that gate is not yet tested
by this chapter record. The distant Fire Kirin return-route report, late-game
interaction-direction report, physical Windows audio and Windows selftest
remain open. No change was made to v0.1.0-preview.1 or frozen input prototypes.
