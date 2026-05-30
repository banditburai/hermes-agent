import sys
import types

import pytest

from gateway import status


def _install_fake_psutil(monkeypatch, *, create_time=None, raises=None):
    """Inject a hermetic fake psutil so the test is identical on every CI platform.

    ``raises`` may be a psutil exception class *name* (resolved against the fake,
    so the instance matches the class the production except clause catches) or any
    other exception instance.
    """
    fake = types.ModuleType("psutil")
    for name in ("NoSuchProcess", "AccessDenied", "ZombieProcess"):
        setattr(fake, name, type(name, (Exception,), {}))
    boom = getattr(fake, raises)("boom") if isinstance(raises, str) else raises

    class _Proc:
        def __init__(self, pid):
            self.pid = pid

        def create_time(self):
            if boom is not None:
                raise boom
            return create_time

    fake.Process = _Proc
    monkeypatch.setitem(sys.modules, "psutil", fake)
    return fake


def test_returns_epoch_microseconds_int(monkeypatch):
    _install_fake_psutil(monkeypatch, create_time=1_748_600_000.123456)
    assert status._get_process_start_time(1234) == 1_748_600_000_123_456


@pytest.mark.parametrize(
    "raises",
    ["NoSuchProcess", "AccessDenied", "ZombieProcess", OSError("io"), ValueError("nan")],
)
def test_unreadable_process_returns_none(monkeypatch, raises):
    _install_fake_psutil(monkeypatch, raises=raises)
    assert status._get_process_start_time(999999) is None


def test_missing_psutil_returns_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "psutil", None)  # forces ImportError on `import psutil`
    assert status._get_process_start_time(1234) is None
