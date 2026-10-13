"""Copy the engine files of a LibreOffice WebAssembly build and write build-info.json.

Usage: python3 -I scripts/collect.py <repo-dir> <work-dir> <out-dir>
Fails (exit 1) when a file is missing or a UI language is not in soffice.data.
"""
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import brotli

ENGINE_FILES = ['soffice.js', 'soffice.wasm', 'soffice.data', 'soffice.data.js.metadata']
# .mo files every UI language must have (Writer, Calc, Impress and the shared UI)
REQUIRED_MO = ['sw', 'sc', 'sd', 'svx', 'cui', 'sfx', 'vcl', 'svt']
# Spelling (.dic and .aff) and hyphenation files shipped with the engine: (target under dicts/, source under the
# dictionaries folder of the LibreOffice sources, main locale). The target is named after the main locale, because
# LibreOffice takes the locale of a system dictionary from its file name and matches it exactly.
DICT_FILES = [
    ('hunspell/en_US.aff', 'en/en_US.aff', 'en-US'),
    ('hunspell/en_US.dic', 'en/en_US.dic', 'en-US'),
    ('hunspell/fr_FR.aff', 'fr_FR/dictionaries/fr.aff', 'fr-FR'),
    ('hunspell/fr_FR.dic', 'fr_FR/dictionaries/fr.dic', 'fr-FR'),
    ('hunspell/de_DE.aff', 'de/de_DE_frami.aff', 'de-DE'),
    ('hunspell/de_DE.dic', 'de/de_DE_frami.dic', 'de-DE'),
    ('hunspell/es_ES.aff', 'es/es_ES.aff', 'es-ES'),
    ('hunspell/es_ES.dic', 'es/es_ES.dic', 'es-ES'),
    ('hunspell/it_IT.aff', 'it_IT/it_IT.aff', 'it-IT'),
    ('hunspell/it_IT.dic', 'it_IT/it_IT.dic', 'it-IT'),
    ('hyphen/hyph_en_US.dic', 'en/hyph_en_US.dic', 'en-US'),
    ('hyphen/hyph_fr_FR.dic', 'fr_FR/dictionaries/hyph_fr.dic', 'fr-FR'),
    ('hyphen/hyph_de_DE.dic', 'de/hyph_de_DE.dic', 'de-DE'),
    ('hyphen/hyph_es_ES.dic', 'es/hyph_es.dic', 'es-ES'),
    ('hyphen/hyph_it_IT.dic', 'it_IT/hyph_it_IT.dic', 'it-IT'),
]
# Licence folder of each source folder
DICT_LICENSE_DIRS = {'en': 'en', 'fr_FR': 'fr', 'de': 'de', 'es': 'es', 'it_IT': 'it'}
DICT_LICENSE_FILES = re.compile(r'^(README.*|COPYING.*|LICENSE.*|license\.txt)$')
# Licence texts a language needs but its source folder lacks: the French (LGPL 2.1 or later) and Italian (LGPL)
# hyphenation patterns; the LGPL 2.1 text ships in the German folder only
DICT_EXTRA_LICENSES = {'fr': ['de/COPYING_LGPL_v2.1.txt'], 'it': ['de/COPYING_LGPL_v2.1.txt']}
OOR = '{http://openoffice.org/2001/registry}'


def parse_env(path):
    """KEY=VALUE lines of a shell env file (quotes removed, comments and blank lines ignored)"""
    values = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key] = value.strip('"\'')
    return values


def missing_language_files(metadata, langs):
    """Language files expected in soffice.data and absent from its metadata"""
    present = {f['filename'] for f in metadata['files']}
    missing = []
    for lang in langs:
        wanted = ['/instdir/share/registry/Langpack-%s.xcd' % lang,
                  '/instdir/share/registry/res/registry_%s.xcd' % lang,
                  '/instdir/share/registry/res/fcfg_langpack_%s.xcd' % lang]
        if lang != 'en-US':
            wanted += ['/instdir/program/resource/%s/LC_MESSAGES/%s.mo' % (lang, m) for m in REQUIRED_MO]
        missing += [w for w in wanted if w not in present]
    return missing


def brotli_size(path):
    """Size of the file once compressed as the module stores it (Brotli quality 11, window 24)"""
    with open(path, 'rb') as f:
        return len(brotli.compress(f.read(), quality=11, lgwin=24))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def xcu_locales(xcu_path, file_name):
    """Locales that a dictionaries.xcu gives to a dictionary file (the node whose Locations names the file)"""
    for node in ET.parse(xcu_path).iter('node'):
        props = {p.get(OOR + 'name'): (p.findtext('value') or '').split() for p in node.findall('prop')}
        if any(loc.rsplit('/', 1)[-1] == file_name for loc in props.get('Locations', [])):
            return props.get('Locales', [])
    return []


def link_names(target, main_locale, locales):
    """Extra file names (symbolic links in the engine) for the other locales of a file named after its main locale"""
    stem, ext = os.path.splitext(os.path.basename(target))
    main = main_locale.replace('-', '_')
    if not stem.endswith(main):
        sys.exit('%s is not named after its main locale %s' % (target, main_locale))
    return [stem[:-len(main)] + loc.replace('-', '_') + ext for loc in locales if loc != main_locale]


