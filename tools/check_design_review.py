"""Validate a frozen review; optionally capture its first desktop/phone images.

Uses Playwright/Chromium in the development environment, not the application.
Existing images are never overwritten. Check out the pinned review commit first.
"""

import argparse
import json
import subprocess
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Links(HTMLParser):
    def __init__(self, folder):
        super().__init__()
        self.folder = folder

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        assert tag not in {"form", "script"}, tag
        assert "csrfmiddlewaretoken" not in str(attrs)
        if tag in {"input", "button", "select", "textarea"}:
            assert "disabled" in attrs, (tag, attrs)
        for name in ["href", "src"]:
            if name not in attrs:
                continue
            parts = urlsplit(attrs[name])
            assert not parts.scheme and not parts.netloc, attrs[name]
            if parts.path:
                assert (self.folder / unquote(parts.path)).is_file(), attrs[name]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=ROOT / "docs/design-review/v1")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    args = parser.parse_args()
    folder = args.folder.resolve()
    manifest = json.loads((folder / "manifest.json").read_text())
    subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            manifest["source_commit"],
            "--",
            "config",
            "core",
            "templates",
            "static",
            "docs/brand-assets/originals",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    if args.capture and list(folder.glob("*.jpg")):
        parser.error("Review images already exist. Never overwrite a review in progress.")
    for path in folder.glob("*.html"):
        Links(folder).feed(path.read_text())
    from playwright.sync_api import sync_playwright

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=args.chromium, headless=True, args=["--no-sandbox"]
            )
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            for width, label in [(1440, "desktop"), (390, "phone")]:
                page.set_viewport_size(
                    {"width": width, "height": 1000 if label == "desktop" else 844}
                )
                for item in manifest["pages"]:
                    path = (folder / item["file"]).relative_to(ROOT).as_posix()
                    response = page.goto(
                        f"http://127.0.0.1:{server.server_port}/{path}", wait_until="networkidle"
                    )
                    assert response.status == 200, item["id"]
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                        item["id"]
                    )
                    page.locator("img").evaluate_all(
                        "async imgs => { imgs.forEach(i => i.loading = 'eager'); await Promise.all(imgs.map(i => i.decode())); }"
                    )
                    assert page.locator("img").evaluate_all(
                        "(imgs)=>imgs.every(i=>i.complete && i.naturalWidth>0)"
                    ), item["id"]
                    target = folder / (item["id"] + "-" + label + ".jpg")
                    if args.capture:
                        page.screenshot(path=str(target), type="jpeg", quality=76, full_page=True)
                    else:
                        assert target.is_file(), target
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(
        f"PASS: {len(manifest['pages'])} read-only pages; desktop/phone assets and layouts; no forms/scripts/CSRF tokens; no overflow or JavaScript errors."
    )


if __name__ == "__main__":
    main()
