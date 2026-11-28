#!/usr/bin/python3 -I
"""Root-owned deployment controller for the private staging site.

Routine deployment never migrates. Explicit Functional reviewed-batch options
permit only checksum-pinned migrations after a private checkpoint.
No password changes, DNS changes or destructive cleanup.
Run `status`, `deploy --archive ... --sha256 ... --commit ...`, or `rollback`.
"""

import argparse
import base64
import contextlib
import fcntl
import hashlib
import http.client
import json
import os
import re
import shutil
import signal
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

BASE = Path("/srv/monkeydo")
STATE = Path("/var/lib/monkeydo-deploy")
ENV_FILE = Path("/etc/monkeydo/staging.env")
DROPIN = Path("/etc/systemd/system/monkeydo-design-review.service.d/release.conf")
UNIT = "monkeydo-design-review.service"
DOMAIN = "staging.monkeydoplay.com"
SOCKET = "/run/monkeydo-staging/gunicorn.sock"
MAX_ARCHIVE = 200 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
BATCH_TWO_MIGRATIONS = {
    "0023_owner_feedback_batch_two.py": "00fbd5dcb3f8465f3df7a61769dbd7936e1fee1e595007e60e85a8697469df4f",
    "0024_membership_draft_revisions.py": "e38b36db654356b714d8d90e1959a3a5369b2d214f6736d1143d94d3493a0a51",
    "0025_customer_referral_source.py": "8cb23953f2f5de290afd433b90f34371481f029e584d8bc1614c5c3a04efe70f",
}

BATCH_THREE_MIGRATIONS = {
    "0026_owner_feedback_batch_three.py": "ac2c2abaaf4d8f39855b3aa15e51e803746a4fb8d1bfd5ef442c10018b3acf6f",
}

BOOKING_MIGRATIONS = {
    "0096_credit_funded_membership_renewals.py": "f3224b30bf4a9385d887982475afcf02396dec72cc54f8fe800686ade113a870",
    "0095_unused_membership_owner_dates.py": "46b437e0831b6d68874ef0c26a0d9f08c690a999af22ff521c499eacb74e8154",
    "0094_paid_visit_split_remainder.py": "6bb85194de1e7ff81aede28aea83b648f22293fcf57e6c82c2ebfd1843b64ee0",
    "0093_membership_calendar_corrections.py": "6a8faa1d72fc5139e1438d9ac040a817317ed9d6b03f105db553223cfbf3e2a7",
    "0092_combined_renewal_bank_receipt.py": "81bdd06ae27374bd12a010f43e143034ebeb703d295800fa0777c21e1edc7792",
    "0091_combined_membership_renewals.py": "4d7c3fd74e8e827ef4ed62e71671a937f9785d6bbfb8ebdeee9f13052c726697",
    "0090_paid_visit_manual_payment.py": "b421124c9ffb2bd3d2d498ade7e71bf579cb09c9f2a75aba564bf7f9fb6da498",
    "0089_paid_visit_recovery_card_storage.py": "7ed1a4fdf4f2ecae271914842e9f64ef4156e69e5a8bf5c66f823798b6d7364a",
    "0088_paid_visit_cancelled_release.py": "29a8e124431b90603a54ca0e1878093fab35d9bfe67200f35e996aa6c6c55cd8",
    "0087_paid_visit_card_recovery.py": "f6a898fcc83e1a7e817526b625a0d6e5200fd541bc982805191e6178560d43d5",
    "0086_paid_visit_card_reservations.py": "c00647376f0f46d0cfd0486e4b46ae2de0fcd3c2f0c65e84d7fcab61024293c6",
    "0085_paid_visit_received_split.py": "8d17c2620092d022a75ebc335b1cadacc151e7fd197f40538613e03d20314417",
    "0084_paid_visit_purchase.py": "1ea54e866e5dc9aba3cd762446b20b5602b2cb105a650aa786bf08a65ce8844c",
    "0083_cancelled_membership_arrival_stop.py": "fa056c603af49668f583f8f5ea58a3107074e0cedbbcb0af367edea93c101266",
    "0082_stop_pending_arrival.py": "036b29e1bd4ebaa478f38ffda87364337b60bed0d61435f5495162c748980738",
    "0081_gift_cancellation_scope.py": "d517d62366d2248c3b430437d7db5635982435170d0426e61bd11b705ceb6b06",
    "0080_pending_visit_returns.py": "2c1370e113019299e2d330f5442bba2b7ceec89e24c30ca61c71109954064958",
    "0079_pending_visit_receipts.py": "47332a8cea223239700cd882c6827e97304c1f6a1014044415d80535f878348c",
    "0078_split_membership_arrival.py": "f7858df2caff7f1f6ed196b312688a9a681901171c8e82876d4ce33e5fc7854f",
    "0077_membership_booking_zelle.py": "2c393689bcc7ed1b870d03d3e02d5f947fc9fad9127d527e0cda9bdbc7bc9170",
    "0076_membership_first_split.py": "2d421da06f91daa90760ef7f796d55cb42705585aefa4432e19a2b59329682de",
    "0075_visit_customer_credit.py": "df972fb578370a3db917cec5930841b969ab59a2b014408a2e5b20173c84c3d2",
    "0074_scheduled_membership_credit_authority.py": "6d7c9a7f364a682832169c35a7323668b96b98fda526c3719b58a67a851df135",
    "0073_scheduled_membership_claims.py": "d75728f4b761f9f04f5e2b8c44ba693f83b940c9d30c1229316659a8e5bda783",
    "0072_initial_public_membership_authority.py": "472a7643f28ba0fd383eb269d4a54135b90b1c2bb687e56fe7e3f6be063bb51e",
    "0071_membership_arrival_owner_resolution.py": "2f603844cf425c9ffb0c05056f9ee2b48ccc1cf0023e6932ab6e23f87b031ad1",
    "0070_pending_membership_arrival.py": "9d73b647628f86a0d8dcae566159fbc78346881905313a514e7f346719771186",
    "0069_combined_membership_arrival.py": "a89c26a3a791567385642e9be6c087fa06fb5a91f72d55e1b228b672ad8bae95",
    "0068_booking_membership_renewal_prompts.py": "c5d4e1a036c61104f14648f46ad83b8d71078c8592c09dc32ed9f4a5a5014313",
    "0067_membership_renewal_notices.py": "1917ed8e799e51899fca4eb652697c59d093b8ceaebcee14849fa7c802b5ff8d",
    "0066_membership_operational_exports.py": "7aec1b0a9e25a8c28b697cb541c4faf44607454f69d1e5c890b3de317a879eb1",
    "0065_owner_credit_corrections.py": "a58ff8b2b370039f9fa31078ac0b99882206f5623e0a267e03c8297208d53236",
    "0063_membership_cancellation_refunds.py": "e1600a0d3079bb8064ad822d1362ceb49ff6aa0c915db630281b6aad03fabba6",
    "0064_customer_credit_conversion.py": "3e16eecc69373e3b8508e8fe2264ab30cd92c2445ce8fbd33fb91e9cde772d4d",
    "0062_booking_membership_owner_decisions.py": "277ed2336d857160cabf28d1367fff828f6a63cb412926ba0ff9c5719d70df3d",
    "0058_membership_follow_on_cohorts.py": "cc2d855ac67e12fd508b4b4cffb57ecf389be736e31c4a8a220967dfba17e4c0",
    "0059_membership_billing_actions.py": "42216fe77b5b8172a4307e95a2b6b21f8e0d342ef7085bc2a9a894c452a3e8c9",
    "0060_membership_card_authorizations.py": "cda39f8af2a1415142b11c4478e0f4af940559de85d37791e71851ba7880909c",
    "0061_verified_membership_renewal_authority.py": "45c2d3a3f5133aa73e15f40ca7b912e8decb90daab35b316eab53fdaaf26a516",
    "0057_membership_benefit_reservations.py": "5bc11feecb58be60aadf0f70ff777b0c883bb4d32d1124fe8d3617465048c992",
    "0027_payment_foundation.py": "d9ddf42e75cb21d1549a403556e4c16073c9cbc3cd4102317f7f155cbcd455e8",
    "0028_financial_record_guards.py": "e3b182b45f60e0e21c11aec5240af42fb883af5dc2b8572043c84cb182f21ea4",
    "0029_waiver_evidence.py": "59436757945de6ac2564d22b36b192152140ed45192e366f9596acb03493068f",
    "0030_waiver_evidence_guards.py": "f0830e0c16b56df506d9c6608afd471624aa850f8505146a2db357d59a36df1c",
    "0031_waiver_optional_metadata.py": "530a9034499e9e96e85edbf24ce6b1b242c66a78c7af8c8be30ecb170c8b26aa",
    "0032_message_outbox.py": "d77253f92b62676215bb020d268962186f46b43d829f822384e7719b35bfe0b8",
    "0033_message_history_guards.py": "1f0b02d741794d6e46c43dd4bf5358989b7ac5ced8856368cd984b20b218789f",
    "0034_waiver_review_revision.py": "da70678c34fce18a38072cf7c7c8863beddad383556d70cdb7a8f3515467ad40",
    "0035_booking_checkout.py": "054811e087d2bfd3e8184847b6337549efb278353e19106a598fad81023acd3b",
    "0036_checkout_record_guards.py": "d8d246b8a5cd6474b27b0a922b5ac014f35782c80f314f281d5ed50cb266d5a2",
    "0037_payment_followup_actions.py": "d196f960fac3ae1eae0d1e4d09f006171f45794de61bba8fe638b3697613820a",
    "0038_remaining_payment_checkout.py": "859cab7bd8003ea7e7af581f63968b064b333364dc4331585841f2430adff78f",
    "0039_system_payment_followup.py": "aa22be6b83affec71b43189c9751efae80d6a227dc39866f79cd3006fdaa4160",
    "0040_actual_receipt_dates.py": "bee599e37c479b2499184e048c189696345fe3733f9f168d0c2624f167b4ce30",
    "0041_waiver_contact_retention.py": "8f547ff62776bbd956494f8117396bb587be2245aeb264fa762a86f88f20a748",
    "0042_encrypted_backup_metadata.py": "308d81709e219789ca6753c6e33f45276c27327306682ee81cf3686b9e760cb3",
    "0043_backup_record_guards.py": "6a21a2144bd3f3da9ea707a467fcf38d816523e4035819d860bc5882cf2b6d6a",
    "0044_mail_delivery_events.py": "9dbbff552dfd23b2a55f48d8d8b6413ee884c5f23885b7f9b90656d1da3a7f92",
    "0045_mail_delivery_status_guards.py": "ba8d3da2cccd0545bda2bfe1ecb6f06291e476f49c914508aee6909469d2afc0",
    "0046_mail_attempt_reconciliation.py": "e02635fb8f1514631f5052fd18e44adebc9e7534fdc5d5b0feef1691ae860c69",
    "0047_backup_issue_review.py": "060d9f0a50f00337ae7746c9830c46056d5052f21ddbd4db7c73aff580779949",
    "0048_seventh_booking_records.py": "fd440c11d8bd37f4c2116447b11537cb5cf4d34eb256a4beff44869bafd4d4d2",
    "0049_seventh_booking_controls.py": "5c4d5d7d5288d7862d6dac8473ab590b609e884e058311dccd3ce043d2776343",
    "0050_seventh_record_guards.py": "0e20f49414670c73f0128917bbcbfa0845cbfb1569a6b8fb80d851c599cff268",
    "0051_paper_waiver_version.py": "5dc195ee1151ada3c6f2f412f38917b077399ee467ee5823270bfc4230f2cb11",
    "0052_booking_comment_scope.py": "66880bf106cd5430b2f0dbe160fdd5838958c2aeef20e53e40cbe267d40a99e8",
    "0053_staff_capacity_hold.py": "888b8bf991c8f465428c6565996481d34c9d3cef31608b768e473522ee1011e5",
    "0056_membership_message_link.py": "7c95ec3672675c942cd1cb59427c05cf193617de5c9ae5f99beda0c1fb5b9d83",
    "0055_membership_payment_purposes.py": "3236e553b0eec76ba041a8c40da921f69c41ee8dbe7ed0c16ae2d310fae4ece8",
    "0054_active_membership_purchases.py": "73bc2c7336a5c3d39e071411b130252972559377f29f25b2322bdb016ce96c2d",
}
BOOKING_UNITS = {
    "monkeydo-functional-backup.service.example": "1975613e1c7bc71881ffba37a41e56f66474f7044f2c72fba2103c08b9b6e1af",
    "monkeydo-functional-backup.timer.example": "52fa3c4e6c95d942d41abd29b030595beedee8e40bd503f87af2b320146804b5",
    "monkeydo-functional-jobs.service.example": "46aca1ecc6cd5916e3f172ae635661f46ebf859386183a7b36ee1164cb7c55f6",
    "monkeydo-functional-jobs.timer.example": "c0f9d6b99c84f5587753bb22d74aab3fcf5d14b5b97598b65085618a52341af8",
    "monkeydo-functional-retention.service.example": "541f5a9b584e2dc6750cbb639c61ebde87a74fc1d54d721eb50aee5f538d6aaa",
    "monkeydo-functional-retention.timer.example": "59a37f36ac62af1521a759e4a885c62d3f78dd85020635a1e1e3214438ee48bd",
}
BOOKING_CAPABILITY = "3351e827516af795bd1aeaaaac8ab9b7f83225f53e759db16fcb5ce972c0c567"

