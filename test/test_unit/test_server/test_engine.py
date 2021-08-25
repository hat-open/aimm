from hat import aio
import pytest

from aimm.server import engine
from aimm.server import common
from aimm import plugins


pytestmark = pytest.mark.asyncio


class MockBackend(common.Backend):

    def __init__(self, models=None):
        self._group = aio.Group()
        self._models = models or []
        self._queue = aio.Queue()

    @property
    def async_group(self):
        return self._group

    @property
    def queue(self):
        return self._queue

    async def get_models(self):
        return self._models

    async def create_model(self, model):
        self._models.append(model)
        self._queue.put_nowait(('create', model))

    async def update_model(self, model):
        index = None
        for i, m in enumerate(self._models):
            if m.instance_id == model.instance_id:
                index = i
        if index is not None:
            self._models[index] = model
        self._queue.put_nowait(('update', model))


async def create_engine(backend=None, group=None):
    backend = backend or MockBackend()
    group = group or aio.Group()
    return await engine.create({'sigterm_timeout': 1,
                                'max_children': 1,
                                'check_children_period': 0.2},
                               backend, group)


async def test_empty():
    eng = await create_engine()
    assert eng.state == {'actions': {}, 'models': {}}
    await eng.async_close()


async def test_models_in_backend():
    models = {1: common.Model(instance=None, model_type='test', instance_id=1),
              2: common.Model(instance=None, model_type='test', instance_id=2)}
    eng = await create_engine(MockBackend(models.values()))
    assert eng.state == {'actions': {}, 'models': models}
    await eng.async_close()


@pytest.mark.timeout(2)
async def test_create_instance(plugin_teardown):
    backend = MockBackend()
    eng = await create_engine(backend)
    state_queue = aio.Queue()

    eng.subscribe_to_state_change(lambda: state_queue.put_nowait(eng.state))

    @plugins.instantiate('test')
    def create(*args, **kwargs):
        return 'test', args, kwargs

    args = (1, 2, 3)
    kwargs = {'p1': 4, 'p2': 5}
    action = eng.create_instance('test', *args, **kwargs)
    model_id = 1
    model = common.Model(instance=('test', args, kwargs),
                         instance_id=model_id,
                         model_type='test')
    await state_queue.get()
    while True:
        state = await state_queue.get()
        if model_id in state['models']:
            break
    assert state['models'][model_id] == model
    assert await action.wait_result() == model
    await backend.queue.get() == ('create', model)
    await eng.async_close()


@pytest.mark.timeout(2)
async def test_add_instance(plugin_teardown):
    backend = MockBackend()
    eng = await create_engine(backend)
    states = []

    queue = aio.Queue()

    def state_change_cb():
        states.append(eng.state)
        queue.put_nowait(True)
    eng.subscribe_to_state_change(state_change_cb)

    await eng.add_instance(None, 'test')
    await queue.get()

    instance_id = 1
    assert states == [{'actions': {},
                       'models': {instance_id: common.Model(
                           instance=None, model_type='test',
                           instance_id=instance_id)}}]
    await backend.queue.get() == ('create',
                                  common.Model(instance=None,
                                               model_type='test',
                                               instance_id=instance_id))
    await eng.async_close()


@pytest.mark.timeout(2)
async def test_fit(plugin_teardown):
    backend = MockBackend()
    eng = await create_engine(backend)

    queue = aio.Queue()

    def state_change_cb():
        queue.put_nowait(eng.state)
    eng.subscribe_to_state_change(state_change_cb)

    await eng.add_instance('instance', 'test')
    await queue.get()
    await backend.queue.get()

    @plugins.fit(['test'])
    def fit(*args, **kwargs):
        return ('instance_fitted', args, kwargs)

    args = (1, 2)
    kwargs = {'p1': 3, 'p2': 4}

    action = eng.fit(1, *args, **kwargs)
    expected_instance = common.Model(
        instance=('instance_fitted', ('instance', *args), kwargs),
        model_type='test',
        instance_id=1)
    await queue.get() == {'models': {1: common.Model(
                              instance=expected_instance,
                              model_type='test',
                              instance_id=1)}}
    model = await action.wait_result()
    assert model == expected_instance
    await backend.queue.get() == ('update',
                                  common.Model(instance=expected_instance,
                                               model_type='test',
                                               instance_id=1))

    # allow model lock to release
    await eng.async_close()


@pytest.mark.timeout(2)
async def test_predict(plugin_teardown):
    backend = MockBackend()
    eng = await create_engine(backend)

    queue = aio.Queue()

    def state_change_cb():
        queue.put_nowait(eng.state)
    eng.subscribe_to_state_change(state_change_cb)

    await eng.add_instance(['instance'], 'test')
    await queue.get()
    await backend.queue.get()

    @plugins.predict(['test'])
    def predict(instance, *args, **kwargs):
        instance.append(1)
        return (instance, args, kwargs)

    args = (1, 2)
    kwargs = {'p1': 3, 'p2': 4}

    action = eng.predict(1, *args, **kwargs)
    expected_instance = (['instance', 1], args, kwargs)
    await queue.get() == {'models': {1: common.Model(
                              instance=expected_instance,
                              model_type='test',
                              instance_id=1)}}
    result = await action.wait_result()
    assert result == expected_instance

    await eng.async_close()
