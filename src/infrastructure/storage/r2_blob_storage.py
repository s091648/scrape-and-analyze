import boto3

from src.config.settings import (
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_PUBLIC_URL,
)
from src.shared.domain.services.blob_storage_service import BlobStorageService


class R2BlobStorageService(BlobStorageService):
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
        )
        return f"{self._public_url}/{key}"

    @classmethod
    def from_env(cls) -> "R2BlobStorageService":
        missing = [
            name
            for name, val in {
                "R2_ACCOUNT_ID": R2_ACCOUNT_ID,
                "R2_ACCESS_KEY_ID": R2_ACCESS_KEY_ID,
                "R2_SECRET_ACCESS_KEY": R2_SECRET_ACCESS_KEY,
                "R2_BUCKET_NAME": R2_BUCKET_NAME,
                "R2_PUBLIC_URL": R2_PUBLIC_URL,
            }.items()
            if not val
        ]
        if missing:
            raise ValueError(f"R2 blob storage config incomplete: missing {missing}")
        return cls(
            account_id=R2_ACCOUNT_ID,
            access_key_id=R2_ACCESS_KEY_ID,
            secret_access_key=R2_SECRET_ACCESS_KEY,
            bucket_name=R2_BUCKET_NAME,
            public_url=R2_PUBLIC_URL,
        )
