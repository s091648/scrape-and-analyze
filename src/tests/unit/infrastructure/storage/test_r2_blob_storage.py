"""Unit tests for R2BlobStorageService."""
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.shared.exceptions import MissingR2ConfigError
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
        CacheControl=R2BlobStorageService.CACHE_CONTROL,
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


def test_from_env_reads_settings(monkeypatch):
    """from_env() builds the client from settings.R2_* constants."""
    monkeypatch.setattr("src.config.settings.R2_ACCOUNT_ID", "env-id")
    monkeypatch.setattr("src.config.settings.R2_ACCESS_KEY_ID", "env-key")
    monkeypatch.setattr("src.config.settings.R2_SECRET_ACCESS_KEY", "env-secret")
    monkeypatch.setattr("src.config.settings.R2_BUCKET_NAME", "env-bucket")
    monkeypatch.setattr("src.config.settings.R2_PUBLIC_URL", "https://env.cdn.example.com")

    with patch("boto3.client"):
        svc = R2BlobStorageService.from_env()

    assert svc._bucket == "env-bucket"
    assert svc._public_url == "https://env.cdn.example.com"


def test_from_env_raises_when_settings_incomplete(monkeypatch):
    """from_env() raises MissingR2ConfigError listing missing settings when any R2_* is empty."""
    monkeypatch.setattr("src.config.settings.R2_ACCOUNT_ID", "")
    monkeypatch.setattr("src.config.settings.R2_ACCESS_KEY_ID", "k")
    monkeypatch.setattr("src.config.settings.R2_SECRET_ACCESS_KEY", "s")
    monkeypatch.setattr("src.config.settings.R2_BUCKET_NAME", "b")
    monkeypatch.setattr("src.config.settings.R2_PUBLIC_URL", "https://x")

    with pytest.raises(MissingR2ConfigError, match="R2_ACCOUNT_ID"):
        R2BlobStorageService.from_env()


def test_iter_keys_paginates_list_objects_v2():
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {"Contents": [{"Key": "a"}, {"Key": "b"}]},
        {"Contents": [{"Key": "c"}]},
    ]
    with patch("boto3.client") as MockClient:
        mock_s3 = MockClient.return_value
        mock_s3.get_paginator.return_value = mock_paginator
        svc = R2BlobStorageService("id", "key", "secret", "bucket", "https://cdn.example.com")
        keys = list(svc.iter_keys("weekly-reports/"))

    mock_s3.get_paginator.assert_called_once_with("list_objects_v2")
    mock_paginator.paginate.assert_called_once_with(Bucket="bucket", Prefix="weekly-reports/")
    assert keys == ["a", "b", "c"]


def test_iter_keys_skips_empty_pages():
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{}]
    with patch("boto3.client") as MockClient:
        mock_s3 = MockClient.return_value
        mock_s3.get_paginator.return_value = mock_paginator
        svc = R2BlobStorageService("id", "key", "secret", "bucket", "https://cdn.example.com")
        keys = list(svc.iter_keys())

    assert keys == []


def test_head_object_returns_raw_metadata():
    with patch("boto3.client") as MockClient:
        mock_s3 = MockClient.return_value
        mock_s3.head_object.return_value = {"CacheControl": "no-cache", "ContentType": "image/webp"}
        svc = R2BlobStorageService("id", "key", "secret", "bucket", "https://cdn.example.com")
        meta = svc.head_object("weekly-reports/t/2026-07-27.webp")

    mock_s3.head_object.assert_called_once_with(Bucket="bucket", Key="weekly-reports/t/2026-07-27.webp")
    assert meta == {"CacheControl": "no-cache", "ContentType": "image/webp"}


def test_refresh_cache_control_copies_object_onto_itself():
    with patch("boto3.client") as MockClient:
        mock_s3 = MockClient.return_value
        svc = R2BlobStorageService("id", "key", "secret", "bucket", "https://cdn.example.com")
        svc.refresh_cache_control("weekly-reports/t/2026-07-27.webp", "image/webp")

    mock_s3.copy_object.assert_called_once_with(
        Bucket="bucket",
        Key="weekly-reports/t/2026-07-27.webp",
        CopySource={"Bucket": "bucket", "Key": "weekly-reports/t/2026-07-27.webp"},
        MetadataDirective="REPLACE",
        ContentType="image/webp",
        CacheControl=R2BlobStorageService.CACHE_CONTROL,
    )
