# lowa-build

LibreOffice for WebAssembly (LOWA), Qt5 GUI build with threads, for the Office Editor Dolibarr module
(engine of `htdocs/custom/odteditor/lowa/`). UI languages: English, French, German, Spanish, Italian.

## Versions

All pins are in `versions.env`: LibreOffice 26.8.1.1 (commit bf6ef266…, TDF signed release tarballs), emsdk 4.0.10
(62a853c…), Qt 5.15.2+wasm from allotropia (qt5 3d440b7…, qtbase a320678…), base image ubuntu:24.04@sha256:534baea….
Our changes to LibreOffice: `patches/core/`.

## Requirements (measured on an i7-8750H, 6 cores / 12 threads, 15 GB RAM)

| | Measured |
|---|---|
| Disk | image 4.0 GB, LibreOffice sources and build tree 13 GB (workdir 4.4 GB, instdir 0.9 GB), source tarballs 0.6 GB, bundled libraries' tarballs 0.7 GB, Qt sources 1.5 GB and install 0.1 GB, ccache 0.5 GB, output 0.3 GB: about 21 GB in all |
| Memory | Qt peak 2.3 GB; LibreOffice peak 9.7 GB RAM + 4.2 GB swap for the full build, 10.6 GB RAM + 3.2 GB swap for the final link alone (container cap 11 GB) |
| Swap | 32 GB total (8 GB existing + 24 GB swapfile) |
| Time | image 4 min, fetch about 10 min (600 MB download), Qt 8.5 min (5 jobs), LibreOffice 2 h 52 min (5 jobs, 6 CPUs, Turbo off); after a change to `soffice.data` only, 17 min (4 jobs); collect 16 min (Brotli quality 11) |

## Build

    ./build.sh preflight     # disk and swap checks; prints the swapfile command if needed
    ./build.sh               # everything in the background; log in out/<label>/build.log
    ./build.sh status        # progress, memory, free disk

Steps can be run alone: `image`, `fetch`, `qt`, `lo`, `collect`. Every heavy step runs in a container capped at
`MEM_LIMIT_GB` RAM plus the free swap minus 4 GB, and at `MAX_CPUS` CPUs; out of memory kills the container, not the
machine, and the LibreOffice step resumes once with a single job. The build stops itself below `STOP_BELOW_DISK_GB`
free disk. Memory peaks are sampled every 30 s from the container's cgroup.

Output: `out/<LO_VERSION>-nl<BUILD_NUMBER>/` — the four engine files, `build-info.json`, `licenses/`, and the
spelling and hyphenation dictionaries in `dicts/` (see Dictionaries).
Into the module: `htdocs/custom/odteditor/dev/update-engine.sh --local out/<label>`.

| File | Raw | Brotli |
|---|---|---|
| soffice.wasm | 166.4 MB | 37.6 MB |
| soffice.data | 113.6 MB | 17.7 MB |
| soffice.js | 0.84 MB | 0.13 MB |
| soffice.data.js.metadata | 0.23 MB | 0.02 MB |
| Total | 281.1 MB | 55.5 MB |

## Smoke test

    python3 tests/smoke/make-samples.py                    # once; needs the desktop LibreOffice and python3-uno
    (cd tests/smoke && npm install)
    python3 -I tests/smoke/serve.py out/<label> 8766 &
    node tests/smoke/run.mjs http://127.0.0.1:8766 '' shot.png
    node tests/smoke/run.mjs http://127.0.0.1:8766 'files=odt&visible=1&lang=fr_FR&ui=fr_FR' fr.png

The first run opens and stores the 7 sample formats (odt, ods, odp, odg, docx, xlsx, pptx); the second shows the
French UI. Results on 26.8.1.1-nl1, median of 3 runs in headless Chromium, against the ZetaOffice build of
2025-05-13 measured the same day: ready 4.5 s (ZetaOffice 4.1 s), 7 formats done 8.5 s (8.7 s), Chromium memory
1.58 GB (1.40 GB). UI checked in en-US, fr, de, es, it; an unpackaged language (`ui=pt_BR`) falls back to English.

