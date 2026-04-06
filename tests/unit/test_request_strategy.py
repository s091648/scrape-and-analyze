import pytest
from unittest.mock import patch
import time as time_module


def test_request_strategy_is_abstract():
    from src.analyzers.strategies.base_request_strategy import RequestStrategy
    with pytest.raises(TypeError):
        RequestStrategy()


def test_request_strategy_requires_acquire():
    from src.analyzers.strategies.base_request_strategy import RequestStrategy

    class MissingAcquire(RequestStrategy):
        def record_usage(self, actual_tokens: int) -> None:
            pass

    with pytest.raises(TypeError):
        MissingAcquire()


def test_request_strategy_requires_record_usage():
    from src.analyzers.strategies.base_request_strategy import RequestStrategy

    class MissingRecord(RequestStrategy):
        def acquire(self, estimated_tokens: int) -> None:
            pass

    with pytest.raises(TypeError):
        MissingRecord()


def test_rate_limit_exhausted_is_exception():
    from src.analyzers.strategies.leaky_bucket_strategy import RateLimitExhausted
    exc = RateLimitExhausted("daily limit hit")
    assert isinstance(exc, Exception)
    assert str(exc) == "daily limit hit"


def test_noop_strategy_acquire_does_nothing():
    from src.analyzers.strategies.no_op_strategy import NoOpStrategy
    s = NoOpStrategy()
    s.acquire(1000)  # must not raise or sleep


def test_noop_strategy_record_usage_does_nothing():
    from src.analyzers.strategies.no_op_strategy import NoOpStrategy
    s = NoOpStrategy()
    s.record_usage(500)  # must not raise

def test_leaky_bucket_acquire_passes_when_under_limits():
    from src.analyzers.strategies.leaky_bucket_strategy import LeakyBucketStrategy
    s = LeakyBucketStrategy(rpm=5, tpm=250_000, rpd=20)
    s.acquire(estimated_tokens=100)  # first request, must not sleep or raise


def test_leaky_bucket_record_usage_updates_tpm_window():
    from src.analyzers.strategies.leaky_bucket_strategy import LeakyBucketStrategy
    s = LeakyBucketStrategy(rpm=5, tpm=250_000, rpd=20)
    s.acquire(estimated_tokens=100)
    s.record_usage(actual_tokens=300)
    # Internal tpm window should have one entry with 300 tokens
    assert len(s._tpm_window) == 1
    assert s._tpm_window[0][1] == 300


def test_leaky_bucket_rpm_blocks_when_full():
    """當 RPM 達到上限時，acquire() 應模擬睡眠直到視窗開啟。"""
    from src.analyzers.strategies.leaky_bucket_strategy import LeakyBucketStrategy

    slept = []
    start_now = 1000.0  # 使用固定的起始時間方便除錯

    # 定義一個模擬時間的類別
    class MockClock:
        def __init__(self, current_time):
            self.current = current_time

        def monotonic(self):
            return self.current

        def sleep(self, duration):
            # 關鍵：模擬時間前進，否則 while 迴圈永遠不會結束
            self.current += duration
            slept.append(duration)

    clock = MockClock(start_now)

    # 初始化策略：RPM=2 (每分鐘最多2次)
    s = LeakyBucketStrategy(rpm=2, tpm=250_000, rpd=20)
    
    # 預填 RPM 視窗：在 t=995 和 t=997 分別發送一次請求
    # 假設視窗長度是 60 秒，這兩筆在 t=1000 時都還在視窗內
    s._rpm_window.append(start_now - 5)
    s._rpm_window.append(start_now - 3)

    # 使用 side_effect 將 MockClock 的方法植入
    with patch('src.analysis.strategies.leaky_bucket_strategy.time.sleep', side_effect=clock.sleep), \
         patch('src.analysis.strategies.leaky_bucket_strategy.time.monotonic', side_effect=clock.monotonic):
        
        # 這次 acquire 會因為 RPM=2 已滿而進入迴圈
        s.acquire(estimated_tokens=100)

    # 驗證
    assert len(slept) >= 1, "應該要觸發 sleep"
    assert sum(slept) > 0, "總睡眠時間應大於 0"
    assert clock.current > start_now, "模擬時間應該有所前進"


def test_leaky_bucket_tpm_blocks_when_full():
    """當 TPM 達到上限時，acquire() 應模擬睡眠直到視窗開啟。"""
    from src.analyzers.strategies.leaky_bucket_strategy import LeakyBucketStrategy

    slept = []
    start_now = 2000.0

    class MockClock:
        def __init__(self, current_time):
            self.current = current_time
        def monotonic(self):
            return self.current
        def sleep(self, duration):
            # 關鍵：讓模擬時間前進，使 TPM 視窗內的舊紀錄能被清除
            self.current += duration
            slept.append(duration)

    clock = MockClock(start_now)

    # 設定 TPM 為 100
    s = LeakyBucketStrategy(rpm=5, tpm=100, rpd=20)
    
    # 預填 TPM 視窗：10秒前使用了 90 tokens (假設視窗為 60 秒)
    s._tpm_window.append((start_now - 10, 90))

    with patch('src.analysis.strategies.leaky_bucket_strategy.time.sleep', side_effect=clock.sleep), \
         patch('src.analysis.strategies.leaky_bucket_strategy.time.monotonic', side_effect=clock.monotonic):
        
        # 請求 20 tokens，總數 110 會超過 100，必須觸發 sleep
        s.acquire(estimated_tokens=20)

    # 驗證邏輯
    assert len(slept) >= 1, "應該要觸發 sleep"
    assert clock.current > start_now, "模擬時間應該有所前進"
    # 確保最終成功加入視窗
    assert sum(t for _, t in s._tpm_window) >= 20


def test_leaky_bucket_cleans_stale_rpm_entries():
    """Entries older than 60s should be evicted from RPM window."""
    from src.analyzers.strategies.leaky_bucket_strategy import LeakyBucketStrategy

    now = time_module.monotonic()
    s = LeakyBucketStrategy(rpm=2, tpm=250_000, rpd=20)
    # Add stale entry (65s ago) — should be cleaned on acquire
    s._rpm_window.append(now - 65)

    with patch('src.analysis.strategies.leaky_bucket_strategy.time.monotonic', return_value=now):
        s.acquire(estimated_tokens=100)  # must not sleep

    # Stale entry should have been evicted; only the new one remains
    assert len(s._rpm_window) == 1


def test_leaky_bucket_raises_when_daily_cap_hit():
    from src.analyzers.strategies.leaky_bucket_strategy import LeakyBucketStrategy, RateLimitExhausted
    s = LeakyBucketStrategy(rpm=100, tpm=1_000_000, rpd=3)
    s._daily_count = 3  # simulate cap already reached
    with pytest.raises(RateLimitExhausted, match="Daily request limit"):
        s.acquire(estimated_tokens=100)


def test_leaky_bucket_daily_count_increments_on_acquire():
    from src.analyzers.strategies.leaky_bucket_strategy import LeakyBucketStrategy
    s = LeakyBucketStrategy(rpm=100, tpm=1_000_000, rpd=20)
    assert s._daily_count == 0
    s.acquire(estimated_tokens=100)
    assert s._daily_count == 1
