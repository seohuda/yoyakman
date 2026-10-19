"""실수로 mock을 빠뜨려도 테스트가 외부 API에 연결되지 않게 한다."""

import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("테스트에서 네트워크 연결은 허용되지 않습니다.")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
