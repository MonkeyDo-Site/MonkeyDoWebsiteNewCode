import base64
import hashlib
import http.server
import io
import json
import os
import socketserver
import stat
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from deploy import monkeydo_deploy as deploy

COMMIT = "a" * 40
PREFIX = "MonkeyDoWebsiteNewCode-" + COMMIT


def package(entries=None):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        defaults = {
            "manage.py": "# approved fixture",
            "requirements.txt": "",
            "config/settings.py": "",
            "core/design_preview.py": "",
            "docs/design-review/v1/manifest.json": json.dumps(
                {"pages": [{"id": "01-home", "file": "01-home.html"}]}
            ),
            "docs/design-review/v1/index.html": "<p>Read-only index</p>",
            "docs/design-review/v1/01-home.html": "<button disabled>Read only</button>",
            "docs/design-review/v1/01-home-desktop.jpg": "fixture",
            "docs/design-review/v1/01-home-phone.jpg": "fixture",
        }
        for name, value in (entries if entries is not None else defaults).items():
            archive.writestr(PREFIX + "/" + name, value)
    return data.getvalue()


class ArchiveTests(unittest.TestCase):
    def test_extracts_only_expected_commit_and_preserves_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.zip"
            source.write_bytes(package())
            target = root / "release"
            target.mkdir()
            deploy.extract_archive(source, target, COMMIT)
            self.assertTrue((target / "manage.py").is_file())
            with zipfile.ZipFile(source) as archive, self.assertRaises(deploy.DeployError):
                deploy.safe_archive(archive, "b" * 40)

    def test_rejects_traversal_symlink_and_duplicate_paths(self):
        for name in ["../escape", "/absolute", "foo\\bar", "foo\nbar"]:
            with (
                self.subTest(name=name),
                zipfile.ZipFile(io.BytesIO(package({name: "x"}))) as archive,
                self.assertRaises(deploy.DeployError),
            ):
                deploy.safe_archive(archive, COMMIT)
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            member = zipfile.ZipInfo(PREFIX + "/link")
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(member, "/etc/passwd")
        with (
            zipfile.ZipFile(io.BytesIO(data.getvalue())) as archive,
            self.assertRaises(deploy.DeployError),
        ):
            deploy.safe_archive(archive, COMMIT)

    def test_rejects_oversized_expansion_and_incomplete_package(self):
        with (
            zipfile.ZipFile(io.BytesIO(package())) as archive,
            patch.object(deploy, "MAX_EXPANDED", 1),
            self.assertRaises(deploy.DeployError),
        ):
            deploy.safe_archive(archive, COMMIT)
        with (
            zipfile.ZipFile(io.BytesIO(package({"manage.py": ""}))) as archive,
            self.assertRaises(deploy.DeployError),
        ):
            deploy.safe_archive(archive, COMMIT)

    def test_upload_checksum_failure_never_runs_candidate_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "releases").mkdir()
            (root / "incoming").mkdir()
            state = root / "state"
            state.mkdir()
            archive = root / "incoming" / ("0" * 32 + ".zip")
            archive.write_bytes(package())
            host = deploy.Host({}, root / "log")
            with (
                patch.object(deploy, "BASE", root),
                patch.object(deploy, "STATE", state),
                patch.object(host, "command") as command,
                self.assertRaises(deploy.DeployError),
            ):
                host.prepare(archive, "0" * 64, COMMIT)
            command.assert_not_called()
            self.assertFalse(list(state.glob("package-*")))

    def test_rejects_symlink_upload_before_candidate_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "releases").mkdir()
            (root / "incoming").mkdir()
            archive = root / "incoming" / ("0" * 32 + ".zip")
            archive.symlink_to(root / "secret")
            (root / "secret").write_text("private")
            host = deploy.Host({}, root / "log")
            with (
                patch.object(deploy, "BASE", root),
                patch.object(deploy, "STATE", root),
                patch.object(host, "command") as command,
                self.assertRaises(OSError),
            ):
                host.prepare(archive, hashlib.sha256(b"private").hexdigest(), COMMIT)
            command.assert_not_called()


