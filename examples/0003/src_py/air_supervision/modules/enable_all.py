from hat.event.server import common
import hat.aio
import logging


mlog = logging.getLogger(__name__)


json_schema_id = None
json_schema_repo = None


async def create(conf, engine, source):
    module = EnableAll()

    module._source = source
    module._subscription = common.Subscription(
        [("gateway", "?", "?", "?", "gateway", "running")]
    )
    module._async_group = hat.aio.Group()
    module._engine = engine

    return module


class EnableAll(common.Module):
    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def process(self, source, event):
        if event.payload.data is False:
            yield common.RegisterEvent(
                event_type=tuple([*event.event_type[:-2], "system", "enable"]),
                source_timestamp=None,
                payload=common.EventPayload(
                    type=common.EventPayloadType.JSON, data=True
                ),
            )