TARGET = "design"
RUNTIME_USER = "monkeydo"
DB_NAME = "monkeydo_staging"
HEALTH_PATHS = (("/staging/access/", 200), ("/", 302), ("/01-home.html", 302))


def select_target(target):
    """Closed target allowlist; paths/units/roles are never supplied by the caller."""
    global \
        TARGET, \
        BASE, \
        STATE, \
        ENV_FILE, \
        DROPIN, \
        UNIT, \
        DOMAIN, \
        SOCKET, \
        RUNTIME_USER, \
        DB_NAME, \
        HEALTH_PATHS
    if target not in {"design", "functional"}:
        raise ValueError("Unknown deployment target")
    TARGET = target
    functional = target == "functional"
    BASE = Path("/srv/monkeydo-functional" if functional else "/srv/monkeydo")
    STATE = Path(
        "/var/lib/monkeydo-functional-deploy" if functional else "/var/lib/monkeydo-deploy"
    )
    ENV_FILE = Path("/etc/monkeydo/functional.env" if functional else "/etc/monkeydo/staging.env")
    UNIT = "monkeydo-functional.service" if functional else "monkeydo-design-review.service"
    DROPIN = Path("/etc/systemd/system") / (UNIT + ".d/release.conf")
    DOMAIN = "staging.monkeydoplay.com"
    SOCKET = (
        "/run/monkeydo-functional/gunicorn.sock"
        if functional
        else "/run/monkeydo-staging/gunicorn.sock"
    )
    RUNTIME_USER = "monkeydo-functional" if functional else "monkeydo"
    DB_NAME = "monkeydo_functional" if functional else "monkeydo_staging"
    HEALTH_PATHS = (
        (
            ("/staging/access/", 200),
            ("/", 302),
            ("/book/", 302),
            ("/book/details/", 302),
            ("/staff/", 200),
        )
        if functional
        else (("/staging/access/", 200), ("/", 302), ("/01-home.html", 302))
    )


class DeployError(Exception):
    pass