class FakeHost:
    def __init__(self):
        self.current = {"release": "/old", "dropin": None}
        self.calls = []
        self.fail_build = False
        self.fail_new = False
        self.fail_restore = False
        self.fail_after_switch = False

    def snapshot(self):
        return dict(self.current)

    def prepare(self, *args):
        self.calls.append("prepare")
        if self.fail_build:
            raise deploy.DeployError("Pending migration or build failure")
        return Path("/new")

    def candidate_snapshot(self, path):
        return {"release": str(path), "dropin": base64.b64encode(b"new environment").decode()}

    def switch(self, target):
        self.calls.append("switch:" + target["release"])
        self.current = dict(target)
        if target["release"] == "/new" and self.fail_after_switch:
            raise deploy.DeployError("Restart failed after pointer switch")
        if target["release"] == "/old" and self.fail_restore:
            raise deploy.DeployError("Restore restart failed")

    def healthy(self):
        self.calls.append("health:" + self.current["release"])
        if self.current["release"] == "/new" and self.fail_new:
            raise deploy.DeployError("Bad gate or HTTPS")


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.host = FakeHost()
        self.controller = deploy.Controller(self.host, self.path)

    def test_success_persists_previous_code_and_python_environment(self):
        self.controller.deploy(Path("source"), "digest", COMMIT)
        state = json.loads(self.path.read_text())
        self.assertEqual(state["previous"], {"release": "/old", "dropin": None})
        self.assertEqual(state["active"]["release"], "/new")
        self.assertIsNone(state["pending"])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_build_or_migration_failure_never_switches_or_stops_site(self):
        self.host.fail_build = True
        with self.assertRaises(deploy.DeployError):
            self.controller.deploy(Path("source"), "digest", COMMIT)
        self.assertEqual(self.host.current["release"], "/old")
        self.assertFalse(any(call.startswith("switch:") for call in self.host.calls))

    def test_failed_health_restores_old_release_and_environment(self):
        self.host.fail_new = True
        with self.assertRaisesRegex(deploy.DeployError, "restored and verified"):
            self.controller.deploy(Path("source"), "digest", COMMIT)
        self.assertEqual(self.host.current, {"release": "/old", "dropin": None})
        self.assertIsNone(json.loads(self.path.read_text())["pending"])

    def test_failure_after_pointer_switch_still_restores_old_release(self):
        self.host.fail_after_switch = True
        with self.assertRaises(deploy.DeployError):
            self.controller.deploy(Path("source"), "digest", COMMIT)
        self.assertEqual(self.host.current["release"], "/old")

    def test_failed_recovery_retains_checkpoint_for_next_command(self):
        self.host.fail_new = True
        self.host.fail_restore = True
        with self.assertRaisesRegex(deploy.DeployError, "could not be verified"):
            self.controller.deploy(Path("source"), "digest", COMMIT)
        self.assertEqual(json.loads(self.path.read_text())["pending"]["release"], "/old")

    def test_interrupted_switch_recovers_before_any_new_build(self):
        deploy.atomic_write(
            self.path,
            json.dumps(
                {"version": 1, "pending": {"release": "/old", "dropin": None}, "previous": None}
            ).encode(),
        )
        self.host.current = {"release": "/new", "dropin": "new"}
        controller = deploy.Controller(self.host, self.path)
        with self.assertRaisesRegex(deploy.DeployError, "recovered"):
            controller.deploy(Path("source"), "digest", COMMIT)
        self.assertNotIn("prepare", self.host.calls)
        self.assertEqual(self.host.current["release"], "/old")
        self.assertIsNone(json.loads(self.path.read_text())["pending"])

    def test_manual_rollback_can_be_undone_and_preserves_database(self):
        self.controller.deploy(Path("source"), "digest", COMMIT)
        self.controller.rollback()
        self.assertEqual(self.host.current["release"], "/old")
        self.controller.rollback()
        self.assertEqual(self.host.current["release"], "/new")
        self.assertFalse(any("migrate" in call for call in self.host.calls))

    def test_second_deployment_lock_is_rejected(self):
        lock = self.path.parent / "lock"
        with (
            deploy.deployment_lock(lock),
            self.assertRaises(deploy.DeployError),
            deploy.deployment_lock(lock),
        ):
            self.fail("Second lock should not be acquired")

    def test_no_previous_release_does_not_change_site(self):
        with self.assertRaises(deploy.DeployError):
            self.controller.rollback()
        self.assertEqual(self.host.calls, [])


