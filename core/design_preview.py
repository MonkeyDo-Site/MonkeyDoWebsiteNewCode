import json
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def frozen_page(request, filename):
    root = settings.BASE_DIR / "docs/design-review/v15"
    manifest = json.loads((root / "manifest.json").read_text())
    html_files = {"index.html"} | {item["file"] for item in manifest["pages"]}
    image_files = {
        item["id"] + suffix
        for item in manifest["pages"]
        for suffix in ("-desktop.jpg", "-phone.jpg")
    }
    if Path(filename).name != filename or filename not in html_files | image_files:
        raise Http404
    if filename in image_files:
        return FileResponse((root / filename).open("rb"), content_type="image/jpeg")
    # The frozen HTML is unchanged on disk. At the hosted root, normalize only
    # local asset paths; the pinned release supplies the same source CSS/images.
    content = (
        (root / filename)
        .read_text()
        .replace("../../../static/", "/static/")
        .replace("../../brand-assets/originals/", "/static/brand/")
        .replace("../../brand-assets/children-originals/", "/static/children/")
    )
    response = HttpResponse(content, content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"] = (
        "default-src 'none'; img-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    return response
