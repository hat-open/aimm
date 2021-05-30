import asyncio
import base64
from hat import aio
import hat.event.common
import pytest

import aimm.server.control.event
from aimm.server import common
from aimm import plugins


pytestmark = pytest.mark.asyncio


class MockClient:

    def __init__(self):
        self._register_queue = aio.Queue()
        self._receive_queue = aio.Queue()

    def register(self, events):
        self._register_queue.put_nowait(events)

    async def receive(self):
        return await self._receive_queue.get()


class MockEngine:
    def __init__(self, state={'models': {}, 'actions': {}},
                 create_instance_cb=None, add_instance_cb=None,
                 update_instance_cb=None, fit_cb=None, predict_cb=None):
        self._state = state
        self._cb = None
        self._create_instance_cb = create_instance_cb
        self._add_instance_cb = add_instance_cb
        self._update_instance_cb = update_instance_cb
        self._fit_cb = fit_cb
        self._predict_cb = predict_cb

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self._state = value
        self._cb()

    def subscribe_to_state_change(self, cb):
        self._cb = cb

    def create_instance(self, *args, **kwargs):
        if self._create_instance_cb:
            return self._create_instance_cb(*args, **kwargs)
        raise NotImplementedError()

    def add_instance(self, *args, **kwargs):
        if self._add_instance_cb:
            return self._add_instance_cb(*args, **kwargs)
        raise NotImplementedError()

    def update_instance(self, *args, **kwargs):
        if self._update_instance_cb:
            return self._update_instance_cb(*args, **kwargs)
        raise NotImplementedError()

    def fit(self, *args, **kwargs):
        if self._fit_cb:
            return self._fit_cb(*args, **kwargs)
        raise NotImplementedError()

    def predict(self, *args, **kwargs):
        if self._predict_cb:
            return self._predict_cb(*args, **kwargs)
        raise NotImplementedError()


def assert_event(event, event_type, payload, source_timestamp=None):
    assert event.event_type == event_type
    assert event.source_timestamp == source_timestamp
    assert event.payload.data == payload


@pytest.mark.timeout(1)
async def test_state():
    client = MockClient()
    engine = MockEngine()
    async with aio.Group() as group:
        control = await aimm.server.control.event.create(
            {'event_prefixes': _prefixes(),
             'state_event_type': ['state'],
             'response_event_type': []},
            engine, group, client)
        events = await client._register_queue.get()
        assert len(events) == 1
        assert_event(events[0], ('state', ), {'models': {}, 'actions': {}})

        await control.async_close()


@pytest.mark.timeout(1)
async def test_create_instance():

    create_queue = aio.Queue()

    def create_instance_cb(model_type, *args, **kwargs):
        complete_future = asyncio.Future()
        create_queue.put_nowait({'model_type': model_type,
                                 'args': args,
                                 'kwargs': kwargs,
                                 'complete_future': complete_future})
        return complete_future

    client = MockClient()
    engine = MockEngine(create_instance_cb=create_instance_cb)
    async with aio.Group() as group:
        control = await aimm.server.control.event.create(
            {'event_prefixes': _prefixes(),
             'state_event_type': ['state'],
             'response_event_type': ['response']},
            engine, group, client)

        events = await client._register_queue.get()  # state

        args = ['a1', 'a2']
        kwargs = {'k1': '1'}
        client._receive_queue.put_nowait([_event(('create_instance', ),
                                                 {'model_type': 'Model1',
                                                  'args': args,
                                                  'kwargs': kwargs,
                                                  'request_id': '1'})])
        call = await create_queue.get()
        assert call['model_type'] == 'Model1'
        assert call['args'] == tuple(args)
        assert call['kwargs'] == kwargs

        call['complete_future'].set_result(common.Model(instance=None,
                                                        instance_id=1,
                                                        model_type='model'))
        events = await client._register_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('response',)
        assert event.payload.data == {'request_id': '1', 'result': 1}

        await control.async_close()


@pytest.mark.timeout(10)
async def test_add_instance(plugin_teardown):

    @plugins.deserialize(['Model1'])
    def deserialize(instance_bytes):
        return instance_bytes.decode('utf-8')

    add_queue = aio.Queue()

    def add_instance_cb(instance, model_type):
        add_queue.put_nowait({'instance': instance, 'model_type': model_type})
        return common.Model(instance=instance,
                            instance_id=2,
                            model_type=model_type)

    client = MockClient()
    engine = MockEngine(add_instance_cb=add_instance_cb)
    async with aio.Group() as group:
        control = await aimm.server.control.event.create(
            {'event_prefixes': _prefixes(),
             'state_event_type': ['state'],
             'response_event_type': ['response']},
            engine, group, client)

        events = await client._register_queue.get()  # state

        client._receive_queue.put_nowait([
            _event(('add_instance', ),
                   {'model_type': 'Model1',
                    'instance': base64.b64encode(
                        'xyz'.encode('utf-8')).decode('utf-8'),
                    'request_id': '1'})])

        call = await add_queue.get()
        assert call['model_type'] == 'Model1'
        assert call['instance'] == 'xyz'

        events = await client._register_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('response',)
        assert event.payload.data == {'request_id': '1', 'result': 2}

        await control.async_close()


