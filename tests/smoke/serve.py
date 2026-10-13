"""Serve the smoke page, the samples and an engine directory with the headers LOWA needs.
Usage: python3 -I tests/smoke/serve.py <engine-dir> [port]   (page at http://127.0.0.1:<port>/)
The engine directory is served under /engine/, with its sub-folders (dicts/hunspell/…)."""
import http.server
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.abspath(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
TYPES = {'.js': 'text/javascript', '.wasm': 'application/wasm', '.metadata': 'application/json', '.data': 'application/octet-stream',
         '.dic': 'application/octet-stream', '.aff': 'application/octet-stream'}


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.split('?', 1)[0]
        if path.startswith('/engine/'):
            rel = os.path.normpath(path[len('/engine/'):])
            if rel.startswith('..') or os.path.isabs(rel):
                return os.path.join(ENGINE, '.missing')
            return os.path.join(ENGINE, rel)
        name = os.path.basename(path)
        if path.startswith('/samples/'):
            return os.path.join(HERE, 'samples', name)
        return os.path.join(HERE, 'www', name or 'index.html')

    def guess_type(self, path):
        return TYPES.get(os.path.splitext(path)[1], super().guess_type(path))

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
