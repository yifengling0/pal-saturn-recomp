# Battle timing: measured causes and optional experiments

## Reproducible baseline

The verified five-patch executable and the isolated observation-only battle
probe reproduced the complete first natural encounter four times. All22 sampled
frames matched, both observed battle scopes returned normally atVB25166, and all
four final backups matched SHA256
`d5fb225425b5e33f165df7c0ff3b2915acfb504246d25f8c05602b866b99bcb6`.
Each probe log contained4252 records with no cap, unmatched scope or unwind.
See `FIRST_BATTLE_ACCEPTANCE.md` for disc, starting-save and input identities.

Times below are guest-clock durations, not accelerated headless wall time.
Nested durations must not be added to their enclosing totals. Neither passing
an exit code nor a whole battle's duration establishes a loading-performance
result: the replay includes deliberate pauses and menu exploration.

## Separate costs

| Segment | Measured guest cost | Interpretation |
|---|---:|---|
| Battle setup23220→23273 |53VB,887.3984ms| Six requests totaling261 sectors |
| Six resource calls within setup |876.2368ms| Current300 sectors/s predicts870ms |
| Sprite upload within setup |8.09ms| Not the dominant setup cost |
| Healing FIREN.AV10,240B |17.7152ms| Resource delivery itself is short |
| Entire healing preparation |98VB,1630.5152ms| Dominated by a fixed game delay |
| Fifty preparation sync calls |97VB,1602.4576ms| Original rendering/tick loop |
| Twenty healing-frame decodes |6.144ms total| Twenty frames, no omitted decode |
| Twenty explicit inter-frame waits |1328.128ms| Each effect frame advances4VB |

Two setup repeats had identical guest stages; host costs were96.179 and111.443ms,
which do not establish a cold-cache versus warm-cache improvement. Two independent
healing repeats likewise had identical guest event fields. Dense frame capture
and concurrent later audits are not used as host-performance benchmarks.

Ordinary attacks also contain explicit game delays: caller0604457C requested40
ticks and spent78VB/1303.3472ms in the observed branch; caller06044820 requested20
ticks and spent40VB/667.3408ms after enemy actions. These are separate from the
healing preparation wait. No global timer or animation-speed change was made.

The whole fight did not repeatedly reloadABC.J,FFF.J,MDAIF.JOE orPPAIF.JOE.
It readFIREN.AV once for healing and several smallAIF.NEW sound chunks. Menu
exploration readBALL.NEW before the first attack; its API byte argument0 means
whole-file, not zero transfer. Its extracted size is143,916B.

## Why healing pauses before its effect

For observed effect33, theFIREN header has20 frames and its flag0x20000000 is clear.
f0603108C callsf06022458(1,7), which changes the high byte of theVDP2BMPNA shadow
at060FFCEC and callsf06021FD8(200). That function divides200 by4 and executes50
render/tick iterations. The shadow table is copied from060FFCC0 to25F80000.

Actual narrow watches show:
- Shadow060FFCEC changes03→07 atVB24325.
- PhysicalBMPNA05F8002C changes0305→0705 atVB24326, before the second sync returns.
- The effect later restores shadow03 atVB24504; hardware0305 follows at24506.

Thus the last48 iterations in this sample are not waiting for the bank's first
hardware commit. A fixed two-iteration replacement is nevertheless unsafe to
generalize: a larger resource can leave a more negative countdown and both
iterations could return without advancing aVBlank. Bank4 has not been verified.

These iterations are not empty sleep. They update battle tick, random-state
consumption, enemy idle presentation and input cancellation. TheRNG core is a
linear congruential generator, but merely compensating its invocation count
would not establish equivalence of all these other effects or their ordering.

## Experiments remain separate from the baseline

The first narrow fixed-two-loop experiment reduced this preparation from98 to2VB
while retaining all20 effect frames at4VB intervals. After aligning by96VB,
126 character/healing regions matched pixel-for-pixel. Only88 whole frames
matched:38 differed within the enemy idle area. After the subsequent enemy turn,
HP was149 instead of150;MP remained94. This is an observable gameplay divergence,
not a deterministic-equivalence fix. The original cancellation window also shrank.

