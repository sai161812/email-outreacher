import importlib
import config
import pytest

@pytest.mark.parametrize("name,value", [
    ("DAILY_SEND_CAP", "0"), ("MIN_DELAY_SECONDS", "-1"),
    ("SEND_DAYS", "wrong"), ("SEND_END_HOUR", "99"),
    ("RESUME_ATTACH_MODE", "wrong"), ("MAX_DELAY_SECONDS", "not a number")
])
def test_invalid_config(monkeypatch, name, value):
    with monkeypatch.context() as patcher:
        patcher.setenv(name, value)
        with pytest.raises(ValueError, match=name):
            importlib.reload(config)
    importlib.reload(config)

def test_model_override(monkeypatch):
    with monkeypatch.context() as patcher:
        patcher.setenv("GEMINI_MODEL", "test-model")
        assert importlib.reload(config).GEMINI_MODEL == "test-model"
    importlib.reload(config)

def test_stdlib_profile_not_shadowed():
    import cProfile
    assert callable(cProfile.run)
