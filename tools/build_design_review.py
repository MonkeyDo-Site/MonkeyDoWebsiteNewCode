"""Export frozen, read-only design pages using an isolated in-memory database.

Run with the project's Python: python tools/build_design_review.py
No app database, credentials, deployed service, or provider is accessed.
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["APP_ENV"] = "test"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/design-review/v1")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--version",
        choices=(
            "V1",
            "V2",
            "V3",
            "V4",
            "V5",
            "V6",
            "V7",
            "V8",
            "V9",
            "V10",
            "V11",
            "V12",
            "V13",
            "V14",
            "V15",
            "V16",
            "V17",
            "V18",
        ),
        default="V1",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        parser.error("Supply the full reviewed source commit hash.")
    out = args.output.resolve()
    if (out / "manifest.json").exists():
        parser.error(
            "This frozen review already exists. Use a new output folder; never overwrite a review in progress."
        )
    subprocess.run(
        [
            "git",
            "diff",
            "--exit-code",
            args.source_commit,
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
    out.mkdir(parents=True, exist_ok=True)

    import django
    from django.conf import settings

    # Set these before Django initializes any connection. This process can only
    # write ephemeral SQLite data; never use a staging or local application DB.
    settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    settings.APP_ENV = "test"
    settings.SECRET_KEY = "artificial-inmemory-design-export-only"
    settings.ALLOWED_HOSTS = ["testserver"]
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.test import Client

    from core.booking_management import create_test_booking
    from core.memberships import create_draft
    from core.models import AccountSecurity, Customer, CustomerComment, Session

    call_command("migrate", verbosity=0)
    now = datetime(2026, 11, 8, 10, tzinfo=ZoneInfo("America/New_York"))
    with patch("django.utils.timezone.now", return_value=now):
        call_command("seed_staging", verbosity=0)
        owner = get_user_model().objects.create_user(
            username="review-owner",
            email="owner@example.invalid",
            is_staff=True,
            is_superuser=True,
        )
        customer = Customer.objects.create(
            last_name="Sample Family", phone="2025550123", email="family@example.invalid"
        )
        CustomerComment.objects.create(
            customer=customer, author=owner, body="Example note for layout review only."
        )
        sessions = list(Session.objects.filter(starts_at__date=now.date()))
        booking = create_test_booking(
            actor=owner,
            customer=customer,
            session_id=sessions[0].pk,
            children=2,
            adults=1,
            creation_key=uuid.uuid4(),
        )
        sessions[1].child_capacity = 0
        sessions[1].total_capacity = 0
        sessions[1].save()
        sessions[2].kind = "party"
        sessions[2].save()
        draft = create_draft(
            actor=owner,
            customer=customer,
            kind="subscription",
            places=2,
            months=3,
            billing="monthly",
            starts_on=now.date(),
            expected_method="card",
            creation_key=uuid.uuid4(),
        )
        client = Client()
        # Fixture authentication exists only in this isolated export process.
        # No application authentication code or deployed access gate is changed.
        client.force_login(owner)
        session = client.session
        session["owner_mfa_version"] = AccountSecurity.objects.get(user=owner).version
        session["owner_verified_at"] = now.timestamp()
        session.save()
        pages = [
            ("01-home", "Home", "/"),
            ("02-about", "About", "/about/"),
            ("03-programs", "Memberships", "/memberships/"),
            ("17-clubs-parties", "Clubs & Parties", "/clubs-parties/"),
            ("04-book", "Book Now — schedule preview", "/book/"),
            ("05-contact", "Contact Us", "/contact/"),
            ("06-today", "Staff Today", "/staff/today/"),
            ("07-customers", "Customer list", "/staff/customers/"),
            ("08-customer", "Customer detail", f"/staff/customers/{customer.pk}/"),
            ("09-customer-edit", "Customer edit", f"/staff/customers/{customer.pk}/edit/"),
            ("10-bookings", "Booking list", "/staff/bookings/"),
            ("11-booking", "Booking detail — setup pending", f"/staff/bookings/{booking.pk}/"),
            ("12-memberships", "Membership draft list", "/staff/memberships/"),
            ("13-membership", "Membership draft detail", f"/staff/memberships/{draft.pk}/"),
            ("14-membership-new", "New membership draft", "/staff/memberships/new/"),
            ("15-calendar", "Owner dated calendar", "/staff/scheduling/?day=2026-11-08"),
            ("16-weekly", "Owner weekly schedule", "/staff/scheduling/weekly/"),
        ]
        routes = {urlsplit(url).path: name + ".html" for name, _, url in pages}
        # Render public pages as a visitor, not as an authenticated owner.
        visitor = Client()
        for index, (name, title, url) in enumerate(pages):
            response = (client if url.startswith("/staff/") else visitor).get(url)
            if response.status_code != 200:
                raise RuntimeError(f"Cannot capture {url}: HTTP {response.status_code}")
            renderer = FrozenHTML(routes, args.source_commit, args.version)
            renderer.feed(response.content.decode())
            rendered = chr(10).join(
                line.rstrip() for line in "".join(renderer.parts).splitlines()
            ) + chr(10)
            if "csrfmiddlewaretoken" in rendered or "<form" in rendered or "<script" in rendered:
                raise RuntimeError(f"Active form/script/CSRF token remained in {name}")
            (out / (name + ".html")).write_text(rendered)
        manifest = {
            "review_version": f"Design review {args.version}",
            "source_commit": args.source_commit,
            "fixture_date": "2026-11-08 America/New_York",
            "fixture_data": "Artificial Sample Family; reserved 555 phone and example.invalid emails.",
            "read_only": True,
            "pages": [
                {"id": name, "title": title, "file": name + ".html"} for name, title, _ in pages
            ],
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        links = "".join(
            f'<li><a href="{name}.html">{html.escape(title)}</a></li>' for name, title, _ in pages
        )
        (out / "index.html").write_text(
            f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MonkeyDo — Design review {args.version}</title><style>body{{font:18px/1.6 system-ui;max-width:850px;margin:40px auto;padding:20px;background:#fbf8f2;color:#273c32}}a{{color:#325a49}}li{{margin:12px 0}}</style><h1>MonkeyDo — Design review {args.version}</h1><p>Frozen design review of source <code>{args.source_commit[:7]}</code>. These are actual rendered layouts with artificial sample records. Buttons/forms are disabled. Backend development can continue separately.</p><p>Review the public pages first, then staff screens. Membership drafts and pending bookings remain unfinished workflows; this is not a functional staging site.</p><ol>{links}</ol><p>Send numbered comments in chat with the page, phone/computer, and requested change. Reference “{args.version}”. This version stays fixed until you finish reviewing it.</p></html>"""
        )
    print(f"Exported {len(pages)} read-only pages from {args.source_commit[:7]} to {out}")


