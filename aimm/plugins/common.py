from typing import Any, ByteString, Callable, Dict, NamedTuple, Optional
from aimm.common import *  # NOQA
import abc
import importlib
import logging


mlog = logging.getLogger(__name__)


class Model(abc.ABC):
    """Interface unifying multiple plugin entry points under same type.
    ``__init__`` method is treated as instantiation function."""

    @abc.abstractmethod
    def fit(self, *args: Any, **kwargs: Any) -> Any:
        """Fit method for model instances"""

    @abc.abstractmethod
    def predict(self, *args: Any, **kwargs: Any) -> Any:
        """Predict method for model instances"""

    @abc.abstractmethod
    def serialize(self) -> ByteString:
        """Serialize method for model instances"""

    @classmethod
    @abc.abstractmethod
    def deserialize(cls, instance_bytes: ByteString) -> "Model":
        """Deserialize method for model instances"""


class DataAccessPlugin(NamedTuple):
    """Object containing data access plugin function and call metadata"""

    name: str
    """plugin name"""
    function: Callable
    """plugin function"""
    state_cb_arg_name: Optional[str] = None
    """name of the keyword argument for the state change cb"""


class InstantiatePlugin(NamedTuple):
    """Object containing instantiate plugin function and call metadata"""

    function: Callable
    """plugin function"""
    state_cb_arg_name: Optional[str] = None
    """name of the keyword argument for the state change cb"""


class FitPlugin(NamedTuple):
    """Object containing fitting plugin function and call metadata"""

    function: Callable
    """plugin function"""
    state_cb_arg_name: Optional[str] = None
    """name of the keyword argument for the state change cb"""
    instance_arg_name: Optional[str] = None
    """name of the keyword argument for the instance argument. If None, pass as
    the first positional argument"""


class PredictPlugin(NamedTuple):
    """Object containing prediction plugin function and call metadata"""

    function: Callable
    """plugin function"""
    state_cb_arg_name: Optional[str] = None
    """name of the keyword argument for the state change cb"""
    instance_arg_name: Optional[str] = None
    """name of the keyword argument for the instance argument. If None, pass as
    the first positional argument"""


class SerializePlugin(NamedTuple):
    """Object containing serialize plugin function and call metadata"""

    function: Callable
    """plugin function"""


class DeserializePlugin(NamedTuple):
    """Object containing serialize plugin function and call metadata"""

    function: Callable
    """plugin function"""


def initialize(conf: Dict):
    """Imports the plugin modules, registering the entry point functions

    Args:
        conf: configuration that follows schema under id
            ``aimm://plugins/schema.yaml#``"""
    for name in conf["names"]:
        importlib.import_module(name)


StateCallback = Callable[[Dict], None]
StateCallback.__doc__ = """
Generic state callback function signature a plugin would receive"""
