# Cold-start opening movie sound-progress cache

## Reproduced failure

The unmodified, five-patch Linux executable reproduces the user's Windows
no-input failure exactly. With a fresh/no save, default settings and fixed RTC,
the opening A1 movie freezes on SHA256
`d50544856df38fb6c8001542f1a51da474cec48fad39033615833a9c2bd8a439`.
The first final static image occurs at VB1453 in the fine-grained trace;
VB1475 was the user's coarse sample, not a proven last decoded frame.
The same image remains through VB6500. START can still leave the movie.
Earlier tests that pressed START at VB1500 did not establish a complete
unattended opening; the later cave/map pictures were another video, A3.

The actual cold opening file is A1.AVI (LBA92291, FAD92441), 2,658,574 bytes,
DUCK video, 265 declared frames at 66,738 microseconds per frame. Its video
chunks comprise 219 `00dc` and 46 `00db` chunks. Counts of distinct screenshots
must not be substituted for the container's frame/chunk count.

## Causal evidence

The guest video clock continues advancing and the movie loop has not returned.
The sound streaming producer reaches `0xB000`, while its cached consumer reads 0.
Demultiplexing then retains audio chunk62 and has no further video chunk.
The CD eventually becomes idle because the stream cannot free that ring space.
Host SDL audio underruns/chunk-drop counters do not observe this guest ring.

The ROM's initialization order, preserved by the recompiler, is:

1. TRUE instruction `06021C00` reads the sound-driver table offset at `25A00404`.
2. `06021C06/06021C0E` cache table/progress pointers at `06040C44/06040C48`.
3. Only then does `06021C1A` call `06035364` to install the sound driver.

In this cold HLE boot, the first header read is 0. The cached pointers become
`25A00000/25A000A0`. Driver installation subsequently writes offset `0x700`;
the actual progress byte at `25A007A0` changes normally. The stale cached read
instead addresses the M68K exception-vector table, whose high byte stays 0.
The M68K/SCSP engine is therefore running; replacing its clock is not justified.

A diagnostic run refreshed only these two pointers from the installed header.
Without input, A1 returned normally at VB2344, then A2 played and returned at
VB6268, followed by title-program loading. These diagnostic timings are not a
claim of completed final-build regression. No video decoder, timer or CD rate
was changed.

## Bounded compatibility correction

A TRUE-only generated hook at `06021C1E`, immediately after the original driver
installation returns, refreshes the cache only when:

- CPU0 and the expected return address match
- The old cache is exactly the proven cold-zero-derived pointer pair
- The installed header offset is nonzero, aligned and leaves the progress word
  entirely within the 512KiB sound RAM

The table offset is read dynamically; `0x700` is not hard-coded into the fix.
Already-correct warm caches, unrelated pointer pairs and invalid headers are
left unchanged. Only the two cache words are written; CPU registers, sound
samples, timer and CD speed are not changed. Actual corrections are logged.
The fix is part of the ordinary PAL game layer, independent of optional input
or animation modes.

Original Saturn BIOS sound-RAM retention before this initialization has not
been established. This corrects the demonstrated cold HLE compatibility path;
it is not evidence that the commercial game necessarily fails on real hardware.

## Verification status

The asset-free planner tests cover cold and already-correct caches, unrelated
pairs, zero/unaligned/out-of-bounds/overflow offsets and the exact upper bound.
All 71 tool tests plus 6 subtests pass on Linux. The real registered callback is
also tested: wrong CPU/return/address, exact big-endian stores, all registers and
unrelated WRAM unchanged, exactly two cold writes and no repeated/warm writes.
An independent callback harness passed ASan/UBSan; leak detection was disabled
because of the execution environment, so no LSan result is claimed.

A fresh complete generation/build (not the diagnostic object-relink) produced
Linux headless SHA256
`1dd10a2ed02022ef8141aee80c10113d06005621e7f82a8e53002258c862549a`.
It passed:

- Cold no-input 7000 VB: all 10 sampled pictures exactly match the corrected
  diagnostic run, one correction log, normal final title.
- Original first battle through victory/return/save: 12/12 baseline pictures
  and final BUP identical.
- Precise-input walking: 94/94 baseline pictures and final BUP identical.
- Quick-preparation group spell: 44/44 baseline pictures and final BUP identical.

The separately instrumented exact-hook run verified all A1/A2 video chunk
sizes/order against the disc: 265 + 930 chunks, no negative processing returns.
The preparation stage returned 0 for all 1195 chunks; the subsequent frame
processing stage returned 0 for 1130 chunks and 1 for 65. The original caller
accepts both 0 and 1 as non-errors. A1 includes 19
zero-length repeated-picture chunks, so 1195 processed chunks do not mean 1195
unique pictures. The broken baseline consumed only A1's first 43 video chunks;
its final decode was VB1451, first final static presentation VB1453. A 19000 VB
unattended title soak remained at the normal title. The observed warm TRUE
reentry is A1→A2, where the now-valid cache is not changed again; the entire
run triggers the correction only once. START 1600 still reaches the same title by VB1900.

Native Windows execution and physical sound-device output still need the
user's local verification. Rebuild the generated game after updating; replacing
only a launcher script cannot add the new hook to an old executable.

## Windows unattended check

Use the rebuilt executable, the user's existing cue and a new output directory:

```powershell
& $exe --cue $cue --headless --save - --settings - --clock 1998-11-01T12:00:00 --vblanks 7000 --shot 1500,1800,2340,4000,6700,7000 --out build\intro-fixed-check
```

Do not supply an input script for this check. The log should contain one
`PAL movie sound cache refreshed after driver install` line, and the final
pictures should show the title rather than the frozen meteor picture. The
expected title PNG SHA256 for this build/configuration is
`9abeb31b0a367f03931d34556464bcd0bbcda3acfbc28868ddfee1bf67c60a18`.
Then run the ordinary SDL window to assess actual sound-device behavior.
