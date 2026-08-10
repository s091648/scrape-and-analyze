from typing import Iterator

import boto3

from src.config import settings
from src.infrastructure.shared.exceptions import MissingR2ConfigError
from src.shared.domain.services.blob_storage_service import BlobStorageService


class R2BlobStorageService(BlobStorageService):
    # Keys are dated (e.g. weekly-reports/<topic_id>/<week_start>.webp) and never overwritten in
    # normal operation, so a long, immutable TTL is safe — this is what was missing from the
    # Lighthouse "Use efficient cache lifetimes" finding (the r2.dev cover image had no
    # Cache-Control at all). Shared by upload() (new objects) and refresh_cache_control() (rewriting
    # objects uploaded before this existed — see scripts/backfill_r2_cache_control.py).
    CACHE_CONTROL = "public, max-age=31536000, immutable"

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_url: str,
    ) -> None:
        self._bucket = bucket_name
        self._public_url = public_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def upload(self, data: bytes, key: str, content_type: str) -> str:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl=self.CACHE_CONTROL,
        )
        return f"{self._public_url}/{key}"

    def iter_keys(self, prefix: str = "") -> Iterator[str]:
        """Yield every object key under `prefix` in this bucket (paginated list_objects_v2)."""
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"]

    def head_object(self, key: str) -> dict:
        """Raw object metadata (ContentType, CacheControl, ...) without downloading the body."""
        return self._client.head_object(Bucket=self._bucket, Key=key)

    def refresh_cache_control(self, key: str, content_type: str) -> None:
        """Rewrite `key`'s metadata in place (S3 copy-onto-self) to this service's current
        `CACHE_CONTROL` policy, without re-downloading/re-uploading the object's bytes."""
        self._client.copy_object(
            Bucket=self._bucket,
            Key=key,
            CopySource={"Bucket": self._bucket, "Key": key},
            MetadataDirective="REPLACE",
            ContentType=content_type,
            CacheControl=self.CACHE_CONTROL,
        )

    @classmethod
    def from_env(cls) -> "R2BlobStorageService":
        missing = [
            name
            for name, val in {
                "R2_ACCOUNT_ID": settings.R2_ACCOUNT_ID,
                "R2_ACCESS_KEY_ID": settings.R2_ACCESS_KEY_ID,
                "R2_SECRET_ACCESS_KEY": settings.R2_SECRET_ACCESS_KEY,
                "R2_BUCKET_NAME": settings.R2_BUCKET_NAME,
                "R2_PUBLIC_URL": settings.R2_PUBLIC_URL,
            }.items()
            if not val
        ]
        if missing:
            raise MissingR2ConfigError(f"R2 blob storage config incomplete: missing {missing}")
        return cls(
            account_id=settings.R2_ACCOUNT_ID,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME,
            public_url=settings.R2_PUBLIC_URL,
        )
