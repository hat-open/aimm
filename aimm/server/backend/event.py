from hat import aio
from hat import util
import base64
import hat.event.common
import itertools

from aimm.server import common
from aimm import plugins


def create_subscription(conf):
    return hat.event.common.create_subscription(
        [tuple([*conf["model_prefix"], "*"])]
    )


async def create(conf, event_client):
    common.json_schema_repo.validate("aimm://server/backend/event.yaml#", conf)
    backend = EventBackend()

    backend._model_prefix = conf["model_prefix"]
    backend._executor = aio.create_executor()
    backend._cbs = util.CallbackRegistry()
    backend._async_group = aio.Group()
    backend._client = event_client
    backend._async_group.spawn(backend._event_loop)

    models = await backend.get_models()
    backend._id_counter = itertools.count(
        max((model.instance_id for model in models), default=1)
    )

    return backend


class EventBackend(common.Backend):
    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def get_models(self):
        events = await self._client.query(
            hat.event.common.QueryLatestParams(
                event_types=[(*self._model_prefix, "*")]
            )
        )
        return [await self._event_to_model(e) for e in events]

    async def create_model(self, model_type, instance):
        model = common.Model(
            model_type=model_type,
            instance=instance,
            instance_id=next(self._id_counter),
        )
        await self._register_model(model)
        return model

    async def update_model(self, model):
        await self._register_model(model)

    def register_model_change_cb(self, cb):
        self._cbs.register(cb)

    async def _event_loop(self):
        while True:
            events = await self._client.receive()
            for event in events:
                self._cbs.notify(await self._event_to_model(event))

    async def _register_model(self, model):
        await self._client.register_with_response(
            [await self._model_to_event(model)]
        )

    async def _model_to_event(self, model):
        instance_b64 = base64.b64encode(
            await self._executor(
                plugins.exec_serialize, model.model_type, model.instance
            )
        ).decode("utf-8")
        return hat.event.common.RegisterEvent(
            type=(*self._model_prefix, str(model.instance_id)),
            source_timestamp=None,
            payload=hat.event.common.EventPayloadJson(
                {"type": model.model_type, "instance": instance_b64},
            ),
        )

    async def _event_to_model(self, event):
        instance = await self._executor(
            plugins.exec_deserialize,
            event.payload.data["type"],
            base64.b64decode(event.payload.data["instance"].encode("utf-8")),
        )
        return common.Model(
            instance=instance,
            instance_id=int(event.type[len(self._model_prefix)]),
            model_type=event.payload.data["type"],
        )
