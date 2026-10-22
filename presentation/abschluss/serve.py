"""Statischer Server für dist/ mit festen MIME-Typen.

Windows-Registry kann .js als text/plain melden; Browser blockieren dann
ES-Module (weiße Seite). Deshalb Typen hier explizit setzen.
"""
import http.server
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8124


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.js': 'text/javascript',
        '.mjs': 'text/javascript',
        '.css': 'text/css',
        '.json': 'application/json',
        '.svg': 'image/svg+xml',
        '.wasm': 'application/wasm',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.webp': 'image/webp',
    }


http.server.ThreadingHTTPServer(('', PORT), Handler).serve_forever()