def atomic_write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".monkeydo-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def safe_archive(archive, commit):
    prefix = "MonkeyDoWebsiteNewCode-" + commit
    seen, expanded = set(), 0
    if len(archive.infolist()) > 20000:
        raise DeployError("Too many archive entries.")
    for entry in archive.infolist():
        path = PurePosixPath(entry.filename)
        kind = stat.S_IFMT(entry.external_attr >> 16)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in entry.filename
            or any(ord(c) < 32 for c in entry.filename)
            or not path.parts
            or path.parts[0] != prefix
            or kind not in {0, stat.S_IFREG, stat.S_IFDIR}
            or entry.filename in seen
            or entry.flag_bits & 1
        ):
            raise DeployError("Unsafe or unexpected archive entry.")
        seen.add(entry.filename)
        expanded += entry.file_size
        if expanded > MAX_EXPANDED:
            raise DeployError("Archive expands beyond the permitted size.")
    required = {
        "manage.py",
        "requirements.txt",
        "config/settings.py",
        "core/design_preview.py",
        "docs/design-review/v1/manifest.json",
    }
    if not all(prefix + "/" + item in seen for item in required):
        raise DeployError("Archive is not the expected design-review release.")
    return prefix


def extract_archive(path, destination, commit):
    with zipfile.ZipFile(path) as archive:
        prefix = safe_archive(archive, commit)
        for entry in archive.infolist():
            relative = PurePosixPath(entry.filename).relative_to(prefix)
            if not relative.parts:
                continue
            target = destination.joinpath(*relative.parts)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if entry.external_attr >> 16 & 0o111 else 0o644)


class FrozenLinks(HTMLParser):
    def __init__(self, folder, release):
        super().__init__()
        self.folder, self.release = folder, release

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag in {"form", "script"} or any(name.startswith("on") for name in attrs):
            raise DeployError("Design bundle contains an active form/script/event handler.")
        if tag in {"input", "button", "select", "textarea"} and "disabled" not in attrs:
            raise DeployError("Design bundle contains an enabled control.")
        for name in ("href", "src"):
            if name not in attrs:
                continue
            parts = urlsplit(attrs[name])
            if parts.scheme or parts.netloc:
                raise DeployError("Design bundle contains an external resource/action.")
            if parts.path:
                target = (self.folder / unquote(parts.path)).resolve()
                if not target.is_relative_to(self.release) or not target.is_file():
                    raise DeployError("Design bundle contains a missing or unsafe asset/link.")


def validate_bundles(release):
    manifests = list((release / "docs/design-review").glob("v[0-9]*/manifest.json"))
    if not manifests:
        raise DeployError("No frozen design bundle is present.")
    for manifest in manifests:
        if manifest.stat().st_size > 1024 * 1024:
            raise DeployError("Unexpectedly large design manifest.")
        data = json.loads(manifest.read_text())
        if not data.get("pages") or len(data["pages"]) > 200:
            raise DeployError("Invalid design page manifest.")
        names = ["index.html"]
        for page in data["pages"]:
            if not re.fullmatch(r"[a-z0-9-]+", page["id"]) or page["file"] != page["id"] + ".html":
                raise DeployError("Invalid design page name.")
            names.append(page["file"])
            for suffix in ("-desktop.jpg", "-phone.jpg"):
                if not (manifest.parent / (page["id"] + suffix)).is_file():
                    raise DeployError("Design screenshot is missing.")
        for name in names:
            path = manifest.parent / name
            if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
                raise DeployError("Design page is missing or too large.")
            content = path.read_text()
            if "csrfmiddlewaretoken" in content:
                raise DeployError("Design page includes a CSRF token.")
            FrozenLinks(manifest.parent, release).feed(content)


def read_environment(path, owner_uid=0):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid or info.st_mode & 0o037:
        raise DeployError("Configuration must be root-owned, private and not a symlink.")
    allowed = {
        "APP_ENV",
        "MONKEYDO_DESIGN_ONLY",
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "DJANGO_TRUST_PROXY",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
    }
    if TARGET == "functional":
        allowed.update(
            {
                "MONKEYDO_CUSTOMER_TEST_BOOKING",
                "MONKEYDO_EMAIL_TRANSPORT",
                "MONKEYDO_TEST_EMAIL_RECIPIENTS",
                "RESEND_API_KEY",
                "MONKEYDO_TRUST_LOCAL_CLIENT_IP",
                "MONKEYDO_RECOVERY_HOLD",
                "MONKEYDO_PAYMENT_SANDBOX",
                "MONKEYDO_WAIVERS",
                "MONKEYDO_BOOKING_EMAIL",
                "MONKEYDO_BOOKING_COMPLETION",
                "MONKEYDO_BACKUPS",
                "BANQUEST_API_SOURCE_KEY",
                "BANQUEST_API_PIN",
                "BANQUEST_TOKENIZATION_PUBLIC_KEY",
                "BANQUEST_WEBHOOK_KEY",
                "RESEND_WEBHOOK_SECRET",
                "MONKEYDO_R2_ACCOUNT_ID",
                "MONKEYDO_R2_WAIVER_BUCKET",
                "MONKEYDO_R2_WAIVER_ACCESS_KEY",
                "MONKEYDO_R2_WAIVER_SECRET_KEY",
                "R2_BACKUP_BUCKET",
                "R2_BACKUP_READ_ACCESS_KEY",
                "R2_BACKUP_READ_SECRET_KEY",
            }
        )
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or name not in allowed or name in result:
            raise DeployError("Unsupported configuration entry; review the protected file locally.")
        # Existing provisioned file uses simple unquoted KEY=value entries.
        if not value or any(c.isspace() for c in value) or any(c in value for c in "\"'`$"):
            raise DeployError("Configuration must use simple unquoted values.")
        result[name] = value
    for name in (
        "MONKEYDO_PAYMENT_SANDBOX",
        "MONKEYDO_WAIVERS",
        "MONKEYDO_BOOKING_EMAIL",
        "MONKEYDO_BOOKING_COMPLETION",
        "MONKEYDO_BACKUPS",
        "MONKEYDO_RECOVERY_HOLD",
    ):
        if name in result and result[name] not in {"0", "1"}:
            raise DeployError("Integration flags must be explicitly 0 or 1.")
    required = {
        "APP_ENV": "staging",
        "MONKEYDO_DESIGN_ONLY": "0" if TARGET == "functional" else "1",
        "POSTGRES_DB": DB_NAME,
        "POSTGRES_USER": RUNTIME_USER,
        "POSTGRES_HOST": "/var/run/postgresql",
        "DJANGO_ALLOWED_HOSTS": DOMAIN,
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://" + DOMAIN,
        "DJANGO_TRUST_PROXY": "1",
    }
    if TARGET == "functional":
        required.update(
            {
                "MONKEYDO_CUSTOMER_TEST_BOOKING": "1",
                "MONKEYDO_EMAIL_TRANSPORT": "resend",
                "MONKEYDO_TRUST_LOCAL_CLIENT_IP": "1",
            }
        )
        if not result.get("RESEND_API_KEY") or not result.get("MONKEYDO_TEST_EMAIL_RECIPIENTS"):
            raise DeployError(
                "Functional staging needs protected email credentials and test recipients."
            )
    if any(result.get(key) != value for key, value in required.items()):
        raise DeployError("Configuration is not the approved isolated staging target.")
    if (
        len(result.get("DJANGO_SECRET_KEY", "")) < 50
        or result.get("POSTGRES_PORT", "5432") != "5432"
    ):
        raise DeployError("Invalid staging secret length or PostgreSQL port.")
    return result


class UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(SOCKET)


def check_response(connection, path, status):
    try:
        connection.request("GET", path, headers={"Host": DOMAIN, "X-Forwarded-Proto": "https"})
        response = connection.getresponse()
        body = response.read(256 * 1024)
        if response.status != status:
            raise DeployError(
                f"Preview path {path} returned HTTP {response.status}; expected {status}."
            )
        if path != "/static/core/site.css":
            if "no-store" not in response.getheader(
                "Cache-Control", ""
            ) or "noindex" not in response.getheader("X-Robots-Tag", ""):
                raise DeployError("Private preview headers are missing.")
        if status == 302 and response.getheader("Location") != "/staging/access/":
            raise DeployError("Preview access gate did not protect the page.")
        if path == "/staging/access/" and b'name="password"' not in body:
            raise DeployError("Preview password form is missing.")
    finally:
        connection.close()


