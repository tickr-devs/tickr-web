"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def _no_breach_service(monkeypatch, request):
    """Tests never call the breached-password service; test_passwords.py fakes its answers."""
    if request.module.__name__.endswith("test_passwords"):
        return
    monkeypatch.setattr("tickrweb.passwords.times_breached", lambda password: 0)