The current `tools/prepare_effect_wait_lab.py` builds a new isolated snapshot;
it never overwrites the baseline. `PAL_SHORT_EFFECT_PREP=1` is explicitly opt-in.
The stronger candidate keeps the original200 argument and50-iteration cap,
restricts itself to the observedmaster/battle/bank7 caller, and may leave the
original loop early only after:

1. At least two original iterations have completed.
2. At least two actual guestVBlanks have elapsed.
3. The realVDP2BMPNA byte equals the requested shadow byte.

The hardware check reads the existing raw register array; it does not perform
anMMIO read or consume anMMIO safe-point budget. Original input cancellation
remains in the loop. RAII confines the change to the specific call and restores
scope on return/unwind. Nonmatching calls, bank4 and default-unset mode retain
the original behavior. Pure-policy and isolated scope tests cover the guards,
register-commit gate, default-off, nested calls and exception cleanup.

The stronger candidate still changes the number of battle ticks when it exits
early. Its real-game testing is ongoing. It is a possible **quick spell
presentation** option, not a global hardware fix and not a default change.
Complete victory/return/save and broader spells require separate acceptance.

Local evidence: `build/battle-analysis-001/first-battle-results.md`,
`first-heal-results.md`, `first-victory-results.md`, `palette-commit-audit.json`,
`build/linux-effect-wait-off-readonly-017`, and
`build/linux-effect-short-readonly-018`. Commercial data and large logs are not
included in source control.

## Commit-gated candidate v3: completed early-combat acceptance

Frozen executable SHA256:
`d5411236a040a4d01a989aaebd7c61cd4f8f584b38757a57c73574205e711920`.
Default-off reproduced the entire original25761VB replay: all22 PNGs,4252
observation events excluding host timestamps, and the final backup matched.

With the option enabled, the scope began atVB24325, actualBMPNA was committed
at24326, and the original loop exited on iteration3 at24328 after three elapsed
VBlanks. Total preparation was4VB rather than98; this preserves more safety than
the fixed-two-loop candidate. All20 effect frames remained at four-VBlank spacing.
After aligning by94VB, all126 character/effect image regions matched;58 whole
frames differed only in the enemy idle region. The observed post-heal battle
HUD wasHP150/MP94, but that one matching value does not establishRNG equivalence.

A separate input-only session then completed attacks, victory, experience2,
money0, 吉運+2, field return and normal game-menu save. It exited0. The new backup
SHA256 is `0b4fa6550580b376e45e3a72a46e0422b57dddfc574a93e2c98358ce8eba9595`,
which is intentionally retained rather than replaced with the baseline backup.
A fresh process loaded its copy atscene16/world(656,1544), with the same saved
field image; its status page showedexperience2,HP150/150,MP97/100,吉運34.
Those are post-battle values, not the earlierHP/MP observation during healing.

Finally, an exported legal button replay reproduced all10 chosen observation
frames and that new backup exactly without the interactive controller. This
establishes reproducibility of the tested optional path, not equivalence to the
original random trajectory or acceptance for untested spells. Evidence is under
`build/linux-effect-wait-v3-readonly-019`.

Independent read-only state accounting further confirms the distinction: both
modes began the wait with identical1MiB highRAM andseed721D3EC0. The original
executed50 iterations/100LCG calls and ended attick595; v3 executed3/6 and ended
attick548. Advancing the short run's seed94 times **offline** produces the original
exitseed9790C40C, but34 otherRAM bytes still differ. No compensation or state
write was applied to the game. Conditional actor paths can make other cases use
more than two random calls per loop, so a constant compensation formula would
not be a general solution. The option remains a presentation-speed preference
with a different random trajectory, while original mode stays available.

## SDL-linked optional presentation build

The same v3 scope can be built with:

```sh
build/venv/bin/python tools/prepare_effect_wait_lab.py \
  --out build/linux-effect-wait-sdl-v3 --sdl-prefix build/prefix --jobs 2
```

