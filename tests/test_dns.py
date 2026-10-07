from types import SimpleNamespace
from unittest.mock import Mock
import dns.resolver
import pytest
import validate

@pytest.mark.parametrize("exception,expected",[(dns.resolver.NXDOMAIN(),False),(dns.resolver.NoAnswer(),False),(dns.resolver.NoNameservers(),None),(TimeoutError(),None)])
def test_dns_error_classification(monkeypatch,exception,expected):
    validate._has_mx_record.cache_clear()
    monkeypatch.setattr(dns.resolver,"resolve",Mock(side_effect=exception))
    assert validate.has_mx_record("example.test") is expected

def test_null_mx_cache_and_expiry(monkeypatch):
    validate._has_mx_record.cache_clear()
    resolve=Mock(return_value=[SimpleNamespace(exchange=".")])
    monkeypatch.setattr(dns.resolver,"resolve",resolve)
    monkeypatch.setattr(validate.time,"monotonic",lambda:1)
    assert validate.has_mx_record("example.test") is False
    validate.has_mx_record("EXAMPLE.TEST")
    assert resolve.call_count==1
    monkeypatch.setattr(validate.time,"monotonic",lambda:301)
    validate.has_mx_record("example.test")
    assert resolve.call_count==2
