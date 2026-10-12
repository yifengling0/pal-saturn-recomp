# Windows packaging safety gate

This is a bounded packaging correction to `tools/make_dist.py`. It does not
change S/W/Q, keyboard mapping, guest code, build injection, or gameplay.

## Use a new output directory

```sh
python tools/make_dist.py --output dist/pal-saturn-recomp-win-x64-new
```

The default remains `dist/pal-saturn-recomp-win-x64`. An existing directory,
empty directory, file, symlink, or redirected parent is refused. The tool never
moves saves, deletes the prior output, resets settings, or scans/deletes the
player's installation to make room. Pick a different `--output`; review any
manual migration of disc, saves, and settings yourself.

Only a newly created, uniquely named sibling staging directory belongs to this
invocation. The package is copied there, checked, then published with no-replace
semantics: Windows `rename`, or Linux `renameat2(RENAME_NOREPLACE)`. A destination
created concurrently is preserved, including an empty directory. Platforms or
filesystems without that operation fail closed. Failed attempts clean up only
the staging directory. If the requested parent did not exist, newly created
empty parent directories may remain. Existing files and their bytes are never
removed or rewritten by failure cleanup.

## Required proof, not reconstructed proof

The input is still the `build/windows-pal-options/recomp-build` tree produced
by the current `tools/winbuild.py build --pal-options` flow. Packaging requires:

- A JSON object `pal-options-build.json`, no duplicate keys, integer schema 1,
  the current option version, and the exact required capability inventory.
- Nonempty, correctly formed 64-hex `exe_sha256` and
  `instrumentation_manifest_sha256`, matching the actual executable and actual
  sibling `recomp/pal-options-manifest.json`.
- Complete input/output hash inventories, expected defaults, required injected
  files, the current source-helper hashes, and an unmodified generated/runtime
  tree checked by `prepare_options(..., verify_only=True)`.
- The corresponding input, effect, cadence, queue, PC98, and field-input hooks
  in the actual generated sources, and field/keyboard runtime integration.
  The data-CD capability also requires the reviewed transformed runtime hash.
- Explicit `SATURN_VDP1_GPL:BOOL=OFF` in the build configuration and successful
  `objdump -p` output identifying the SDL3 DLL import.

Missing, null, empty, malformed, stale, partial, and mismatching proof is
refused. The packager never writes a manifest to make an old build pass, invokes
an injector, or repairs build inputs. The matching build sidecar is included in
the package. It remains a consistency record, not a cryptographic publisher
signature or an independent proof of what a malicious compiler linked. Do not
reuse a synthetic test fixture as release provenance.

## What may be included

The staged file inventory is fixed: executable, SDL DLL, build sidecar,
launcher, README, NOTICE, settings, disc instructions, and either save
instructions or one explicitly selected internal BUP. Unexpected files,
symlinks, special files, and forbidden disc/archive suffixes are refused. Copy
hashes, the complete checksum list, and unchanged build/input identity are
checked before publication. The checksum list excludes itself.

`--with-save /path/to/private.bup` is only for a private package. The input must
be a regular, non-symlink `.bup` with a complete internal-backup record layout
and at most 32 KiB, following the runtime's `bios.cpp` storage format. A BIN/CUE
or raw disc renamed `.bup`, an empty file, a truncated record, and oversized input are refused.
The source is copied, never modified. This option does not accept cartridge
images or arbitrary renamed files. BUP has no authenticated format signature;
structural validation is not a copyright/content certification of arbitrary
user-created bytes.

## Rights notice

The packaged NOTICE separates the MIT-covered saturn-recomp runtime and
zlib-covered SDL from original game logic produced by static recompilation.
No bundled disc/resource files does not mean no game-derived code. The NOTICE
makes no claim of Softstar authorization, of an entirely MIT/zlib executable,
or of a package containing only nongame code. GPL=OFF does not settle the
rights of other components. This gate is not a license-compliance clearance for
public distribution; verify applicable component notices and original-game
rights before distributing.

## Regression checks and verified scope

```sh
python -m unittest discover -s tools/tests -p test_make_dist.py -v
```

The suite creates all output, disc, save, and failure fixtures in temporary
directories. Its EXE/DLL and guest statements are synthetic and never executed.
It uses real helper files and the reviewed open-runtime CD transform. The
unrelated runtime-support pin catalog is replaced by an empty synthetic variant
inside the tests; the production verifier and packaging checks are not replaced.

Every deliberate failure snapshots and compares the source and preexisting
output bytes and directory/symlink inventory. Cases cover invalid proof,
self-consistent unsupported feature claims, omitted/changed instrumentation,
old private disc/settings/saves, path redirection, BUP validation, copy/scan/
checksum/late-provenance/publish failures, and fresh output. A Linux syscall test
also creates an empty destination after the preflight and verifies no overwrite.

Validation on 2026-10-12: 47 focused tests passed. Separately, the current real
source generation passed the unmocked read-only option verifier and all six
guest-hook groups; SHA-256 of all 161 generated/runtime files remained
unchanged. This check preceded the separate temporary MENU_PROBE diagnostics.
After those diagnostics changed the runtime host, the same verifier correctly
refused it: recorded host SHA `a98bae42bf2bc102d760338745ce5f128ce01f9c0eb7bfcc8784ff1730663cac`,
observed SHA `df89af0a56ced3f5e3e27cbe4cf93625bdb0b4d0abf317ce85342231ae1d8293`.
No manifest was rewritten to bless the diagnostic source. No real user output,
disc, or save was used for a failure test.
The available build is Linux ELF, so actual Windows PE/DLL packaging and
Windows filesystem behavior have not been executed in this environment.

The earlier whole-tools unittest run completed 289 tests (288 passed, one
optional upstream integration skipped). A subsequent full pytest run, with that
optional integration enabled, reported 304 passed, two failed, and 158 passed
subtests. The two failures were in the concurrently changing keyboard helper /
planner contract (`tick(epoch, vblank)` versus older tests and a changed cursor
hook), outside this packaging change. This is not a claim that the evolving
whole checkout passes all tests. The packaging suite itself remains green.