Observed executable SHA256:
`4072f42a3da960a4c0e35540f60d249094648711a3314e599af01783be287c0b`.
Its headless replay with the option enabled completes the full natural battle,
save and return route, matching10 reference RGB images and the exact v3 saved
backup, exit0. Evidence is under
`build/linux-effect-wait-v3-readonly-019/on_sdl_v3_headless_replay`.
This verifies the SDL-linked binary's game path; an actual window/audio-device
comparison of the quick presentation is still pending. The option remains off
by default, independently of the walking-input experiment.

## Original Sword Technique: independent first-cast measurement

A later legitimate night-temple route learned Sword Technique (skill2, menu
cost10MP). From an independent downhill checkpoint, the original runtime
naturally encountered two enemies and selected the skill through normal menus.
Observed target HP42→-35, displayed damage77, MP111→101; the enemy turn followed
and the normal command menu returned. This measurement branch stops in battle
at that menu; the separate main route completed two casts, victory and save.

Exact successive-VBlank images establish these first visible boundaries:

| Event | VBlank | From supplied confirm |
| --- | ---: | ---: |
| Target confirmation A supplied | 4007 | 0 |
| Target HUD disappears | 4013 | 6 |
| Player starts visible preparation movement | 4033 | 26 |
| Standing casting pose | 4045 | 38 |
| First visible flying sword | 4162 | 155 |
| Enemy HP write42→-35 | 4271 | 264 |
| First visible damage77 | 4272 | 265 |
| Command menu returns, HP143/160 MP101/111 | 4460 | 453 |

155 fields is about2.59 seconds at the normal cadence. The453-field total
includes the enemy's turn and cannot all be called spell loading.

Sword effect10 has **26 frames**, unlike the healing effect's20. Preparation
f0603108C takes4063→4161,98VB/1633.8944ms; FIREN's12288 bytes take only21.1968ms.
The same bank7 shadow write occurs4064 and actual hardware commit4065, while
50 original sync iterations continue until4161. Those waits account for97VB /
1597.2352ms. The26 decoder calls total7.4752ms. All26 dedicated animation waits
are4VB, with an additional2VB tick between frames9 and10; the whole effect span
is106VB/1768.448ms. Nested costs are not added to their enclosing totals.

Original versus observation-probe replays match all487 same-VBlank RGB images;
two extra bank audits each match19 images. Three probe runs have the same2364
guest events, no cap, no unmatched pairs; all processes exit0 and preserve source
and copied BUP hashes. The planned4649 stop unwinds the outer battle and current
present/sync scopes: it is not a complete battle-scope return. Report and exact
commands: `build/sword-timing-analysis-001/REPORT.md`.

The independently tested original preparation wait agrees with the healing
case, but optional-short-mode behavior on these26 sword frames is being tested
separately. This evidence alone does not enable or validate that option.

### Optional v3 Sword Technique acceptance

The subsequent bounded A/B test completed using the frozen optional v3 binary.
Both the environment variable being absent and explicitly0 reproduce all487
original images,2364 normalized guest-probe events and unchanged BUP. No default
setting changed.

With the option enabled, physical bank7 commits at4065; at4067 the third loop
has elapsed3VB and the physical byte matches, so preparation exits normally.
Preparation becomes4VB rather than98. First flying sword4068, damage77 at4178,
and command menu4366 are all94VB (about1.57 seconds) earlier. Input-to-first
flying sword falls from155 to61VB, approximately2.59 to1.02 seconds.

All26 effect frames and their26 dedicated4VB waits close normally; the extra2VB
between frames9 and10 is retained. TargetHP42→-35, MP111→101, and menuHP143/160
match this original sample. That equality is not proof of RNG equivalence.

In108 effect-aligned image pairs the player area matches108/108 and the full
image80/108. Observed differences lie in enemy idle regions; where swords overlap
enemies, no independent sword-layer equality is asserted. The HUD matches in320
compared images through20VB after the menu return, but the menu selection
arrow's flashing phase differs. Whole-scene deterministic equivalence is not
claimed. This remains an opt-in presentation/experience change.

