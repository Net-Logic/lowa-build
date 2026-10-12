# lowa-build

LibreOffice WebAssembly build for the Office Editor Dolibarr module.

## Dictionaries (not included)

The engine has no spell-checking dictionaries. Measured on LibreOffice 26.8.1.1's dictionaries
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

Feasibility: LibreOffice packages dictionaries as extensions, and the WebAssembly configuration disables
extensions (`--enable-wasm-strip` sets `enable_extensions=no`). But its Hunspell spell checker also reads plain
`.dic`/`.aff` files from "system" paths, which configure enables for Emscripten ("whether to use dicts from external
paths... yes", directory `file:///usr/share/hunspell`), and from the `DICPATH` environment variable
(`lingucomponent/source/lingutil/lingutil.cxx`). So dictionaries can be written into the engine's file system before
LibreOffice starts, without rebuilding the engine: see the runtime check below.
