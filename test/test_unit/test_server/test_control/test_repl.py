from hat import aio
import asyncio
import hashlib
import pytest

from aimm import plugins
from aimm.server import common
import aimm.client.repl
import aimm.server.control.repl
import aimm.server.engine


pytestmark = pytest.mark.asyncio


class MockEngine(common.Engine):
    def __init__(self, state={'models': {}, 'actions': {}},
                 create_instance_cb=None, add_instance_cb=None,
                 update_instance_cb=None, fit_cb=None, predict_cb=None):
        self._state = state
        self._cb = lambda: None
        self._create_instance_cb = create_instance_cb
        self._add_instance_cb = add_instance_cb
        self._update_instance_cb = update_instance_cb
        self._fit_cb = fit_cb
        self._predict_cb = predict_cb
        self._group = aio.Group()

    @property
    def async_group(self):
        return self._group

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
            return aimm.server.engine._Action(
                self._group.create_subgroup(), aio.call,
                self._create_instance_cb, *args, **kwargs)
        raise NotImplementedError()

    async def add_instance(self, *args, **kwargs):
        if self._add_instance_cb:
            return await aio.call(self._add_instance_cb, *args, **kwargs)
        raise NotImplementedError()

    async def update_instance(self, *args, **kwargs):
        if self._update_instance_cb:
            return await aio.call(self._update_instance_cb, *args, **kwargs)
        raise NotImplementedError()

    def fit(self, *args, **kwargs):
        if self._fit_cb:
            return aimm.server.engine._Action(
                self._group.create_subgroup(), aio.call,
                self._fit_cb, *args, **kwargs)
        raise NotImplementedError()

    def predict(self, *args, **kwargs):
        if self._predict_cb:
            return aimm.server.engine._Action(
                self._group.create_subgroup(), aio.call,
                self._predict_cb, *args, **kwargs)
        raise NotImplementedError()


@pytest.fixture
def juggler_port(unused_tcp_port):
    return unused_tcp_port


@pytest.fixture
def conf(juggler_port):
    password_hash = hashlib.sha256()
    password_hash.update('password'.encode('utf-8'))
    return {'server': {'host': '127.0.0.1', 'port': juggler_port},
            'users': [{
                'username': 'user',
                'password': password_hash.hexdigest()}]}


async def test_login(conf, juggler_port, monkeypatch):
    engine = MockEngine()
    engine.state = {'models': {}, 'actions': {}}
    async with aio.Group() as group:
        await aimm.server.control.repl.create(conf, engine, group, None)
        client = aimm.client.repl.AIMM()
        with monkeypatch.context() as ctx:
            aimm.client.repl.input = input
            ctx.setattr(aimm.client.repl, 'input', lambda _: 'user')
            ctx.setattr(aimm.client.repl, 'getpass', lambda _: 'password')
            await client.connect(f'ws://127.0.0.1:{juggler_port}/ws')
        await asyncio.sleep(0.3)
        assert client.state == {'models': {}, 'actions': {}}
        await client.async_close()


async def _connect(username, password, port, monkeypatch):
    client = aimm.client.repl.AIMM()
    with monkeypatch.context() as ctx:
        aimm.client.repl.input = input
        ctx.setattr(aimm.client.repl, 'input', lambda _: username)
        ctx.setattr(aimm.client.repl, 'getpass', lambda _: password)
        await client.connect(f'ws://127.0.0.1:{port}/ws')
    return client


@pytest.fixture
def plugins_model1(plugin_teardown):

    @plugins.serialize(['Model1'])
    def serialize1(instance):
        return instance.encode('utf-8')

    @plugins.deserialize(['Model1'])
    def deserialize1(instance_bytes):
        return instance_bytes.decode('utf-8')

    yield