Six runs exit0 without FATAL, cap or an unclosed spell effect. The4649 stop is
intentional while battle remains active, not a whole-battle return. The separate
original main route's victory/save does not certify this optional branch's
whole battle. All source BUP/executable/tracked source identities are preserved.
Full evidence: `build/sword-short-v3-001/REPORT.md` and `summary.json`.

### Optional v3 full Sword Technique victory/save/load loop

The optional branch was then tested independently through a whole battle, not
borrowed from the original route. Two legitimate Sword Technique casts each
retain26 frames and4VB preparation. The second enemy goes42→-35 with77 shown;
MP writes111→101→91 and victory restores it to101. Rewards show experience8,
money8 and a separate Hemostatic Herb drop page. The single battle returns
normally at5243, with no unwind, unmatched pair, LIMIT or FATAL.

The first genuine field save was too close to a roaming enemy: waiting or
reloading soon started another encounter. Those observations and one unsuccessful
short retreat are retained, not labelled safe reloads. The accepted branch uses
ordinary LEFT input after rewards to return to already visited scene8, then
saves through the game menu. It triggers no new story or battle.

The final independent save SHA256 is
`40b5f1f2cbadf2ed7fdcdd7e482d5a345b0ecbd459ac390e9e2a13466bfd63cd`.
A new process loads scene8/world(1424,936), HP151/160, MP101/111, money595.
Map, money menu and complete status images exactly match the saved branch.
Ordinary non-agent replay reproduces the same final BUP and8/8 observed images;
a separate HP audit agrees with all3720 guest probe records, and reload replay
matches3/3 images without rewriting the backup. The BUP is private and not
included in the source/recovery package.

This closes the tested optional sword branch through victory, rewards, return,
real save and new-process load. It does not erase the known random-trajectory,
idle and menu-flash differences or enable the option by default. Detailed full
commands and retained unsuccessful observations:
`build/sword-short-v3-victory-001/REPORT.md` and `summary.json`.

## Yue Ru's first group spell, original-timing measurement

Two independent complete replays through357599 use the unchanged original
executable and all experimental switches zero.706/706 decoded RGB frames match
between them, and16/16 available main-route frames match. No function-level
probe was added for this measurement; narrow/broad original watch windows
provide the following distinct state and visible-frame boundaries:

- Final party confirm356681; menu/HUD gone356688.
- Forward-movement state356710, visible356716; cast pose state356722,
  visible356728.
- First sword-energy image356847,166 fields after final confirm (about2.77
  guest seconds). Last visible energy356902; clear356903.
- The14 effect frames advance0..13 in4-field holds; the visible interval is
  56 fields. This is neither the20-frame healing effect nor26-frame Sword
  Technique effect measured earlier.
- All three enemy HP fields change32→−20/−21/−21 at356906; the first damage
  numbers52/53/53 are visible356907.
- Role2, actually mapped to the current first party slot, spends7MP80→73 at
  356926. Victory restores3 at357250,73→76, matching the original
  currentMP+trunc((maxMP-currentMP)/2) branch with maximum80.
- Money1875→1881 at357007;6XP/6-money reward visible357008; map returns357317.

The later natural fight independently shows79→72 while still in combat, so
its cost observation has no victory restoration mixed in. Do not describe the
first fight's final net loss4 as the spell's cost.

These are virtual-frame and original memory-write measurements, not physical
keyboard-to-display latency or host-performance results under concurrent
logging. The interval from effect-frame count setup to first image is not
labelled CD I/O or decoding time without a function-level observation. Existing
quick-spell tests of healing and Sword Technique do not establish group-spell
acceptance; that separate opt-in A/B remains pending.

Evidence: `build/yueru-spell-timing-001/REPORT.md`, `summary.json`,
`final-parity.json` and `timeline.json`. The full input's source is the older
island-cave-bridge save, not the later Hidden Dragon bridge save. Both runs stop
before the new post-battle save, so their equal BUP files alone are not used as
proof that the post-battle MP was saved.

## Opt-in quick group spell: separate short-save acceptance