class ConfigurationTests(unittest.TestCase):
    def test_protected_config_accepts_only_the_design_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "environment"
            values = {
                "APP_ENV": "staging",
                "MONKEYDO_DESIGN_ONLY": "1",
                "POSTGRES_DB": "monkeydo_staging",
                "POSTGRES_USER": "monkeydo",
                "POSTGRES_HOST": "/var/run/postgresql",
                "DJANGO_ALLOWED_HOSTS": deploy.DOMAIN,
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://" + deploy.DOMAIN,
                "DJANGO_TRUST_PROXY": "1",
                "DJANGO_SECRET_KEY": "x" * 64,
            }

            def write():
                path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
                path.chmod(0o600)

            write()
            self.assertEqual(deploy.read_environment(path, os.getuid())["APP_ENV"], "staging")
            values["APP_ENV"] = "production"
            write()
            with self.assertRaises(deploy.DeployError):
                deploy.read_environment(path, os.getuid())
            values["APP_ENV"] = "staging"
            values["DJANGO_SECRET_KEY"] = "$(untrusted)"
            write()
            with self.assertRaises(deploy.DeployError):
                deploy.read_environment(path, os.getuid())
            write()
            path.chmod(0o644)
            with self.assertRaises(deploy.DeployError):
                deploy.read_environment(path, os.getuid())

    def test_logs_redact_secret_and_do_not_print_it(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = "artificial-secret-value"
            log = Path(directory) / "log"
            host = deploy.Host({"DJANGO_SECRET_KEY": secret}, log)
            result = __import__("subprocess").CompletedProcess(
                [], 1, "trace " + secret, "error " + secret
            )
            with (
                patch("deploy.monkeydo_deploy.subprocess.run", return_value=result),
                self.assertRaises(deploy.DeployError),
            ):
                host.command(["false"], cwd=Path(directory))
            self.assertNotIn(secret, log.read_text())
            self.assertIn("[REDACTED]", log.read_text())


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/staging/access/" else 302)
        self.send_header("Location", "/staging/access/")
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()
        self.wfile.write(b'<input name="password">')


class UnixHealthTests(unittest.TestCase):
    def test_actual_unix_http_checks_gate_without_submitting_password(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "socket")
            server = socketserver.UnixStreamServer(path, Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(deploy, "SOCKET", path):
                    deploy.check_response(
                        deploy.UnixConnection("localhost", timeout=2), "/staging/access/", 200
                    )
                    deploy.check_response(deploy.UnixConnection("localhost", timeout=2), "/", 302)
                    with self.assertRaises(deploy.DeployError):
                        deploy.check_response(
                            deploy.UnixConnection("localhost", timeout=2), "/", 200
                        )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


class FilesystemActivationTests(unittest.TestCase):
    def test_switch_and_restore_preserve_legacy_venv_and_exact_service_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "releases/old").mkdir(parents=True)
            (root / "releases/old/manage.py").write_text("old")
            (root / "releases/new").mkdir()
            (root / "releases/new/manage.py").write_text("new")
            (root / "staging/venv").mkdir(parents=True)
            (root / "staging/venv/legacy").write_text("keep original Python environment")
            (root / "staging/current").symlink_to(root / "releases/old")
            dropin = root / "systemd/release.conf"
            with patch.object(deploy, "BASE", root), patch.object(deploy, "DROPIN", dropin):
                host = deploy.Host({}, root / "log")
                old = host.snapshot()
                commands = []
                with patch.object(host, "command", side_effect=lambda args: commands.append(args)):
                    host.switch(host.candidate_snapshot(root / "releases/new"))
                    self.assertEqual((root / "staging/current").resolve(), root / "releases/new")
                    self.assertIn(str(root / "releases/new/.venv/bin/gunicorn"), dropin.read_text())
                    host.switch(old)
                self.assertEqual((root / "staging/current").resolve(), root / "releases/old")
                self.assertFalse(dropin.exists())
                self.assertEqual(
                    (root / "staging/venv/legacy").read_text(), "keep original Python environment"
                )
                self.assertEqual(commands[0], ["systemctl", "stop", deploy.UNIT])
                self.assertEqual(commands[-1], ["systemctl", "start", deploy.UNIT])

    def test_pending_migrations_halt_actual_preparation_pipeline_before_switch(self):
        from types import SimpleNamespace

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "releases").mkdir()
            (root / "incoming").mkdir()
            state = root / "state"
            state.mkdir()
            archive = root / "incoming" / ("0" * 32 + ".zip")
            content = package()
            archive.write_bytes(content)
            commands = []

            def command(args, **kwargs):
                commands.append((args, kwargs))
                if "migrate" in args:
                    self.assertIn("--check", args)
                    raise deploy.DeployError("Pending migrations")

            host = deploy.Host({}, root / "log")
            account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
            with (
                patch.object(deploy, "BASE", root),
                patch.object(deploy, "STATE", state),
                patch("pwd.getpwnam", return_value=account),
                patch.object(host, "command", side_effect=command),
                self.assertRaisesRegex(deploy.DeployError, "Pending migrations"),
            ):
                host.prepare(archive, hashlib.sha256(content).hexdigest(), COMMIT)
            self.assertTrue(any("collectstatic" in args for args, kwargs in commands))
            self.assertTrue(all("systemctl" not in args for args, kwargs in commands))
            self.assertTrue(any(kwargs.get("user") == "monkeydo" for args, kwargs in commands))

    def test_fifo_upload_is_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "releases").mkdir()
            (root / "incoming").mkdir()
            archive = root / "incoming" / ("0" * 32 + ".zip")
            os.mkfifo(archive)
            host = deploy.Host({}, root / "log")
            with (
                patch.object(deploy, "BASE", root),
                patch.object(deploy, "STATE", root),
                self.assertRaisesRegex(deploy.DeployError, "regular file"),
            ):
                host.prepare(archive, "0" * 64, COMMIT)


