"""Shared fixtures. Every test runs with the network forbidden (B4 acceptance criterion 6)."""
import socket
import urllib.request

import pytest


class NetworkForbidden(AssertionError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    calls = []

    def _blocked_urlopen(*a, **k):
        calls.append(a)
        raise NetworkForbidden("network call attempted in a test: %r" % (a[:1],))

    def _blocked_connect(self, *a, **k):
        raise NetworkForbidden("socket connect attempted in a test")

    monkeypatch.setattr(urllib.request, "urlopen", _blocked_urlopen)
    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    yield calls
    assert not calls, "a code path called urllib.request.urlopen without injection"
