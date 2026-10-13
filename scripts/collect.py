"""Copy the engine files of a LibreOffice WebAssembly build and write build-info.json.

Usage: python3 -I scripts/collect.py <repo-dir> <work-dir> <out-dir>
Fails (exit 1) when a file is missing or a UI language is not in soffice.data.
"""
import datetime
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

import brotli

ENGINE_FILES = ['soffice.js', 'soffice.wasm', 'soffice.data', 'soffice.data.js.metadata']
# .mo files every UI language must have (Writer, Calc, Impress and the shared UI)
REQUIRED_MO = ['sw', 'sc', 'sd', 'svx', 'cui', 'sfx', 'vcl', 'svt']


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
        'stats': stats,
    }
    with open(os.path.join(out, 'build-info.json'), 'w') as f:
        json.dump(info, f, indent=2)
        f.write('\n')
    for n in ENGINE_FILES:
        print('%-26s raw %12d  br %12d' % (n, info['files'][n]['raw'], info['files'][n]['br']))


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
