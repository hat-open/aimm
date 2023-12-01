import hat.aio
import hat.event.server.common


json_schema_id = None
json_schema_repo = None


async def create(conf, engine, source):
    module = ReadingsModule()

    module._source = source
    module._subscription = hat.event.server.common.Subscription(
        [("gateway", "?", "example", "?", "gateway", "reading")]
    )
    module._async_group = hat.aio.Group()
    module._engine = engine

    return module


class ReadingsModule(hat.event.server.common.Module):
    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def process(self, source, event):
        yield hat.event.server.common.RegisterEvent(
            event_type=("gui", "system", "timeseries", "reading"),
            source_timestamp=event.source_timestamp,
            payload=event.payload,
        )