class Host:
    def __init__(self, environment, log):
        self.environment, self.log = environment, log
        self.current = BASE / "staging/current"

    def command(self, args, user=None, runtime=False, cwd=None, timeout=180):
        environment = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
        # Preserve configured proxy/CA routing without inheriting unrelated secrets.
        for name in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "no_proxy",
            "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE",
            "PIP_CERT",
        ):
            if name in os.environ:
                environment[name] = os.environ[name]
        if runtime:
            environment.update(self.environment)
            environment["DJANGO_SETTINGS_MODULE"] = "config.settings"
        if user:
            args = ["/usr/sbin/runuser", "-u", user, "--", *args]
        result = subprocess.run(
            args,
            env=environment,
            cwd=cwd or BASE,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        redacted = (result.stdout or "") + (result.stderr or "")
        for name, value in self.environment.items():
            if value and (
                name.endswith("_KEY")
                or any(word in name for word in ("SECRET", "PASSWORD", "TOKEN", "PIN"))
            ):
                redacted = redacted.replace(value, "[REDACTED]")
        with self.log.open("a") as output:
            output.write(redacted)
        if result.returncode and "migrate" in args and "--check" in args:
            raise DeployError(
                "Database migration check failed. Pending migrations need a separate plan; no migrations were applied."
            )
        if result.returncode:
            raise DeployError("A deployment command failed; see the protected server log.")
        return result.stdout.strip()

    def validate(self):
        for directory in (BASE / "releases", STATE):
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise DeployError(
                    "Release/state directories need root ownership and no group/other write."
                )
        if self.command(["systemctl", "show", UNIT, "--property=User", "--value"]) != RUNTIME_USER:
            raise DeployError("Unexpected service user; no change made.")
        if self.command(["systemctl", "show", UNIT, "--property=Group", "--value"]) != "www-data":
            raise DeployError("Unexpected service group; no change made.")
        dropins = self.command(
            ["systemctl", "show", UNIT, "--property=DropInPaths", "--value"]
        ).split()
        if dropins and dropins != [str(DROPIN)]:
            raise DeployError("Unexpected service overrides; review them before deploying.")
        self.snapshot()

    def snapshot(self):
        if not self.current.is_symlink():
            raise DeployError("The current release must be a symlink.")
        target = self.current.resolve(strict=True)
        if not target.is_relative_to(BASE / "releases") or not (target / "manage.py").is_file():
            raise DeployError("Current release is outside the approved release directory.")
        if DROPIN.is_symlink():
            raise DeployError("Unexpected systemd override symlink.")
        if DROPIN.exists() and (DROPIN.stat().st_uid != 0 or DROPIN.stat().st_mode & 0o022):
            raise DeployError("Systemd override is not protected.")
        return {
            "release": str(target),
            "dropin": base64.b64encode(DROPIN.read_bytes()).decode() if DROPIN.exists() else None,
        }

    def schema_checkpoint(self, commit):
        folder = STATE / "schema-checkpoints"
        folder.mkdir(mode=0o700, exist_ok=True)
        info = folder.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise DeployError("Schema-checkpoint directory must be root-owned and private.")
        backup = folder / (commit + "-" + uuid.uuid4().hex + ".dump")
        fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as output:
            result = subprocess.run(
                [
                    "/usr/sbin/runuser",
                    "-u",
                    "postgres",
                    "--",
                    "/usr/bin/pg_dump",
                    "--format=custom",
                    "--dbname=monkeydo_functional",
                ],
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=180,
                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                check=False,
            )
            output.flush()
            os.fsync(output.fileno())
        if result.returncode or backup.stat().st_size == 0:
            raise DeployError("Private database checkpoint failed; schema was not changed.")
        # Validate the custom archive's catalogue before authorizing any schema changes.
        self.command(["/usr/bin/pg_restore", "--list", str(backup)])
        with backup.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        atomic_write(
            backup.with_suffix(".json"),
            json.dumps(
                {
                    "database": DB_NAME,
                    "release_commit": commit,
                    "sha256": digest,
                    "size": backup.stat().st_size,
                    "archive_catalogue_verified": True,
                }
            ).encode(),
        )
        return backup

    def reviewed_batch_two(self, candidate, commit):
        if TARGET != "functional":
            raise DeployError("Reviewed batch-two schema preparation is Functional-only.")
        for name, expected in BATCH_TWO_MIGRATIONS.items():
            path = candidate / "core/migrations" / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise DeployError("Reviewed migration checksum mismatch; no schema update started.")
        migration_host = Host(
            self.environment | {"POSTGRES_USER": "monkeydo-functional-migrate"}, self.log
        )
        arguments = [str(candidate / ".venv/bin/python"), "manage.py", "reviewed_batch_two_schema"]
        migration_host.command(
            arguments, user="monkeydo-functional-migrate", runtime=True, cwd=candidate
        )
        print(
            "Reviewed database preflight passed. Saving a private checkpoint and applying approved updates...",
            flush=True,
        )
        backup = None
        failure = None
        try:
            self.command(["systemctl", "stop", UNIT])
            backup = self.schema_checkpoint(commit)
            report = json.loads(
                migration_host.command(
                    arguments + ["--apply"],
                    user="monkeydo-functional-migrate",
                    runtime=True,
                    cwd=candidate,
                    timeout=600,
                )
            )
        except Exception as error:
            failure = error
        finally:
            # The current code pointer has not changed. Restore its service even if
            # backup/migration fails; completed additive changes are never reversed.
            self.command(["systemctl", "start", UNIT])
            self.healthy()
        if failure:
            raise DeployError(
                "Reviewed database step stopped. The existing release was restarted and verified. Completed schema steps were retained; inspect the protected log before retrying."
            ) from failure
        print("Reviewed database updates verified. Private checkpoint:", backup, flush=True)
        return {"applied": report["applied"], "checkpoint": str(backup)}

    def reviewed_batch_three(self, candidate, commit):
        if TARGET != "functional":
            raise DeployError("Reviewed batch-three schema preparation is Functional-only.")
        for name, expected in BATCH_THREE_MIGRATIONS.items():
            path = candidate / "core/migrations" / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise DeployError("Reviewed migration checksum mismatch; no schema update started.")
        migration_host = Host(
            self.environment | {"POSTGRES_USER": "monkeydo-functional-migrate"}, self.log
        )
        arguments = [
            str(candidate / ".venv/bin/python"),
            "manage.py",
            "reviewed_batch_three_schema",
        ]
        migration_host.command(
            arguments, user="monkeydo-functional-migrate", runtime=True, cwd=candidate
        )
        print(
            "Reviewed database preflight passed. Saving a private checkpoint and applying approved updates...",
            flush=True,
        )
        backup = None
        failure = None
        try:
            self.command(["systemctl", "stop", UNIT])
            backup = self.schema_checkpoint(commit)
            report = json.loads(
                migration_host.command(
                    arguments + ["--apply"],
                    user="monkeydo-functional-migrate",
                    runtime=True,
                    cwd=candidate,
                    timeout=600,
                )
            )
        except Exception as error:
            failure = error
        finally:
            # The current code pointer has not changed. Restore its service even if
            # backup/migration fails; completed additive changes are never reversed.
            self.command(["systemctl", "start", UNIT])
            self.healthy()
        if failure:
            raise DeployError(
                "Reviewed database step stopped. The existing release was restarted and verified. Completed schema steps were retained; inspect the protected log before retrying."
            ) from failure
        print("Reviewed database updates verified. Private checkpoint:", backup, flush=True)
        return {"applied": report["applied"], "checkpoint": str(backup)}

    def booking_resources(self):
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            name, _, value = line.partition(":")
            if name in {"MemTotal", "MemAvailable"}:
                values[name] = int(value.split()[0]) * 1024
        if (
            values.get("MemTotal", 0) < 1536 * 1024 * 1024
            or values.get("MemAvailable", 0) < 512 * 1024 * 1024
            or shutil.disk_usage(BASE).free < 3 * 1024 * 1024 * 1024
        ):
            raise DeployError(
                "Insufficient resources for reviewed booking workers/backup. Review Droplet size and current resize price before any purchase; no schema update started."
            )

    def booking_accounts(self):
        import pwd

        try:
            account = pwd.getpwnam("monkeydo-functional-backup")
        except KeyError:
            self.command(
                [
                    "/usr/sbin/useradd",
                    "--system",
                    "--user-group",
                    "--no-create-home",
                    "--home-dir",
                    "/nonexistent",
                    "--shell",
                    "/usr/sbin/nologin",
                    "monkeydo-functional-backup",
                ]
            )
            account = pwd.getpwnam("monkeydo-functional-backup")
        if not 0 < account.pw_uid < 1000 or account.pw_shell != "/usr/sbin/nologin":
            raise DeployError("Unexpected dedicated backup service identity.")
        sql = """DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='monkeydo-functional-backup') THEN
                CREATE ROLE "monkeydo-functional-backup" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='monkeydo-functional-backup' AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
                OR EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member WHERE r.rolname='monkeydo-functional-backup') THEN
                RAISE EXCEPTION 'Unexpected backup role privileges';
            END IF;
        END $$;
        GRANT CONNECT ON DATABASE monkeydo_functional TO "monkeydo-functional-backup";
        GRANT USAGE ON SCHEMA public TO "monkeydo-functional-backup";
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO "monkeydo-functional-backup";
        GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO "monkeydo-functional-backup";"""
        self.command(
            [
                "/usr/sbin/runuser",
                "-u",
                "postgres",
                "--",
                "/usr/bin/psql",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-d",
                "monkeydo_functional",
                "-c",
                sql,
            ]
        )

    def booking_units_installed(self):
        return [
            Path("/etc/systemd/system") / name.removesuffix(".example")
            for name in BOOKING_UNITS
            if (Path("/etc/systemd/system") / name.removesuffix(".example")).is_file()
        ]

    def stop_booking_workers(self):
        if TARGET == "functional":
            units = self.booking_units_installed()
            if units:
                for suffix in (".timer", ".service"):
                    names = [p.name for p in units if p.suffix == suffix]
                    if names:
                        self.command(["systemctl", "stop"] + names)

    def start_booking_workers(self):
        if TARGET == "functional":
            timers = [p.name for p in self.booking_units_installed() if p.suffix == ".timer"]
            if timers:
                self.command(["systemctl", "start"] + timers)

    def install_booking_runtime(self, candidate):
        for name, digest in BOOKING_UNITS.items():
            source = candidate / "deploy" / name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                raise DeployError(
                    "Reviewed worker unit checksum mismatch. Website remains deployed; worker setup needs review."
                )
        for name in BOOKING_UNITS:
            atomic_write(
                Path("/etc/systemd/system") / name.removesuffix(".example"),
                (candidate / "deploy" / name).read_bytes(),
                0o644,
            )
        self.command(["systemctl", "daemon-reload"])
        timers = [name.removesuffix(".example") for name in BOOKING_UNITS if ".timer." in name]
        self.command(["systemctl", "enable"] + timers)
        self.start_booking_workers()

    def reviewed_booking(self, candidate, commit):
        if TARGET != "functional":
            raise DeployError("Reviewed booking schema preparation is Functional-only.")
        for name, expected in BOOKING_MIGRATIONS.items():
            path = candidate / "core/migrations" / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise DeployError(
                    "Reviewed booking migration checksum mismatch; no schema update started."
                )
        self.booking_resources()
        migration_host = Host(
            self.environment | {"POSTGRES_USER": "monkeydo-functional-migrate"}, self.log
        )
        arguments = [
            str(candidate / ".venv/bin/python"),
            "manage.py",
            "reviewed_booking_completion_schema",
        ]
        migration_host.command(
            arguments, user="monkeydo-functional-migrate", runtime=True, cwd=candidate
        )
        self.booking_accounts()
        backup = None
        failure = None
        print(
            "Reviewed booking database preflight passed. Saving a private checkpoint before the approved upgrade...",
            flush=True,
        )
        try:
            self.stop_booking_workers()
            self.command(["systemctl", "stop", UNIT])
            backup = self.schema_checkpoint(commit)
            report = json.loads(
                migration_host.command(
                    arguments + ["--apply"],
                    user="monkeydo-functional-migrate",
                    runtime=True,
                    cwd=candidate,
                    timeout=600,
                )
            )
        except Exception as error:
            failure = error
        finally:
            self.command(["systemctl", "start", UNIT])
            self.healthy()
            self.start_booking_workers()
        if failure:
            raise DeployError(
                "Reviewed booking update stopped. Existing code was restarted; inspect the protected log. External effects are never reversed by a database rollback."
            ) from failure
        return {"applied": report["applied"], "checkpoint": str(backup)}

    def prepare(
        self,
        archive,
        digest,
        commit,
        reviewed_batch_two=False,
        reviewed_batch_three=False,
        reviewed_booking=False,
    ):
        import pwd

        incoming = BASE / "incoming"
        if archive.parent != incoming or not re.fullmatch(r"[a-f0-9]{32}\.zip", archive.name):
            raise DeployError("Upload the archive through the approved incoming directory.")
        candidate = BASE / "releases" / ("release-" + commit + "-" + uuid.uuid4().hex[:8])
        candidate.mkdir(mode=0o755)
        package = STATE / ("package-" + uuid.uuid4().hex + ".zip")
        try:
            fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as source, package.open("xb") as output:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise DeployError("Upload must be a regular file.")
                os.chmod(package, 0o600)
                size, hashed = 0, hashlib.sha256()
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_ARCHIVE:
                        raise DeployError("Uploaded archive is too large.")
                    hashed.update(chunk)
                    output.write(chunk)
            if hashed.hexdigest() != digest:
                raise DeployError("Archive checksum mismatch; the active release is unchanged.")
            if shutil.disk_usage(BASE).free < MAX_EXPANDED + 1024 * 1024 * 1024:
                raise DeployError("Insufficient free disk space for a separate release.")
            extract_archive(package, candidate, commit)
            validate_bundles(candidate)
        finally:
            package.unlink(missing_ok=True)
        account = pwd.getpwnam("monkeydo-deploy")
        for name in (".venv", "staticfiles"):
            directory = candidate / name
            if directory.exists():
                raise DeployError(
                    "Archive must not contain a virtualenv or collected static directory."
                )
            directory.mkdir(mode=0o755)
            os.chown(directory, account.pw_uid, account.pw_gid)
        python = str(candidate / ".venv/bin/python")
        self.command(
            ["python3", "-m", "venv", str(candidate / ".venv")], user="monkeydo-deploy", timeout=180
        )
        self.command(
            [python, "-m", "pip", "install", "-r", str(candidate / "requirements.txt")],
            user="monkeydo-deploy",
            timeout=600,
        )
        self.command(
            [python, "manage.py", "collectstatic", "--noinput"],
            user="monkeydo-deploy",
            runtime=True,
            cwd=candidate,
        )
        self.command([python, "manage.py", "check"], user=RUNTIME_USER, runtime=True, cwd=candidate)
        schema_update = None
        if reviewed_booking:
            schema_update = self.reviewed_booking(candidate, commit)
        elif reviewed_batch_two:
            schema_update = self.reviewed_batch_two(candidate, commit)
        elif reviewed_batch_three:
            schema_update = self.reviewed_batch_three(candidate, commit)
        # This checks the migration plan only. It never runs a migration.
        self.command(
            [python, "manage.py", "migrate", "--check"],
            user=RUNTIME_USER,
            runtime=True,
            cwd=candidate,
        )
        probe = "import django;django.setup();from django.conf import settings;assert settings.ROOT_URLCONF=='config.design_preview_urls';assert settings.DESIGN_REVIEW_ONLY"
        if TARGET == "functional":
            self.command(
                [python, "manage.py", "functional_staging_preflight"],
                user=RUNTIME_USER,
                runtime=True,
                cwd=candidate,
            )
            if (candidate / "core/management/commands/booking_stage_preflight.py").is_file():
                self.command(
                    [python, "manage.py", "booking_stage_preflight"],
                    user=RUNTIME_USER,
                    runtime=True,
                    cwd=candidate,
                )
        else:
            self.command([python, "-c", probe], user=RUNTIME_USER, runtime=True, cwd=candidate)
        metadata = {
            "commit": commit,
            "archive_sha256": digest,
            "prepared_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "migrations_applied": bool(schema_update and schema_update["applied"]),
            "reviewed_schema_update": schema_update,
        }
        atomic_write(
            candidate / ".monkeydo-release.json", json.dumps(metadata, indent=2).encode(), 0o644
        )
        return candidate

    def ensure_visit_credit_compatible(self, target):
        marker = target / "deploy/visit-credit-v2.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "bd2c0d93924523d4e6a482ab4d045327c27c360b77451631d04636d108bfbb72"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='core_customercreditapplication' AND column_name='booking_checkout_id')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify visit-credit compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_customercreditapplication WHERE booking_checkout_id IS NOT NULL)"
            ]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage accepted visit credit. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_membership_split_compatible(self, target):
        marker = target / "deploy/membership-first-split-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "59c17332da9384dc05f07934a083f9ad768f161cdafdb65028d68ce168cf818b"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql + ["SELECT to_regclass('public.core_membershippurchase') IS NOT NULL"]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify membership-split compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_membershippurchase p JOIN core_membershipdraft m ON m.id=p.membership_id WHERE m.expected_method='split')"
            ]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage accepted split membership payments. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_membership_bank_compatible(self, target):
        marker = target / "deploy/membership-booking-zelle-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "e919a1144cae7919f679ac31f76f9e1d5c2d00fdd938361f7a4e3b069a428a19"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql + ["SELECT to_regclass('public.core_membershipbankallocation') IS NOT NULL"]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify membership bank-allocation compatibility; no release switch allowed."
            )
        used = self.command(psql + ["SELECT EXISTS (SELECT 1 FROM core_membershipbankallocation)"])
        if used != "f":
            raise DeployError(
                "This older release cannot manage accepted membership bank allocations. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_split_arrival_compatible(self, target):
        marker = target / "deploy/split-membership-arrival-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "291070a4283ec7f21d83209baa81b679e96330d76be13f70892f9ab5d929fe4f"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql + ["SELECT to_regclass('public.core_membershiparrivalintent') IS NOT NULL"]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify split-arrival compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_membershiparrivalintent i JOIN core_membershipdraft m ON m.id=i.purchase_id WHERE m.expected_method='split')"
            ]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage accepted split membership arrivals. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_pending_visit_compatible(self, target):
        marker = target / "deploy/pending-visit-receipts-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "98ac8c638022d629404dece199f6fa0044cf42e6cbca5a1ebc8216a8988ac7e9"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql + ["SELECT to_regclass('public.core_membershiparrivalreceipt') IS NOT NULL"]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify pending-visit receipt compatibility; no release switch allowed."
            )
        used = self.command(psql + ["SELECT EXISTS (SELECT 1 FROM core_membershiparrivalreceipt)"])
        if used != "f":
            raise DeployError(
                "This older release cannot manage accepted pending visit receipts. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_pending_return_compatible(self, target):
        marker = target / "deploy/pending-visit-returns-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "f9cfe86e376275139e387a265b01dc47518bad45a585a8b230b6ed0f4664e99c"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql + ["SELECT to_regclass('public.core_membershiparrivalreceiptreturn') IS NOT NULL"]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify pending-visit return compatibility; no release switch allowed."
            )
        used = self.command(
            psql + ["SELECT EXISTS (SELECT 1 FROM core_membershiparrivalreceiptreturn)"]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage recorded pending visit returns. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_pending_stop_compatible(self, target):
        marker = target / "deploy/pending-arrival-stop-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "5cffd9bbf098fce1e189b343bfbf834e253fc23f2a490661fddfd2bc2ae8c7e8"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql + ["SELECT to_regclass('public.core_membershiparrivalclosure') IS NOT NULL"]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify pending-arrival stop compatibility; no release switch allowed."
            )
        used = self.command(psql + ["SELECT EXISTS (SELECT 1 FROM core_membershiparrivalclosure)"])
        if used != "f":
            raise DeployError(
                "This older release cannot manage recorded stopped arrivals. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_cancelled_member_stop_compatible(self, target):
        marker = target / "deploy/pending-cancelled-membership-stop-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "0eef0d1e00f8a58d9682048eed7866bbae5d61f0082b01ebfb7de894eb462a9e"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='core_membershiparrivalclosure' AND column_name='cancellation_id')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify cancelled-membership arrival-stop compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_membershiparrivalclosure WHERE cancellation_id IS NOT NULL)"
            ]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage cancellation-linked stopped arrivals. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_paid_visit_purchase_compatible(self, target):
        marker = target / "deploy/paid-visit-purchase-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "0e523ae9dc9c0cf0edba4a1b67b77d1ae2a171176f20c51d3908a00fea6cfa9f"
        ):
            return self.ensure_paid_visit_received_split_compatible(target)
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershippurchase')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify paid-visit purchase compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_membershippurchase p JOIN core_membershipdraft d ON d.id=p.membership_id WHERE d.snapshot ? 'paid_visit_purchase')"
            ]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage paid-visit membership purchases. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_paid_visit_received_split_compatible(self, target):
        marker = target / "deploy/paid-visit-received-split-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "786ec7a2763dc4adaca49da62b7d47a21574468cd548c205fe9d0a7ce0783fa8"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershippurchase')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify paid-visit received-split compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_membershippurchase p JOIN core_membershipdraft d ON d.id=p.membership_id WHERE d.expected_method='split' AND d.snapshot ? 'paid_visit_purchase')"
            ]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage paid-visit received-split membership purchases. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_paid_visit_card_compatible(self, target):
        marker = target / "deploy/paid-visit-card-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "b2c1d5b915a81f1e89dd83d4619a2599a147b31347991e4e0846bb2e01645e54"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershippaidvisitintent')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify paid-visit card compatibility; no release switch allowed."
            )
        used = self.command(psql + ["SELECT EXISTS (SELECT 1 FROM core_membershippaidvisitintent)"])
        if used != "f":
            raise DeployError(
                "This older release cannot manage paid-visit card reservations. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_paid_visit_card_recovery_compatible(self, target):
        marker = target / "deploy/paid-visit-card-recovery-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "c9923fde85107ccf2c489440fc27d855df8a1f59bc8a692c8abdeb19411f99c9"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershippaidvisitrecovery')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify paid-visit card recovery compatibility; no release switch allowed."
            )
        used = self.command(
            psql + ["SELECT EXISTS (SELECT 1 FROM core_membershippaidvisitrecovery)"]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage paid-visit card recoveries. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_paid_visit_cancelled_release_compatible(self, target):
        marker = target / "deploy/paid-visit-cancelled-release-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "e18281acb6210cb5f8eadcbc12c8ad4d48f23808d83b36ebf95f18f0e8db4440"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershippaidvisitcancellation')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify cancelled paid-visit release compatibility; no release switch allowed."
            )
        used = self.command(
            psql + ["SELECT EXISTS (SELECT 1 FROM core_membershippaidvisitcancellation)"]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage cancelled paid-visit releases. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_paid_visit_recovery_storage_compatible(self, target):
        marker = target / "deploy/paid-visit-recovery-card-storage-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "d73f5ddfa7faa2636be8795ffb1b451175e4c1614903e9346f8927a2b84f0ae7"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershippaidvisitcardstorage')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify paid-visit recovery card storage compatibility; no release switch allowed."
            )
        used = self.command(
            psql + ["SELECT EXISTS (SELECT 1 FROM core_membershippaidvisitcardstorage)"]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage paid-visit recovery card storages. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_paid_visit_manual_compatible(self, target):
        marker = target / "deploy/paid-visit-manual-payment-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "ea86d3725ea53d98a951fb49af12550a5d70d997c9b45649f37cb0048ffade3e"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershippaidvisitmanualpayment')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify paid-visit received replacement payment compatibility; no release switch allowed."
            )
        used = self.command(
            psql + ["SELECT EXISTS (SELECT 1 FROM core_membershippaidvisitmanualpayment)"]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage paid-visit received replacement payments. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_combined_renewals_compatible(self, target):
        marker = target / "deploy/combined-renewals-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "e6436b78adfd55e0632b3b2a9b72f0aa7dbc6a77617ce05e1348bbb5ae86ce01"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershiprenewalbatch')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify combined renewal checkout compatibility; no release switch allowed."
            )
        used = self.command(psql + ["SELECT EXISTS (SELECT 1 FROM core_membershiprenewalbatch)"])
        if used != "f":
            raise DeployError(
                "This older release cannot manage combined renewal checkouts. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_credit_renewals_compatible(self, target):
        marker = target / "deploy/credit-renewals-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "b59b87c67e494e27c4060d26c162cebe421366601bfb23addd3823b3f3520439"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershipcreditrenewalbatch')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify credit-funded renewal checkout compatibility; no release switch allowed."
            )
        used = self.command(
            psql + ["SELECT EXISTS (SELECT 1 FROM core_membershipcreditrenewalbatch)"]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage credit-funded renewal checkouts. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_renewal_bank_compatible(self, target):
        marker = target / "deploy/renewal-bank-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "2afbce221e71f3f88887c34dc1c009b7a72433efefb27f9d3a5f19345adc4808"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershiprenewalbatchbank')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify combined renewal bank receipt compatibility; no release switch allowed."
            )
        used = self.command(
            psql + ["SELECT EXISTS (SELECT 1 FROM core_membershiprenewalbatchbank)"]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage combined renewal bank receipts. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_membership_calendar_compatible(self, target):
        marker = target / "deploy/membership-calendar-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "cca488a5adc22035532565aeaddee2a5890f63f3f02528ce9cb70990bf0de304"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershipcalendarcorrection')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify membership calendar correction compatibility; no release switch allowed."
            )
        used = self.command(
            psql + ["SELECT EXISTS (SELECT 1 FROM core_membershipcalendarcorrection)"]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage membership calendar corrections. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_paid_visit_split_compatible(self, target):
        marker = target / "deploy/paid-visit-split-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "885eff0cbc9e4a33abef71f2b0c9a6e30cfaefcd1f3d38277f69ff2f6f7c8da1"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershippaidvisitsplit')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify paid-visit split-remainder compatibility; no release switch allowed."
            )
        used = self.command(psql + ["SELECT EXISTS (SELECT 1 FROM core_membershippaidvisitsplit)"])
        if used != "f":
            raise DeployError(
                "This older release cannot manage paid-visit split-remainders. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_unused_owner_dates_compatible(self, target):
        marker = target / "deploy/unused-owner-dates-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest()
            == "12ba8de21f0f09adbc0d6aa5930306f14ddb7d8a19eeda482a24587c01254b74"
        ):
            return True
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='core_membershipcalendarcorrection')"
            ]
        )
        if present == "f":
            return True
        if present != "t":
            raise DeployError(
                "Cannot verify unused membership owner date-exception compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_membershipcalendarcorrection WHERE facts->'owner_date_exception'='true'::jsonb)"
            ]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage unused membership owner date-exceptions. Keep compatible code or fix forward; no database rollback was performed."
            )
        return True

    def ensure_booking_compatible(self, target):
        marker = target / "deploy/booking-completion-v1.capability"
        if (
            marker.is_file()
            and hashlib.sha256(marker.read_bytes()).hexdigest() == BOOKING_CAPABILITY
        ):
            self.ensure_visit_credit_compatible(target)
            self.ensure_membership_split_compatible(target)
            self.ensure_membership_bank_compatible(target)
            self.ensure_split_arrival_compatible(target)
            self.ensure_pending_visit_compatible(target)
            self.ensure_pending_return_compatible(target)
            self.ensure_pending_stop_compatible(target)
            self.ensure_cancelled_member_stop_compatible(target)
            compatible = self.ensure_paid_visit_purchase_compatible(target)
            self.ensure_paid_visit_card_compatible(target)
            self.ensure_paid_visit_card_recovery_compatible(target)
            self.ensure_paid_visit_cancelled_release_compatible(target)
            self.ensure_paid_visit_recovery_storage_compatible(target)
            self.ensure_paid_visit_manual_compatible(target)
            self.ensure_combined_renewals_compatible(target)
            self.ensure_renewal_bank_compatible(target)
            self.ensure_membership_calendar_compatible(target)
            self.ensure_paid_visit_split_compatible(target)
            self.ensure_unused_owner_dates_compatible(target)
            self.ensure_credit_renewals_compatible(target)
            return compatible
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql + ["SELECT to_regclass('public.core_paymentoperation') IS NOT NULL"]
        )
        if present == "f":
            return False
        if present != "t":
            raise DeployError(
                "Cannot verify booking workflow compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_booking WHERE workflow='integrated_v1') OR EXISTS (SELECT 1 FROM core_paymentsetup) OR EXISTS (SELECT 1 FROM core_financialsale) OR EXISTS (SELECT 1 FROM core_waiversignature) OR EXISTS (SELECT 1 FROM core_messagedelivery) OR EXISTS (SELECT 1 FROM core_backuprun)"
            ]
        )
        if used != "f":
            raise DeployError(
                "This older release cannot manage existing integrated bookings, payments, waivers, messages or backups. Keep compatible code or fix forward; no database rollback can reverse external effects."
            )
        return False

    def ensure_compatible_release(self, target):
        if TARGET != "functional":
            return
        if self.ensure_booking_compatible(target):
            return
        migration = target / "core/migrations/0026_owner_feedback_batch_three.py"
        if (
            migration.is_file()
            and hashlib.sha256(migration.read_bytes()).hexdigest()
            == BATCH_THREE_MIGRATIONS[migration.name]
        ):
            return
        psql = [
            "/usr/sbin/runuser",
            "-u",
            "postgres",
            "--",
            "/usr/bin/psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-d",
            "monkeydo_functional",
            "-c",
        ]
        present = self.command(
            psql + ["SELECT to_regclass('public.core_sessionreservationblock') IS NOT NULL"]
        )
        if present == "f":
            return
        if present != "t":
            raise DeployError(
                "Could not verify release/schema compatibility; no release switch allowed."
            )
        used = self.command(
            psql
            + [
                "SELECT EXISTS (SELECT 1 FROM core_calendardate WHERE backend_only) OR EXISTS (SELECT 1 FROM core_session WHERE custom_blocking) OR EXISTS (SELECT 1 FROM core_sessionreservationblock WHERE active)"
            ]
        )
        if used != "f":
            raise DeployError(
                "Older code cannot enforce the current private dates/custom sessions/reservation blocks. Keep a compatible release; no database rollback was performed."
            )

    def switch(self, snapshot):
        target = Path(snapshot["release"])
        if not target.is_relative_to(BASE / "releases") or not (target / "manage.py").is_file():
            raise DeployError("Saved release target is unavailable; manual recovery required.")
        self.stop_booking_workers()
        self.command(["systemctl", "stop", UNIT])
        try:
            self.ensure_compatible_release(target)
        except BaseException:
            # Keep the original pointer and restart it even on a refused rollback.
            self.command(["systemctl", "start", UNIT])
            self.start_booking_workers()
            raise
        temporary = self.current.parent / (".current-" + uuid.uuid4().hex)
        temporary.symlink_to(target)
        os.replace(temporary, self.current)
        if snapshot["dropin"] is None:
            DROPIN.unlink(missing_ok=True)
        else:
            atomic_write(DROPIN, base64.b64decode(snapshot["dropin"], validate=True), 0o644)
        self.command(["systemctl", "daemon-reload"])
        self.command(["systemctl", "start", UNIT])

    def candidate_snapshot(self, path):
        text = f"[Service]\nEnvironmentFile=\nEnvironmentFile={ENV_FILE}\nWorkingDirectory={path}\nExecStart=\nExecStart={path}/.venv/bin/gunicorn config.wsgi:application --workers {1 if TARGET == 'functional' else 2} --umask 7 --bind unix:{SOCKET} --timeout 60\nEnvironment=APP_ENV=staging\nEnvironment=MONKEYDO_DESIGN_ONLY={0 if TARGET == 'functional' else 1}\n"
        if TARGET == "functional":
            text += "Environment=MONKEYDO_CUSTOMER_TEST_BOOKING=1\n"
        return {"release": str(path), "dropin": base64.b64encode(text.encode()).decode()}

    def healthy(self):
        deadline = time.monotonic() + 30
        while True:
            try:
                for path, status in (*HEALTH_PATHS, ("/static/core/site.css", 200)):
                    check_response(UnixConnection("localhost", timeout=5), path, status)
                for path, status in HEALTH_PATHS:
                    check_response(
                        http.client.HTTPSConnection(
                            DOMAIN, timeout=10, context=ssl.create_default_context()
                        ),
                        path,
                        status,
                    )
                return
            except (OSError, http.client.HTTPException, DeployError) as error:
                with self.log.open("a") as output:
                    output.write(f"Health check: {type(error).__name__}: {error}\n")
                if time.monotonic() >= deadline:
                    raise DeployError(
                        "Local/private-gate or public HTTPS verification failed."
                    ) from None
                time.sleep(1)


