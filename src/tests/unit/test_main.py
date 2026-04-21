import time
from src.main import check_timeout, MAX_EXECUTION_TIME


def test_check_timeout_returns_true_when_exceeded():
    start_time = time.time() - MAX_EXECUTION_TIME - 1
    assert check_timeout(start_time) is True


def test_check_timeout_returns_false_when_not_exceeded():
    start_time = time.time()
    assert check_timeout(start_time) is False