class DurableCommitTests(unittest.TestCase):
    def test_failure_to_commit_success_still_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            host = FakeHost()
            controller = deploy.Controller(host, path)
            save = controller.save
            attempts = []

            def failing_save():
                attempts.append(1)
                if len(attempts) == 2:
                    raise OSError("Simulated full disk")
                save()

            with (
                patch.object(controller, "save", side_effect=failing_save),
                self.assertRaisesRegex(deploy.DeployError, "restored and verified"),
            ):
                controller.deploy(Path("archive"), "digest", COMMIT)
            self.assertEqual(host.current["release"], "/old")
            self.assertIsNone(json.loads(path.read_text())["pending"])


class FrozenBundleTests(unittest.TestCase):
    def test_missing_asset_or_enabled_form_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive.zip"
            archive.write_bytes(package())
            release = root / "release"
            release.mkdir()
            deploy.extract_archive(archive, release, COMMIT)
            deploy.validate_bundles(release)
            page = release / "docs/design-review/v1/01-home.html"
            for content in [
                "<form></form>",
                "<script>alert(1)</script>",
                "<button>Save</button>",
                '<img src="missing.jpg">',
                '<img src="https://external.invalid/image.jpg">',
                '<a href="../../../../etc/passwd">Bad</a>',
            ]:
                page.write_text(content)
                with self.assertRaises(deploy.DeployError):
                    deploy.validate_bundles(release)


class DuplicateArchiveTests(unittest.TestCase):
    def test_duplicate_and_absolute_entries_rejected_even_with_valid_required_files(self):
        import warnings

        for name in [PREFIX + "/manage.py", "/absolute", "../escape"]:
            data = io.BytesIO(package())
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(data, "a") as archive:
                    archive.writestr(name, "untrusted")
            with (
                zipfile.ZipFile(io.BytesIO(data.getvalue())) as archive,
                self.assertRaises(deploy.DeployError),
            ):
                deploy.safe_archive(archive, COMMIT)
