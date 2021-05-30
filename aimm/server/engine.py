import asyncio
from functools import partial
import itertools
from hat import aio
from hat import util
import logging

from aimm import plugins
from aimm.server import common
from aimm.server import mprocess

from typing import Dict, Callable, Any


mlog = logging.getLogger(__name__)


async def create(conf: Dict,
                 backend: common.Backend,
                 group: aio.Group) -> 'Engine':
    """Create engine

    Args:
        conf: configuration that follows schema with id
            ``aimm://server/main.yaml#/definitions/engine``
        backend: backend
        group: async group

    Returns:
        Engine
    """
    engine = Engine()

    models = await backend.get_models()

    engine._group = group
    engine._backend = backend
    engine._conf = conf
    engine._state = {'actions': {},
                     'models': {model.instance_id: model for model in models}}
    engine._locks = {instance_id: asyncio.Lock()
                     for instance_id in engine._state['models']}

    engine._instance_id_gen = itertools.count(
        max(engine._state['models'], default=0) + 1)
    engine._action_id_gen = itertools.count()

    engine._pool = mprocess.ProcessManager(
        conf['max_children'], group.create_subgroup(),
        conf['check_children_period'], conf['sigterm_timeout'])
    engine._callback_registry = util.CallbackRegistry()

    return engine


class Engine(aio.Resource):
    """Engine class, use :func:`create` to instantiate"""

    @property
    def async_group(self) -> aio.Group:
        return self._group

    @property
    def state(self) -> Dict:
        """Engine state, contains references to all models and actions. It's
        never modified in-place, instead :meth:`subscribe_to_state_change`
        should be used"""
        return self._state

    def subscribe_to_state_change(
            self,
            cb: Callable[[], None]) -> util.CallbackRegistry:
        """Subscribes to any changes to the engine state

        Args:
            cb: callback, called when state changes

        Returns:
            Handle for cancelling subscription"""
        return self._callback_registry.register(cb)

    def create_instance(self,
                        model_type: str,
                        *args: Any,
                        **kwargs: Any) -> asyncio.Task:
        """Creates a model instance and stores it in state

        Args:
            model_type: model type
            *args: instantiation arguments
            **kwargs: instantiation keyword arguments

        Returns
            Reference to the action in charge of the managable call. Result of
            the task is model instance"""
        action_id = next(self._action_id_gen)
        instance_id = next(self._instance_id_gen)
        state_cb = partial(self._update_action, action_id)
        state_cb(None)
        task = self.async_group.spawn(_create_instance, self._pool, model_type,
                                      instance_id, args, kwargs, state_cb)

        def on_complete(result_future):
            try:
                model = result_future.result()
            except asyncio.CancelledError:
                return
            except Exception:
                return
            self._set_model(model)
            self._group.spawn(self._backend.create_model, model)
        task.add_done_callback(on_complete)

        return task

    def add_instance(self,
                     instance: Any,
                     model_type: str) -> common.Model:
        """Adds existing instance to the state

        Args:
            instance: model instance
            model_type: model type

        Returns:
            Created model"""
        model = common.Model(instance=instance,
                             model_type=model_type,
                             instance_id=next(self._instance_id_gen))
        self._set_model(model)
        self._group.spawn(self._backend.create_model, model)
        return model

    async def update_instance(self, model: common.Model):
        """Update existing instance in the state

        Args:
            model: model"""
        self._set_model(model)

    async def fit(self,
                  instance_id: int,
                  *args: Any,
                  **kwargs: Any) -> asyncio.Task:
        """Fits an existing model instance. The used fitting function is the
        one assigned to the model type. The instance, while it is being fitted,
        is not accessable by any of the other functions that would use it
        (other calls to fit, predictions, etc.).

        Args:
            instance_id: id of model instance that will be fitted
            *args: arguments to pass to the fitting function - if of type
                :class:`aimm.server.common.DataAccess`, the value passed to the
                fitting function is the result of the call to that plugin,
                other arguments are passed directly
            **kwargs: keyword arguments, work the same as the positional
                arguments

        Returns:
            Reference to the task calling the fitting function, result of the
            task is updated model instance
        """
        instance_lock = self._locks[instance_id]
        await instance_lock.acquire()
        model = self.state['models'][instance_id]

        action_id = next(self._action_id_gen)
        state_cb = partial(self._update_action, action_id)
        state_cb({})
        task = self.async_group.spawn(
            _fit, self._pool, model, args, kwargs, state_cb)

        def on_complete(result_future):
            try:
                new_model = result_future.result()
            except asyncio.CancelledError:
                return
            except Exception:
                return

            self._set_model(new_model)
            save_task = self._group.spawn(self._backend.update_model,
                                          new_model)
            save_task.add_done_callback(lambda _: instance_lock.release())
        task.add_done_callback(on_complete)

        return task

    async def predict(self,
                      instance_id: int,
                      *args: Any,
                      **kwargs: Any) -> asyncio.Task:
        """Uses an existing model instance to perform a prediction. The used
        prediction function is the one assigned to model's type. The instance,
        while prediction is called, is not accessable by any of the other
        functions that would use it (other calls to predict, fittings, etc.).
        If instance has changed while predicting, it is updated in the state
        and database.

        Args:
            instance_id: id of the model instance used for prediction
            *args: arguments to pass to the predict function - if of type
                :class:`aimm.server.common.DataAccess`, the value passed to the
                predict function is the result of the call to that plugin,
                other arguments are passed directly
            **kwargs: keyword arguments, work the same as the positional
                arguments

        Returns:
            Reference to task of the managable predict call, result of it is
            the model's prediction
        """
        instance_lock = self._locks[instance_id]
        await instance_lock.acquire()
        model = self.state['models'][instance_id]

        action_id = next(self._action_id_gen)
        state_cb = partial(self._update_action, action_id)
        state_cb({})
        task = self.async_group.spawn(
            _predict, self._pool, model, args, kwargs, state_cb)

        def on_complete(_):
            self._update_state(self.state)  # TODO try to remove this
            instance_lock.release()
        task.add_done_callback(on_complete)

        return task

    def _update_action(self, action_id, action_state):
        actions = dict(self.state['actions'])
        actions.update({action_id: action_state})
        self._update_state(dict(self.state, actions=actions))

    def _set_model(self, model):
        if model.instance_id not in self._locks:
            self._locks[model.instance_id] = asyncio.Lock()
        models = dict(self.state['models'])
        models.update({model.instance_id: model})
        self._update_state(dict(self.state, models=models))

    def _update_state(self, new_state):
        self._state = new_state
        self._callback_registry.notify()


