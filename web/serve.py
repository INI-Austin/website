"""Preview server for the built site.

Two things `python -m http.server` gets wrong for this.

It sends Last-Modified and no Cache-Control, so a browser is free to reuse a
page it already has. That is fine for serving files and useless for previewing
edits: you rebuild, reload, and see the old page.

And it will not serve /about, because there is no file by that name. The site
is linked without extensions and GitHub Pages resolves /about to about.html on
its own, so a preview that cannot do the same makes every link on every page
look broken locally while being correct in production.

    python3 serve.py [port] [dir]
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class PagesHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".webp": "image/webp"}

    def send_head(self):
        """Fall back to <path>.html, the way GitHub Pages does."""
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path.endswith("/") or "." in Path(path).name:
            return super().send_head()
        if Path(self.translate_path(path + ".html")).is_file():
            self.path = path + ".html"
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write("%s %s\n" % (self.address_string(), format % args))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    root = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).parent)
    handler = partial(PagesHandler, directory=root)
    print(f"serving {root} on http://localhost:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
