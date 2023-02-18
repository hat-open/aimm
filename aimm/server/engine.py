from functools import partial
from hat import aio
from hat import util
import asyncio
import itertools
import logging
import typing

from aimm import plugins
from aimm.server import common
from aimm.server import mprocess


mlog = logging.getLogger(__name__)


async def create(
    conf: typing.Dict, backend: common.Backend, group: aio.Group
) -> common.Engine:
    """Create engine

    Args:
        conf: configuration that follows schema with id
            ``aimm://server/schema.yaml#/definitions/engine``
        backend: backend
        group: async group

    Returns:
        engine
    """
    engine = _Engine()

    models = await backend.get_models()

    engine._group = group
    engine._backend = backend
    engine._conf = conf
    engine._state = {
        "actions": {},
        "models": {model.instance_id: model for model in models},
    }
    engine._locks = {
        instance_id: asyncio.Lock() for instance_id in engine._state["models"]
    }

    engine._action_id_gen = itertools.count(1)

    engine._pool = mprocess.ProcessManager(
        conf["max_children"],
        group.create_subgroup(),
        conf["check_children_period"],
        conf["sigterm_timeout"],
    )
    engine._callback_registry = util.CallbackRegistry()

    return engine


class _Engine(common.Engine):
    """Engine implementation, use :func:`create` to instantiate"""

    @property
    def async_group(self):
        return self._group

    @property
    def state(self):
        return self._state

    def subscribe_to_state_change(self, cb):
        return self._callback_registry.register(cb)

    def create_instance(self, model_type, *args, **kwargs):
        action_id = next(self._action_id_gen)
        state_cb = partial(self._update_action, action_id)
        return _Action(
            self._group.create_subgroup(),
            self._act_create_instance,
            model_type,
            args,
            kwargs,
            state_cb,
        )

    async def add_instance(self, model_type, instance):
        model = await self._backend.create_model(model_type, instance)
        self._set_model(model)
        return model

    async def update_instance(self, model: common.Model):
        """Update existing instance in the state"""
        self._set_model(model)
        await self._backend.update_model(model)

    def fit(self, instance_id, *args, **kwargs):
        action_id = next(self._action_id_gen)
        state_cb = partial(self._update_action, action_id)
        return _Action(
            self._group.create_subgroup(),
            self._act_fit,
            instance_id,
            args,
            kwargs,
            state_cb,
        )

    def predict(self, instance_id, *args, **kwargs):
        action_id = next(self._action_id_gen)
        state_cb = partial(self._update_action, action_id)
        return _Action(
            self._group.create_subgroup(),
            self._act_predict,
            instance_id,
            args,
            kwargs,
            state_cb,
        )

    def _update_action(self, action_id, action_state):
        actions = dict(self.state["actions"])
        actions.update({action_id: action_state})
        self._update_state(dict(self.state, actions=actions))

    def _set_model(self, model):
        if model.instance_id not in self._locks:
            self._locks[model.instance_id] = asyncio.Lock()
        models = dict(self.state["models"])
        models.update({model.instance_id: model})
        self._update_state(dict(self.state, models=models))

    def _update_state(self, new_state):
        self._state = new_state
        self._callback_registry.notify()

    async def _act_create_instance(self, model_type, args, kwargs, state_cb):
        reactive = _ReactiveState(
            {
                "meta": {
                    "call": "create_instance",
                    "model_type": model_type,
                    "args": [str(a) for a in args],
                    "kwargs": {k: str(v) for k, v in kwargs.items()},
                }
            }
        )
        reactive.register_state_change_cb(lambda: state_cb(reactive.state))

        reactive.update(dict(reactive.state, progress="accessing_data"))
        args, kwargs = await _derive_data_access_args(
            self._pool, args, kwargs, reactive.register_substate("data_access")
        )

        reactive.update(dict(reactive.state, progress="executing"))
        handler = self._pool.create_handler(
            reactive.register_substate("action").update
        )
        instance = await handler.run(
            plugins.exec_instantiate,
            model_type,
            handler.proc_notify_state_change,
            *args,
            **kwargs
        )

        reactive.update(dict(reactive.state, progress="storing"))
        model = await self._backend.create_model(model_type, instance)
        self._set_model(model)

        reactive.update(dict(reactive.state, progress="complete"))

        return model

    async def _act_fit(self, instance_id, args, kwargs, state_cb):
        reactive = _ReactiveState(
            {
                "meta": {
                    "call": "fit",
                    "model": instance_id,
                    "args": [str(a) for a in args],
                    "kwargs": {k: str(v) for k, v in kwargs.items()},
                }
            }
        )
        reactive.register_state_change_cb(lambda: state_cb(reactive.state))

        reactive.update(dict(reactive.state, progress="accessing_data"))
        args, kwargs = await _derive_data_access_args(
            self._pool, args, kwargs, reactive.register_substate("data_access")
        )

        reactive.update(dict(reactive.state, progress="executing"))
        handler = self._pool.create_handler(
            reactive.register_substate("action").update
        )

        model = self.state["models"][instance_id]
        async with self._locks[instance_id]:
            instance = await handler.run(
                plugins.exec_fit,
                model.model_type,
                model.instance,
                handler.proc_notify_state_change,
                *args,
                **kwargs
            )
        new_model = model._replace(instance=instance)

        reactive.update(dict(reactive.state, progress="storing"))
        await self._backend.update_model(new_model)

        reactive.update(dict(reactive.state, progress="complete"))
        self._set_model(new_model)
        return new_model

    async def _act_predict(self, instance_id, args, kwargs, state_cb):
        reactive = _ReactiveState(
            {
                "meta": {
                    "call": "predict",
                    "model": instance_id,
                    "args": [str(a) for a in args],
                    "kwargs": {k: str(v) for k, v in kwargs.items()},
                }
            }
        )
        reactive.register_state_change_cb(lambda: state_cb(reactive.state))

        reactive.update(dict(reactive.state, progress="accessing_data"))
        args, kwargs = await _derive_data_access_args(
            self._pool, args, kwargs, reactive.register_substate("data_access")
        )

        handler = self._pool.create_handler(
            reactive.register_substate("action").update
        )
        async with self._locks[instance_id]:
            model = self.state["models"][instance_id]
            prediction = await handler.run(
                plugins.exec_predict,
                model.model_type,
                model.instance,
                handler.proc_notify_state_change,
                *args,
                **kwargs
            )
        reactive.update(dict(reactive.state, progress="complete"))
        return prediction


