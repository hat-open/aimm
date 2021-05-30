from hat import aio
import pytest

from aimm.server.backend import sqlite
from aimm.server import common
from aimm import plugins


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def backend(tmp_path):
    backend = await sqlite.create({'path': str(tmp_path / 'backend.db')},
                                  aio.Group(), None)
    yield backend
    await backend.async_close()


async def test_create(tmp_path):
    backend = await sqlite.create({'path': str(tmp_path / 'backend.db')},
                                  aio.Group(), None)
    assert backend
    await backend.async_close()


async def test_models(backend, plugin_teardown):
    @plugins.serialize(['test'])
    def serialize(instance):
        return instance.encode('utf-8')

    @plugins.deserialize(['test'])
    def deserialize(instance_blob):
        return instance_blob.decode('utf-8')

    model = common.Model(instance_id=1, instance='instance', model_type='test')
    await backend.create_model(model)
    assert await backend.get_models() == [model]

    model_updated = model._replace(instance='instance2')
    await backend.update_model(model_updated)
    assert await backend.get_models() == [model_updated]
