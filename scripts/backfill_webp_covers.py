#!/usr/bin/env python
# scripts/backfill_webp_covers.py
"""
Backfill weekly-report cover images from PNG to WebP on Cloudflare R2.

Cover images generated before src/infrastructure/intelligence/image/image_encoding.py existed are
PNGs at generation-native resolution — a real example was ~1.1MB, of which Lighthouse's
image-delivery-insight audit estimated ~85% (951KB) was wasted purely from format/compression
choice (specs/021-ssr-public-pages). This script re-encodes each existing PNG cover in place:
downloads it from R2, downscales + re-encodes as WebP (the same `encode_as_webp` helper new
reports already go through), re-uploads under a new `.webp` key, and updates
weekly_reports.cover_image_url to point at it. The original `.png` object is left in R2 untouched
(not deleted) — this script only ever adds objects and updates DB pointers.

Usage:
    # Local (uses DATABASE_URL + R2_* from .env):
    uv run python scripts/backfill_webp_covers.py [--limit N] [--dry-run]

    # Remote staging (default) — see `make backfill-webp-covers-remote` for the Makefile
    # target, which also swaps in .env.staging's R2_* values (see Makefile comment on why R2
    # credentials need a different mechanism than REMOTE_RAILWAY_*_DB_URL):
    uv run python scripts/backfill_webp_covers.py --remote [--limit N]

    # Remote production:
    uv run python scripts/backfill_webp_covers.py --remote --env production [--limit N]

Required env vars (from .env / .env.staging / .env.production):
    DATABASE_URL (or REMOTE_RAILWAY_STAGING_DB_URL / REMOTE_RAILWAY_DB_URL for --remote)
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_URL
"""
import argparse
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Backfill weekly-report cover images from PNG to WebP")
    parser.add_argument("--limit", type=int, default=0, help="Max reports to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Report what would change without downloading/uploading/writing")
    parser.add_argument("--remote", action="store_true", help="Use remote DATABASE_URL instead of local")
    parser.add_argument("--env", choices=["staging", "production"], default="staging",
                         help="Remote environment (requires --remote). Default: staging")
    parser.add_argument("--max-width", type=int, default=None,
                         help="Downscale images wider than this (default: image_encoding.DEFAULT_MAX_WIDTH)")
    parser.add_argument("--quality", type=int, default=None,
                         help="WebP encode quality, 1-100 (default: image_encoding.DEFAULT_QUALITY)")
    args = parser.parse_args()

    if args.remote:
        if args.env == "production":
            remote_url = os.environ.get("REMOTE_RAILWAY_DB_URL", "")
            env_var = "REMOTE_RAILWAY_DB_URL"
        else:
            remote_url = os.environ.get("REMOTE_RAILWAY_STAGING_DB_URL", "")
            env_var = "REMOTE_RAILWAY_STAGING_DB_URL"
        if not remote_url:
            print(f"ERROR: {env_var} must be set in .env", file=sys.stderr)
            sys.exit(1)
        os.environ["DATABASE_URL"] = remote_url
        print(f"Using remote DB ({args.env}): {env_var}")

    import requests
    from sqlalchemy import text

    from src.infrastructure.intelligence.image.image_encoding import (
        DEFAULT_MAX_WIDTH,
        DEFAULT_QUALITY,
        encode_as_webp,
    )
    from src.infrastructure.persistence.database import get_session, init_db
    from src.infrastructure.storage.r2_blob_storage import R2BlobStorageService
    from src.shared.logging import get_logger

    logger = get_logger(__name__)
    max_width = args.max_width or DEFAULT_MAX_WIDTH
    quality = args.quality or DEFAULT_QUALITY

    try:
        blob_storage = R2BlobStorageService.from_env()
    except Exception as exc:
        print(f"ERROR: R2 config incomplete — {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Using R2 bucket: {os.environ.get('R2_BUCKET_NAME', '')} "
          f"({os.environ.get('R2_PUBLIC_URL', '')})")

    init_db()
    session = get_session()

    query = text("""
        SELECT id, cover_image_url
        FROM intelligence.weekly_reports
        WHERE cover_image_url IS NOT NULL
          AND cover_image_url ILIKE '%.png'
        ORDER BY created_at DESC
    """ + (" LIMIT :limit" if args.limit else ""))
    params = {"limit": args.limit} if args.limit else {}
    rows = session.execute(query, params).fetchall()

    print(f"Found {len(rows)} PNG cover image(s) to convert"
          + (" (dry run — no writes)" if args.dry_run else ""))
    logger.info(
        "backfill_webp_covers_start",
        total=len(rows), dry_run=args.dry_run,
        env=args.env if args.remote else "local",
        max_width=max_width, quality=quality,
    )

    converted = 0
    failed = 0
    total_before = 0
    total_after = 0

    for row in rows:
        report_id = str(row[0])
        old_url = row[1]

        if "/weekly-reports/" not in old_url:
            print(f"  SKIP {report_id}: URL doesn't look like a weekly-report cover key: {old_url}")
            failed += 1
            continue
        new_key = "weekly-reports/" + old_url.split("/weekly-reports/", 1)[1]
        new_key = new_key.rsplit(".", 1)[0] + ".webp"

        try:
            resp = requests.get(old_url, timeout=30)
            resp.raise_for_status()
            original_bytes = resp.content
            webp_bytes = encode_as_webp(original_bytes, max_width=max_width, quality=quality)

            total_before += len(original_bytes)
            total_after += len(webp_bytes)
            print(f"  {report_id}: {len(original_bytes):,}B -> {len(webp_bytes):,}B "
                  f"({100 * (1 - len(webp_bytes) / len(original_bytes)):.0f}% smaller)")

            if args.dry_run:
                converted += 1
                continue

            new_url = blob_storage.upload(webp_bytes, new_key, "image/webp")
            session.execute(
                text("UPDATE intelligence.weekly_reports SET cover_image_url = :url WHERE id = :id"),
                {"url": new_url, "id": report_id},
            )
            session.commit()
            converted += 1
            logger.info("backfill_webp_covers_converted", report_id=report_id,
                        old_url=old_url, new_url=new_url,
                        before_bytes=len(original_bytes), after_bytes=len(webp_bytes))
        except Exception as exc:
            session.rollback()
            failed += 1
            logger.error("backfill_webp_covers_failed", report_id=report_id,
                         old_url=old_url, error=type(exc).__name__, detail=str(exc))
            print(f"  FAILED {report_id}: {type(exc).__name__}: {exc}")

    logger.info("backfill_webp_covers_complete", converted=converted, failed=failed, total=len(rows))
    print(f"\nDone: {converted} converted, {failed} failed, {len(rows)} total")
    if total_before:
        print(f"Total size: {total_before:,}B -> {total_after:,}B "
              f"({100 * (1 - total_after / total_before):.0f}% smaller)")


if __name__ == "__main__":
    main()
