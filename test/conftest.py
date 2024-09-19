from hat import aio
import pytest

from aimm import plugins


def pytest_configure():
    aio.init_asyncio()


@pytest.fixture
def plugin_teardown():
    yield
    plugins.unload_all()
