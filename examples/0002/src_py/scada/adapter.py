import logging

from hat import aio
from hat import util
from hat import json
from hat.gui import common
import hat.event.common


mlog = logging.getLogger(__name__)


def create_subscription(_):
    return hat.event.common.create_subscription(
        [("measurement", "?", "?"), ("estimation", "?", "?")]
    )


class Adapter(common.Adapter):
    def __init__(self, _, event_client):
        self._state = {"measurement": [], "estimation": []}
        self._event_client = event_client
        self._change_cbs = util.CallbackRegistry()
        self._group = aio.Group()

    @property
    def async_group(self):
        return self._group

    @property
    def state(self):
        return self._state

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
        session = Session(self, state, self._group.create_subgroup())
        self._change_cbs.register(session.on_change)
        return session


class Session(common.AdapterSession):
    def __init__(self, adapter, state, group):
        self._adapter = adapter
        self._state = state
        self._group = group

        self.on_change()

    @property
    def async_group(self):
        return self._group

    def process_request(self, name, data):
        pass

    def on_change(self):
        self._state.set([], self._adapter.state)


info = common.AdapterInfo(
    create_subscription=create_subscription, create_adapter=Adapter
)
