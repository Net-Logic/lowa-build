"""Size of the Hunspell spelling, hyphenation and thesaurus data of the UI languages.
Usage: python3 -I scripts/measure-dicts.py <dictionaries-dir>
Two figures per language: every dictionary file of the language's directory (all regional variants,
hyphenation, thesaurus), and spelling only for the main variant (.dic and .aff of en_US, fr_FR, de_DE,
es_ES, it_IT). Brotli as the module stores the engine (quality 11, window 24)."""
import os
import sys

import brotli

DIRS = {'en': ('en', 'en_US'), 'fr': ('fr_FR', 'dictionaries/fr'), 'de': ('de', 'de_DE_frami'), 'es': ('es', 'es_ES'), 'it': ('it_IT', 'it_IT')}
KINDS = ('.dic', '.aff', '.dat', '.idx')


def sizes(paths):
    raw = b''
    for path in paths:
        with open(path, 'rb') as f:
            raw += f.read()
    return len(paths), len(raw), len(brotli.compress(raw, quality=11, lgwin=24))


def main(root):
    totals = [0, 0, 0, 0]
    for lang, (sub, main) in DIRS.items():
        folder = os.path.join(root, sub)
        every = [os.path.join(dp, n) for dp, _, names in os.walk(folder) for n in sorted(names) if n.endswith(KINDS)]
        spelling = [os.path.join(folder, main + ext) for ext in ('.dic', '.aff') if os.path.isfile(os.path.join(folder, main + ext))]
        c1, r1, b1 = sizes(every)
        c2, r2, b2 = sizes(spelling)
        totals = [totals[0] + r1, totals[1] + b1, totals[2] + r2, totals[3] + b2]
        print('%-3s %-6s all %3d files raw %10d br %9d | spelling %-12s %d files raw %10d br %9d' % (lang, sub, c1, r1, b1, main, c2, r2, b2))
    print('total             all raw %10d br %9d | spelling raw %10d br %9d' % tuple(totals))


if __name__ == '__main__':
    main(sys.argv[1])
