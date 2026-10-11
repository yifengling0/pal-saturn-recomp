# Real SDL fast-preparation comparison

2026-10-11. A fresh combined input-v4/effect-v3 SDL executable was built from
the portable injection path (SHA256
`9848ab495d32be4ca958c383941a61045b3494269bf646436ebc9f49e6c3cf37`).
The precise-input option is off in this comparison, data multiplier1; only
`PAL_SHORT_EFFECT_PREP=1` differs from original timing. No animation-cadence
multiplier is used. Real native OpenGL windows were recorded, without resume,
dummy video, speed editing or reconstruction from still screenshots.

For the same first-battle Qi Liao cast, script A confirmation occurs at24267.
The menu disappears24273 in both modes; visible startup movement24294 and
casting pose24306 also agree. Preparation begins24324. First effect appears
at24425 original versus24331 quick; the20th effect frame is24501/24407, effect
end24505/24411, visible enemy jump24512/24418 and command return24617/24523.
The94VB improvement is in preparation,98→4VB. All20 effect frames retain their
original4VB intervals. Startup pose and enemy turns are not globally accelerated.

In the real30fps videos, measured from visible menu disappearance:

| Event | Original seconds | Quick seconds |
|---|---:|---:|
| Startup movement |0.333|0.367|
| First effect |2.533|0.967|
| Effect end |3.867|2.300|
| Enemy jump |4.000|2.400|
| Command return |5.733|4.167|

These are video wall-clock measurements with roughly33ms frame quantization,
not guest time divided by60. The7-second side-by-side keeps0.5 seconds before
the common visible menu-disappearance anchor and leaves each source at original
playback speed. It does not remove waiting between confirmation and effect.
The confirmation input itself is not visible physical-keyboard evidence; it is
ordinary scripted pad input, with its guest timestamp recorded separately.
Original full replay wall time472.765s exceeds429.772s guest time by about43s
under cloud load; this is not a clean whole-game performance benchmark.

The quick native SDL replay exits0 after25656VB, with41/41 same-frame RGB images,
450 pad-state events/timestamps and final BUP equal to its independent headless
reference. It wins, receives experience2/money0/luck+2, returns to scene16,
world(656,1544), and saves normally. A separate default run matches12/12 prior
native original frames and the original BUP. Compared at matching effect phases,
126/126 character/effect regions are equal;58 full-screen differences in enemy
idle regions are retained, not hidden as equivalent random behavior.

All four delivered videos fully decode. The full quick battle recording lasts
53.033 seconds; the short parallel and two unlabelled single-side excerpts each
last7 seconds. Display labels/cropping are presentation edits only. Audio-device
opening still fails in the cloud (no sound card); these videos have no audio
track and establish no Windows or physical-audio pass.

The source-controlled report contains no game video or save. Private evidence
is in `build/native-fast-spell-001` and the separate native comparison delivery.
The user's subsequently requested1.25/1.5 animation speed is a different task
and is not represented as part of this verified preparation-only comparison.
