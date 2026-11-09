#!/usr/bin/python3 -I
"""Root-owned deployment controller for the private design review only.

No database migrations, password changes, DNS changes or destructive cleanup.
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
    DOMAIN = "testing.monkeydoplay.com" if functional else "staging.monkeydoplay.com"
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
            if any(word in name for word in ("SECRET", "PASSWORD", "TOKEN", "PIN", "KEY")):
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

    def prepare(self, archive, digest, commit):
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
        else:
            self.command([python, "-c", probe], user=RUNTIME_USER, runtime=True, cwd=candidate)
        metadata = {
            "commit": commit,
            "archive_sha256": digest,
            "prepared_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "migrations_applied": False,
        }
        atomic_write(
            candidate / ".monkeydo-release.json", json.dumps(metadata, indent=2).encode(), 0o644
        )
        return candidate

    def switch(self, snapshot):
        target = Path(snapshot["release"])
        if not target.is_relative_to(BASE / "releases") or not (target / "manage.py").is_file():
            raise DeployError("Saved release target is unavailable; manual recovery required.")
        self.command(["systemctl", "stop", UNIT])
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
            self.state.update(previous=previous, pending=None, active=target)
            self.save()
        except BaseException as failure:
            try:
                self.host.switch(previous)
                self.host.healthy()
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

    def deploy(self, archive, digest, commit):
        self.recover()
        self.host.healthy()
        print("Preparing a separate release; the existing site stays running...", flush=True)
        candidate = self.host.prepare(archive, digest, commit)
        print("Checks passed. Switching the release and verifying HTTPS...", flush=True)
        self.activate(self.host.candidate_snapshot(candidate))
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
    sub.add_parser("rollback")
    sub.add_parser("status")
    args = parser.parse_args()
    select_target(args.target)
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
                controller.deploy(args.archive, args.sha256, args.commit)
    except Exception as error:
        print("Deployment stopped:", str(error), file=sys.stderr)
        print("Protected log:", log, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