A separate normal load from the newer Hidden Dragon bridge save reaches the
same three32HP enemies using a recorded short input. Its random/timing phase
is not the older full-story prefix. Baseline, v3 flag unset and explicit0 each
have399/399 equal same-field images. A full6988-field baseline/default0 replay
also has28/28 equal images and identical final BUP. The default is unchanged.

In this short phase, preparation4704→4803 (99VB) becomes4704→4707 (3VB).
FIREN.AV reads14,336 bytes in24.3712 guest ms in both modes. The original50
synchronizations become2 after actual BMPNA matches the requested bank, with
2 elapsed fields. The first visible energy4806→4710 advances96VB, about1.60
seconds; input-to-energy166→70VB. This is a measured instance, not a promise
that every preparation takes3 fields or improves by exactly96.

All14 decodes and4VB holds remain, including the original2VB before first
decode. Total effect duration56VB and decode total9.1136ms are unchanged.
Of58 event-aligned images,56 full images match and all58 character-region
images match; two early full-image differences lie in the enemy region. This
is not claimed as a separately isolated effect-layer proof.

Damage changes53/52/53→52/53/52. Both spend7MP80→73; victory restores73→76.
The option therefore retains the tested targets, cost and effect sequence,
but does not preserve the original random trajectory. It remains opt-in.

The enabled branch completes6XP/6-money and luck+1 rewards, normal return,
ordinary movement back to the bridge, normal menu save and a fresh-process
load. Ordinary non-agent replay matches28/28 images,1770 guest events and the
saved BUP; an HP audit matches44/44 images, and reload replay7/7. All full runs
return normally without unwind/FATAL/trace limit. The independent save hash is
`5c2dbb61e480edd8a7c27e776c78d32846bfde1ef51c5b4a9bffe0721da5d63b`.

Final saved/loaded map images are byte-identical. Earlier status/item images
retain612 low-amplitude RGB differences in a small character-region rectangle,
maximum channel difference7. Displayed status numbers, six visible item entries
and quantities, and the selected descriptions match. This is not a claim that
the whole menu image or the complete inventory structure was independently
verified as equal. The differences and intermediate failed starts/navigation
attempts remain in the report rather than being hidden.

Fixed reward-confirmation inputs absorb the96VB gain, so both complete runs
return at5039. Do not report an entire battle shortened by96 fields. The short
4992 stop was still in the reward UI and is not used as full-battle acceptance.
No broader spell/bank/cancel/native-SDL/audio or RNG-equivalence claim is made.
Evidence: `build/quick-yueru-group-spell-001/REPORT.md` and `summary.json`.

## 2026-10-11: original confirmation skip independently reproduced

A [2018 Saturn playthrough author's description](https://www.bilibili.com/video/BV1es411j7Uo/)
says confirmation can advance the apparent spell pause. That page is a lead,
not a timing measurement. The current Taiwan image now independently confirms
an original input-exit path with all enhancement options disabled.

Using the same normal three-party save and Thunder-vs-tiger input prefix:

| Original input during preparation | Preparation start/end | Wait | Effect frames |
|---|---|---:|---:|
| No extra confirmation (reference) |5917→6015|98VB|7, original4VB holds|
| Hold A from5900 to5942 |5917→5918|1VB|7, original4VB holds|
| Hold A from5900 to6050 |5917→5918|1VB|7, original4VB holds|
| Tap A5930→5942 after start |5917→5935|18VB|7, original4VB holds|

Static tracing agrees: the original wait at06021FD8 calls06022B8C during battle
and exits when its returned action flag is1. No forced guest-memory write or
new runtime skip was used for these cases. `build/original-confirm-skip-001`
contains the legal input scripts, read-only observation logs and event pairs.
All three extra-input processes exit0. Held confirmation changes the observed
random battle trajectory (the sampled tiger HP differs), so this is not a claim
of state equivalence with idle waiting. Nor does this establish every controller
mapping or every spell's behavior.

The quick-preparation option automates a bounded early exit after the verified
resource/palette condition, without requiring repeated confirmation. It remains
an optional experience change. The presence of the native skip does not justify
sending confirmation through later menus/dialogue or removing all waits.
