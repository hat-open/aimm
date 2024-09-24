from hat.event import common
import hat.aio
import logging


mlog = logging.getLogger(__name__)


class EnableAll(common.Module):
    def __init__(self, _, engine, source):
        self._source = source
        self._subscription = common.create_subscription(
            [("event", "?", "eventer", "gateway/gateway")]
        )
        self._async_group = hat.aio.Group()
        self._engine = engine

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def process(self, source, event):
        if event.payload.data == "CONNECTED":
            return [
                common.RegisterEvent(
                    type=("gateway", "example", "device", "system", "enable"),
                    source_timestamp=None,
                    payload=common.EventPayloadJson(data=True),
                )
            ]


info = common.ModuleInfo(create=EnableAll)