def collect_dicts(dict_root, out):
    """Copy the dictionaries and their licences to out/dicts and out/licenses/dictionaries; their build-info entries"""
    entries = []
    for target, source, main_locale in DICT_FILES:
        path = os.path.join(dict_root, source)
        if not os.path.isfile(path):
            sys.exit('Missing dictionary file: ' + path)
        folder = source.split('/')[0]
        locales = xcu_locales(os.path.join(dict_root, folder, 'dictionaries.xcu'), os.path.basename(source))
        if main_locale not in locales:
            sys.exit('%s: %s not in the locales of %s/dictionaries.xcu (%s)' % (source, main_locale, folder, ' '.join(locales)))
        # Main locale first, each locale once (an xcu may repeat one)
        locales = list(dict.fromkeys([main_locale] + locales))
        dest = os.path.join(out, 'dicts', target)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(path, dest)
        entries.append({'name': target, 'source': source, 'locales': locales,
                        'links': link_names(target, main_locale, locales),
                        'raw': os.path.getsize(dest), 'br': brotli_size(dest), 'sha256': sha256_file(dest)})
    for source_dir in sorted({os.path.dirname(s) for _, s, _ in DICT_FILES}):
        licenses = os.path.join(out, 'licenses', 'dictionaries', DICT_LICENSE_DIRS[source_dir.split('/')[0]])
        os.makedirs(licenses, exist_ok=True)
        for name in sorted(os.listdir(os.path.join(dict_root, source_dir))):
            if DICT_LICENSE_FILES.match(name) and os.path.isfile(os.path.join(dict_root, source_dir, name)):
                shutil.copyfile(os.path.join(dict_root, source_dir, name), os.path.join(licenses, name))
    for lang, sources in DICT_EXTRA_LICENSES.items():
        for source in sources:
            path = os.path.join(dict_root, source)
            if not os.path.isfile(path):
                sys.exit('Missing licence file: ' + path)
            shutil.copyfile(path, os.path.join(out, 'licenses', 'dictionaries', lang, os.path.basename(source)))
    return entries


def main(repo, work, out):
    env = parse_env(os.path.join(repo, 'versions.env'))
    src = os.path.join(work, 'src', 'libreoffice-' + env['LO_VERSION'])
    inst = os.path.join(src, 'workdir', 'installation', 'LibreOffice', 'emscripten')
    os.makedirs(os.path.join(out, 'licenses'), exist_ok=True)
    for name in ENGINE_FILES:
        path = os.path.join(inst, name)
        if not os.path.isfile(path):
            sys.exit('Missing engine file: ' + path)
        shutil.copyfile(path, os.path.join(out, name))
    with open(os.path.join(out, 'soffice.data.js.metadata')) as f:
        metadata = json.load(f)
    langs = ['en-US'] + env['LANGS'].split()
    missing = missing_language_files(metadata, langs)
    if missing:
        sys.exit('Language files missing from soffice.data:\n  ' + '\n  '.join(missing))

    licenses = {
        'MPL-2.0.txt': os.path.join(src, 'COPYING.MPL'),
        'Qt-LICENSE.GPL3': os.path.join(work, 'qt5-src', 'qtbase', 'LICENSE.GPL3'),
        'Qt-LICENSE.LGPL3': os.path.join(work, 'qt5-src', 'qtbase', 'LICENSE.LGPL3'),
        'Emscripten-LICENSE': os.path.join(work, 'stats', 'emscripten-LICENSE'),
    }
    lo_license = os.path.join(src, 'instdir', 'LICENSE.html')
    if os.path.isfile(lo_license):
        licenses['LibreOffice-LICENSE.html'] = lo_license
    else:
        licenses['LibreOffice-license.xml'] = os.path.join(src, 'readlicense_oo', 'license', 'license.xml')
    for dest, path in licenses.items():
        if not os.path.isfile(path):
            sys.exit('Missing licence file: ' + path)
        shutil.copyfile(path, os.path.join(out, 'licenses', dest))
    dicts = collect_dicts(os.path.join(src, 'dictionaries'), out)

    stats = {}
    for path in sorted(glob.glob(os.path.join(work, 'stats', '*.json'))):
        with open(path) as f:
            stats[os.path.basename(path)[:-5]] = json.load(f)
    with open(os.path.join(src, 'autogen.input')) as f:
        autogen_input = [line.rstrip('\n') for line in f if line.strip()]
    repo_commit = subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    info = {
        'label': '%s-nl%s' % (env['LO_VERSION'], env['BUILD_NUMBER']),
        'lo_version': env['LO_VERSION'],
        'lo_commit': env['LO_COMMIT'],
        # Link time of soffice.wasm in the build tree (the copy in out/ has a new mtime)
        'build_date': datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(inst, 'soffice.wasm')), datetime.timezone.utc).strftime('%Y-%m-%d'),
        'repo_commit': repo_commit,
        'emsdk_version': env['EMSDK_VERSION'],
        'emsdk_commit': env['EMSDK_COMMIT'],
        'qt5_commit': env['QT5_COMMIT'],
        'qtbase_commit': env['QTBASE_COMMIT'],
        'base_image': env['BASE_IMAGE'],
        'patches': {os.path.basename(p): sha256_file(p) for p in sorted(glob.glob(os.path.join(repo, 'patches', 'core', '*.patch')))},
        'autogen_input': autogen_input,
        'langs': langs,
        'files': {n: {'raw': os.path.getsize(os.path.join(out, n)), 'br': brotli_size(os.path.join(out, n))} for n in ENGINE_FILES},
        'dicts': dicts,
        'stats': stats,
    }
    with open(os.path.join(out, 'build-info.json'), 'w') as f:
        json.dump(info, f, indent=2)
        f.write('\n')
    for n in ENGINE_FILES:
        print('%-26s raw %12d  br %12d' % (n, info['files'][n]['raw'], info['files'][n]['br']))
    print('%-26s raw %12d  br %12d  (%d files)' % ('dictionaries', sum(d['raw'] for d in dicts), sum(d['br'] for d in dicts), len(dicts)))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
