"""Write the raw engine files of a module lowa/ directory (Brotli-compressed) into <dest>.
Usage: python3 -I tests/smoke/unpack-module-engine.py <lowa-dir> <dest>"""
import json
import os
import sys

import brotli

src, dest = sys.argv[1], sys.argv[2]
os.makedirs(dest, exist_ok=True)
with open(os.path.join(src, 'engine.json')) as f:
    engine = json.load(f)
for name, meta in engine['files'].items():
    with open(os.path.join(src, name), 'rb') as f:
        data = f.read()
    if meta.get('encoding', 'br') == 'br':
        data = brotli.decompress(data)
    with open(os.path.join(dest, name), 'wb') as f:
        f.write(data)
    print(name, len(data))
