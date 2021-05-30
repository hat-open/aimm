import asyncio
import base64
import contextlib
import logging
import hat.event.common
from hat import aio

from aimm.server import common
from aimm import plugins


mlog = logging.getLogger(__name__)


def create_subscription(conf):
    return hat.event.common.Subscription(
        [tuple([*p, '*']) for p in conf['event_prefixes'].values()])


async def create(conf, engine, group, event_client):
    common.json_schema_repo.validate('aimm://server/control/event.yaml#', conf)
    if event_client is None:
        raise ValueError('attempting to create event control without hat '
                         'compatibility')

    control = EventControl()

    control._client = event_client
    control._engine = engine
    control._group = group
    control._event_prefixes = conf['event_prefixes']
    control._state_event_type = conf['state_event_type']
    control._response_event_type = conf['response_event_type']
    control._executor = aio.create_executor()
    control._notified_state = {}

    control._group.spawn(control._main_loop)

    control._notify_state()
    control._engine.subscribe_to_state_change(control._notify_state)

    return control


class EventControl(common.Control, aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._group

    def _notify_state(self):
        state_json = _state_to_json(self._engine)
        if state_json == self._notified_state:
            return
        self._client.register([_register_event(self._state_event_type,
                                               state_json)])
        self._notified_state = state_json

    async def _main_loop(self):

        def prefix_match(action_prefix, event):
            if action_prefix not in self._event_prefixes:
                return False
            return hat.event.common.matches_query_type(
                event.event_type, self._event_prefixes[action_prefix] + ['*'])

        with contextlib.suppress(asyncio.CancelledError):
            while True:
                events = await self._client.receive()
                for event in events:
                    if prefix_match('create_instance', event):
                        self.async_group.spawn(self._create_instance, event)
                    if prefix_match('add_instance', event):
                        self.async_group.spawn(self._add_instance, event)
                    if prefix_match('update_instance', event):
                        self.async_group.spawn(self._update_instance, event)
                    if prefix_match('fit', event):
                        self.async_group.spawn(self._fit, event)
                    if prefix_match('predict', event):
                        self.async_group.spawn(self._predict, event)

    async def _create_instance(self, event):
        data = event.payload.data
        model_type = data['model_type']
        args = [await self._process_arg(arg) for arg in data['args']]
        kwargs = {k: await self._process_arg(v) for k, v
                  in data['kwargs'].items()}
        task = self._engine.create_instance(model_type, *args, **kwargs)
        result = None
        try:
            await task
            result = task.result().instance_id
        except Exception as e:
            mlog.warning('instance creation failed with exception %s', e,
                         exc_info=e)
        self._client.register([_register_event(
            self._response_event_type,
            {'request_id': data['request_id'],
             'result': result})])

    async def _add_instance(self, event):
        data = event.payload.data
        instance = await self._instance_from_json(data['instance'],
                                                  data['model_type'])
        model = self._engine.add_instance(instance, data['model_type'])
        self._client.register([_register_event(
            self._response_event_type,
            {'request_id': data['request_id'],
             'result': model.instance_id})])

    async def _update_instance(self, event):
        event_prefix = self._event_prefixes.get('update_instance')
        instance_id = int(event.event_type[len(event_prefix)])
        data = event.payload.data
        model_type = data['model_type']
        model = common.Model(
            model_type=data['model_type'],
            instance_id=instance_id,
            instance=await self._instance_from_json(data['instance'],
                                                    model_type))
        await self._engine.update_instance(model)
        self._client.register([_register_event(
            self._response_event_type,
            {'request_id': data['request_id'], 'result': True})])

    async def _fit(self, event):
        event_prefix = self._event_prefixes.get('fit')
        if event_prefix is None:
            return
        data = event.payload.data
        instance_id = int(event.event_type[len(event_prefix)])
        if instance_id not in self._engine.state['models']:
            return
        args = [await self._process_arg(a) for a in data['args']]
        kwargs = {k: await self._process_arg(v) for k, v
                  in data['kwargs'].items()}

        task = await self._engine.fit(instance_id, *args, **kwargs)
        try:
            await task
        except Exception as e:
            mlog.warning('fitting failed with exception %s', e, exc_info=e)
        self._client.register([_register_event(
            self._response_event_type,
            {'request_id': data['request_id'], 'result': True})])

    async def _predict(self, event):
        event_prefix = self._event_prefixes.get('predict')
        data = event.payload.data
        instance_id = int(event.event_type[len(event_prefix)])
        if instance_id not in self._engine.state['models']:
            return
        args = [await self._process_arg(a) for a in data['args']]
        kwargs = {k: await self._process_arg(v) for k, v
                  in data['kwargs'].items()}

        task = await self._engine.predict(instance_id, *args, **kwargs)
        try:
            prediction = await task
        except Exception as e:
            mlog.warning('prediction failed with exception %s', e, exc_info=e)
        else:
            self._client.register([_register_event(
                self._response_event_type,
                {'request_id': data['request_id'],
                 'result': prediction})])

    async def _process_arg(self, arg):
        if not (isinstance(arg, dict) and arg.get('type') == 'data_access'):
            return arg
        return common.DataAccess(name=arg['name'],
                                 args=arg['args'],
                                 kwargs=arg['kwargs'])

    async def _instance_from_json(self, instance_b64, model_type):
        return await self._executor(plugins.exec_deserialize,
                                    model_type,
                                    base64.b64decode(instance_b64))


def _state_to_json(engine):
    return {
        'models': {
            instance_id: model.model_type for instance_id, model
            in engine.state['models'].items()},
        'actions': engine.state['actions']}


def _register_event(event_type, payload, source_timestamp=None):
    return hat.event.common.RegisterEvent(
        event_type=tuple(event_type),
        source_timestamp=source_timestamp,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=payload))
