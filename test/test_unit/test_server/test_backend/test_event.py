from hat import aio
import base64
import pytest

from aimm.server.backend import event
from aimm.server import common
from aimm import plugins


pytestmark = pytest.mark.asyncio


class MockClient:

    def __init__(self, query_result=[]):
        self._query_result = query_result
        self._query_queue = aio.Queue()
        self._register_queue = aio.Queue()

    async def query(self, query_data):
        self._query_queue.put_nowait(query_data)
        return self._query_result

    async def register_with_response(self, events):
        self._register_queue.put_nowait(events)
        return events


@pytest.fixture
def string_plugins(plugin_teardown):

    @plugins.serialize(['type'])
    def serialize_type(instance):
        return instance.encode('utf-8')

    @plugins.deserialize(['type'])
    def deserialize_type(instance_bytes):
        return instance_bytes.decode('utf-8')


async def test_create_model(string_plugins):
    mock_client = MockClient()
    async with aio.Group() as group:
        backend = await event.create({'model_prefix': ['model']}, group,
                                     mock_client)
        assert await backend.get_models() == []

        await backend.create_model(common.Model(instance='instance',
                                                model_type='type',
                                                instance_id=1))
        events = await mock_client._register_queue.get()
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == ('model', '1')
        assert ev.source_timestamp is None
        exp_instance_bytes = 'instance'.encode('utf-8')
        assert ev.payload.data == {
            'type': 'type',
            'instance': base64.b64encode(exp_instance_bytes).decode('utf-8')}


async def test_get_models(string_plugins):
    mock_client = MockClient()
    async with aio.Group() as group:
        backend = await event.create({'model_prefix': ['model']}, group,
                                     mock_client)
        assert await backend.get_models() == []

        await backend.create_model(common.Model(instance='instance',
                                                model_type='type',
                                                instance_id=1))
        events = await mock_client._register_queue.get()
        mock_client._query_result = events

        models = await backend.get_models()
        assert len(models) == 1
        model = models[0]
        assert model.instance == 'instance'
        assert model.model_type == 'type'
        assert model.instance_id == 1


async def test_update_model(string_plugins):
    mock_client = MockClient()
    async with aio.Group() as group:
        backend = await event.create({'model_prefix': ['model']}, group,
                                     mock_client)
        assert await backend.get_models() == []

        await backend.create_model(common.Model(instance='instance',
                                                model_type='type',
                                                instance_id=1))
        await mock_client._register_queue.get()

        await backend.update_model(common.Model(instance='instance2',
                                                model_type='type',
                                                instance_id=1))
        events = await mock_client._register_queue.get()
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == ('model', '1')
        assert ev.source_timestamp is None
        exp_instance_bytes = 'instance2'.encode('utf-8')
        assert ev.payload.data == {
            'type': 'type',
            'instance': base64.b64encode(exp_instance_bytes).decode('utf-8')}
