"""REPL client module. Provides a minimal interface that follows the protocol
specified by the REPL control."""

from getpass import getpass
from hat import aio
from hat import juggler
from hat import util
import base64
import hashlib
import numpy
import numpy.typing
import pandas
import typing

from aimm import plugins
from aimm.common import JSON


class AIMM(aio.Resource):
    """Class that manages connections to AIMM REPL control, directly maps
    available functions to its methods
    """

    def __init__(self):
        self._address = None
        self._group = aio.Group()
        self._connection = None
        self._state = None

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._group

    @property
    def address(self) -> typing.Optional[str]:
        """Current address object is connected to"""
        return self._address

    @property
    def state(self) -> 'JSON':
        """Current state reported from the AIMM server"""
        return self._state

    async def connect(self, address: str, autoflush_delay: float = 0.2):
        """Connects to the specified remote address. Login data is received
        from a user prompt. Passwords are hashed with SHA-256 before sending
        login request."""
        connection = await juggler.connect(
            address, autoflush_delay=autoflush_delay)
        connection = juggler.RpcConnection(connection, {})
        self._address = address

        username = input('Username: ')
        password_hash = hashlib.sha256()
        password_hash.update(getpass('Password: ').encode('utf-8'))
        await connection.call('login', username, password_hash.hexdigest())

        self._connection = connection
        self._group.spawn(connection.wait_closed).add_done_callback(
            lambda _: self._clear_connection())
        self._connection.register_change_cb(self._on_remote_state_change)

    async def create_instance(self,
                              model_type: str,
                              *args: 'PluginArg',
                              **kwargs: 'PluginArg'
                              ) -> 'Model':
        """Creates a model instance on the remote server"""
        args = tuple(_arg_to_json(a) for a in args)
        kwargs = {k: _arg_to_json(v) for k, v in kwargs.items()}
        model_json = await self._connection.call('create_instance', model_type,
                                                 args, kwargs)
        return Model(self, model_json['instance_id'], model_json['model_type'])

    async def add_instance(self,
                           model_type: str,
                           instance: typing.Any) -> 'Model':
        """Adds an existing instance on the remote server"""
        model_json = await self._connection.call(
            'add_instance', model_type, _instance_to_b64(instance, model_type))
        return Model(self, model_json['instance_id'], model_json['model_type'])

    async def update_instance(self,
                              model_type: str,
                              instance_id: int,
                              instance: typing.Any) -> 'Model':
        """Replaces an existing instance with a new one"""
        model_json = await self._connection.call(
            'update_instance', model_type, instance_id,
            _instance_to_b64(instance, model_type))
        return Model(self, model_json['instance_id'], model_json['model_type'])

    async def fit(self,
                  instance_id: int,
                  *args: 'PluginArg',
                  **kwargs: 'PluginArg') -> 'Model':
        """Fits an instance on the remote server"""
        args = tuple(_arg_to_json(a) for a in args)
        kwargs = {k: _arg_to_json(v) for k, v in kwargs.items()}
        model_json = await self._connection.call('fit', instance_id, args,
                                                 kwargs)
        return Model(self, model_json['instance_id'], model_json['model_type'])

    async def predict(self,
                      instance_id: int,
                      *args: 'PluginArg',
                      **kwargs: 'PluginArg') -> typing.Any:
        """Uses an instance on the remote server for a prediction"""
        args = tuple(_arg_to_json(a) for a in args)
        kwargs = {k: _arg_to_json(v) for k, v in kwargs.items()}
        result = await self._connection.call('predict', instance_id, args,
                                             kwargs)
        return _result_from_json(result)

    def _clear_connection(self):
        self._connection = None

    def _on_remote_state_change(self):
        self._state = {'models': {}, 'actions': {}}
        remote_state = self._connection.remote_data
        self._state['models'] = {int(k): Model(self, k, v['model_type'])
                                 for k, v in remote_state['models'].items()}
        self._state['actions'] = {int(k): v
                                  for k, v in remote_state['actions'].items()}


class Model:
    """Represents an AIMM model instance and provides a simplified interface
    for using or changing it remotely."""

    def __init__(self, aimm: AIMM, instance_id: int, model_type: str):
        self._aimm = aimm
        self._instance_id = instance_id
        self._model_type = model_type

    async def fit(self, *args: 'PluginArg', **kwargs: 'PluginArg'):
        """Fits the model"""
        await self._aimm.fit(self._instance_id, *args, **kwargs)

    async def predict(self, *args: 'PluginArg',
                      **kwargs: 'PluginArg') -> typing.Any:
        """Uses the model to generate a prediction"""
        return await self._aimm.predict(self._instance_id, *args, **kwargs)

    def __repr__(self):
        return (f'aimm.client.repl.Model<{self._model_type}>'
                f'(instance_id={self._instance_id})')


class DataAccessArg(typing.NamedTuple):
    """If passed as an argument, remote server calls a data access plugin and
    passes its result instead of this object"""

    name: str
    """name of the remote data access plugin"""
    args: typing.List['PluginArg'] = []
    """positional arguments for the data access plugin call"""
    kwargs: typing.Dict[str, 'PluginArg'] = {}
    """keyword arguments for the data access plugin call"""


PluginArg = typing.Union['DataAccessArg', numpy.typing.ArrayLike,
                         pandas.DataFrame, pandas.Series, JSON]
"""Represents a generic, plugin-specific argument"""
util.register_type_alias('PluginArg')


def _arg_to_json(arg):
    if isinstance(arg, DataAccessArg):
        return {'type': 'data_access',
                'name': arg.name,
                'args': arg.args,
                'kwargs': arg.kwargs}
    if isinstance(arg, numpy.ndarray):
        return {'type': 'numpy_array',
                'dtype': str(arg.dtype),
                'data': arg.tolist()}
    if isinstance(arg, pandas.DataFrame):
        return {'type': 'pandas_dataframe',
                'data': arg.to_dict()}
    if isinstance(arg, pandas.Series):
        return {'type': 'pandas_series',
                'data': arg.tolist()}
    return arg


def _result_from_json(v):
    if not isinstance(v, dict):
        return v
    if v.get('type') == 'numpy_array':
        return numpy.array(v['data'])
    if v.get('type') == 'pandas_dataframe':
        return pandas.DataFrame.from_dict(v['data'])
    if v.get('type') == 'pandas_series':
        return pandas.Series(v['data'])
    return v


def _instance_to_b64(instance, model_type):
    return base64.b64encode(
        plugins.exec_serialize(model_type, instance)).decode('utf-8')


def _instance_from_b64(instance_b64, model_type):
    return base64.b64decode(
        plugins.exec_deserialize(model_type, instance_b64))
