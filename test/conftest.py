from hat import aio
import asyncio
import pytest

from aimm import plugins


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    aio.init_asyncio()


@pytest.fixture
def plugin_teardown():
    yield
    plugins.unload_all()
