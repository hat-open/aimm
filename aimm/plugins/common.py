import abc
import importlib
import logging
import typing

from aimm.plugins import decorators
from aimm.common import *  # NOQA


mlog = logging.getLogger(__name__)


class Model(abc.ABC):
    """Interface unifying multiple plugin entry points under same type.
    ``__init__`` method is treated as instantiate function."""

    @abc.abstractmethod
    def fit(self,
            *args: typing.Any,
            **kwargs: typing.Any) -> typing.Any:
        """Fit method for model instances"""

    @abc.abstractmethod
    def predict(self,
                *args: typing.Any,
                **kwargs: typing.Any) -> typing.Any:
        """Predict method for model instances"""

    @abc.abstractmethod
    def serialize(self) -> typing.ByteString:
        """Serialize method for model instances"""

    @abc.abstractclassmethod
    def deserialize(cls, instance_bytes: typing.ByteString) -> 'Model':
        """Deserialize method for model instances"""


class DataAccessPlugin(typing.NamedTuple):
    """Object containing data access plugin function and call metadata"""

    name: str
    """plugin name"""
    function: typing.Callable
    """plugin function"""
    state_cb_arg_name: typing.Optional[str] = None
    """name of the keyword argument for the state change cb"""


class InstantiatePlugin(typing.NamedTuple):
    """Object containing instantiate plugin function and call metadata"""

    function: typing.Callable
    """plugin function"""
    state_cb_arg_name: typing.Optional[str] = None
    """name of the keyword argument for the state change cb"""


class FitPlugin(typing.NamedTuple):
    """Object containing fitting plugin function and call metadata"""

    function: typing.Callable
    """plugin function"""
    state_cb_arg_name: typing.Optional[str] = None
    """name of the keyword argument for the state change cb"""
    instance_arg_name: typing.Optional[str] = None
    """name of the keyword argument for the instance argument. If None, pass as
    the first positional argument"""


class PredictPlugin(typing.NamedTuple):
    """Object containing prediction plugin function and call metadata"""

    function: typing.Callable
    """plugin function"""
    state_cb_arg_name: typing.Optional[str] = None
    """name of the keyword argument for the state change cb"""
    instance_arg_name: typing.Optional[str] = None
    """name of the keyword argument for the instance argument. If None, pass as
    the first positional argument"""


class SerializePlugin(typing.NamedTuple):
    """Object containing serialize plugin function and call metadata"""

    function: typing.Callable
    """plugin function"""


class DeserializePlugin(typing.NamedTuple):
    """Object containing serialize plugin function and call metadata"""

    function: typing.Callable
    """plugin function"""


def initialize(conf: typing.Dict):
    """Imports the plugin modules, registering the entry point functions

    Args:
        conf: configuration that follows schema under id
            ``aimm://plugins.yaml#``"""
    for name in conf['names']:
        importlib.import_module(name)


def default_state_cb(*args, **kwargs):
    return


StateCallback: typing.Type = typing.NewType(
    'StateCallback', typing.Callable[[typing.Dict], None])
StateCallback.__doc__ = """
Generic state callback function signature a plugin would receive"""


def exec_data_access(name: str,
                     state_cb: typing.Optional[StateCallback] = None,
                     *args: typing.Any,
                     **kwargs: typing.Any) -> typing.Any:
    """Uses a loaded plugin to access data

    Args:
        name: data access name
        state_cb: state callback function
        *args: additional positional arguments
        **kwargs: additional keyword arguments

    Returns:
        Accessed data"""
    if state_cb is None:
        state_cb = default_state_cb
    plugin = decorators.get_data_access(name)
    kwargs = _kwargs_add_state_cb(plugin.state_cb_arg_name, state_cb, kwargs)
    return plugin.function(*args, **kwargs)


def exec_instantiate(model_type: str,
                     state_cb: typing.Optional[StateCallback] = None,
                     *args: typing.Any,
                     **kwargs: typing.Any) -> typing.Any:
    """Uses a loaded plugin to create a model instance

    Args:
        model_type: model type
        state_cb: state callback function
        *args: additional positional arguments
        **kwargs: additional keyword arguments

    Returns:
        instance"""
    if state_cb is None:
        state_cb = default_state_cb
    plugin = decorators.get_instantiate(model_type)
    kwargs = _kwargs_add_state_cb(plugin.state_cb_arg_name, state_cb, kwargs)
    return plugin.function(*args, **kwargs)


def exec_fit(model_type: str,
             instance: typing.Any,
             state_cb: typing.Optional[StateCallback] = None,
             *args: typing.Any,
             **kwargs: typing.Any) -> typing.Any:
    """Uses a loaded plugin to fit a model instance

    Args:
        model_type: model type
        instance: model instance
        state_cb: state callback function
        *args: additional positional arguments
        **kwargs: additional keyword arguments

    Returns:
        updated model instance"""
    if state_cb is None:
        state_cb = default_state_cb
    plugin = decorators.get_fit(model_type)
    kwargs = _kwargs_add_state_cb(plugin.state_cb_arg_name, state_cb, kwargs)
    args, kwargs = _args_add_instance(plugin.instance_arg_name, instance, args,
                                      kwargs)
    return plugin.function(*args, **kwargs)


def exec_predict(model_type: str,
                 instance: typing.Any,
                 state_cb: typing.Optional[StateCallback] = None,
                 *args: typing.Any,
                 **kwargs: typing.Any) -> typing.Any:
    """Uses a loaded plugin to perform a prediction with a given model
    instance

    Args:
        model_type: model type
        instance: model instance
        state_cb: state callback function
        *args: additional positional arguments
        **kwargs: additional keyword arguments

    Returns:
        prediction"""
    if state_cb is None:
        state_cb = default_state_cb
    plugin = decorators.get_predict(model_type)
    kwargs = _kwargs_add_state_cb(plugin.state_cb_arg_name, state_cb, kwargs)
    args, kwargs = _args_add_instance(plugin.instance_arg_name, instance, args,
                                      kwargs)
    return plugin.function(*args, **kwargs)


def exec_serialize(model_type: str,
                   instance: typing.Any) -> typing.ByteString:
    """Uses a loaded plugin to convert model into bytes

    Args:
        model_type (str): model type
        instance (typing.Any): model instance

    Returns:
        instance bytes"""
    plugin = decorators.get_serialize(model_type)
    return plugin.function(instance)


def exec_deserialize(model_type: str,
                     instance_bytes: typing.ByteString) -> typing.Any:
    """Uses a loaded plugin to convert bytes into a model instance

    Args:
        model_type: model type
        instance_bytes: model instance bytes

    Returns:
        instance"""
    plugin = decorators.get_deserialize(model_type)
    return plugin.function(instance_bytes)


def _kwargs_add_state_cb(state_cb_arg_name, cb, kwargs):
    if state_cb_arg_name:
        if state_cb_arg_name in kwargs:
            raise Exception('state cb already set')
        kwargs = dict(kwargs, **{state_cb_arg_name: cb})
    return kwargs


def _args_add_instance(instance_arg_name, instance, args, kwargs):
    if instance_arg_name:
        if instance_arg_name in kwargs:
            raise Exception('instance already set')
        kwargs = dict(kwargs, **{instance_arg_name: instance})
        return args, kwargs
    return (instance, *args), kwargs
