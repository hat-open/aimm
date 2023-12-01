from typing import Any, ByteString

from aimm.plugins import common
from aimm.plugins import decorators


def exec_data_access(
    name: str,
    state_cb: common.StateCallback = lambda state: None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Uses a loaded plugin to access data"""
    plugin = decorators.get_data_access(name)
    kwargs = _kwargs_add_state_cb(plugin.state_cb_arg_name, state_cb, kwargs)
    return plugin.function(*args, **kwargs)


def exec_instantiate(
    model_type: str,
    state_cb: common.StateCallback = lambda state: None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Uses a loaded plugin to create a model instance"""
    plugin = decorators.get_instantiate(model_type)
    kwargs = _kwargs_add_state_cb(plugin.state_cb_arg_name, state_cb, kwargs)
    return plugin.function(*args, **kwargs)


def exec_fit(
    model_type: str,
    instance: Any,
    state_cb: common.StateCallback = lambda state: None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Uses a loaded plugin to fit a model instance"""
    plugin = decorators.get_fit(model_type)
    kwargs = _kwargs_add_state_cb(plugin.state_cb_arg_name, state_cb, kwargs)
    args, kwargs = _args_add_instance(
        plugin.instance_arg_name, instance, args, kwargs
    )
    return plugin.function(*args, **kwargs)


def exec_predict(
    model_type: str,
    instance: Any,
    state_cb: common.StateCallback = lambda state: None,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Uses a loaded plugin to perform a prediction with a given model
    instance"""
    plugin = decorators.get_predict(model_type)
    kwargs = _kwargs_add_state_cb(plugin.state_cb_arg_name, state_cb, kwargs)
    args, kwargs = _args_add_instance(
        plugin.instance_arg_name, instance, args, kwargs
    )
    return plugin.function(*args, **kwargs)


def exec_serialize(model_type: str, instance: Any) -> ByteString:
    """Uses a loaded plugin to convert model into bytes"""
    plugin = decorators.get_serialize(model_type)
    return plugin.function(instance)


def exec_deserialize(model_type: str, instance_bytes: ByteString) -> Any:
    """Uses a loaded plugin to convert bytes into a model instance"""
    plugin = decorators.get_deserialize(model_type)
    return plugin.function(instance_bytes)


def _kwargs_add_state_cb(state_cb_arg_name, cb, kwargs):
    if state_cb_arg_name:
        if state_cb_arg_name in kwargs:
            raise Exception("state cb already set")
        kwargs = dict(kwargs, **{state_cb_arg_name: cb})
    return kwargs


def _args_add_instance(instance_arg_name, instance, args, kwargs):
    if instance_arg_name:
        if instance_arg_name in kwargs:
            raise Exception("instance already set")
        kwargs = dict(kwargs, **{instance_arg_name: instance})
        return args, kwargs
    return (instance, *args), kwargs
