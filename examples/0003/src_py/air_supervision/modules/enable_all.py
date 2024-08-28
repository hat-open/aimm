from hat.event import common
import hat.aio
import logging


mlog = logging.getLogger(__name__)


async def create(conf, engine, source):
    module = EnableAll()

    module._source = source
    module._subscription = common.create_subscription(
        [("event", "?", "eventer", "gateway")]
    )
    module._async_group = hat.aio.Group()
    module._engine = engine

    return module


info = common.ModuleInfo(create=create)


class EnableAll(common.Module):
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
