"""Breached passwords are refused; only a 5-character hash prefix leaves the server."""

import hashlib
import io

import pytest
from django.core.exceptions import ValidationError

from tickrweb import passwords

PASSWORD = "correct horse battery staple"
DIGEST = hashlib.sha1(PASSWORD.encode()).hexdigest().upper()


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _service(monkeypatch, body: str, seen: list):
    def urlopen(request, timeout):
        seen.append(request)
        return _Answer(body.encode("ascii"))

    monkeypatch.setattr(passwords.urllib.request, "urlopen", urlopen)


def test_a_breached_password_is_refused(monkeypatch):
    seen = []
    _service(monkeypatch, f"0000000000000000000000000000000000A:0\r\n{DIGEST[5:]}:42\r\n", seen)
    with pytest.raises(ValidationError) as refused:
        passwords.BreachedPasswordValidator().validate(PASSWORD)
    assert refused.value.code == "password_breached"
    assert seen[0].full_url == passwords.RANGE_URL + DIGEST[:5]
    assert seen[0].get_header("Add-padding") == "true"
    assert PASSWORD not in seen[0].full_url and DIGEST[5:] not in seen[0].full_url


def test_a_password_not_in_the_list_passes(monkeypatch):
    _service(monkeypatch, "0000000000000000000000000000000000A:3\r\n", [])
    passwords.BreachedPasswordValidator().validate(PASSWORD)


def test_padding_entries_with_count_zero_do_not_refuse(monkeypatch):
    _service(monkeypatch, f"{DIGEST[5:]}:0\r\n", [])
    passwords.BreachedPasswordValidator().validate(PASSWORD)


def test_an_outage_accepts_the_password_and_logs_no_password(monkeypatch, caplog):
    def down(request, timeout):
        raise OSError("unreachable " + PASSWORD)

    monkeypatch.setattr(passwords.urllib.request, "urlopen", down)
    passwords.BreachedPasswordValidator().validate(PASSWORD)
    assert "breached-password check unavailable: OSError" in caplog.text
    assert PASSWORD not in caplog.text
