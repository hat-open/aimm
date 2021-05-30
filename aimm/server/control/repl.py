import asyncio
import base64
import contextlib
from hat import juggler
from hat import aio
import logging
import numpy
import pandas
import traceback

from aimm.server import common
from aimm import plugins


mlog = logging.getLogger(__name__)


async def create(conf, engine, group, _):
    common.json_schema_repo.validate('aimm://server/control/repl.yaml#', conf)
    control = REPLControl()

    srv_conf = conf['server']
    server = await juggler.listen(
        srv_conf['host'], srv_conf['port'], control._connection_cb,
        pem_file=srv_conf.get('pem_file'),
        autoflush_delay=srv_conf.get('autoflush_delay', 0.2),
        shutdown_timeout=srv_conf.get('shutdown_timeout', 0.1))

    control._conf = conf
    control._engine = engine
    control._group = group
    control._server = server
    control._connections = []

    control._group.spawn(aio.call_on_cancel, control._cleanup)

    return control


class REPLControl(common.Control, aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._group

    def _connection_cb(self, connection):
        self._connections.append(connection)
        self._group.spawn(self._connection_loop, connection)
        self._group.spawn(connection.wait_closed).add_done_callback(
            lambda _: self._connections.remove(connection))

    async def _connection_loop(self, connection):
        with contextlib.suppress(ConnectionError, asyncio.CancelledError):
            msg = await connection.receive()
            if (msg['type'] != 'login'
                    or msg['data'] not in self._conf['users']):
                await connection.async_close()
                return

            await connection.send({'type': 'login_success'})

            await self._set_state(connection)
            with self._engine.subscribe_to_state_change(
                    lambda: self._group.spawn(self._set_state, connection)):
                while True:
                    await self._handle_msg(await connection.receive(),
                                           connection)

    async def _set_state(self, connection):
        connection.set_local_data(await _state_to_json(self._engine.state))

    async def _handle_msg(self, msg, connection):
        if msg['type'] == 'create_instance':
            await self._create_instance(msg['data'], connection)
        elif msg['type'] == 'add_instance':
            await self._add_instance(msg['data'], connection)
        elif msg['type'] == 'update_instance':
            await self._update_instance(msg['data'], connection)
        elif msg['type'] == 'fit':
            await self._fit(msg['data'], connection)
        elif msg['type'] == 'predict':
            await self._predict(msg['data'], connection)

    async def _cleanup(self):
        if self._connections:
            await asyncio.wait([c.async_close() for c in self._connections],
                               return_when=asyncio.ALL_COMPLETED)
        await self._server.async_close()

    async def _create_instance(self, data, connection):
        model_type = data['model_type']
        args = [_arg_from_json(a) for a in data['args']]
        kwargs = {k: _arg_from_json(v) for k, v in data['kwargs'].items()}

        task = self._engine.create_instance(model_type, *args, **kwargs)
        try:
            result = await task
        except Exception as e:
            await connection.send(_exc_msg(e))
        else:
            await connection.send({'type': 'result',
                                   'success': True,
                                   'model': await _model_to_json(result)})

    async def _add_instance(self, data, connection):
        instance = await _instance_from_json(data['instance'],
                                             data['model_type'])
        model = self._engine.add_instance(instance, data['model_type'])
        await connection.send({'success': True,
                               'model': await _model_to_json(model)})

    async def _update_instance(self, data, connection):
        model_type = data['model_type']
        model = common.Model(
            model_type=model_type,
            instance_id=data['instance_id'],
            instance=await _instance_from_json(data['instance'], model_type))
        await self._engine.update_instance(model)
        await connection.send({'type': 'result',
                               'success': True,
                               'model': await _model_to_json(model)})

    async def _fit(self, data, connection):
        instance_id = data['instance_id']
        args = [_arg_from_json(a) for a in data['args']]
        kwargs = {k: _arg_from_json(v) for k, v in data['kwargs'].items()}

        task = await self._engine.fit(instance_id, *args, **kwargs)
        try:
            result = await task
        except Exception as e:
            await connection.send(_exc_msg(e))
        else:
            await connection.send({'type': 'result',
                                   'success': True,
                                   'model': await _model_to_json(result)})

    async def _predict(self, data, connection):
        instance_id = data['instance_id']
        args = [_arg_from_json(a) for a in data['args']]
        kwargs = {k: _arg_from_json(v) for k, v in data['kwargs'].items()}

        task = await self._engine.predict(instance_id, *args, **kwargs)
        try:
            result = await task
        except Exception as e:
            await connection.send(_exc_msg(e))
        else:
            await connection.send({'type': 'result',
                                   'success': True,
                                   'result': _prediction_to_json(result)})


async def _state_to_json(state):
    return {
        'models': {model_id: await _model_to_json(model)
                   for model_id, model in state['models'].items()},
        'actions': state['actions']}


async def _model_to_json(model):
    executor = aio.create_executor()
    instance_bytes = base64.b64encode(
        await executor(plugins.exec_serialize, model.model_type,
                       model.instance)).decode('utf-8')
    return {'instance_id': model.instance_id,
            'model_type': model.model_type,
            'instance': instance_bytes}


def _prediction_to_json(prediction):
    if isinstance(prediction, pandas.DataFrame):
        return {'type': 'pandas_dataframe',
                'data': prediction.to_dict()}
    if isinstance(prediction, pandas.Series):
        return {'type': 'pandas_series',
                'data': prediction.tolist()}
    if isinstance(prediction, numpy.ndarray):
        return {'type': 'numpy_array',
                'data': prediction.tolist()}
    return prediction


async def _instance_from_json(instance_b64, model_type):
    executor = aio.create_executor()
    return await executor(plugins.exec_deserialize, model_type,
                          base64.b64decode(instance_b64))


def _arg_from_json(arg):
    if not isinstance(arg, dict):
        return arg
    if arg.get('type') == 'data_access':
        return common.DataAccess(name=arg['name'],
                                 args=arg['args'],
                                 kwargs=arg['kwargs'])
    if arg.get('type') == 'numpy_array':
        return numpy.array(arg['data'], dtype=arg['dtype'])
    if arg.get('type') == 'pandas_dataframe':
        return pandas.DataFrame.from_dict(arg['data'])
    if arg.get('type') == 'pandas_series':
        return pandas.Series(arg['data'])
    return arg


def _exc_msg(e):
    return {'type': 'result', 'success': False, 'exception': str(e),
            'traceback': traceback.format_exc()}
