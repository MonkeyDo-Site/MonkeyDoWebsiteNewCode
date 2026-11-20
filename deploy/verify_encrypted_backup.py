#!/usr/bin/env python3
"""Run on a protected isolated recovery workstation, never on DigitalOcean/R2.

Requires Python/psycopg, OpenSSL and matching PostgreSQL client tools. The local
restore role needs CREATEDB but no superuser/CREATEROLE or access to live systems.
The encrypted private key remains here; OpenSSL prompts locally for its passphrase.
This creates and drops only its own random temporary database. No production restore.
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from psycopg import sql


def verify(
    *, archive, manifest, private_key, host, port, user, pg_restore="pg_restore", openssl="openssl"
):
    if host not in {"127.0.0.1", "::1", "/tmp", "/var/run/postgresql"}:
        raise ValueError("Use the isolated workstation's local PostgreSQL server.")
    facts = json.loads(Path(manifest).read_text())
    if facts.get("format") != "MonkeyDo-CMS-AES256-GCM-v1":
        raise ValueError("Unsupported archive format.")
    archive = Path(archive)
    with archive.open("rb") as source:
        if (
            archive.stat().st_size != facts["ciphertext_bytes"]
            or hashlib.file_digest(source, "sha256").hexdigest() != facts["ciphertext_sha256"]
        ):
            raise ValueError("Encrypted archive integrity does not match its downloaded manifest.")
    key = Path(private_key)
    if key.is_symlink() or not key.is_file() or (os.name == "posix" and key.stat().st_mode & 0o077):
        raise ValueError("Protect the private recovery key for your user only.")
    # Authenticate the complete CMS file BEFORE pg_restore can execute any SQL.
    # Plaintext exists only in a private temporary file on this isolated runner.
    with tempfile.TemporaryFile() as plaintext:
        subprocess.run(
            [
                openssl,
                "cms",
                "-decrypt",
                "-binary",
                "-inform",
                "DER",
                "-in",
                str(archive),
                "-inkey",
                str(key),
            ],
            stdout=plaintext,
            check=True,
        )
        plaintext.seek(0)
        database = "monkeydo_restore_check_" + uuid.uuid4().hex[:12]
        options = dict(host=host, port=port, user=user, dbname="postgres", connect_timeout=10)
        with psycopg.connect(**options, autocommit=True) as connection:
            role = connection.execute(
                "SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=current_user"
            ).fetchone()
            if not role or role[0] or role[1] or not role[2]:
                raise ValueError("Use a dedicated isolated restore role with CREATEDB only.")
            connection.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database))
            )
            try:
                environment = dict(os.environ, PGHOST=host, PGPORT=str(port), PGUSER=user)
                subprocess.run(
                    [
                        pg_restore,
                        "--exit-on-error",
                        "--no-owner",
                        "--no-acl",
                        "--no-password",
                        "--dbname",
                        database,
                    ],
                    stdin=plaintext,
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    check=True,
                    timeout=600,
                )
                with psycopg.connect(**(options | {"dbname": database})) as restored:
                    latest = restored.execute(
                        "SELECT name FROM django_migrations WHERE app='core' ORDER BY name DESC LIMIT 1"
                    ).fetchone()
                    tables = restored.execute(
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
                    ).fetchone()[0]
                    missing = restored.execute(
                        "SELECT to_regclass('public.core_booking') IS NULL OR to_regclass('public.core_paymentoperation') IS NULL OR to_regclass('public.core_waiversignature') IS NULL"
                    ).fetchone()[0]
                    if not latest or missing or tables < 20:
                        raise ValueError(
                            "Required application tables/migration history did not restore."
                        )
                    restored.execute("SELECT count(*) FROM core_booking").fetchone()
                    restored.execute("SELECT count(*) FROM core_financialposting").fetchone()
                return {
                    "backup_id": facts["backup_id"],
                    "result": "isolated_restore_verified",
                    "core_migration": latest[0],
                    "tables": tables,
                }
            finally:
                connection.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database))
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--user", default="monkeydo-restore-check")
    parser.add_argument("--isolated-workstation", action="store_true", required=True)
    args = vars(parser.parse_args())
    args.pop("isolated_workstation")
    print(json.dumps(verify(**args), indent=2))


if __name__ == "__main__":
    main()
