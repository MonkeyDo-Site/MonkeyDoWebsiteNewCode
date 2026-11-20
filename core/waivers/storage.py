"""Private, bounded Cloudflare R2 evidence access with no local signed-file copy."""

import hashlib
import re

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables

MAX_EVIDENCE = 2 * 1024 * 1024


class EvidenceUnavailable(Exception):
    def __init__(self):
        super().__init__("Private waiver evidence could not be verified.")


class EvidenceMissing(EvidenceUnavailable):
    pass


def enabled():
    if not settings.WAIVER_ENABLED or settings.APP_ENV not in {"test", "development", "staging"}:
        raise ValidationError("Signed waiver integration is not enabled.")


class EvidenceStore:
    @sensitive_variables()
    def __init__(self):
        enabled()
        if (
            not re.fullmatch(r"[a-f0-9]{32}", settings.R2_ACCOUNT_ID)
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", settings.R2_WAIVER_BUCKET)
            or "staging" not in settings.R2_WAIVER_BUCKET
            or not settings.R2_WAIVER_ACCESS_KEY
            or not settings.R2_WAIVER_SECRET_KEY
        ):
            raise EvidenceUnavailable()
        self.bucket = settings.R2_WAIVER_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_WAIVER_ACCESS_KEY,
            aws_secret_access_key=settings.R2_WAIVER_SECRET_KEY,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=15,
                retries={"total_max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )

    def validate_key(self, key):
        if not re.fullmatch(r"staging/waivers/[a-f0-9]{32}\.html", key):
            raise EvidenceUnavailable()

    @sensitive_variables()
    def get(self, key, expected_hash):
        self.validate_key(key)
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=key)
            body = result["Body"]
            try:
                if result.get("ContentLength", 0) > MAX_EVIDENCE:
                    raise EvidenceUnavailable()
                data = body.read(MAX_EVIDENCE + 1)
            finally:
                body.close()
            if len(data) > MAX_EVIDENCE or hashlib.sha256(data).hexdigest() != expected_hash:
                raise EvidenceUnavailable()
            return data
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                raise EvidenceMissing() from None
            raise EvidenceUnavailable() from None
        except (BotoCoreError, OSError, KeyError, TypeError, ValueError):
            raise EvidenceUnavailable() from None

    @sensitive_variables()
    def put(self, key, data, expected_hash):
        self.validate_key(key)
        if (
            not data
            or len(data) > MAX_EVIDENCE
            or hashlib.sha256(data).hexdigest() != expected_hash
        ):
            raise EvidenceUnavailable()
        # Stable retry identity plus conditional creation prevents overwriting evidence.
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                IfNoneMatch="*",
                ContentType="text/html; charset=utf-8",
                CacheControl="private, no-store",
                Metadata={"sha256": expected_hash},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") not in {"PreconditionFailed", "412"}:
                raise EvidenceUnavailable() from None
        except (BotoCoreError, OSError):
            raise EvidenceUnavailable() from None
        # Do not claim a signature is saved until the actual bytes are read and verified.
        return self.get(key, expected_hash)

    def delete(self, key):
        self.validate_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"NoSuchKey", "NotFound", "404"}:
                return
            raise EvidenceUnavailable() from None
        except (BotoCoreError, OSError):
            raise EvidenceUnavailable() from None
        raise EvidenceUnavailable()