class Controller:
    def __init__(self, host, state_path):
        self.host, self.path = host, state_path
        self.state = (
            json.loads(state_path.read_text())
            if state_path.exists()
            else {"version": 1, "previous": None, "pending": None}
        )
        if self.state.get("version") != 1:
            raise DeployError("Unsupported deployment state version.")

    def save(self):
        atomic_write(self.path, json.dumps(self.state, indent=2).encode())

    def recover(self):
        if self.state.get("pending"):
            print("Recovering the previous release from an interrupted deployment...", flush=True)
            self.host.switch(self.state["pending"])
            self.host.healthy()
            if hasattr(self.host, "start_booking_workers"):
                self.host.start_booking_workers()
            self.state["pending"] = None
            self.save()
            raise DeployError("Interrupted deployment recovered. Run the requested command again.")

    def activate(self, target):
        previous = self.host.snapshot()
        before_state = dict(self.state)
        self.state["pending"] = previous
        self.save()
        try:
            self.host.switch(target)
            self.host.healthy()
            if hasattr(self.host, "start_booking_workers"):
                self.host.start_booking_workers()
            self.state.update(previous=previous, pending=None, active=target)
            self.save()
        except BaseException as failure:
            try:
                self.host.switch(previous)
                self.host.healthy()
                if hasattr(self.host, "start_booking_workers"):
                    self.host.start_booking_workers()
            except BaseException:
                self.state["pending"] = previous
                try:
                    self.save()
                except BaseException:
                    pass
                raise DeployError(
                    "Recovery could not be verified. Inspect the service and protected logs before another deployment."
                ) from failure
            self.state = before_state | {"pending": None}
            try:
                self.save()
            except BaseException:
                raise DeployError(
                    "Previous release restored, but deployment-state persistence failed. Inspect the protected logs before another update."
                ) from failure
            raise DeployError(
                "Update failed. The previous release was restored and verified."
            ) from failure

    def deploy(
        self,
        archive,
        digest,
        commit,
        reviewed_batch_two=False,
        reviewed_batch_three=False,
        reviewed_booking=False,
    ):
        if sum((reviewed_batch_two, reviewed_batch_three, reviewed_booking)) > 1:
            raise DeployError("Choose only one reviewed schema batch.")
        self.recover()
        self.host.healthy()
        print("Preparing a separate release; the existing site stays running...", flush=True)
        if reviewed_batch_two or reviewed_batch_three or reviewed_booking:
            # Persist recovery before the optional schema step can stop the service.
            # A killed process is then handled by the existing recover-on-next-run path.
            self.state["pending"] = self.host.snapshot()
            self.save()
            try:
                options = (
                    {"reviewed_booking": True}
                    if reviewed_booking
                    else {"reviewed_batch_three": True}
                    if reviewed_batch_three
                    else {"reviewed_batch_two": True}
                )
                candidate = self.host.prepare(archive, digest, commit, **options)
            except BaseException:
                try:
                    self.host.healthy()
                except BaseException:
                    self.host.switch(self.state["pending"])
                    self.host.healthy()
                self.state["pending"] = None
                self.save()
                raise
            self.state["pending"] = None
            self.save()
        else:
            candidate = self.host.prepare(archive, digest, commit)
        print("Checks passed. Switching the release and verifying HTTPS...", flush=True)
        self.activate(self.host.candidate_snapshot(candidate))
        if reviewed_booking:
            self.host.install_booking_runtime(candidate)
        print("Deployment verified. Previous code and Python environment are retained.")

    def rollback(self):
        self.recover()
        if not self.state.get("previous"):
            raise DeployError("No previous managed deployment is available yet.")
        self.activate(self.state["previous"])
        print("Previous release restored and verified. Database data was unchanged.")


