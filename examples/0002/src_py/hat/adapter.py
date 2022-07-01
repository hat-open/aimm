from hat import aio
from hat import util
from hat import json
from hat.gui import common
import hat.event.common


json_schema_id = 'hat-aimm://adapter.yaml#'
json_schema_repo = json.SchemaRepository(json.decode("""
---
id: 'hat-aimm://adapter.yaml#'
type: object
...
""", format=json.Format.YAML))


def create_subscription(conf):
    return hat.event.common.Subscription([('measurement', '?', '?'),
                                          ('estimation', '?', '?')])


async def create_adapter(conf, event_client):
    adapter = Adapter()
    adapter._state = {}
    adapter._event_client = event_client
    adapter._change_cbs = util.CallbackRegistry()
    adapter._group = aio.Group()
    adapter._group.spawn(adapter._run)
    return adapter


class Adapter(common.Adapter):

    @property
    def async_group(self):
        return self._group

    async def create_session(self, client):
        return Session(self, client, self._group.create_subgroup())

    async def _run(self):
        try:
            while True:
                events = await self._event_client.receive()
                for event in events:
                    self._state = json.set_(self._state,
                                            list(event.event_type),
                                            event.payload.data)
                self._change_cbs.notify()
        finally:
            self._group.close()


class Session(common.AdapterSession):

    def __init__(self, adapter, client, group):
        self._adapter = adapter
        self._client = client
        self._group = group
        self._group.spawn(self._run)
        self._on_change()
        adapter._change_cbs.register(self._on_change)

    @property
    def async_group(self):
        return self._group

    async def _run(self):
        self._on_change()
        with self._adapter._change_cbs.register(self._on_change):
            try:
                await self.async_group.wait_closing()
            finally:
                self._client.close()

    def _on_change(self):
        if self._client.is_open:
            self._client.set_local_data(self._adapter._state)
