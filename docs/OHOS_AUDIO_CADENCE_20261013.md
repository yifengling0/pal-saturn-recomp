# OHOS speaker / Bluetooth stutter: bounded phase fix and live evidence

Status: deterministic source-path fix and local regression passed; **no device listening pass**.
No phone/tablet was connected. This does not attribute tablet-speaker stutter to Bluetooth.
The proposed remote `docs/OHOS_PHONE_EVIDENCE_20261013.md` returned 404 at review time;
its unpublished contents were not used as source evidence.

## What is confirmed

Pinned SDL revision `930cd0dbf8d1b6fdc5b91711d8d71542c1df0960` was inspected locally:

- [`SDL_ohaudio.c`](https://github.com/libsdl-org/SDL/blob/930cd0dbf8d1b6fdc5b91711d8d71542c1df0960/src/audio/ohaudio/SDL_ohaudio.c)
  already requests `AUDIOSTREAM_LATENCY_MODE_FAST`, queries actual callback frame size,
  and has a three-quantum device ring. Requesting 1024 from SDL does not guarantee 1024.
  Its renderer callback independently pads unavailable device-ring bytes with silence.
- [`SDL_audio.c`](https://github.com/libsdl-org/SDL/blob/930cd0dbf8d1b6fdc5b91711d8d71542c1df0960/src/audio/SDL_audio.c)
  independently zero-fills an incomplete stream read before handing it to the backend.
- [`SDL_audiocvt.c`](https://github.com/libsdl-org/SDL/blob/930cd0dbf8d1b6fdc5b91711d8d71542c1df0960/src/audio/SDL_audiocvt.c)
  calls the observer with estimated source bytes required after conversion/resampler history.
  A shortage here is not a measured hardware underrun. Source queue queries do not include
  PCM already pulled into the device ring, renderer, mixer or route buffers.
- `sound_tick` submits whatever PCM is due from `master_poll_devices`; actual chunks are not
  necessarily 735 frames. The 735/60 Hz cadence below is an equal-production aggregate model.
- `host_pace` rebases its time origin if more than 100 ms behind. This can preserve a wall-time
  audio production deficit; the patch counts such rebases but does not change game pacing.

### Reproducible phase defect

4096/44100 is 92.8798 ms. The old initial source lead is 4410 frames (100 ms).
Immediately after a 4096 pull it leaves just 314 frames (7.12 ms), less than one
735-frame (16.67 ms) producer tick. A constant average rate alone does not prevent short reads.

The deterministic 60-second model sweeps 105 source/pull phases. Old lead yields 0–18
short reads and at most 420 missing source frames total, with no dropped real PCM.
These are bounded phase gaps, **not evidence that a large ongoing stutter is explained**.
A producer 0.136% slow, or repeated 101 ms clock rebases, causes continued shortages.
The model also distinguishes a one-time 1/2/3-pull startup burst: a three-pull burst can
exceed even the new prime. Neither this patch nor the tests claim to remove that case.

## Patch 0022

Only the already identified OHAudio path changes its one-time initial source prime:

- Preserve the old lead for small quanta.
- Otherwise request one converted quantum plus 882 source frames (20 ms).
- Limit the requested initial lead to 5512 frames and to the existing 11025-frame cap
  minus one pull quantum minus 882 frames. No source-cap increase.
- If an unusually large/invalid device quantum cannot fit that budget, retain the old
  bounded prime rather than claiming the desired coverage. Such a case remains observable.
- 4096 at 44100 Hz: 4978 frames / 112.88 ms, only 568 frames / 12.88 ms more than before.
- 4096 at 48000 Hz: ceil(4096×44100/48000)+882 = 4646 frames / 105.35 ms.

The 20 ms allowance covers a 16.67 ms aggregate producer tick plus at most 3.33 ms extra
lateness. It does **not** cover arbitrary 20–40 ms scheduling jitter on top of that tick,
persistent slow production, renderer-ring starvation, Bluetooth backpressure, or route changes.
It is not an adaptive attempt to chase those conditions. Adaptive growth remains off by default.
There is no menu re-prime, dropped-PCM workaround, game-speed adjustment or sample-rate change.

### Live evidence without Quit

On the producer thread, emit two `sat_note` lines per five seconds while PCM is being pushed:

- `audio live`: interval wall seconds, accepted/dropped/failed PCM, push count, min/max real
  chunk sizes, pre-push **source input bytes** min/max, max non-recognized-lifecycle push gap,
  empty observations, lifecycle resets and pacing rebases.
- `audio live requests`: interval callback/short-callback counts and source-byte estimates;
  current device rate/quantum; cumulative maximum request and initial/recovery zeros.

No new allocation, clock query, I/O or locks were added to the stream callback. Counters are
relaxed atomic snapshots; a window boundary is approximate, not a synchronized callback trace.
Logging itself is synchronous on the producer, not free: its actual device overhead remains
unmeasured and subsequent push-gap telemetry can reveal it. There is no log while entirely
paused/stalled; the first push after recovery reports the elapsed window. Window wall time
includes pauses, and `lifecycle_resets` explicitly marks contaminated windows. Do not infer
steady PCM/sec from such a window. The first window includes prime/startup effects.

## Validation and limits

Commands from the repository root:

```sh
python audit/harmony-audio/test_audio_cadence.py
python audit/harmony-audio/run_audio_tests.py --runtime <patched-runtime> \
  --sdl-prefix <native-SDL-prefix> --build-dir build/audio-tests
python -m unittest discover -s tools/tests -p 'test_*.py'
```

- 38 pure C++ policy checks, UBSan, pass.
- Full tool-suite invocation: 358 tests, OK with four skips for unavailable optional/private
  test inputs. This is not a zero-skip release acceptance result.
- 43 actual-host cases / 4613 checks, UBSan, pass.
- Six actual SDL stream schedules, 60 virtual seconds each: 44100/48000 output rate × three
  phases, exact integer-ratio 4096 pulls; 735 source frames split into 147/221/367 chunks;
  selected producer ticks delayed 100 source frames (2.27 ms). Zero short reads, real-PCM
  drops, failures or repeat source padding. PCM production and source counts are conserved.
- The split chunks are adjacent at the same simulated tick; this tests variable chunk sizes,
  **not** the actual device producer-thread timing distribution.
- C++ menu pause/resume calls are same-time boundaries, confirming no repeated prime/reset
  side effects. Actual pause duration and changed pull phase are covered only by the Python model.
- Python sweeps additional 20/40 ms jitter, finite menu durations/resume phase, startup bursts,
  rate deficit and rebase cases; `cadence-results.json` preserves all outcomes, including limits.
  At both output rates, 210 phase cases with small jitter have zero candidate short reads/drops.
- Stream/device methods for opening, pausing and resuming remain mocked. Real SDL conversion
  and manual stream reads are exercised, **not** the OHAudio thread, hardware or audible output.
- Exact patch application to the existing 0019 source checked. No HAP or fresh native build
  was done in this worktree; final E/orientation/audio integration must build both OHOS ABIs.

## Integration contract

`prepare_linux_runtime.py` adds patch number 22 after 19 (20/21 are not invented dependencies).
`cadence-source-hashes.json` pins the two raw changed files; `cadence-host-stage-hashes.json`
records this worktree's host transform replay. `replay_host_hashes.py --host <raw host.cpp>`
replays the current checkout's precise, paired, keyboard, guard and prompt transforms in memory.
Run it again **after merging the E planner**. It never edits allowlists or build output.
Raw/precise/paired acceptance pins are included. New host/helper pairing is fail-closed, so
an old 100 ms helper cannot accompany a new diagnostic host. The final OHOS host pins remain
owned by integration and must be replaced with the exact new mapping/accelerated outputs.
Do not manually edit generated sources or label an older HAP as containing this patch.

## Device capture recipe

Use the newly integrated, regenerated, built and signed HAP; preserve the startup SDL driver,
revision, obtained device Hz/quantum and initial-zero counts. With the existing authorized hdc
connection, `python tools/ohosbuild.py --logs --device <verified-device-id>` reads an existing
hilog snapshot without build/install/restart/log clearing. It can be run while playing because
`audio live` no longer waits for Quit. Retain the original full capture, not only filtered lines.
If the current setup redirects native stderr to a file, capture that file as already configured;
no new on-device path is assumed here.

Capture 3–6 minutes steady speaker playback, then five in-game and five host-menu cycles,
background/foreground and route switch, with approximate times of heard gaps. Capture Bluetooth
separately. Look at non-startup windows with no lifecycle resets:

1. `short_calls/additional_bytes_est` rising alongside audible gaps suggests source insufficiency;
   inspect accepted frames/window, real push gaps/chunks and pacing rebases.
2. Zero source shortage but audible gaps leaves downstream OHAudio/device/route issues open.
3. Drops or put/query failures are separate faults, not successful recovery.
4. Do not use source `empty` alone, render consumption average alone, or A2DP-full logs alone
   to select a universal root cause or declare the speaker path fixed.