class FrozenHTML(HTMLParser):
    def __init__(self, routes, source, version="V1"):
        super().__init__(convert_charrefs=False)
        self.routes, self.source, self.parts = routes, source, []
        self.version = version
        self.suppress_script = False

    def handle_decl(self, decl):
        self.parts.append("<!" + decl + ">")

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.suppress_script = True
            return
        if self.suppress_script:
            return
        if tag == "input" and attrs.get("name") == "csrfmiddlewaretoken":
            return
        if tag == "form":
            tag = "div"
        for key in list(attrs):
            if key.startswith("on") or key in {"action", "method", "formaction", "formmethod"}:
                attrs.pop(key)
        if tag in {"input", "button", "select", "textarea"}:
            attrs["disabled"] = None
        for key in ("href", "src"):
            if key not in attrs:
                continue
            value = attrs[key]
            if value.startswith("/static/brand/"):
                attrs[key] = "../../brand-assets/originals/" + value.removeprefix("/static/brand/")
            elif value.startswith("/static/children/"):
                attrs[key] = "../../brand-assets/children-originals/" + value.removeprefix(
                    "/static/children/"
                )
            elif value.startswith("/static/"):
                attrs[key] = "../../../static/" + value.removeprefix("/static/")
            elif value.startswith("/"):
                parts = urlsplit(value)
                attrs[key] = self.routes.get(parts.path, "#actions-disabled")
                if attrs[key] != "#actions-disabled" and parts.fragment:
                    attrs[key] += "#" + parts.fragment
                if attrs[key] == "#actions-disabled":
                    attrs["aria-disabled"] = "true"
                    attrs["title"] = "This action is not available in the frozen design preview."
            elif key == "href" and value.startswith(("mailto:", "tel:")):
                attrs[key] = "#actions-disabled"
                attrs["aria-disabled"] = "true"
        text = "".join(
            " "
            + key
            + (('="' + html.escape(str(value), quote=True) + '"') if value is not None else "")
            for key, value in attrs.items()
        )
        self.parts.append("<" + tag + text + ">")
        if tag == "body":
            self.parts.append(
                f'<aside id="actions-disabled" style="padding:12px 20px;background:#273c32;color:white;font:14px/1.5 system-ui">Design review {self.version} · Source {self.source[:7]} · Read-only · <a href="index.html" style="color:white">Review page index</a></aside>'
            )

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "script":
            self.suppress_script = False
            return
        if not self.suppress_script:
            self.parts.append("</" + ("div" if tag == "form" else tag) + ">")

    def handle_data(self, data):
        if not self.suppress_script:
            self.parts.append(data)

    def handle_entityref(self, name):
        self.parts.append("&" + name + ";")

    def handle_charref(self, name):
        self.parts.append("&#" + name + ";")


if __name__ == "__main__":
    main()
