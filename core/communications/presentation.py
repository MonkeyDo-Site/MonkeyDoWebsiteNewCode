"""Branded confirmation rendering from the message's frozen plain-text snapshot."""

from django.conf import settings
from django.templatetags.static import static
from django.utils.html import escape, format_html, urlize
from django.utils.safestring import mark_safe


def confirmation_html(text):
    paragraphs = []
    for paragraph in text.split("\n\n"):
        lines = []
        for line in paragraph.splitlines():
            safe = mark_safe(urlize(escape(line), autoescape=False))
            if line in {
                "You're all set for your Monkey Do adventure!",
                "You're all set for your MonkeyDo adventure!",
            }:
                safe = format_html('<strong style="color:#ad415d;font-size:24px">{}</strong>', safe)
            elif line.startswith(
                ("We look forward to seeing you ", "Your total is $", "You selected to pay via ")
            ):
                safe = format_html("<strong>{}</strong>", safe)
            lines.append(str(safe))
        paragraphs.append(
            '<p style="margin:0 0 20px;line-height:1.6">' + "<br>".join(lines) + "</p>"
        )
    logo = settings.BOOKING_STAGING_ORIGIN.rstrip("/") + static("brand/Final MonkeyDo logo.jpg")
    return str(
        format_html(
            '<!doctype html><html><body style="margin:0;background:#faf7ef;color:#293e34;font-family:Arial,sans-serif">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#faf7ef"><tr><td align="center" style="padding:24px 12px">'
            '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#eef2e8;border-radius:20px">'
            '<tr><td style="padding:28px"><img src="{}" alt="MonkeyDo Adventurous Play" width="150" style="display:block;max-width:150px;height:auto;margin-bottom:24px">'
            '<p style="font-size:12px;color:#ad415d">MONKEYDO STAGING TEST — This is a test booking, not a real visit or payment.</p>{}</td></tr></table></td></tr></table></body></html>',
            logo,
            mark_safe("".join(paragraphs)),
        )
    )
