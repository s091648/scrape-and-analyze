import logging
import os
import sys
from logging_loki import LokiHandler

def configure_loki():
    # 確保名稱跟你在 Railway 設定的一模一樣
    url = os.environ.get("GRAFANA_LOKI_URL")
    user = os.environ.get("GRAFANA_LOKI_USER")
    key = os.environ.get("GRAFANA_API_KEY")

    if not all([url, user, key]):
        print(f"DEBUG LOKI: Missing vars - URL: {bool(url)}, User: {bool(user)}, Key: {bool(key)}", file=sys.stderr)
        return

    # 打印一點除錯資訊到 Railway 控制台 (非 Loki)
    print(f"DEBUG LOKI: Attempting connection to {url} with user {user}", file=sys.stderr)

    try:
        handler = LokiHandler(
            url=url,
            auth=(user, key),
            tags={"app": "scraper", "env": "production"},
            version="1",
        )
        
        # 只傳送 INFO 以上的日誌，避免 OTLP 的重試警告造成死循環
        handler.setLevel(logging.INFO)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        print("DEBUG LOKI: Handler added successfully", file=sys.stderr)
        
    except Exception as e:
        print(f"DEBUG LOKI: Failed to setup handler: {e}", file=sys.stderr)