async def test_create_instance(plugins_model1, conf, juggler_port,
                               monkeypatch):

    create_queue = aio.Queue()

    async def create_instance_cb(model_type, *args, **kwargs):
        done_future = asyncio.Future()
        create_queue.put_nowait({'model_type': model_type,
                                 'args': args,
                                 'kwargs': kwargs,
                                 'done_future': done_future})
        return await done_future

    engine = MockEngine(create_instance_cb=create_instance_cb)
    async with aio.Group() as group:
        await aimm.server.control.repl.create(conf, engine, group, None)
        client = await _connect('user', 'password', juggler_port, monkeypatch)

        args = ['a1', 'a2']
        kwargs = {'k1': '1'}
        task = group.spawn(client.create_instance, 'Model1', *args, **kwargs)
        call = await create_queue.get()
        assert call['model_type'] == 'Model1'
        assert call['args'] == tuple(args)
        assert call['kwargs'] == kwargs

        call['done_future'].set_result(common.Model(instance='xyz',
                                                    instance_id=1,
                                                    model_type='Model1'))
        model = await task
        assert model


async def test_add_instance(plugins_model1, conf, juggler_port, monkeypatch):

    add_queue = aio.Queue()

    async def add_instance_cb(instance, model_type):
        done_future = asyncio.Future()
        add_queue.put_nowait({'instance': instance,
                              'model_type': model_type,
                              'done_future': done_future})
        return await done_future

    engine = MockEngine(add_instance_cb=add_instance_cb)
    async with aio.Group() as group:
        await aimm.server.control.repl.create(conf, engine, group, None)
        client = await _connect('user', 'password', juggler_port, monkeypatch)

        task = group.spawn(client.add_instance, 'Model1', 'xyz')
        call = await add_queue.get()
        assert call['instance'] == 'xyz'
        assert call['model_type'] == 'Model1'

        call['done_future'].set_result(common.Model(instance='xyz',
                                                    instance_id=1,
                                                    model_type='Model1'))
        model = await task
        assert model


async def test_fit(plugins_model1, conf, juggler_port, monkeypatch):

    fit_queue = aio.Queue()

    async def fit_cb(instance_id, *args, **kwargs):
        done_future = asyncio.Future()
        fit_queue.put_nowait({'instance_id': instance_id,
                              'args': args,
                              'kwargs': kwargs,
                              'done_future': done_future})
        return await done_future

    engine = MockEngine(fit_cb=fit_cb)
    async with aio.Group() as group:
        await aimm.server.control.repl.create(conf, engine, group, None)
        client = await _connect('user', 'password', juggler_port, monkeypatch)

        args = ['a1', 'a2']
        kwargs = {'k1': '1'}
        task = group.spawn(client.fit, 1, *args, **kwargs)
        call = await fit_queue.get()
        assert call['instance_id'] == 1
        assert call['args'] == tuple(args)
        assert call['kwargs'] == kwargs

        call['done_future'].set_result(common.Model(instance='xyz',
                                                    instance_id=1,
                                                    model_type='Model1'))
        model = await task
        assert model


async def test_predict(plugins_model1, conf, juggler_port, monkeypatch):

    predict_queue = aio.Queue()

    async def predict_cb(instance_id, *args, **kwargs):
        done_future = asyncio.Future()
        predict_queue.put_nowait({'instance_id': instance_id,
                                  'args': args,
                                  'kwargs': kwargs,
                                  'done_future': done_future})
        return await done_future

    engine = MockEngine(predict_cb=predict_cb)
    async with aio.Group() as group:
        await aimm.server.control.repl.create(conf, engine, group, None)
        client = await _connect('user', 'password', juggler_port, monkeypatch)

        args = ['a1', 'a2']
        kwargs = {'k1': '1'}
        task = group.spawn(client.predict, 1, *args, **kwargs)
        call = await predict_queue.get()
        assert call['instance_id'] == 1
        assert call['args'] == tuple(args)
        assert call['kwargs'] == kwargs

        call['done_future'].set_result([1, 2, 3, 4])
        assert await task == [1, 2, 3, 4]