@contextlib.contextmanager
def deployment_lock(path):
    with path.open("a") as lock:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DeployError("Another deployment is running; no change made.") from None
        yield


def interrupted(signum, frame):
    raise DeployError("Deployment interrupted.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("design", "functional"), default="design")
    sub = parser.add_subparsers(dest="operation", required=True)
    deploy = sub.add_parser("deploy")
    deploy.add_argument("--archive", type=Path, required=True)
    deploy.add_argument("--sha256", required=True)
    deploy.add_argument("--commit", required=True)
    reviewed = deploy.add_mutually_exclusive_group()
    reviewed.add_argument("--apply-reviewed-batch-two", action="store_true")
    reviewed.add_argument("--apply-reviewed-batch-three", action="store_true")
    reviewed.add_argument("--apply-reviewed-booking", action="store_true")
    sub.add_parser("rollback")
    sub.add_parser("status")
    args = parser.parse_args()
    select_target(args.target)
    if (
        getattr(args, "apply_reviewed_batch_two", False)
        or getattr(args, "apply_reviewed_batch_three", False)
        or getattr(args, "apply_reviewed_booking", False)
    ) and args.target != "functional":
        parser.error("Reviewed schema updates require the Functional target.")
    if os.geteuid() != 0:
        parser.error("Run through the authorized root SSH account.")
    if args.operation == "deploy" and (
        not re.fullmatch("[a-f0-9]{40}", args.commit)
        or not re.fullmatch("[a-f0-9]{64}", args.sha256)
    ):
        parser.error("Use a full commit and SHA-256 digest.")
    os.umask(0o022)
    STATE.mkdir(mode=0o700, exist_ok=True)
    state_info = STATE.lstat()
    if not stat.S_ISDIR(state_info.st_mode) or state_info.st_uid != 0 or state_info.st_mode & 0o077:
        parser.error("Deployment state directory must be root-owned and private.")
    log = STATE / (
        "deploy-"
        + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        + "-"
        + uuid.uuid4().hex[:8]
        + ".log"
    )
    atomic_write(log, b"Private staging deployment log\n")
    for name in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(name, interrupted)
    try:
        with deployment_lock(STATE / "deploy.lock"):
            host = Host(read_environment(ENV_FILE), log)
            host.validate()
            controller = Controller(host, STATE / "state.json")
            if args.operation == "status":
                print("Staging target:", TARGET, DOMAIN)
                print("Current release:", host.snapshot()["release"])
                print("Interrupted recovery pending:", bool(controller.state.get("pending")))
                host.healthy()
                print("Private gate and HTTPS checks passed.")
            elif args.operation == "rollback":
                controller.rollback()
            else:
                controller.deploy(
                    args.archive,
                    args.sha256,
                    args.commit,
                    args.apply_reviewed_batch_two,
                    args.apply_reviewed_batch_three,
                    args.apply_reviewed_booking,
                )
    except Exception as error:
        print("Deployment stopped:", str(error), file=sys.stderr)
        print("Protected log:", log, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