## A newer LibreOffice

Change `LO_VERSION`, `LO_COMMIT`, `LO_SRC_URL`, `LO_TARBALLS`; check `static/README.wasm.md` of that version for
the emsdk and Qt versions (`EMSDK_*`, `QT*_COMMIT`); download and pin `checksums.sha256`; set `BUILD_NUMBER=1`;
run `./build.sh`. If `patches/core/` no longer applies, `fetch` stops: update the patch against the new file.

## Dictionaries

The build output holds the spelling and hyphenation dictionaries of the main variant of the five languages, from
`libreoffice-dictionaries-<version>.tar.xz` (`collect`, `out/<label>/dicts/`, licences in
`out/<label>/licenses/dictionaries/`): `hunspell/{en_US,fr_FR,de_DE,es_ES,it_IT}.{dic,aff}` and
`hyphen/hyph_{en_US,fr_FR,de_DE,es_ES,it_IT}.dic`, 9.9 MB raw, 2.2 MB Brotli. LibreOffice takes the locale of such a
file from its name and matches it exactly, so each file is named after its main locale and `build-info.json` lists,
per file, the other locales of the upstream `dictionaries.xcu` as `links`: the module creates them as symbolic links
(`fr_BE.dic` → `fr_FR.dic`). Not covered (other upstream dictionaries): en-GB, en-AU, en-CA, en-ZA, de-AT, de-CH and
the Latin American Spanish spelling (their hyphenation is covered). Thesaurus: not shipped.

Sizes of all the dictionaries of these languages, measured on LibreOffice 26.8.1.1's dictionaries
(`scripts/measure-dicts.py`), Brotli as the module stores the engine:

| Language | Spelling only (main variant) raw | Brotli | Everything (variants, hyphenation, thesaurus) raw | Brotli |
|---|---|---|---|---|
| English (en_US) | 0.55 MB | 0.17 MB | 22.8 MB | 2.90 MB |
| French (fr) | 1.44 MB | 0.29 MB | 6.3 MB | 1.08 MB |
| German (de_DE_frami) | 4.38 MB | 0.89 MB | 79.7 MB | 4.47 MB |
| Spanish (es_ES) | 0.89 MB | 0.20 MB | 23.2 MB | 0.77 MB |
| Italian (it_IT) | 1.37 MB | 0.30 MB | 3.5 MB | 0.81 MB |
| Total | 8.6 MB | 1.85 MB | 135.4 MB | 10.0 MB |

The raw size matters too: the engine's file system lives in browser memory.

LibreOffice packages dictionaries as extensions, which the WebAssembly build disables, but its spell checker and
hyphenator also read plain files from the system folders that configure sets for Emscripten (`DICT_SYSTEM_DIR`
`/usr/share/hunspell`, `HYPH_SYSTEM_DIR` `/usr/share/hyphen`): the files are written there before LibreOffice starts.

Smoke test: `node tests/smoke/run.mjs http://127.0.0.1:8766 'files=odt&dicts=1'` loads the dictionaries of the
served build; the probe lists the locales and checks one word per locale and the hyphenation of a long word.
Start-up (median of 3, 26.8.1.1-nl2): ready 4876 ms with the dictionaries, 4860 ms without. Opening the 7 sample
documents (French text) takes longer once the French dictionary is in use: 12.6 s instead of 9.7 s.

## Licences

LibreOffice: MPL-2.0. Qt for WebAssembly: the wasm platform plugin is GPLv3 (or commercial), the rest of Qt
LGPLv3/GPL; it is statically linked, so the engine as a whole is conveyed under GPLv3 and its complete source
(this repository, the pinned sources, `patches/`) must be offered with it. Emscripten runtime: MIT / University of
Illinois NCSA; libc++, libc++abi, compiler-rt: Apache-2.0 with LLVM exception; musl: MIT; dlmalloc: public domain.
Fonts: see LibreOffice's licence file in `out/<label>/licenses/`. This repository's own scripts: GPLv3 or later
(`COPYING`); `patches/core/*`: MPL-2.0; `tests/smoke/www/zeta.js` (zetajs): MIT.
