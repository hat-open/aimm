import hat.aio
import hat.event.common


class ReadingsModule(hat.event.common.Module):
    def __init__(self, _, engine, source):
        self._source = source
        self._subscription = hat.event.common.create_subscription(
            [("gateway", "example", "?", "gateway", "reading")]
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
        return [
            hat.event.common.RegisterEvent(
                type=("gui", "system", "timeseries", "reading"),
                source_timestamp=event.source_timestamp,
                payload=event.payload,
            )
        ]


info = hat.event.common.ModuleInfo(create=ReadingsModule)