async def _create_instance(pool, model_type, instance_id, args, kwargs,
                           state_cb):
    composite = _CompositeState({'meta': {'call': 'create_instance',
                                          'model_type': model_type,
                                          'args': args,
                                          'kwargs': kwargs}})
    composite.register_state_change_cb(lambda: state_cb(composite.state))

    composite.update(dict(composite.state, progress='accessing_data'))
    args, kwargs = await _derive_data_access_args(
        pool, args, kwargs, composite.register_substate('data_access'))

    composite.update(dict(composite.state, progress='executing'))
    handler = pool.create_handler(composite.register_substate('action').update)
    handler.run(
        plugins.exec_instantiate,
        model_type, handler.proc_notify_state_change, *args, **kwargs)
    instance = await handler.result
    composite.update(dict(composite.state, progress='complete'))

    return common.Model(instance=instance,
                        model_type=model_type,
                        instance_id=instance_id)


async def _fit(pool, model, args, kwargs, state_cb):
    composite = _CompositeState({'meta': {'call': 'fit',
                                          'model': model.instance_id,
                                          'args': args,
                                          'kwargs': kwargs}})
    composite.register_state_change_cb(lambda: state_cb(composite.state))

    composite.update(dict(composite.state, progress='accessing_data'))
    args, kwargs = await _derive_data_access_args(
        pool, args, kwargs, composite.register_substate('data_access'))

    composite.update(dict(composite.state, progress='executing'))
    handler = pool.create_handler(composite.register_substate('action').update)
    handler.run(
        plugins.exec_fit,
        model.model_type, model.instance, handler.proc_notify_state_change,
        *args, **kwargs)
    instance = await handler.result
    composite.update(dict(composite.state, progress='complete'))

    return model._replace(instance=instance)


async def _predict(pool, model, args, kwargs, state_cb):
    composite = _CompositeState({'meta': {'call': 'predict',
                                          'model': model.instance_id,
                                          'args': args,
                                          'kwargs': kwargs}})
    composite.register_state_change_cb(lambda: state_cb(composite.state))

    composite.update(dict(composite.state, progress='accessing_data'))
    args, kwargs = await _derive_data_access_args(
        pool, args, kwargs, composite.register_substate('data_access'))

    handler = pool.create_handler(composite.register_substate('action').update)
    handler.run(
        plugins.exec_predict,
        model.model_type, model.instance, handler.proc_notify_state_change,
        *args, **kwargs)
    prediction = await handler.result
    mlog.warning(prediction)
    composite.update(dict(composite.state, progress='complete'))
    return prediction


async def _derive_data_access_args(pool, args, kwargs, composite_state):
    actions = {}
    for i, arg in enumerate(args):
        if not isinstance(arg, common.DataAccess):
            continue
        actions[i] = _get_data_access_action(pool, composite_state, i, arg)
    for key, value in kwargs.items():
        if not isinstance(value, common.DataAccess):
            continue
        actions[key] = _get_data_access_action(pool, composite_state, key,
                                               value)

    if actions:
        await asyncio.wait([proc.result for proc in actions.values()
                            if not proc.result.done()])
        args = list(args)
        for key, proc in actions.items():
            if isinstance(key, int):
                args[key] = proc.result.result()
            elif isinstance(key, str):
                kwargs[key] = proc.result.result()
    return args, kwargs


def _get_data_access_action(pool, composite_state, key, data_access):
    handler = pool.create_handler(
        composite_state.register_substate(key).update)
    handler.run(
        plugins.exec_data_access,
        data_access.name, handler.proc_notify_state_change,
        *data_access.args, **data_access.kwargs)
    return handler


class _CompositeState:
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
        composite = _CompositeState(self._state.get(key, {}))
        composite.register_state_change_cb(
            partial(self._on_substate_change, key))
        self._substates[key] = composite
        return composite

    def _on_substate_change(self, key):
        self._state = {**self._state, **{key: self._substates[key].state}}
        self._cb_registry.notify()
