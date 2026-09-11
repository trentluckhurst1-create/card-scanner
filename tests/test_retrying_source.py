import httpx
import pytest

from card_scanner.retrying_source import RetryingStoreSource


class FakeSource:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def search(self, sport, query="", limit=50):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def http_error(status):
    request = httpx.Request("GET", "https://store.test/products.json")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("store error", request=request, response=response)


def test_retries_transient_503_then_succeeds():
    source = FakeSource([http_error(503), ["ok"]])
    wrapped = RetryingStoreSource(source, attempts=3, base_delay_seconds=0)
    assert wrapped.search("NBA") == ["ok"]
    assert source.calls == 2


def test_retries_429_with_bounded_attempts():
    source = FakeSource([http_error(429), http_error(429), ["ok"]])
    wrapped = RetryingStoreSource(source, attempts=3, base_delay_seconds=0)
    assert wrapped.search("NFL") == ["ok"]
    assert source.calls == 3


def test_does_not_retry_hard_403():
    source = FakeSource([http_error(403), ["should not run"]])
    wrapped = RetryingStoreSource(source, attempts=3, base_delay_seconds=0)
    with pytest.raises(httpx.HTTPStatusError):
        wrapped.search("AFL")
    assert source.calls == 1


def test_stops_after_retry_budget():
    source = FakeSource([http_error(503), http_error(503), http_error(503), ["late"]])
    wrapped = RetryingStoreSource(source, attempts=3, base_delay_seconds=0)
    with pytest.raises(httpx.HTTPStatusError):
        wrapped.search("NBA")
    assert source.calls == 3
