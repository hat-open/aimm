import logging

from hat import aio
from hat import util
from hat import json
from hat.gui import common
import hat.event.common


mlog = logging.getLogger(__name__)


def create_subscription(conf):
    return hat.event.common.create_subscription(
        [("measurement", "?", "?"), ("estimation", "?", "?")]
    )


async def create_adapter(conf, event_client):
    adapter = Adapter()
    adapter._state = {"measurement": [], "estimation": []}
    adapter._event_client = event_client
    adapter._change_cbs = util.CallbackRegistry()
    adapter._group = aio.Group()
    return adapter


info = common.AdapterInfo(
    create_subscription=create_subscription, create_adapter=create_adapter
)


class Adapter(common.Adapter):
    @property
    def async_group(self):
        return self._group

    async def process_events(self, events):
        for event in events:
            reading_kind, index, measurement_kind = event.type
            self._state = json.set_(
                self._state,
                [reading_kind, int(index), measurement_kind],
                event.payload.data,
            )
        self._change_cbs.notify()

    async def create_session(self, user, roles, state, notify_cb):
        return Session(self, state, self._group.create_subgroup())


class Session(common.AdapterSession):
    def __init__(self, adapter, state, group):
        self._adapter = adapter
        self._state = state
        self._group = group

        self._group.spawn(self._run)
        self._on_change()
        adapter._change_cbs.register(self._on_change)

    @property
    def async_group(self):
        return self._group

    def process_request(self, name, data):
        pass

    async def _run(self):
        self._on_change()
        with self._adapter._change_cbs.register(self._on_change):
            await self.async_group.wait_closing()

    def _on_change(self):
        self._state.set([], self._adapter._state)
