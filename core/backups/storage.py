"""Private R2 backup bucket, isolated from waiver data, bounded streaming verification."""

import hashlib
import re

import boto3
from botocore.config import Config
from django.conf import settings

MAX_BACKUP = 8 * 1024 * 1024 * 1024


class BackupUnavailable(Exception):
    pass


class BackupStore:
    def __init__(self, *, read_only=False):
        bucket = settings.R2_BACKUP_BUCKET
        access = settings.R2_BACKUP_READ_ACCESS_KEY if read_only else settings.R2_BACKUP_ACCESS_KEY
        secret = settings.R2_BACKUP_READ_SECRET_KEY if read_only else settings.R2_BACKUP_SECRET_KEY
        if (
            not re.fullmatch(r"[a-f0-9]{32}", settings.R2_ACCOUNT_ID)
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket)
            or "staging" not in bucket
            or bucket == settings.R2_WAIVER_BUCKET
            or not access
            or not secret
        ):
            raise BackupUnavailable("backup_configuration")
        self.bucket, self.read_only = bucket, read_only
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=30,
                retries={"total_max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )

    def validate(self, key):
        if not re.fullmatch(r"staging/backups/[0-9]{4}-[0-9]{2}-[a-f0-9]{32}\.cms", key):
            raise BackupUnavailable("backup_key")

    def read(self, key):
        self.validate(key)
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        if not 0 < response.get("ContentLength", 0) <= MAX_BACKUP:
            response["Body"].close()
            raise BackupUnavailable("backup_size")
        return response

    def verify(self, key, digest, size):
        response = self.read(key)
        body = response["Body"]
        count = 0
        hashed = hashlib.sha256()
        try:
            while block := body.read(1024 * 1024):
                count += len(block)
                if count > MAX_BACKUP:
                    raise BackupUnavailable("backup_size")
                hashed.update(block)
        finally:
            body.close()
        if count != size or hashed.hexdigest() != digest:
            raise BackupUnavailable("backup_integrity")

    def put(self, key, source, digest, size):
        if self.read_only or not 0 < size <= MAX_BACKUP:
            raise BackupUnavailable("backup_write")
        self.validate(key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=source,
            ContentLength=size,
            IfNoneMatch="*",
            ContentType="application/pkcs7-mime",
            Metadata={"sha256": digest},
            CacheControl="private, no-store",
        )
        self.verify(key, digest, size)

    def delete(self, key):
        if self.read_only:
            raise BackupUnavailable("backup_write")
        self.validate(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                return
            raise
        raise BackupUnavailable("backup_delete_unconfirmed")
