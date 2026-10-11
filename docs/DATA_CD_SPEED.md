# Optional faster data-sector delivery

This is a native-port timing option, disabled by default (`1`). It changes the
emulated readiness time of **data** sectors read from the user's local image;
it does not overclock the guest CPU, VBlank, SCSP or CD-DA audio delivery.
`1`, `2` and `4` multiply the previous **300 data sectors/second** baseline.
They are not names for physical CD 1x/2x/4x drive speeds. CD-DA remains75 sectors/s.

## Implementation and isolation

`patches/0006-optional-data-cd-delivery-speed.patch` is the auditable source diff.
The stable shared runtime still uses exactly0001–0005 and its existing identity
marker. `winbuild.py --pal-options` copies that runtime into its own build tree,
then `pal_data_cd_speed.py` applies the hash-checked0006 transform to the copy.
Do not apply0006 manually to the shared five-patch checkout or change its marker.
The installer accepts known LF/CRLF versions, preserves the newline style,
verifies the resulting hash, is idempotent and rejects unknown/edited input.

The only scheduling change is the data branch's sector deadline rate. Audio
branch rate, sector order, transfer data, guest clock and existing command
logic remain intact. The value is parsed at machine initialization; invalid
values fail explicitly. Re-start the process to change the multiplier.

## Actual first-battle measurements

The same original-timing input route and starting BUP were used, with precise
input and short-effect options off. Guest time, not wall-clock render speed:

| Data multiplier | Six-resource stage | Entry to first displayed battle |
|---|---:|---:|
|1, original300 sectors/s|876.2368ms|887.3984ms /53VB|
|2|441.3440ms|452.5056ms /27VB|
|4|223.744ms|331.0592ms /20VB|

The remaining4x transition includes about97.6ms of original display
synchronization. Faster sector delivery is not a promise that every stage,
every spell or the whole battle runs four times faster. Spell preparation's
separate scripted delay is handled by `--quick-spell`, not this option.

In bounded file-page cold/hot checks, the actual host data read took only about
2.61–3.15ms cold versus0.27–0.55ms hot for the measured span. Readiness still waits
for guest CD-sector deadlines. This supports changing guest data delivery
rather than assuming a fast local filesystem already removes the delay.

## Regression and gameplay limits

- Default unset and explicit1 each match22/22 original RGB frames,4252 ordered
  guest probe records after removing host timestamps, and the final BUP.
- Real CD-block synthetic tests cover data deadlines, order, full-buffer/recovery,
  flags, transfer counts/content, deletion, filtering, read failure/retry,
  repeat, pause, file boundaries, same-speed state round-trip and CD-DA.
  Three multipliers produce identical CD-DA PCM sample sequences in that fixture.
-4x completes first-battle victory, reward, return to the field, normal save and
  independent-process load. The saved/loaded map is pixel-identical.
-2x's unchanged fixed input initially stops at the reward page at25761VB. That
  incomplete run is retained; ordinary confirmations and menu-save inputs extend
  it to26400VB, with normal battle return at25804. Independent load restores the
  same saved map and leaves the BUP unchanged.
- The random trajectory can change: the measured4x reward grants luck+1 while
  original timing grants+2. This is not a deterministic-equivalence fix. No
  artificial RNG compensation was added.
- Normal game BUP load is tested. Loading an in-flight machine `.state` made at
  another data multiplier is not accepted as compatible. Use the same multiplier
  for runtime-state files, or use normal in-game BUP saves instead.
- Windows native sound-device playback and all game/CD streaming paths remain
  unverified. Synthetic unchanged CD-DA is not a real sound-device quality pass.

## Windows usage after building the options executable

```powershell
& $py tools\run_pal_profile.py original --data-cd-speed 1 --exe $exe -- --cue $cue --save - --settings - --out build\win-cd-1
& $py tools\run_pal_profile.py original --data-cd-speed 2 --exe $exe -- --cue $cue --save - --settings - --out build\win-cd-2
& $py tools\run_pal_profile.py original --data-cd-speed 4 --exe $exe -- --cue $cue --save - --settings - --out build\win-cd-4
```

Use a fresh copy of the same normal save for meaningful manual A/B testing.
The launcher requires a matching executable hash and `data_cd_speed` capability
in `pal-options-build.json` before accepting2/4. Older two-option executables
are deliberately rejected for those speeds. All options can be tested together
later, but first test the data multiplier by itself.

No-ROM regression, on either Windows or Linux with a C++20 compiler:

```text
python tools/run_data_cd_speed_tests.py --runtime third_party/saturn-recomp-pal/runtime --out build/data-cd-synthetic-new
```

The output directory must be new. Source runtime and existing results remain
unchanged; `summary.json` records compile/test exit statuses and actual commands.

## Integrated-build confirmation

The shared Windows-driver path was rebuilt with all three capabilities in a
fresh Linux test directory. This is a real full generate/inject/static-link run,
not a mock and not a native Windows result. Its data1/4/2 replays respectively
match22/22,22/22 and26/26 independent prototype RGB frames and each mode's own
final BUP. The4x profile launch also verifies the executable capability hash and
prints the actual1200-sector/s runtime setting.61 tooling tests plus6 subtests
pass; the no-ROM CD driver passes both ordinary and space-containing paths.
No runtime-state cross-speed compatibility claim is made.
