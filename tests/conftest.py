import os

import pytest

from tests.ssh_fakes import FakeBox, start_fake_box


@pytest.fixture
def sparkd_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SPARKD_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
async def fake_box():
    box = FakeBox()
    server, port = await start_fake_box(box)
    yield box, port
    server.close()
    await server.wait_closed()