@pytest.mark.timeout(1)
async def test_update_instance(plugin_teardown):

    @plugins.deserialize(['Model1'])
    def deserialize(instance_bytes):
        return instance_bytes.decode('utf-8')

    update_queue = aio.Queue()

    async def update_instance_cb(model):
        update_queue.put_nowait(model)
        return model

    client = MockClient()
    engine = MockEngine(update_instance_cb=update_instance_cb)
    async with aio.Group() as group:
        control = await aimm.server.control.event.create(
            {'event_prefixes': _prefixes(),
             'state_event_type': ['state'],
             'response_event_type': ['response']},
            engine, group, client)

        events = await client._register_queue.get()  # state

        client._receive_queue.put_nowait([
            _event(('update_instance', '10'),
                   {'model_type': 'Model1',
                    'instance': base64.b64encode(
                        'xyz'.encode('utf-8')).decode('utf-8'),
                    'request_id': '1'})])

        model = await update_queue.get()
        assert model == common.Model(model_type='Model1',
                                     instance='xyz',
                                     instance_id=10)

        events = await client._register_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('response',)
        assert event.payload.data == {'request_id': '1', 'result': True}

        await control.async_close()


@pytest.mark.timeout(1)
async def test_fit():

    fit_queue = aio.Queue()

    async def fit_cb(model_id, *args, **kwargs):
        done_future = asyncio.Future()
        fit_queue.put_nowait({'done_future': done_future,
                              'args': args,
                              'kwargs': kwargs,
                              'model_id': model_id})
        return done_future

    client = MockClient()
    engine = MockEngine({'models': {11: common.Model('M', None, 11)},
                         'actions': {}},
                        fit_cb=fit_cb)
    async with aio.Group() as group:
        control = await aimm.server.control.event.create(
            {'event_prefixes': _prefixes(),
             'state_event_type': ['state'],
             'response_event_type': ['response']},
            engine, group, client)

        events = await client._register_queue.get()  # state

        client._receive_queue.put_nowait([
            _event(('fit', '11'),
                   {'args': ['a', 'b'],
                    'kwargs': {'c': 'd', 'e': 'f'},
                    'request_id': '1'})])

        call = await fit_queue.get()
        assert call['model_id'] == 11
        assert call['args'] == ('a', 'b')
        assert call['kwargs'] == {'c': 'd', 'e': 'f'}

        call['done_future'].set_result('fitted instance')

        events = await client._register_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('response',)
        assert event.payload.data == {'request_id': '1', 'result': True}

        await control.async_close()


@pytest.mark.timeout(1)
async def test_predict():

    predict_queue = aio.Queue()

    async def predict_cb(model_id, *args, **kwargs):
        done_future = asyncio.Future()
        predict_queue.put_nowait({'done_future': done_future,
                                  'args': args,
                                  'kwargs': kwargs,
                                  'model_id': model_id})
        return done_future

    client = MockClient()
    engine = MockEngine({'models': {12: common.Model('M', None, 12)},
                         'actions': {}},
                        predict_cb=predict_cb)
    async with aio.Group() as group:
        control = await aimm.server.control.event.create(
            {'event_prefixes': _prefixes(),
             'state_event_type': ['state'],
             'response_event_type': ['response']},
            engine, group, client)

        events = await client._register_queue.get()  # state

        client._receive_queue.put_nowait([
            _event(('predict', '12'),
                   {'args': ['a', 'b'],
                    'kwargs': {'c': 'd', 'e': 'f'},
                    'request_id': '1'})])

        call = await predict_queue.get()
        assert call['model_id'] == 12
        assert call['args'] == ('a', 'b')
        assert call['kwargs'] == {'c': 'd', 'e': 'f'}

        call['done_future'].set_result('prediction')

        events = await client._register_queue.get()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('response',)
        assert event.payload.data == {'request_id': '1',
                                      'result': 'prediction'}

        await control.async_close()


def _register_event(event_type, payload, source_timestamp=None):
    return hat.event.common.RegisterEvent(
        event_type=event_type,
        source_timestamp=source_timestamp,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=payload))


def _event(event_type, payload, source_timestamp=None,
           event_id=hat.event.common.EventId(server=0, instance=0)):
    return hat.event.common.Event(
        event_id=event_id,
        event_type=event_type,
        timestamp=hat.event.common.now(),
        source_timestamp=source_timestamp,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=payload))


def _prefixes():
    return {'create_instance': ['create_instance'],
            'add_instance': ['add_instance'],
            'update_instance': ['update_instance'],
            'fit': ['fit'],
            'predict': ['predict']}