class _Action(common.Action):
    def __init__(self, async_group, fn, *args, **kwargs):
        self._group = async_group
        self._task = self._group.spawn(fn, *args, **kwargs)

    @property
    def async_group(self):
        return self._group

    async def wait_result(self):
        return await self._task


async def _derive_data_access_args(pool, args, kwargs, reactive_state):
    actions = {}
    async with aio.Group() as group:
        for i, arg in enumerate(args):
            if not isinstance(arg, common.DataAccess):
                continue
            actions[i] = group.spawn(
                _get_data_access_action, pool, reactive_state, i, arg
            )
        for key, value in kwargs.items():
            if not isinstance(value, common.DataAccess):
                continue
            actions[key] = group.spawn(
                _get_data_access_action, pool, reactive_state, i, arg
            )

        if actions:
            await asyncio.wait([task for task in actions.values()])
            args = list(args)
            for key, task in actions.items():
                if isinstance(key, int):
                    args[key] = task.result()
                elif isinstance(key, str):
                    kwargs[key] = task.result()
    return args, kwargs


async def _get_data_access_action(pool, reactive_state, key, data_access):
    handler = pool.create_handler(reactive_state.register_substate(key).update)
    return await handler.run(
        plugins.exec_data_access,
        data_access.name,
        handler.proc_notify_state_change,
        *data_access.args,
        **data_access.kwargs
    )


class _ReactiveState:
    def __init__(self, state):
        self._state = state
        self._substates = {}
        self._cb_registry = util.CallbackRegistry()

    @property
    def state(self):
        return self._state

    def register_state_change_cb(self, cb):
        return self._cb_registry.register(cb)

    def update(self, state):
        self._state = state
        self._cb_registry.notify()

    def register_substate(self, key):
        reactive = _ReactiveState(self._state.get(key, {}))
        reactive.register_state_change_cb(
            partial(self._on_substate_change, key)
        )
        self._substates[key] = reactive
        return reactive

    def _on_substate_change(self, key):
        self._state = {**self._state, **{key: self._substates[key].state}}
        self._cb_registry.notify()
