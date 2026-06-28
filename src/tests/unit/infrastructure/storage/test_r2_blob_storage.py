"""Unit tests for R2BlobStorageService."""
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.storage.r2_blob_storage import R2BlobStorageService


def _make_service(
    account_id="abc123",
    access_key_id="key",
    secret_access_key="secret",
    bucket_name="my-bucket",
    public_url="https://pub.example.com",
):
    with patch("boto3.client"):
        svc = R2BlobStorageService(
            account_id=account_id,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            bucket_name=bucket_name,
            public_url=public_url,
        )
    return svc


def test_upload_calls_put_object():
    with patch("boto3.client") as MockClient:
        mock_s3 = MockClient.return_value
        svc = R2BlobStorageService("id", "key", "secret", "bucket", "https://cdn.example.com")
        svc.upload(b"data", "reports/img.png", "image/png")

    mock_s3.put_object.assert_called_once_with(
        Bucket="bucket",
        Key="reports/img.png",
        Body=b"data",
        ContentType="image/png",
    )


def test_upload_returns_public_url():
    with patch("boto3.client"):
        svc = R2BlobStorageService("id", "key", "secret", "bucket", "https://cdn.example.com")
        url = svc.upload(b"data", "reports/img.png", "image/png")

    assert url == "https://cdn.example.com/reports/img.png"


def test_upload_strips_trailing_slash_from_public_url():
    with patch("boto3.client"):
        svc = R2BlobStorageService("id", "key", "secret", "bucket", "https://cdn.example.com/")
        url = svc.upload(b"data", "key.png", "image/png")

    assert url == "https://cdn.example.com/key.png"


def test_client_initialized_with_r2_endpoint():
    with patch("boto3.client") as MockClient:
        R2BlobStorageService("my-account-id", "k", "s", "b", "https://pub.example.com")

    call_kwargs = MockClient.call_args[1]
    assert "my-account-id.r2.cloudflarestorage.com" in call_kwargs["endpoint_url"]


def test_upload_propagates_s3_error():
    with patch("boto3.client") as MockClient:
        mock_s3 = MockClient.return_value
        mock_s3.put_object.side_effect = Exception("S3 access denied")
        svc = R2BlobStorageService("id", "key", "secret", "bucket", "https://cdn.example.com")

        with pytest.raises(Exception, match="S3 access denied"):
            svc.upload(b"data", "key", "image/png")


def test_from_env_reads_env_vars(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "env-id")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "env-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "env-secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "env-bucket")
    monkeypatch.setenv("R2_PUBLIC_URL", "https://env.cdn.example.com")

    with patch("boto3.client"):
        svc = R2BlobStorageService.from_env()

    assert svc._bucket == "env-bucket"
    assert svc._public_url == "https://env.cdn.example.com"
