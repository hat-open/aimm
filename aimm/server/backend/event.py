import base64
from hat import aio
import hat.event.common

from aimm.server import common
from aimm import plugins


def create_subscription(conf):
    return hat.event.common.Subscription([tuple([*conf['model_prefix'], '*'])])


async def create(conf, group, event_client):
    common.json_schema_repo.validate('aimm://server/backend/event.yaml#',
                                     conf)
    backend = EventBackend()

    backend._model_prefix = conf['model_prefix']
    events = await event_client.query(hat.event.common.QueryData(
        event_types=[[*backend._model_prefix, '*']], unique_type=True))

    backend._events = {e.event_type[len(backend._model_prefix)]: e
                       for e in events}
    backend._executor = aio.create_executor()
    backend._group = group
    backend._client = event_client

    return backend


class EventBackend(common.Backend, aio.Resource):

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._group

    async def get_models(self):
        return [await self._event_to_model(ev) for ev in self._events.values()]

    async def create_model(self, model):
        await self._register_model(model)

    async def update_model(self, model):
        await self._register_model(model)

    async def _register_model(self, model):
        ev = await self._client.register_with_response(
            [await self._model_to_event(model)])
        self._events[model.instance_id] = ev

    async def _model_to_event(self, model):
        instance_b64 = base64.b64encode(await self._executor(
            plugins.exec_serialize, model.model_type,
            model.instance)).decode('utf-8')
        return hat.event.common.RegisterEvent(
            event_type=[*self._model_prefix, str(model.instance_id)],
            source_timestamp=None,
            payload=hat.event.common.EventPayload(
                type=hat.event.common.EventPayloadType.JSON,
                data={'type': model.model_type,
                      'instance': instance_b64}))

    async def _event_to_model(self, event):
        instance = await self._executor(
            plugins.exec_deserialize,
            event.payload.data['type'],
            base64.b64decode(event.payload.data['instance'].encode('utf-8')))
        return common.Model(
            instance=instance,
            instance_id=int(event.event_type[len(self._model_prefix)]),
            model_type=event.payload.data['type'])
