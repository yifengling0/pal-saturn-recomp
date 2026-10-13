# Phone/tablet landscape and bounded audio prime integration

Base: published E fix `c203eca935c0a061bfa787311b62534dc6e5117b`, tree
`7c1646473555caba6bf786a61eb1785f9da857eb`. Walking, chest/prompt and battle
helpers remain unchanged. No ROM, save, HAP, signing material or secrets are
included in this change. Existing Release assets are not updated.

## Final behavior and compiler correction

Phone and tablet share landscape startup resources and the SDL-owned main-window
lifecycle policy. PC/2in1 retains the base restricted orientation and skips this
runtime policy. Runtime retries, epoch cancellation, foreground recovery and
exception-isolated disposal are retained.

The first real integrated `assembleHap` rejected `implements
AbilityLifecycleCallback`: the installed SDK declares a class, not an interface.
The final version registers an explicitly typed object forwarding all nine
required callbacks. It does not extend or construct a platform callback class.
The Node adapter regression now checks that object and all required members;
real CompileArkTS subsequently passed. Node tests alone are not ArkTS acceptance.

OHAudio gains bounded phase headroom (4096/44100 initial prime 112.88 ms) and
producer-side live diagnostics every five seconds. Adaptation remains off;
there is no callback logging or new walking change. Source shortage is not a
hardware underrun, and this does not establish that speaker stutter is fixed.
Detailed assumptions and capture recipe: `OHOS_AUDIO_CADENCE_20261013.md`.

## Reproducible identities

The clean pinned upstream was prepared through the actual full patch chain,
including 0022. `audit/harmony-audio/replay_host_hashes.py --host
third_party/saturn-recomp-pal/runtime/src/host/host.cpp` independently replayed
raw, precise, paired, keyboard and prompt stages. Final stages are recorded in
`audit/harmony-audio/integrated-host-stage-hashes.json`:

- Ordinary: `f2ae4720395b317f8fdaf372c148021f565eafbfc02aa5278b46e2df848edabc`
- Accelerated: `6ddaa48666cbada98adde0527ae6f205f13e6967479e684aa29553c3b9c61b23`

Exact final OHOS pins were replaced and prior E-only pins are rejected. No
manifest or generated source was manually edited to bypass validation. Both
formal runtimes were freshly generated and built. The ordinary generation
initially encountered a stale generated helper; its previous generated directory
was preserved separately and a fresh generation was made at the original path.

## Verified results

- Final tools: **404 tests + 201 subtests passed, zero skips**, with optional
  upstream/private original-generated inputs supplied.
- Phone service regressions: **7 passed**, including the SDK callback adapter.
- Audio: **38 policy checks, 43 actual-host cases / 4613 checks**, UBSan, against
  the final accelerated production host; source hashes unchanged during testing.
- Formal ordinary and accelerated Linux builds passed. No diagnostic scheduler
  is in either executable.
- Release `assembleHap` passed: **33 tasks, 21 executed, 12 up-to-date**. Real
  CompileArkTS and CompileResource executed; both ARM64 and x86_64 native builds
  used the existing absolute-path caches, then packaged the new host identity.
- Both packaged `libmain.so` libraries contain final host SHA, `audio live`,
  battle acknowledgement and original walking setting; compile commands have
  release `-O2`. No `PAL_TEST_EVENTS`, `BATTLETEST planned=` or
  `test_battle_events` diagnostic scheduler markers are present.
- Packaged manifest uses `$string:pal_start_orientation`; compiled resources
  contain landscape/restricted values and `restool dump config` returns phone
  and tablet qualifiers. Compiled ArkTS contains lifecycle and orientation logs.
- Artifact hashes and precise boundaries: `evidence/mobile-integration-20261013.json`.

ArkTS warnings remain for existing deprecated/platform-specific APIs. The
orientation runtime skips unsupported 2in1/TV devices. `git diff --check` reports
three literal blank context lines inside unified patch 0022; these are required
patch syntax, and actual patch application passed.

## Not yet verified

The HAP is unsigned and was not installed on a physical device. No phone/tablet
rotation, background/resume, speaker, Bluetooth or Windows hardware acceptance
is claimed. Build success is not gameplay or audible-output acceptance. Collect
several non-startup five-second audio windows with event times and listen on the
actual device before deciding whether the remaining issue is source pacing or
downstream OHAudio/output routing.
