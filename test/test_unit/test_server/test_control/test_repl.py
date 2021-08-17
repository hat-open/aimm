from hat import aio
import asyncio
import pytest
import aimm.client.repl
import aimm.server.control.repl


pytestmark = pytest.mark.asyncio


_password_hash = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # NOQA


class MockEngine:
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


async def test_login(unused_tcp_port, monkeypatch):
    engine = MockEngine()
    engine.state = {'models': {}, 'actions': {}}
    async with aio.Group() as group:
        await aimm.server.control.repl.create(
            {'server': {'host': '127.0.0.1', 'port': unused_tcp_port},
             'users': [{
                 'username': 'user',
                 'password': _password_hash}]},
            engine, group, None)
        client = aimm.client.repl.AIMM()
        with monkeypatch.context() as ctx:
            aimm.client.repl.input = input
            ctx.setattr(aimm.client.repl, 'input', lambda _: 'user')
            ctx.setattr(aimm.client.repl, 'getpass', lambda _: 'password')
            await client.connect(f'ws://127.0.0.1:{unused_tcp_port}/ws')
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
    await asyncio.sleep(0.3)
    assert client.state is not None
    return client


async def test_create_instance(unused_tcp_port, monkeypatch):
    engine = MockEngine()
    engine.state = {'models': {}, 'actions': {}}
    async with aio.Group() as group:
        await aimm.server.control.repl.create(
            {'server': {'host': '127.0.0.1', 'port': unused_tcp_port},
             'users': [{
                 'username': 'user',
                 'password': _password_hash}]},
            engine, group, None)
        await _connect('user', 'password', unused_tcp_port, monkeypatch)
